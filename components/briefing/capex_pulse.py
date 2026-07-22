"""Briefing · AI Capex Pulse band.

Human-read digestion scorecard for the capex cycle (spec
docs/superpowers/specs/2026-07-03-capex-pulse-redesign-design.md): one plate
— an auto-derived verdict caption over a five-row datasheet (capex, revenue,
coverage gap, valuation, fragile tier; tone = health, one dot per row) — then
the coverage-gap chart and cluster-fundamentals trends behind a History
expander. By design a cross-check the reader eyeballs against the scenario
odds — nothing here feeds the odds mechanically.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.capex import (
    CURATION_OVERDUE_DAYS,
    build_chips,
    compute_verdict,
    coverage_gap_series,
    curation_age_days,
    fundamentals_history,
    parse_capex,
)
from lib.cards import render_section_head
from lib.charts import (
    CHART_ACCENT,
    CHART_LINE,
    CHART_PALETTE,
    INK_FALLBACK,
    PLOTLY_CONFIG,
    STATUS_NEG,
    STATUS_POS,
    STATUS_WARN,
    chart_data_table,
    style_fig,
)
from lib.clock import today as clock_today
from lib.data_loader import data_fingerprint, load_all_reports, load_capex_quarterly
from lib.formatters import _escape_dollars

_TONE_COLOR = {"good": STATUS_POS, "watch": STATUS_WARN, "stress": STATUS_NEG,
               "neutral": INK_FALLBACK, "na": INK_FALLBACK}

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


def _dot(tone: str) -> str:
    """Inline health dot — the one place tone becomes a color."""
    c = _TONE_COLOR.get(tone, INK_FALLBACK)
    return (f'<span style="display:inline-block;width:8px;height:8px;'
            f'border-radius:50%;background:{c};margin-right:6px;'
            f'vertical-align:middle;"></span>')


def _overdue_html(overdue_days: int | None) -> str:
    """Curation-overdue banner, or '' when the file is fresh enough."""
    if overdue_days is None or overdue_days <= CURATION_OVERDUE_DAYS:
        return ""
    return (f'<div style="margin:0 0 8px;font-family:var(--mono);font-size:11px;'
            f'color:{STATUS_WARN};">⚠ CURATION OVERDUE — newest core capex row '
            f'is {overdue_days}d old; a newer quarter has likely been reported. '
            f'Update data/capex_quarterly.json.</div>')


def _datasheet_html(verdict: dict, chips: list) -> str:
    """The plate: one table — a captioned verdict header, then one row per
    chip (spec §1). Fixed geometry — widths come from the colgroup in
    theme.css's .capex-sheet, never from content. Tone appears once per row
    as a dot in the No. cell, not as a border on every block.

    The verdict/gloss line sits in ``<caption>`` rather than a body ``<tr>``:
    it summarizes the table, isn't a data row, and keeping it out of
    ``<tbody>``/``<thead>`` rows keeps the row count exactly 1 header row + 1
    row per chip.
    """
    vcolor = _TONE_COLOR.get(verdict["tone"], INK_FALLBACK)
    rows = ""
    for i, c in enumerate(chips, start=1):
        rows += (
            f'<tr>'
            f'<td class="cs-no">{_dot(c["tone"])}{i:02d}</td>'
            f'<td class="cs-measure">{_escape_dollars(c["measure"])}</td>'
            f'<td class="cs-value">{_escape_dollars(c["value"])}</td>'
            f'<td class="cs-remark">{_escape_dollars(c["remark"])}</td>'
            f'</tr>')
    return (
        f'<table class="capex-sheet">'
        f'<caption class="cs-read">'
        f'<span class="cs-state" style="color:{vcolor};">'
        f'{_escape_dollars(verdict["label"])}</span> '
        f'<span class="cs-gloss">{_escape_dollars(verdict["gloss"])}</span>'
        f'</caption>'
        f'<colgroup><col class="c-no"><col class="c-measure">'
        f'<col class="c-value"><col class="c-remark"></colgroup>'
        f'<thead><tr class="cs-head"><th scope="col">No</th>'
        f'<th scope="col">Measure</th><th scope="col">Value</th>'
        f'<th scope="col">What it means</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>')


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
                    # CHART_LINE (ink-3, ~5.4:1) not CHART_MUTED (ink-4, ~2.68:1):
                    # the muted tone fell below the 3:1 floor for graphical objects
                    # and the reference line was near-invisible on --paper.
                    line=dict(color=CHART_LINE))
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
    today = clock_today()  # == date.today() unless TEST_DATE frozen (visual-regression)
    render_section_head(
        "AI Capex Pulse",
        "Digestion cross-check — human-read, not a wired signal")
    for w in capex["warnings"]:
        st.caption(f"⚠ capex file: {w}")
    chips = build_chips(capex, fund_df, today)
    by_key = {c["key"]: c for c in chips}
    verdict = compute_verdict(capex, fund_df, chips)
    st.markdown(
        "".join([
            _overdue_html(curation_age_days(capex, today)),
            _datasheet_html(verdict, [by_key[k] for k in
                                      ("capex", "rev", "gap", "val", "fragile")]),
        ]),
        unsafe_allow_html=True)
    # Declutter pass 2026-07-21: the gap chart + its data table were always
    # rendered (~380px) below the verdict/hero/chips (now the datasheet plate),
    # which already carry the read. Both histories now share one collapsed
    # expander — the spec's human-read scorecard stays visible, the evidence
    # is one click away.
    gaps = coverage_gap_series(capex, fund_df)
    if gaps or not fund_df.empty:
        with st.expander("History — coverage gap & cluster fundamentals"):
            if gaps:
                df = _gap_chart_frame(gaps)
                st.plotly_chart(_gap_fig(df), use_container_width=True,
                                config=PLOTLY_CONFIG)
                chart_data_table(df)
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
