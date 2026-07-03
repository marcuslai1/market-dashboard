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

from lib.charts import (
    ACCENT_LINK,
    ACCENT_WILDCARD,
    PLOTLY_CONFIG,
    STATUS_MUTED,
    STATUS_NEG,
    STATUS_POS,
    chart_data_table,
    style_fig,
)
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
        out = {}
        for k, v in probs.items():
            # Guard float() the same way the legacy branch (and
            # extract_scenario_history) do — a malformed value must not crash the
            # Report-Comparison drift table.
            try:
                mid = float(v) if v is not None else None
            except (ValueError, TypeError):
                mid = None
            disp = f"{int(mid)}%" if mid is not None else "—"
            out[_norm_scenario(k)] = (disp, mid)
        return out
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
            # Per-case writeups (restored 2026-06-08) live alongside the integer
            # probabilities in geopolitical.scenarios[name].description. Surface
            # them here — the probabilities dict stays the source of truth for
            # the odds, the scenarios block supplies the prose.
            new_scenarios = geo.get("scenarios", {}) or {}
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
                    "description": (new_scenarios.get(name) or {}).get("description", ""),
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


_SCENARIO_ORDER = {"Base": 0, "Optimistic": 1, "Pessimistic": 2, "Wildcard": 3}


def _render_move_log(moves: list[dict], colors: dict[str, str]) -> str:
    """Render probability shifts as a dated editorial ledger (HTML string).

    Days descend (newest first); within a day, shifts follow the canonical
    Base → Optimistic → Pessimistic → Wildcard order. Each shift card carries
    a scenario-coloured rail, a from→to readout with an odds bar, and the full
    untruncated narrative for that case.
    """
    by_date: dict[pd.Timestamp, list[dict]] = {}
    for m in moves:
        by_date.setdefault(m["date"], []).append(m)

    days_html = []
    for d in sorted(by_date, reverse=True):
        day_moves = sorted(
            by_date[d], key=lambda m: _SCENARIO_ORDER.get(m["scenario"], 99)
        )
        n = len(day_moves)
        rows = []
        for m in day_moves:
            color = colors.get(m["scenario"], STATUS_MUTED)
            delta = m["delta"]
            arrow = "▲" if delta > 0 else "▼"
            desc = m["description"].strip()
            desc_html = (
                _escape_dollars(desc) if desc
                else '<span style="color:var(--ink-4)">No narrative recorded for this shift.</span>'
            )
            rows.append(
                f'<div class="scn-move" style="border-left-color:{color}">'
                f'<div class="scn-meta">'
                f'<div class="scn-name" style="color:{color}">{m["scenario"]}</div>'
                f'<div class="scn-shift">'
                f'<span class="scn-from">{m["from"]:.0f}%</span>'
                f'<span class="scn-arr">→</span>'
                f'<span class="scn-to">{m["to"]:.0f}%</span>'
                f'<span class="scn-delta" style="color:{color}">{arrow}&#8201;{abs(delta):.0f}</span>'
                f'</div>'
                f'<div class="scn-bar">'
                f'<span class="scn-bar-fill" style="width:{min(m["to"], 100):.0f}%;background:{color}"></span>'
                f'</div>'
                f'</div>'
                f'<div class="scn-desc">{desc_html}</div>'
                f'</div>'
            )
        date_label = f'{d.strftime("%b")} {d.day}, {d.year}'  # "Jun 13, 2026" (Win-safe)
        days_html.append(
            f'<div class="scn-day">'
            f'<div class="scn-day-rule">'
            f'<span class="scn-day-date">{date_label}</span>'
            f'<span class="scn-day-dow">{d.strftime("%A")}</span>'
            f'<span class="scn-day-count">{n} shift{"s" if n != 1 else ""}</span>'
            f'</div>'
            f'{"".join(rows)}'
            f'</div>'
        )
    return f'<div class="scn-log">{"".join(days_html)}</div>'


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
        "Base":        ACCENT_LINK,
        "Optimistic":  STATUS_POS,
        "Pessimistic": STATUS_NEG,
        "Wildcard":    ACCENT_WILDCARD,
    }
    # A distinct marker per series so identity never rests on colour alone —
    # Optimistic (green) + Pessimistic (red) are the classic colour-blind
    # confusable pair. The shapes double as meaning: ▲ optimistic, ▼ pessimistic.
    scenario_symbols = {
        "Base":        "circle",
        "Optimistic":  "triangle-up",
        "Pessimistic": "triangle-down",
        "Wildcard":    "diamond",
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
                line=dict(color=scenario_colors.get(sc_name, STATUS_MUTED), width=2),
                marker=dict(symbol=scenario_symbols.get(sc_name, "circle"), size=7),
                hovertemplate=f"<b>{sc_name}</b><br>%{{x|%b %d}}: %{{customdata}}<extra></extra>",
                customdata=sc_data["probability_str"],
            ))
    fig.update_layout(
        yaxis_title="Probability %", height=240,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(style_fig(fig), use_container_width=True, config=PLOTLY_CONFIG)
    st.caption(
        "Line chart — each macro scenario's probability (%) over the selected "
        "window; the dated ledger below lists the exact shifts. These are "
        "Claude's uncalibrated narrative lean, not measured or scored forecasts."
    )
    chart_data_table(
        sc_df.sort_values(["date", "scenario"])[["date", "scenario", "probability_str"]]
        .rename(columns={"probability_str": "probability"})
    )

    # ── Days when probabilities actually moved ──
    st.subheader("Days when probabilities moved")
    st.caption(
        "By design the prompt carries forward yesterday's odds unless a named event justifies a shift — "
        "this log shows only the days where Claude actually changed at least one scenario. Each card is one "
        "shift; the narrative beside it is that case's full macro write-up for the day (base / optimistic / "
        "pessimistic / wildcard outcome)."
    )

    # Collect each shift with raw values so we can render a readable ledger
    # (the old st.dataframe clipped the narrative column to one truncated line).
    moves = []
    for sc_name in sc_df["scenario"].unique():
        sc_data = sc_df[sc_df["scenario"] == sc_name].sort_values("date")
        prev_p = None
        for _, row in sc_data.iterrows():
            p = row["probability_mid"]
            if p is None or pd.isna(p):
                continue
            if prev_p is not None and abs(p - prev_p) >= 0.5:
                moves.append({
                    "date": pd.Timestamp(row["date"]),
                    "scenario": sc_name,
                    "from": prev_p,
                    "to": p,
                    "delta": p - prev_p,
                    "description": row.get("description") or "",
                })
            prev_p = p

    if moves:
        st.markdown(_render_move_log(moves, scenario_colors), unsafe_allow_html=True)
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
