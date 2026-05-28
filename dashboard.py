"""MarketReport Analytics Dashboard.

Run with: streamlit run dashboard.py

Slim orchestrator — page-level UI lives in ``components/``. This module owns:
- ``st.set_page_config`` + theme CSS injection
- the masthead/nav call (returns the active page)
- sidebar filter controls (date range, live-prices toggle, refresh)
- global filter helpers (``filter_reports`` / ``filter_prices``)
- the page elif chain that dispatches to ``components.<page>``
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from live_prices import fetch_live_quotes, overlay_live
from lib.catalog import RETIRED_TICKERS
from lib.cards import render_section_head
from lib.data_loader import load_all_reports, load_sqlite_prices
from lib.pills import _render_live_caption
from lib.state import init_session_state, is_first_mount, mark_mounted
from components.briefing import (
    render_action_card,
    render_calendar,
    render_catalyst_playbook,
    render_changes,
    render_contrarian_candidates,
    render_macro,
    render_pulse,
    render_stance,
)
from components.briefing.calendar import calendar_card_html
from components.briefing.macro import macro_card_html, risks_card_html
from components.briefing.stance import stance_band_html
from components.masthead import render_masthead_and_nav
from components.watchlist import render_watchlist

# ── Config ──
DATA_DIR = Path(__file__).parent / "data"
ASSETS_DIR = Path(__file__).parent / "assets"

st.set_page_config(page_title="MarketReport Dashboard", layout="wide")

# ── Session state bootstrap ──
# Must run BEFORE any component reads st.session_state.has_mounted / density.
# mark_mounted() flips has_mounted at the absolute bottom of this script so
# subsequent reruns are quiet.
init_session_state()

# ── Theme CSS: dark editorial (Newsreader serif + JetBrains Mono + Inter Tight) ──
# Stylesheet lives at assets/theme.css; injected once at startup. Edit the file
# (not this module) to change visuals.
_THEME_CSS = (Path(__file__).parent / "assets" / "theme.css").read_text(encoding="utf-8")
st.markdown(f"<style>{_THEME_CSS}</style>", unsafe_allow_html=True)

# ── First-mount one-shot animations ──
# Inject the animation-applying selectors only on the very first script run of
# the session. On subsequent reruns the <style> block is absent, so the rules
# don't exist and the keyframes (registered globally in theme.css) stay dormant.
# This decouples animation gating from any wrapper-div nesting.
if is_first_mount():
    st.markdown(
        "<style>"
        ".risk-card[data-severity=\"HIGH\"] {"
        " animation: risk-severity-pulse var(--dur-slow) var(--ease-out) 1; }"
        ".tk-details[data-signal-changed=\"true\"] > summary {"
        " animation: tk-signal-flash var(--dur-slow) var(--ease-out) 1; }"
        ".tk-details[data-signal=\"ACCUMULATE\"][data-signal-changed=\"true\"] > summary {"
        " animation-name: tk-signal-flash-accumulate; }"
        ".tk-details[data-signal=\"WATCH\"][data-signal-changed=\"true\"] > summary {"
        " animation-name: tk-signal-flash-watch; }"
        ".tk-details[data-signal=\"CAUTION\"][data-signal-changed=\"true\"] > summary {"
        " animation-name: tk-signal-flash-caution; }"
        "</style>",
        unsafe_allow_html=True,
    )

# ── Density override ──
# theme.css declares the relaxed defaults in :root. When the user picks Compact
# in the sidebar, we inject a later-in-document-order :root block that wins via
# cascade order.
if st.session_state.density == "compact":
    st.markdown(
        "<style>:root {"
        " --card-pad-y: 16px;"
        " --card-pad-x: 16px;"
        " --card-gap: 20px;"
        "}</style>",
        unsafe_allow_html=True,
    )


# ── Masthead + top nav ──
page = render_masthead_and_nav()


# ── Sidebar: status summary ──
_status_reports = load_all_reports()
_latest_date = max(_status_reports.keys()) if _status_reports else "—"
_latest_rpt = _status_reports.get(_latest_date, {})
_sig_counts = _latest_rpt.get("portfolio_snapshot", {}).get("signal_counts", {})

_status_html = '<div class="sidebar-status">'
_status_html += (
    '<div class="status-row">'
    '<span class="status-label">Latest report</span>'
    f'<span class="status-value">{_latest_date}</span></div>'
)
_status_html += (
    '<div class="status-row">'
    '<span class="status-label">Tickers</span>'
    f'<span class="status-value">{sum(_sig_counts.values())}</span></div>'
)
_sig_dots = ""
for _sig, _color in [("BUY", "#22c55e"), ("ACCUMULATE", "#3498db"),
                      ("WATCH", "#f59e0b"), ("HOLD", "#6b7280"),
                      ("CAUTION", "#ef4444")]:
    _cnt = _sig_counts.get(_sig, 0)
    if _cnt:
        _sig_dots += (
            f'<span style="color:{_color};font-weight:700;margin-right:8px;">'
            f'●{_cnt}</span>'
        )
_status_html += (
    '<div class="status-row" style="margin-top:4px;">'
    '<span class="status-label">Signals</span>'
    f'<span>{_sig_dots}</span></div>'
)
_status_html += '</div>'
st.sidebar.markdown(_status_html, unsafe_allow_html=True)

st.sidebar.divider()


# ── Sidebar: date range filter ──
_default_end = date.today()
_default_start = _default_end - timedelta(days=30)
_range_presets = {"30 days": 30, "7 days": 7, "All": None}
_preset = st.sidebar.radio("Range", list(_range_presets.keys()), horizontal=True, key="range_preset")
_preset_days = _range_presets[_preset]
if _preset_days is not None:
    _pre_start = _default_end - timedelta(days=_preset_days)
else:
    _pre_start = date(2020, 1, 1)  # effectively "all time"
date_range = st.sidebar.date_input(
    "Date range", value=(_pre_start, _default_end), key="date_range"
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    DATE_START, DATE_END = date_range
else:
    DATE_START, DATE_END = _pre_start, _default_end


def filter_reports(reports: dict) -> dict:
    """Filter reports dict to the selected date range."""
    filtered = {}
    for date_str, rpt in reports.items():
        try:
            d = date.fromisoformat(date_str)
            if DATE_START <= d <= DATE_END:
                filtered[date_str] = rpt
        except ValueError:
            continue
    return filtered


def filter_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Filter price DataFrame to the selected date range."""
    if df.empty:
        return df
    return df[(df["date"].dt.date >= DATE_START) & (df["date"].dt.date <= DATE_END)]


st.sidebar.divider()


# ── Sidebar: signal legend ──
st.sidebar.markdown(
    '<div style="font-size:0.8em;color:#b0b0b0;line-height:1.6;">'
    '<span style="color:#22c55e;font-weight:700;">● BUY</span> — Enter now<br>'
    '<span style="color:#3498db;font-weight:700;">● ACCUMULATE</span> — Add on strength<br>'
    '<span style="color:#f59e0b;font-weight:700;">● WATCH</span> — Waiting for trigger<br>'
    '<span style="color:#6b7280;font-weight:700;">● HOLD</span> — Maintain<br>'
    '<span style="color:#ef4444;font-weight:700;">● CAUTION</span> — Trim / avoid'
    '</div>',
    unsafe_allow_html=True,
)

st.sidebar.divider()

# ── Sidebar: density toggle ──
# Radio holds the display label ("Relaxed"/"Compact"); on_change normalises to
# the canonical lowercase value in st.session_state.density. The :root override
# above watches that canonical value.
st.sidebar.radio(
    "Density",
    options=["Relaxed", "Compact"],
    index=0 if st.session_state.density == "relaxed" else 1,
    horizontal=True,
    key="density_radio",
    on_change=lambda: st.session_state.update(density=st.session_state.density_radio.lower()),
)

st.sidebar.divider()
LIVE_PRICES = st.sidebar.toggle(
    "Live prices (Yahoo)",
    value=True,
    help="When on, benchmarks and watchlist Last/Δ show live Yahoo quotes "
         "(60s cache). Snapshot fields like RSI / 1mo / SMA stay frozen at the "
         "report date. Historical reports are never overlaid.",
)

if st.sidebar.button("↻ Refresh Data"):
    st.cache_data.clear()
    st.rerun()


# ════════════════════════════════════════════
# PAGE 0: Briefing
# ════════════════════════════════════════════
if page == "Briefing":
    all_reports = load_all_reports()
    if not all_reports:
        st.error("No report files found in market_data/.")
        st.stop()

    sorted_dates = sorted(all_reports.keys(), reverse=True)
    latest_date = sorted_dates[0]
    report = all_reports[latest_date]
    prev_report = all_reports[sorted_dates[1]] if len(sorted_dates) >= 2 else None

    _live = fetch_live_quotes() if LIVE_PRICES else {}
    if _live:
        report = overlay_live(report, _live)

    snapshot = report.get("portfolio_snapshot", {})
    watchlist = report.get("watchlist", {})
    benchmarks = report.get("benchmarks", {})
    geo = report.get("geopolitical", {})
    events = report.get("events_this_week", []) or []
    trigger_map = report.get("macro_trigger_map", []) or []
    contrarians = report.get("contrarian_candidates", []) or []

    # Stance band: single st.markdown so the lane-wrapper actually scopes both
    # the lede (stance deck) and ledger (signal counts) as grid children.
    st.markdown(stance_band_html(snapshot, len(watchlist)), unsafe_allow_html=True)

    # Crisis flag — heuristic scan for "crisis dislocation" in writeup text
    _crisis_markers = {"crisis dislocation", "crisis-dislocation", "crisis_dislocation"}
    _crisis_detected = any(
        any(m in str(wl_entry.get("writeup") or {}).lower() for m in _crisis_markers)
        for wl_entry in watchlist.values()
    )
    if _crisis_detected:
        st.markdown(
            '<div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.4);'
            'border-radius:4px;padding:12px 18px;margin-bottom:16px;'
            'font-family:var(--mono);font-size:12px;letter-spacing:0.07em;color:#ef4444;">'
            'CRISIS DISLOCATION FLAG ACTIVE — elevated signal noise. '
            'Treat all AVOID/CAUTION signals as provisional.'
            '</div>',
            unsafe_allow_html=True,
        )

    _render_live_caption(_live, LIVE_PRICES)
    render_pulse(benchmarks)
    render_changes(
        watchlist,
        prev_report.get("watchlist", {}) if prev_report else {},
    )
    render_action_card(watchlist, events)
    render_catalyst_playbook(trigger_map)
    render_contrarian_candidates(contrarians)

    band_html = (
        '<div class="lane-wrapper">'
        + macro_card_html(report.get("macro_summary", ""), geo, report.get("commodities_note", ""))
        + risks_card_html(geo)
        + calendar_card_html(events)
        + '</div>'
    )
    st.markdown(band_html, unsafe_allow_html=True)

    st.markdown(
        '<div style="margin-top:28px;padding:14px 16px;border-top:1px solid var(--rule);'
        'font-family:var(--mono);font-size:11px;letter-spacing:0.18em;'
        'text-transform:uppercase;color:var(--ink-3);">'
        'Methodology &amp; formulas → see the <b style="color:var(--ink);">Terminology</b> tab'
        '</div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════
# PAGE: Watchlist (full drill-down view; covers any past report date)
# ════════════════════════════════════════════
elif page == "Watchlist":
    all_reports = load_all_reports()
    if not all_reports:
        st.error("No report files found in market_data/.")
        st.stop()
    sorted_dates = sorted(all_reports.keys(), reverse=True)
    selected_date = st.selectbox(
        "Report date", sorted_dates, index=0, key="watchlist_date"
    )
    report = all_reports[selected_date]
    _is_latest = selected_date == sorted_dates[0]
    _live = fetch_live_quotes() if (LIVE_PRICES and _is_latest) else {}
    if _live:
        report = overlay_live(report, _live)
    watchlist = report.get("watchlist", {})
    benchmarks = report.get("benchmarks", {})

    # Compute the signal-change diff vs the immediately-prior report date.
    # Tickers that newly appeared / disappeared (signal "—") are excluded so we
    # don't flash rows whose change is structural rather than analytical.
    sel_idx = sorted_dates.index(selected_date)
    prev_wl = (
        all_reports[sorted_dates[sel_idx + 1]].get("watchlist", {})
        if sel_idx + 1 < len(sorted_dates) else {}
    )
    changed = {
        tk for tk in watchlist
        if prev_wl.get(tk, {}).get("signal", "—") != watchlist.get(tk, {}).get("signal", "—")
        and prev_wl.get(tk, {}).get("signal", "—") != "—"
        and watchlist.get(tk, {}).get("signal", "—") != "—"
    }

    sub_label = f"{sum(1 for tk in watchlist if tk not in RETIRED_TICKERS)} names · click any row to expand"
    if selected_date != sorted_dates[0]:
        sub_label += f" · viewing {selected_date}"
    render_section_head("The Watchlist", sub_label)
    _render_live_caption(_live, LIVE_PRICES and _is_latest)
    render_pulse(benchmarks)
    render_watchlist(watchlist, changed_tickers=changed)


# ════════════════════════════════════════════
# PAGE 2: Signal Tracker
# ════════════════════════════════════════════
elif page == "Signal Tracker":
    from components.signal_tracker import render_signal_tracker_page
    render_signal_tracker_page(
        filter_reports(load_all_reports()),
        filter_prices(load_sqlite_prices()),
    )


# ════════════════════════════════════════════
# PAGE: Scenario Log
# ════════════════════════════════════════════
elif page == "Scenario Log":
    from components.scenario_log import render_scenario_log_page
    render_scenario_log_page(filter_reports(load_all_reports()))


# ════════════════════════════════════════════
# PAGE: Pipeline Stats
# ════════════════════════════════════════════
elif page == "Pipeline Stats":
    from components.pipeline_stats import render_pipeline_stats_page
    render_pipeline_stats_page(filter_reports(load_all_reports()))


# ════════════════════════════════════════════
# PAGE: Report Comparison
# ════════════════════════════════════════════
elif page == "Report Comparison":
    from components.report_comparison import render_report_comparison_page
    render_report_comparison_page(filter_reports(load_all_reports()))


# ════════════════════════════════════════════
# PAGE: Terminology — methodology & formulas reference
# ════════════════════════════════════════════
elif page == "Terminology":
    from components.terminology import render_terminology_page
    render_terminology_page()


# ── First-mount flag flip ──
# Must be the absolute last line — after every elif branch can render. On the
# next rerun, is_first_mount() returns False and the one-shot CSS keyframes
# (signal-flash, severity-pulse) stay dormant.
mark_mounted()
