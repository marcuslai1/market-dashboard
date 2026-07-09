"""Signal Tracker · Caution-trim experiment band (below the paper-book band).

Renders the 25 output-only caution-trim paper books (MarketReport spec
2026-07-09) as a compact comparison table + a select-to-compare NAV curve,
against the ``v1_flat10`` baseline. Measurement-Gate-exempt / hypothesis-grade:
single-regime, tiny-n — deliberately low-prominence (collapsed) and banner-
capped so it never reads as a performance verdict. All data comes from
``data/paper_nav.csv`` (the trim books are NOT in the report's ``variants``
array — they are ``surface_in_block=False`` upstream). The dashboard's only
arithmetic is first-row→last-row returns and rebasing to 100.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.charts import (
    CHART_ACCENT,
    CHART_LINE,
    CHART_PALETTE,
    PLOTLY_CONFIG,
    style_fig,
)

BASELINE = "v1_flat10"

# caution_bucket trigger key -> reader label
_TRIGGER_LABEL = {"any": "Any CAUTION", "ext": "Over-extended",
                  "rsi": "Overbought (RSI)", "val": "Expensive (valuation)",
                  "thesis": "Thesis deterioration"}


def _parse_pid(pid: str) -> tuple[str, str, str]:
    """``v1_tc_<trigger>_<frac>[s|r]`` -> (trigger label, magnitude, re-add)."""
    body = pid[len("v1_tc_"):]
    trig, _, tail = body.partition("_")
    trig_label = _TRIGGER_LABEL.get(trig, trig)
    if tail == "100":
        return trig_label, "100% (exit)", "—"
    return trig_label, f"{tail[:-1]}%", ("re-add" if tail.endswith("r")
                                         else "sticky")


def _return(series: pd.Series) -> float | None:
    """First-valid -> last-valid percent return, or None."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2 or s.iloc[0] == 0:
        return None
    return (s.iloc[-1] / s.iloc[0] - 1) * 100.0


def _build_table(nav_df: pd.DataFrame) -> tuple[pd.DataFrame, float | None,
                                                float | None]:
    """(rows DataFrame sorted by Δ-vs-baseline desc, baseline NAV %, SPY %)."""
    base = nav_df[nav_df["policy_id"] == BASELINE].sort_values("date")
    base_ret = _return(base["nav_units"]) if not base.empty else None
    spy_ret = _return(base["spy_close"]) if not base.empty else None
    rows = []
    for pid in sorted(p for p in nav_df["policy_id"].unique()
                      if p.startswith("v1_tc_")):
        d = nav_df[nav_df["policy_id"] == pid].sort_values("date")
        nav = _return(d["nav_units"])
        if nav is None:
            continue
        trig, mag, readd = _parse_pid(pid)
        rows.append({
            "Trigger": trig, "Magnitude": mag, "Re-add": readd,
            "NAV %": round(nav, 2),
            "Δ vs base": round(nav - base_ret, 2) if base_ret is not None
            else None,
            "Δ vs SPY": round(nav - spy_ret, 2) if spy_ret is not None
            else None,
            "_pid": pid,
        })
    tbl = pd.DataFrame(rows)
    if not tbl.empty and "Δ vs base" in tbl:
        tbl = tbl.sort_values("Δ vs base", ascending=False,
                              na_position="last").reset_index(drop=True)
    return tbl, base_ret, spy_ret


def _curve_fig(nav_df: pd.DataFrame, pids: list[str]):
    """Rebased-to-100 NAV curves for the selected books + baseline + SPY.
    All books share one date axis (same SPY sessions), so a pivot aligns them.
    """
    piv = nav_df.pivot_table(index="date", columns="policy_id",
                             values="nav_units", aggfunc="last").sort_index()
    spy = nav_df.groupby("date")["spy_close"].first().sort_index()
    x = pd.to_datetime(piv.index, errors="coerce")
    fig = go.Figure()

    def _add(series, name, color, width):
        s = pd.to_numeric(series, errors="coerce")
        v = s.dropna()
        if v.empty or v.iloc[0] == 0:
            return
        fig.add_scatter(x=x, y=(s / v.iloc[0] * 100.0).values, mode="lines",
                        name=name, line=dict(color=color, width=width))

    _add(spy, "SPY", CHART_LINE, 1.4)
    if BASELINE in piv.columns:
        _add(piv[BASELINE], "Baseline", CHART_ACCENT, 2.4)
    for i, pid in enumerate(pids):
        if pid in piv.columns:
            trig, mag, readd = _parse_pid(pid)
            label = f"{trig} · {mag}" + ("" if readd in ("—", "sticky")
                                         else " (re-add)")
            _add(piv[pid], label, CHART_PALETTE[i % len(CHART_PALETTE)], 1.8)
    fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      yaxis_title="rebased · inception = 100")
    return style_fig(fig)


def render_trim_experiment(nav_df: pd.DataFrame) -> None:
    """Collapsed caution-trim experiment band. Silent when the trim books are
    absent from the export (pre-2026-07-09 nav files carry only the stop books).
    """
    if nav_df is None or nav_df.empty:
        return
    if not any(str(p).startswith("v1_tc_")
               for p in nav_df["policy_id"].unique()):
        return
    tbl, base_ret, spy_ret = _build_table(nav_df)
    if tbl.empty:
        return

    with st.expander("Caution-trim experiment · 25 variant books "
                     "(measurement only)", expanded=False):
        base_txt = (f"Baseline v1_flat10 {base_ret:+.1f}%"
                    if base_ret is not None else "Baseline v1_flat10 seeded")
        spy_txt = f" · SPY {spy_ret:+.1f}%" if spy_ret is not None else ""
        st.caption(
            f"{base_txt}{spy_txt}. Output-only paper books that **trim** a "
            "held position when it flips to CAUTION, vs the hold-through "
            "baseline. **Single-regime (trend-up) window, ~3–5 trims — a "
            "hypothesis, not a verdict.** Read as a factorial (consistent "
            "gradients across triggers/magnitudes), not a leaderboard.")

        st.dataframe(tbl.drop(columns="_pid"), use_container_width=True,
                     hide_index=True)

        default = [tbl.iloc[0]["_pid"]] if not tbl.empty else []
        options = list(tbl["_pid"])
        labels = {row["_pid"]: f'{row["Trigger"]} · {row["Magnitude"]}'
                  + ("" if row["Re-add"] in ("—", "sticky")
                     else " (re-add)")
                  for _, row in tbl.iterrows()}
        picked = st.multiselect(
            "Overlay books (baseline + SPY always shown):", options=options,
            default=default, format_func=lambda p: labels.get(p, p),
            key="trim_curve_pick")
        st.plotly_chart(_curve_fig(nav_df, picked),
                        use_container_width=True, config=PLOTLY_CONFIG)
