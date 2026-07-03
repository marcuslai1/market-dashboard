"""Briefing · AI Capex Pulse band.

Human-read digestion scorecard for the capex cycle (spec
docs/superpowers/specs/2026-07-03-capex-pulse-redesign-design.md): an
auto-derived verdict line, the coverage gap as a dated hero with a forward
note, the four remaining signals as a keyed list (color = health, arrow =
direction), then the coverage-gap chart and cluster-fundamentals trends. By
design a cross-check the reader eyeballs against the scenario odds — nothing
here feeds the odds mechanically.
"""
from __future__ import annotations

from datetime import date as _date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.capex import (CURATION_OVERDUE_DAYS, build_chips, compute_verdict,
                       coverage_gap_series, curation_age_days,
                       forward_revenue_note, fundamentals_history, parse_capex)
from lib.cards import render_section_head
from lib.charts import (CHART_ACCENT, CHART_LINE, CHART_PALETTE, INK_FALLBACK,
                        PLOTLY_CONFIG, STATUS_NEG, STATUS_POS, STATUS_WARN,
                        chart_data_table, style_fig)
from lib.data_loader import data_fingerprint, load_all_reports, load_capex_quarterly
from lib.formatters import _escape_dollars

_TONE_COLOR = {"good": STATUS_POS, "watch": STATUS_WARN, "stress": STATUS_NEG,
               "neutral": INK_FALLBACK, "na": INK_FALLBACK}
_ARROW = {"up": "▲", "down": "▼", "none": ""}

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


def _verdict_html(verdict: dict) -> str:
    """The headline read: colored dot + STATE + one-sentence gloss."""
    color = _TONE_COLOR.get(verdict["tone"], INK_FALLBACK)
    return (
        f'<div style="display:flex;align-items:baseline;gap:8px;padding:10px 12px;'
        f'border:1px solid var(--rule);border-left:3px solid {color};margin:0 0 10px;">'
        f'<span style="font-family:var(--mono);font-size:12px;font-weight:700;'
        f'letter-spacing:0.08em;color:{color};white-space:nowrap;">'
        f'{_dot(verdict["tone"])}{_escape_dollars(verdict["label"])}</span>'
        f'<span style="font-size:12.5px;color:var(--ink-2);line-height:1.45;">'
        f'{_escape_dollars(verdict["gloss"])}</span></div>')


def _hero_gap_html(gap: dict, note: dict | None) -> str:
    """Coverage gap as the accented hero: one dated number + optional forward note."""
    color = _TONE_COLOR.get(gap["tone"], INK_FALLBACK)
    asof = (f'<span style="font-family:var(--mono);font-size:10px;'
            f'color:var(--ink-3);">as of {_escape_dollars(gap["asof"])} earnings</span>'
            if gap["asof"] != "—" else "")
    fwd = ""
    if note is not None:
        fwd = (f'<div style="margin-top:4px;font-size:11.5px;color:var(--ink-3);">'
               f'↳ revenue has since {note["direction"]} to {note["now_pct"]:+.1f}% '
               f'({note["now_asof"]}); the matching capex quarter is not reported '
               f'yet, so the next gap may {note["hint"]}.</div>')
    return (
        f'<div style="padding:10px 12px;border:1px solid var(--rule);'
        f'border-left:3px solid {color};margin:0 0 8px;">'
        f'<div style="font-family:var(--mono);font-size:10px;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:var(--ink-3);">'
        f'{_escape_dollars(gap["label"])} · {_escape_dollars(gap["sub"])}</div>'
        f'<div style="margin-top:3px;font-size:13px;color:var(--ink-2);">'
        f'{_dot(gap["tone"])}{_escape_dollars(gap["detail"])} &nbsp;{asof}</div>'
        f'{fwd}</div>')


def _signals_html(chips: list) -> str:
    """The non-gap signals as a legible keyed row (dot + label + arrow + detail + sub)."""
    cells = ""
    for c in chips:
        color = _TONE_COLOR.get(c["tone"], INK_FALLBACK)
        arrow = _ARROW.get(c["arrow"], "")
        arrow_s = (f'<span style="color:{color};font-weight:600;">{arrow}</span> '
                   if arrow else "")
        cells += (
            f'<div style="flex:1 1 200px;min-width:190px;padding:8px 10px;'
            f'border:1px solid var(--rule);border-left:3px solid {color};">'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.06em;text-transform:uppercase;color:var(--ink-3);">'
            f'{_dot(c["tone"])}{_escape_dollars(c["label"])} · {_escape_dollars(c["asof"])}</div>'
            f'<div style="margin-top:3px;font-size:12.5px;color:var(--ink-2);'
            f'line-height:1.4;">{arrow_s}{_escape_dollars(c["detail"])}</div>'
            f'<div style="margin-top:2px;font-size:10.5px;color:var(--ink-3);'
            f'line-height:1.35;">{_escape_dollars(c["sub"])}</div></div>')
    key = (
        '<div style="margin-top:6px;font-family:var(--mono);font-size:10px;'
        'color:var(--ink-3);">'
        f'<span style="color:{STATUS_POS};">●</span> healthy · '
        f'<span style="color:{STATUS_WARN};">●</span> watch · '
        f'<span style="color:{STATUS_NEG};">●</span> stress &nbsp;&nbsp;'
        '▲▼ = direction only</div>')
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{cells}</div>{key}'


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
    today = _date.today()
    render_section_head(
        "AI Capex Pulse",
        "Digestion cross-check — human-read, not a wired signal")
    for w in capex["warnings"]:
        st.caption(f"⚠ capex file: {w}")
    chips = build_chips(capex, fund_df, today)
    by_key = {c["key"]: c for c in chips}
    verdict = compute_verdict(capex, fund_df, chips)
    note = forward_revenue_note(capex, fund_df)
    st.markdown(
        "".join([
            _overdue_html(curation_age_days(capex, today)),
            _verdict_html(verdict),
            _hero_gap_html(by_key["gap"], note),
            _signals_html([by_key[k] for k in ("capex", "rev", "val", "fragile")]),
        ]),
        unsafe_allow_html=True)
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
