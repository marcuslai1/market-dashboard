"""Briefing · AI Capex Pulse band.

Human-read digestion scorecard for the capex cycle (spec
docs/superpowers/specs/2026-07-03-capex-pulse-design.md): five chips, the
coverage-gap chart, and cluster-fundamentals trends behind an expander. By
design a cross-check the reader eyeballs against the scenario odds — nothing
here feeds the odds mechanically.
"""
from __future__ import annotations

from datetime import date as _date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.capex import (CURATION_OVERDUE_DAYS, build_chips, coverage_gap_series,
                       curation_age_days, current_read, fundamentals_history,
                       parse_capex)
from lib.cards import render_section_head
from lib.charts import (CHART_ACCENT, CHART_MUTED, CHART_PALETTE, INK_FALLBACK,
                        PLOTLY_CONFIG, STATUS_NEG, STATUS_POS, STATUS_WARN,
                        chart_data_table, style_fig)
from lib.data_loader import data_fingerprint, load_all_reports, load_capex_quarterly
from lib.formatters import _escape_dollars

_STATE_GLYPH = {"ok": "✅", "warn": "⚠", "accel": "▲", "na": "—"}
_STATE_COLOR = {"ok": STATUS_POS, "warn": STATUS_WARN, "accel": CHART_ACCENT,
                "na": INK_FALLBACK}

_TREND_METRICS = [("revenue_growth_pct", "Revenue growth %"),
                  ("earnings_growth_pct", "Earnings growth %"),
                  ("fcf_yield_pct", "FCF yield %"),
                  ("forward_pe", "Forward P/E")]


@st.cache_data(show_spinner=False, max_entries=2)
def _fundamentals_cached(cache_key: tuple, _reports: dict) -> pd.DataFrame:
    """Corpus-derived fundamentals frame, memoized on the cheap fingerprint.

    Same contract as the Signal-Tracker derives (review P7-2): ``cache_key`` is
    ``data_fingerprint()``; the heavy corpus is ``_``-prefixed so it is never
    hashed.
    """
    return fundamentals_history(_reports)


def _chips_html(chips: list, overdue_days: int | None) -> str:
    """Chip-row scorecard + optional curation-overdue banner, as one HTML string."""
    overdue = ""
    if overdue_days is not None and overdue_days > CURATION_OVERDUE_DAYS:
        overdue = (
            f'<div style="margin:0 0 8px;font-family:var(--mono);font-size:11px;'
            f'color:{STATUS_WARN};">⚠ CURATION OVERDUE — newest core capex row '
            f'is {overdue_days}d old; a newer quarter has likely been reported. '
            f'Update data/capex_quarterly.json.</div>'
        )
    cells = ""
    for c in chips:
        color = _STATE_COLOR.get(c["state"], INK_FALLBACK)
        cells += (
            f'<div style="flex:1 1 170px;min-width:160px;padding:8px 10px;'
            f'border:1px solid var(--rule);border-left:3px solid {color};">'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.08em;text-transform:uppercase;color:var(--ink-3);">'
            f'{_escape_dollars(c["label"])} · {_escape_dollars(c["asof"])}</div>'
            f'<div style="margin-top:3px;font-size:12.5px;color:var(--ink-2);'
            f'line-height:1.45;">'
            f'<span style="color:{color};font-weight:600;">'
            f'{_STATE_GLYPH.get(c["state"], "—")}</span> '
            f'{_escape_dollars(c["detail"])}</div></div>'
        )
    return f'{overdue}<div style="display:flex;flex-wrap:wrap;gap:8px;">{cells}</div>'


def _gap_chart_frame(gap_rows: list) -> pd.DataFrame:
    """The exact frame behind the gap chart (also the a11y table)."""
    return pd.DataFrame(
        [{"quarter": g["cq"], "capex_yoy_pct": g["capex_yoy_pct"],
          "rev_growth_pct": g["rev_growth_pct"], "gap_pp": g["gap_pp"]}
         for g in gap_rows],
        columns=["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"])


def _gap_fig(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_bar(x=df["quarter"], y=df["gap_pp"], name="Coverage gap (pp)",
                marker_color=[STATUS_POS if v >= 0 else STATUS_NEG
                              for v in df["gap_pp"]])
    fig.add_scatter(x=df["quarter"], y=df["capex_yoy_pct"],
                    name="Core capex YoY %", mode="lines+markers",
                    line=dict(color=CHART_MUTED))
    fig.add_scatter(x=df["quarter"], y=df["rev_growth_pct"],
                    name="Beneficiary revenue growth %", mode="lines+markers",
                    line=dict(color=CHART_ACCENT))
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_fig(fig)


def _cluster_medians(fund_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """dates × clusters pivot of per-cluster medians for *metric*."""
    if fund_df.empty:
        return pd.DataFrame()
    df = fund_df[fund_df["cluster"] != ""].dropna(subset=[metric])
    if df.empty:
        return pd.DataFrame()
    return df.groupby(["date", "cluster"])[metric].median().unstack("cluster")


def _trend_fig(pivot: pd.DataFrame):
    fig = go.Figure()
    for i, cluster in enumerate(pivot.columns):
        fig.add_scatter(x=list(pivot.index), y=pivot[cluster], mode="lines",
                        name=str(cluster),
                        line=dict(color=CHART_PALETTE[i % len(CHART_PALETTE)],
                                  width=1.6))
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_fig(fig)


def render_capex_pulse() -> None:
    """The AI Capex Pulse band (Briefing). Degrades chip-by-chip, never crashes."""
    capex = parse_capex(load_capex_quarterly())
    fund_df = _fundamentals_cached(data_fingerprint(), load_all_reports())
    if not capex["series"] and fund_df.empty:
        return
    today = _date.today()
    render_section_head(
        "AI Capex Pulse",
        "Digestion scorecard — human-read cross-check, not a wired signal")
    for w in capex["warnings"]:
        st.caption(f"⚠ capex file: {w}")
    st.markdown(_chips_html(build_chips(capex, fund_df, today),
                            curation_age_days(capex, today)),
                unsafe_allow_html=True)
    cr = current_read(capex, fund_df)
    if cr:
        st.caption(
            f"Current read: beneficiary revenue {cr['rev_growth_pct']:+.1f}% "
            f"({cr['rev_asof']}) vs core capex {cr['capex_yoy_pct']:+.1f}% YoY "
            f"({cr['capex_cq']}) → gap {cr['gap_pp']:+.1f}pp. The revenue side "
            f"is only as old as the report corpus.")
    gaps = coverage_gap_series(capex, fund_df)
    if gaps:
        df = _gap_chart_frame(gaps)
        st.plotly_chart(_gap_fig(df), use_container_width=True,
                        config=PLOTLY_CONFIG)
        chart_data_table(df)
    if not fund_df.empty:
        with st.expander("Cluster fundamentals over time"):
            for metric, label in _TREND_METRICS:
                pivot = _cluster_medians(fund_df, metric)
                if pivot.empty:
                    continue
                st.markdown(
                    f'<div style="font-family:var(--mono);font-size:10px;'
                    f'letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:var(--ink-3);margin:8px 0 2px;">{label}</div>',
                    unsafe_allow_html=True)
                st.plotly_chart(_trend_fig(pivot), use_container_width=True,
                                config=PLOTLY_CONFIG)
                chart_data_table(pivot.reset_index())
