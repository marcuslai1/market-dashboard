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

import streamlit as st

from live_prices import fetch_live_quotes, overlay_live
from lib.catalog import RETIRED_TICKERS, SIGNAL_ORDER, SIGNAL_VERBS
from lib.cards import render_section_head
from lib.data_loader import load_all_reports, load_sqlite_prices
from lib.filters import filter_prices, filter_reports
from lib.pills import _render_live_caption, signal_text_color
from lib.state import init_session_state, is_first_mount, mark_mounted
from components.briefing import (
    render_action_card,
    render_catalyst_playbook,
    render_changes,
    render_contrarian_candidates,
    render_pulse,
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

# ── First-mount flag flip ──
# Flip immediately after the one-shot animation <style> above has been decided.
# is_first_mount() is only read there, so flipping now is safe — and doing it
# here (rather than at the bottom) means an early st.stop() in any page branch
# can't leave has_mounted False and re-fire the intro animations next run.
mark_mounted()


# ── Masthead + top nav ──
page = render_masthead_and_nav()


# ── Sidebar: status summary ──
_status_reports = load_all_reports()
_latest_date = max(_status_reports.keys()) if _status_reports else "—"
_latest_rpt = _status_reports.get(_latest_date, {})

# ── Body-level data refresh + freshness indicator ──
# The sidebar holds a "Refresh Data" button, but on mobile/narrow viewports the
# Streamlit chrome that carries the sidebar-expand arrow is hidden, leaving the
# sidebar (and its refresh) unreachable. Surface a compact refresh here in the
# main flow so every viewport can reload the latest data. Mirrors the sidebar
# button's clear-cache + rerun behaviour.
_fresh_col, _refresh_col = st.columns([4, 1])
with _fresh_col:
    st.markdown(
        f'<div style="font-family:var(--mono);font-size:11px;color:var(--ink-3);'
        f'padding-top:6px;">Data as of <span style="color:var(--ink-2);">'
        f'{_latest_date}</span></div>',
        unsafe_allow_html=True,
    )
with _refresh_col:
    if st.button("↻ Refresh", use_container_width=True,
                 help=f"Reload the latest data (showing {_latest_date})"):
        st.cache_data.clear()
        st.rerun()
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
for _sig in SIGNAL_ORDER:
    _cnt = _sig_counts.get(_sig, 0)
    if _cnt:
        _sig_dots += (
            f'<span style="color:{signal_text_color(_sig)};font-weight:700;margin-right:8px;">'
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


st.sidebar.divider()


# ── Sidebar: signal legend ──
# Built from the canonical catalog (colors + verbs) so the palette and verbs
# never drift from lib/catalog.py / assets/catalog.json.
_legend_rows = "<br>".join(
    f'<span style="color:{signal_text_color(_s)};font-weight:700;">● {_s}</span>'
    f' — {SIGNAL_VERBS.get(_s, "")}'
    for _s in SIGNAL_ORDER
)
st.sidebar.markdown(
    f'<div style="font-size:0.8em;color:#b0b0b0;line-height:1.6;">{_legend_rows}</div>',
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

    # Data-coverage banner — only when the report ran on incomplete data.
    # A degraded run disarms cluster medians + extension-regime checks, so the
    # whole briefing should carry a visible trust caveat. Silent on clean days.
    _dc = (report.get("meta") or {}).get("data_coverage") or {}
    if _dc.get("coverage_degraded"):
        _skipped = _dc.get("skipped") or []
        _skip_note = f" Missing: {', '.join(_skipped[:8])}." if _skipped else ""
        st.markdown(
            '<div class="briefing-banner" data-tone="warn">⚠ Data coverage degraded — '
            f'{_dc.get("fetched")}/{_dc.get("expected")} names fetched.'
            f'{_skip_note} Cluster medians and extension-regime checks are '
            'disarmed today; treat signals as provisional.</div>',
            unsafe_allow_html=True,
        )

    # ACCUMULATE paper-phase status — one measured line (replaces the old
    # per-ticker "PAPER TRADE" labels; the [paper] tag rides in what_to_do).
    # Present only on days carrying ≥1 ACCUMULATE; sourced from the pipeline's
    # gate readout, so it never drifts from the Measurement Gate.
    _aps = report.get("accumulate_paper_status")
    if isinstance(_aps, dict) and _aps.get("line"):
        _grad = _aps.get("graduated")
        st.markdown(
            f'<div class="briefing-banner" data-tone="{"ok" if _grad else "test"}">'
            f'{"✅" if _grad else "🧪"} {_aps["line"]}</div>',
            unsafe_allow_html=True,
        )

    # Crisis flag — heuristic scan for "crisis dislocation" in writeup text
    _crisis_markers = {"crisis dislocation", "crisis-dislocation", "crisis_dislocation"}
    _crisis_detected = any(
        any(m in str(wl_entry.get("writeup") or {}).lower() for m in _crisis_markers)
        for wl_entry in watchlist.values()
    )
    if _crisis_detected:
        st.markdown(
            '<div class="briefing-banner" data-tone="crisis">'
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

    # Context band: Macro note (lede) + Active Risks (ledger) on row 1, then the
    # Week-Ahead calendar as a full-width strip on row 2. Placing the catalyst
    # list in its own strip (rather than stacking it under Risks in the right
    # column) keeps the row heights balanced and removes the tall empty void
    # that used to sit beside the short Macro note.
    band_html = (
        '<div class="lane-wrapper">'
        + macro_card_html(report.get("macro_summary", ""), geo,
                          report.get("commodities_note", ""),
                          report.get("macro_indicators", {}))
        + risks_card_html(geo)
        + calendar_card_html(events, lane="strip")
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
        filter_reports(load_all_reports(), DATE_START, DATE_END),
        filter_prices(load_sqlite_prices(), DATE_START, DATE_END),
    )


# ════════════════════════════════════════════
# PAGE: Scenario Log
# ════════════════════════════════════════════
elif page == "Scenario Log":
    from components.scenario_log import render_scenario_log_page
    render_scenario_log_page(filter_reports(load_all_reports(), DATE_START, DATE_END))


# ════════════════════════════════════════════
# PAGE: Pipeline Stats
# ════════════════════════════════════════════
elif page == "Pipeline Stats":
    from components.pipeline_stats import render_pipeline_stats_page
    render_pipeline_stats_page(filter_reports(load_all_reports(), DATE_START, DATE_END))


# ════════════════════════════════════════════
# PAGE: Report Comparison
# ════════════════════════════════════════════
elif page == "Report Comparison":
    from components.report_comparison import render_report_comparison_page
    render_report_comparison_page(filter_reports(load_all_reports(), DATE_START, DATE_END))


# ════════════════════════════════════════════
# PAGE: Terminology — methodology & formulas reference
# ════════════════════════════════════════════
elif page == "Terminology":
    from components.terminology import render_terminology_page
    render_terminology_page()
