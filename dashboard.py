"""MarketReport Analytics Dashboard.

Run with: streamlit run dashboard.py

Slim orchestrator — page-level UI lives in ``components/``. This module owns:
- ``st.set_page_config`` + theme CSS injection
- the page functions + ``st.navigation`` registry (real URL per page)
- the masthead/nav call (returns the selected page title)
- sidebar controls (status block, density, live-prices toggle, refresh)
- ``_pg.run()`` dispatch at the bottom

Information only since 2026-10-01 (MarketReport spec
2026-10-01-info-only-watchlist, O6 / O7; tag ``pre-label-removal``): no page
renders a signal label for any report date. The Tracker and Review pages, the
sidebar's signal dots, legend and date-range filter went with the labels.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

# The Briefing page is the pulse strip, the daily briefing card and the market
# read (2026-09-29). The signal blocks (stance band, changes ribbon, clusters,
# action card) and the model-written ones (active risks, macro note) were
# removed once the report LLM went off on 09-28; the calendar folded into the
# briefing card's Week ahead + Upcoming events.
from components.briefing import render_pulse
from components.briefing.daily_briefing import briefing_card_html
from components.briefing.market_read import market_read_card_html
from components.masthead import render_masthead_and_nav
from components.watchlist import render_watchlist
from lib.cards import data_health_banners_html, render_section_head
from lib.data_loader import (
    list_report_dates,
    load_briefings,
    load_earnings_map,
    load_market_reads,
    load_report,
    load_text_asset,
)
from lib.pills import _render_live_caption
from lib.state import init_session_state, mark_mounted
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
# The Watchlist's first-mount signal flash went with the labels (2026-10-01);
# nothing reads has_mounted now, but the flag stays flipped early so a future
# one-shot animation cannot re-fire after an early st.stop() in a page branch.
mark_mounted()


# ════════════════════════════════════════════
# Page bodies. Each runs via st.navigation → _pg.run() at the bottom of this
# script, AFTER the sidebar has assigned LIVE_PRICES — the functions read that
# module global at call time.
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

        # Data-health banners — degraded coverage, a zero-news run — so the page
        # carries a visible trust caveat. Silent on clean days.
        _banners = data_health_banners_html(report.get("meta"))
        if _banners:
            st.markdown(_banners, unsafe_allow_html=True)

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

        sub_label = "The whole book, facts only · click any row for the detail"
        if not _is_latest:
            sub_label += f" · viewing {selected_date}"
        render_section_head("The Watchlist", sub_label, masthead=True)
        _banners = data_health_banners_html(report.get("meta"))
        if _banners:
            st.markdown(_banners, unsafe_allow_html=True)
        _render_live_caption(_live, LIVE_PRICES and _is_latest)
        render_pulse(benchmarks)
        # Every report date renders the same facts-only grid: a report that
        # still carries signal labels in its JSON (to the pipeline cutover)
        # shows exactly what a label-free one does (spec O6).
        render_watchlist(watchlist,
                         report_date=(report.get("meta") or {}).get("report_date"))

    _render_watchlist_body()


# Tabs removed 2026-09-29: Scenario Log (model-written scenario odds, no new data
# since the report LLM went off on 09-28), Pipeline Stats (DeepSeek tokens and
# cost, all zero since 09-28 — restore from git if the LLM flag is turned back
# on) and Report Comparison (a signal-change view). The Clusters and
# Fundamentals tabs went on 2026-07-24; their Briefing cards on 2026-09-29.
# The Signal Tracker and Review pages went on 2026-10-01 with the labels
# (MarketReport spec 2026-10-01-info-only-watchlist, O7; tag pre-label-removal
# restores them).


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
    "Terminology": st.Page(_page_terminology, title="Terminology", url_path="terminology"),
}
_pg = st.navigation(list(_PAGES.values()), position="hidden")


# ── Masthead + top nav ──
page = render_masthead_and_nav(_pg.title)
if page != _pg.title:
    st.switch_page(_PAGES[page])


# ── Sidebar: status summary ──
# Only the latest report is needed here — load it lazily rather than parsing
# every report. The ticker count is the latest watchlist's own length (it used
# to be the sum of the signal counts; the signal dots, the signal legend and the
# date-range filter that fed only the Tracker went on 2026-10-01).
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

_status_html = (
    '<div class="sidebar-status">'
    '<div class="status-row">'
    '<span class="status-label">Latest report</span>'
    f'<span class="status-value">{_latest_date}</span></div>'
    '<div class="status-row">'
    '<span class="status-label">Tickers</span>'
    f'<span class="status-value">{len(_latest_rpt.get("watchlist") or {})}</span></div>'
    '</div>'
)
st.sidebar.markdown(_status_html, unsafe_allow_html=True)

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
