"""Scenario Log page: time-series of macro scenario probabilities.

Also home to the scenario helpers (`_norm_scenario`, `_get_probs`,
`extract_scenario_history`) — the Scenario Log and the trend section of the
Report Comparison page both consume them, so they live here and Report
Comparison imports from this module.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.formatters import _escape_dollars

_SCENARIO_NORMALIZE = {
    "base_case": "base", "optimistic_case": "optimistic",
    "pessimistic_case": "pessimistic",
}


def _norm_scenario(name: str) -> str:
    """Normalise scenario key to a consistent short name, then title-case."""
    key = name.lower().strip()
    key = _SCENARIO_NORMALIZE.get(key, key)
    return key.replace("_", " ").title()


def _get_probs(rpt):
    """Extract scenario probabilities from either new or legacy format.

    Returns dict of {scenario_name: (display_string, midpoint_float)}.
    """
    geo = rpt.get("geopolitical", {})
    # New format: geopolitical.probabilities = {base: 50, ...}
    probs = geo.get("probabilities", {})
    if probs:
        return {_norm_scenario(k): (str(v), float(v) if v is not None else None) for k, v in probs.items()}
    # Legacy format: geopolitical.scenarios = {base_case: {probability: "50-55%"}}
    result = {}
    for name, sc in geo.get("scenarios", {}).items():
        prob_str = sc.get("probability", "—")
        mid = None
        try:
            cleaned = prob_str.replace("%", "").strip()
            if "-" in cleaned:
                lo, hi = cleaned.split("-")
                mid = (float(lo) + float(hi)) / 2
            elif cleaned:
                mid = float(cleaned)
        except (ValueError, AttributeError, TypeError):
            pass
        result[_norm_scenario(name)] = (prob_str, mid)
    return result


def extract_scenario_history(reports: dict) -> pd.DataFrame:
    """Build scenario probability tracking from all reports."""
    rows = []
    for date_str, report in reports.items():
        geo = report.get("geopolitical", {})

        # New simple format: geopolitical.probabilities = {base: 50, optimistic: 22, ...}
        probs = geo.get("probabilities", {})
        if probs:
            for name, val in probs.items():
                mid = None
                prob_str = ""
                try:
                    mid = float(val)
                    prob_str = f"{int(mid)}%"
                except (ValueError, TypeError):
                    pass
                rows.append({
                    "date": pd.to_datetime(date_str),
                    "scenario": _norm_scenario(name),
                    "probability_str": prob_str,
                    "probability_mid": mid,
                    "description": "",
                })
            continue  # Skip legacy format if new format present

        # Legacy format: geopolitical.scenarios = {base_case: {probability: "50-55%", ...}}
        scenarios = geo.get("scenarios", {})
        for name, sc in scenarios.items():
            prob_str = sc.get("probability", "")
            # Parse "50-55%" into midpoint
            mid = None
            try:
                cleaned = prob_str.replace("%", "").strip()
                if "-" in cleaned:
                    lo, hi = cleaned.split("-")
                    mid = (float(lo) + float(hi)) / 2
                elif cleaned:
                    mid = float(cleaned)
            except (ValueError, AttributeError):
                pass
            rows.append({
                "date": pd.to_datetime(date_str),
                "scenario": _norm_scenario(name),
                "probability_str": prob_str,
                "probability_mid": mid,
                "description": sc.get("description", ""),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def render_scenario_log_page(reports: dict) -> None:
    """Render the Scenario Log page.

    Args:
        reports: filtered reports dict (date-keyed).
    """
    st.title("Scenario Probability Tracking")
    sc_df = extract_scenario_history(reports)

    if sc_df.empty:
        st.warning("No scenario data available yet.")
        st.stop()

    scenario_colors = {
        "Base":        "#3b82f6",
        "Optimistic":  "#22c55e",
        "Pessimistic": "#ef4444",
        "Wildcard":    "#a855f7",
    }
    st_color_names = {
        "Base": "blue", "Optimistic": "green",
        "Pessimistic": "red", "Wildcard": "violet",
    }

    # ── Compact time-series (small chart) ──
    st.subheader("Probabilities Over Time")
    fig = go.Figure()
    for sc_name in sc_df["scenario"].unique():
        sc_data = sc_df[sc_df["scenario"] == sc_name].sort_values("date")
        if sc_data["probability_mid"].notna().any():
            fig.add_trace(go.Scatter(
                x=sc_data["date"], y=sc_data["probability_mid"],
                mode="lines+markers", name=sc_name,
                line=dict(color=scenario_colors.get(sc_name, "#6b7280"), width=2),
                hovertemplate=f"<b>{sc_name}</b><br>%{{x|%b %d}}: %{{customdata}}<extra></extra>",
                customdata=sc_data["probability_str"],
            ))
    fig.update_layout(
        yaxis_title="Probability %", height=240,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, width="stretch")

    # ── Days when probabilities actually moved ──
    st.subheader("Days when probabilities moved")
    st.caption(
        "By design the prompt carries forward yesterday's odds unless a named event justifies a shift — "
        "this table shows only the days where Claude actually changed at least one scenario."
    )
    move_rows = []
    for sc_name in sc_df["scenario"].unique():
        sc_data = sc_df[sc_df["scenario"] == sc_name].sort_values("date")
        prev_p, prev_d = None, None
        for _, row in sc_data.iterrows():
            p = row["probability_mid"]
            if p is None or pd.isna(p):
                continue
            if prev_p is not None and abs(p - prev_p) >= 0.5:
                move_rows.append({
                    "Date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                    "Scenario": sc_name,
                    "From": f"{prev_p:.0f}%",
                    "To": f"{p:.0f}%",
                    "Δ": f"{p - prev_p:+.0f}",
                    "New description": row.get("description") or "",
                })
            prev_p = p
            prev_d = row["date"]

    if move_rows:
        moves_df = pd.DataFrame(move_rows).sort_values("Date", ascending=False).reset_index(drop=True)
        st.dataframe(moves_df, width="stretch", hide_index=True)
    else:
        st.caption("No probability shifts in the selected date range.")

    # ── Latest scenario detail (collapsed) ──
    latest_d = sc_df["date"].max()
    if pd.notna(latest_d):
        latest_data = sc_df[sc_df["date"] == latest_d]
        with st.expander(f"Latest scenarios — {pd.Timestamp(latest_d).strftime('%Y-%m-%d')}", expanded=False):
            for _, row in latest_data.iterrows():
                cn = st_color_names.get(row["scenario"], "gray")
                st.markdown(
                    f"**:{cn}[{row['scenario']}]** — {row['probability_str']}"
                )
                if row.get("description"):
                    st.caption(_escape_dollars(row["description"]))
