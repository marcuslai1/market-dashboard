"""MarketReport Analytics Dashboard.

Run with: streamlit run dashboard.py

Slim orchestrator — page-level UI lives in ``components/``. This module owns:
- ``st.set_page_config`` + theme CSS injection
- the page functions + ``st.navigation`` registry (real URL per page)
- the masthead/nav call (returns the selected page title)
- sidebar filter controls (date range, live-prices toggle, refresh)
- ``_pg.run()`` dispatch at the bottom
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import streamlit as st

# The Briefing page is the pulse strip, the daily briefing card and the market
# read (2026-09-29). The signal blocks (stance band, changes ribbon, clusters,
# action card) and the model-written ones (active risks, macro note) were
# removed once the report LLM went off on 09-28; the calendar folded into the
# briefing card's Week ahead + Further out. Signals stay on the measurement pages.
from components.briefing import render_pulse
from components.briefing.daily_briefing import briefing_card_html
from components.briefing.market_read import market_read_card_html
from components.masthead import render_masthead_and_nav
from components.watchlist import render_watchlist
from components.watchlist.grid import signal_day_counts
from lib.cards import render_section_head
from lib.catalog import SIGNAL_ORDER, SIGNAL_VERBS
from lib.clock import today as clock_today
from lib.data_loader import (
    data_fingerprint,
    list_report_dates,
    load_all_reports,
    load_briefings,
    load_earnings_map,
    load_market_reads,
    load_paper_nav,
    load_report,
    load_signal_log,
    load_sqlite_prices,
    load_text_asset,
)
from lib.filters import filter_prices, filter_reports
from lib.pills import _render_live_caption, signal_text_color
from lib.state import init_session_state, is_first_mount, mark_mounted
from live_prices import fetch_live_quotes, overlay_live

# ── Config ──
DATA_DIR = Path(__file__).parent / "data"
ASSETS_DIR = Path(__file__).parent / "assets"

st.set_page_config(page_title="MarketReport Dashboard", layout="wide")

# ── Session state bootstrap ──
# Must run BEFORE any component reads st.session_state.has_mounted / density.
# mark_mounted() flips has_mounted below so subsequent reruns are quiet.
init_session_state()

# ── Theme CSS: dark editorial (Newsreader serif + JetBrains Mono + Inter Tight) ──
# Stylesheet lives at assets/theme.css. The <style> block must be re-emitted on
# every rerun (Streamlit removes elements not produced this run), but the ~49KB
# file read is cached by mtime via load_text_asset — so reruns pay a cheap stat()
# instead of decoding the whole file each time, while edits still hot-reload.
_THEME_CSS = load_text_asset(Path(__file__).parent / "assets" / "theme.css")
st.markdown(f"<style>{_THEME_CSS}</style>", unsafe_allow_html=True)

# ── First-mount one-shot animations ──
# Inject the animation-applying selectors only on the very first script run of
# the session. On subsequent reruns the <style> block is absent, so the rules
# don't exist and the keyframes (registered globally in theme.css) stay dormant.
# This decouples animation gating from any wrapper-div nesting.
if is_first_mount():
    st.markdown(
        "<style>"
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


# ════════════════════════════════════════════
# Page bodies. Each runs via st.navigation → _pg.run() at the bottom of this
# script, AFTER the sidebar has assigned LIVE_PRICES / DATE_START / DATE_END —
# the functions read those module globals at call time.
# ════════════════════════════════════════════
def _page_briefing() -> None:
    _dates = list_report_dates()
    if not _dates:
        st.error("No report files found in market_data/.")
        st.stop()

    # Lazily load only the latest + prior report (not all ~80). Fall back one day
    # if the newest file is unreadable, so a truncated report degrades to the last
    # good briefing rather than an empty page.
    latest_date = _dates[-1]
    _base_report = load_report(latest_date)
    _prev_date = _dates[-2] if len(_dates) >= 2 else None
    if not _base_report and _prev_date:
        latest_date, _base_report = _prev_date, load_report(_prev_date)
    if not _base_report:
        st.error("No readable report files found in data/.")
        st.stop()

    # Live prices are the only per-minute-changing input on the Briefing, and the
    # Yahoo fetch can stall for a few seconds. Rendering the body inside a fragment
    # keeps that fetch off the main script run — masthead, nav, and sidebar paint
    # immediately — and lets the body auto-refresh every 60s (when live prices are
    # on) without re-parsing reports or rebuilding the masthead. overlay_live only
    # touches price/chg_pct, so every component still reads the frozen snapshot for
    # RSI / SMA / valuation.
    @st.fragment(run_every=(60 if LIVE_PRICES else None))
    def _render_briefing_body() -> None:
        _live = fetch_live_quotes() if LIVE_PRICES else {}
        report = overlay_live(_base_report, _live) if _live else _base_report
        benchmarks = report.get("benchmarks") or {}

        # Data-coverage banner — only when the report ran on incomplete data, so
        # the page carries a visible trust caveat. Silent on clean days.
        _dc = (report.get("meta") or {}).get("data_coverage") or {}
        if _dc.get("coverage_degraded"):
            _skipped = _dc.get("skipped") or []
            _skip_note = f" Missing: {', '.join(_skipped[:8])}." if _skipped else ""
            st.markdown(
                '<div class="briefing-banner" data-tone="warn">⚠ Data coverage degraded — '
                f'{_dc.get("fetched")}/{_dc.get("expected")} names fetched.{_skip_note}</div>',
                unsafe_allow_html=True,
            )

        _render_live_caption(_live, LIVE_PRICES)
        render_pulse(benchmarks)

        # The daily briefing (Claude in the terminal, MarketReport /briefing skill):
        # moves and why, the week ahead, earnings, further-out dates, chart facts.
        _briefing = briefing_card_html(load_briefings(),
                                       (report.get("meta") or {}).get("report_date"),
                                       load_earnings_map())
        if _briefing:
            st.markdown(_briefing, unsafe_allow_html=True)

        # Experimental market-read card. Sits BELOW the proven briefing blocks
        # (owner decision 2026-09-09): it is a 4-session adviser and must not
        # front-run instruments that have passed a measurement bar. Renders
        # nothing until a read has been published, and carries no score — see
        # components/briefing/market_read.py for why.
        _mr = market_read_card_html(load_market_reads())
        if _mr:
            st.markdown(_mr, unsafe_allow_html=True)

        st.markdown(
            '<div style="margin-top:28px;padding:14px 16px;border-top:1px solid var(--rule);'
            'font-family:var(--mono);font-size:11px;letter-spacing:0.18em;'
            'text-transform:uppercase;color:var(--ink-3);">'
            'Methodology &amp; formulas → see the <b style="color:var(--ink);">Terminology</b> tab'
            '</div>',
            unsafe_allow_html=True,
        )

    _render_briefing_body()


def _page_watchlist() -> None:
    _dates_desc = list_report_dates()[::-1]  # newest first for the selector
    if not _dates_desc:
        st.error("No report files found in market_data/.")
        st.stop()
    selected_date = st.selectbox(
        "Report date", _dates_desc, index=0, key="watchlist_date"
    )
    _is_latest = selected_date == _dates_desc[0]
    sel_idx = _dates_desc.index(selected_date)
    _prev_date = _dates_desc[sel_idx + 1] if sel_idx + 1 < len(_dates_desc) else None

    # Same treatment the Briefing body got in the perf pass: the Yahoo fetch
    # runs inside a fragment, so a live-quote cache miss can't block the
    # masthead/sidebar paint, and live prices auto-refresh every 60s in
    # isolation. The selectbox stays on the main run so picking a date
    # redefines the fragment with the right run_every (historical dates never
    # fetch or auto-refresh).
    @st.fragment(run_every=(60 if (LIVE_PRICES and _is_latest) else None))
    def _render_watchlist_body() -> None:
        report = load_report(selected_date)
        _live = fetch_live_quotes() if (LIVE_PRICES and _is_latest) else {}
        if _live:
            report = overlay_live(report, _live)
        watchlist = report.get("watchlist", {})
        benchmarks = report.get("benchmarks", {})

        # Compute the signal-change diff vs the immediately-prior report date.
        # Tickers that newly appeared / disappeared (signal "—") are excluded so
        # we don't flash rows whose change is structural rather than analytical.
        # Only the selected report + its predecessor are parsed, not the whole
        # corpus.
        prev_wl = load_report(_prev_date).get("watchlist", {}) if _prev_date else {}
        changed = {
            tk for tk in watchlist
            if prev_wl.get(tk, {}).get("signal", "—") != watchlist.get(tk, {}).get("signal", "—")
            and prev_wl.get(tk, {}).get("signal", "—") != "—"
            and watchlist.get(tk, {}).get("signal", "—") != "—"
        }

        # The name count moved out of the descriptor: the filter chips carry it
        # now (they double as the book's distribution readout) and the footer
        # restates it. The descriptor states scope + interaction instead, so
        # nothing else has to explain that rows expand.
        sub_label = "The whole book · click any row for the full read"
        if not _is_latest:
            sub_label += f" · viewing {selected_date}"
        render_section_head("The Watchlist", sub_label, masthead=True)
        _render_live_caption(_live, LIVE_PRICES and _is_latest)
        render_pulse(benchmarks)
        # "day N" under each pill: consecutive reports with the same shipped
        # call, from the signal log (MarketReport clean-sheet §12.12 display).
        _log = load_signal_log()
        _day_counts = {}
        if not _log.empty and {"date", "ticker", "signal"} <= set(_log.columns):
            _log = _log.dropna(subset=["date", "ticker", "signal"])
            _day_counts = signal_day_counts(
                _log.assign(date=_log["date"].dt.strftime("%Y-%m-%d"))[
                    ["date", "ticker", "signal"]].itertuples(index=False, name=None),
                str(selected_date)[:10],
                {tk: v.get("signal") for tk, v in watchlist.items()})
        render_watchlist(watchlist, changed_tickers=changed, day_counts=_day_counts)

        # Contrarian candidates moved off the Briefing (overhaul 2026-07):
        # oversold names with a recovery thesis are name-level setups, so they
        # sit with the names page. Rare — silent on most days.
        from components.briefing import render_contrarian_candidates
        render_contrarian_candidates(report.get("contrarian_candidates", []) or [])

    _render_watchlist_body()


# Tabs removed 2026-09-29: Scenario Log (model-written scenario odds, no new data
# since the report LLM went off on 09-28), Pipeline Stats (DeepSeek tokens and
# cost, all zero since 09-28 — restore from git if the LLM flag is turned back
# on) and Report Comparison (a signal-change view the Watchlist date picker and
# the Tracker's signal-changes drawer already cover). The Clusters and
# Fundamentals tabs went on 2026-07-24; their Briefing cards on 2026-09-29.


def _page_signal_tracker() -> None:
    from components.briefing import render_calibration
    from components.signal_tracker import render_signal_tracker_page

    # Signal calibration moved off the Briefing (overhaul 2026-07): "how have
    # today's signals actually performed" is the Tracker's own subject, so it
    # leads the page. Anchored to the latest report, not the filtered range.
    _cal_dates = list_report_dates()
    if _cal_dates:
        _cal_latest = load_report(_cal_dates[-1])
        render_calibration(
            _cal_latest.get("calibration_insights"),
            _cal_latest.get("watchlist", {}),
        )
    render_signal_tracker_page(
        filter_reports(load_all_reports(), DATE_START, DATE_END),
        filter_prices(load_sqlite_prices(), DATE_START, DATE_END),
        # Cheap corpus signature so the page's derived frames memoize across
        # filter/toggle reruns instead of recomputing O(reports × tickers).
        cache_key=(data_fingerprint(), DATE_START, DATE_END),
        # The raw-direction popover reads the pipeline's exported outcomes
        # (session basis) for calls dated inside the range — R12 F04.
        log_df=load_signal_log(),
        date_range=(DATE_START, DATE_END),
    )


def _page_retrospective() -> None:
    from components.retrospective import render_retrospective_page
    # Not sidebar-date-filtered: the page's month picker is its own time
    # control and the archive should always be complete.
    _dates = list_report_dates()
    _latest = load_report(_dates[-1]) if _dates else {}
    render_retrospective_page(_latest, load_signal_log(), load_paper_nav())


def _page_terminology() -> None:
    from components.terminology import render_terminology_page
    render_terminology_page()


# ── Native navigation ──
# st.navigation gives each page a real URL (/briefing, /watchlist, …) so deep
# links, browser refresh, AND back/forward all work natively. position="hidden"
# suppresses Streamlit's own nav chrome — the masthead radio below is the
# visible navigation, mirroring into st.switch_page.
_PAGES = {
    "Briefing": st.Page(_page_briefing, title="Briefing", url_path="briefing", default=True),
    "Watchlist": st.Page(_page_watchlist, title="Watchlist", url_path="watchlist"),
    "Signal Tracker": st.Page(_page_signal_tracker, title="Signal Tracker", url_path="signal-tracker"),
    "Retrospective": st.Page(_page_retrospective, title="Retrospective", url_path="retrospective"),
    "Terminology": st.Page(_page_terminology, title="Terminology", url_path="terminology"),
}
_pg = st.navigation(list(_PAGES.values()), position="hidden")


# ── Masthead + top nav ──
page = render_masthead_and_nav(_pg.title)
if page != _pg.title:
    st.switch_page(_PAGES[page])


# ── Sidebar: status summary ──
# Only the latest report's snapshot is needed here — load it lazily rather than
# parsing every report just to read one signal_counts block.
_report_dates = list_report_dates()
_latest_date = _report_dates[-1] if _report_dates else "—"
_latest_rpt = load_report(_latest_date) if _report_dates else {}

# ── Body-level refresh row: removed in the 2026-07-24 density pass ──
# It cost ~62px directly under the nav on every page and duplicated two things
# that already exist: the masthead's right block carries the date ("Last close
# …"), and the sidebar carries "↻ Refresh Data". Its original reason — that the
# sidebar was unreachable on narrow viewports — no longer holds: theme.css
# force-pins the sidebar-expand chip visible at every width (see the
# stExpandSidebarButton block), so the sidebar refresh is always reachable.
_sig_counts = (_latest_rpt.get("portfolio_snapshot") or {}).get("signal_counts") or {}

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
# clock_today() == date.today() in production (TEST_DATE unset); the visual-
# regression harness sets TEST_DATE to freeze this today-anchored default range,
# which drives the date-filtered pages' content (keeps pixel baselines stable).
_default_end = clock_today()
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

if st.sidebar.button(
    "↻ Refresh Data",
    help="Clear the data cache and refetch reports + live prices. Same action as "
         "the ↻ Refresh button in the main column (surfaced there for narrow "
         "viewports where the sidebar is collapsed).",
):
    st.cache_data.clear()
    st.rerun()


# ── Run the active page ──
_pg.run()
