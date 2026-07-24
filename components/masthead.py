"""Masthead and top navigation.

`render_masthead_and_nav` draws the editorial brand band at the top of the
page and the top-of-main-area radio that selects the active page. It returns
the selected page name so callers can drive their page-routing chain.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from lib.data_loader import list_report_dates, load_report
from lib.formatters import _escape_dollars

_NAV_PAGES = [
    "Briefing",
    "Watchlist",
    "Clusters",
    "Fundamentals",
    "Signal Tracker",
    "Retrospective",
    "Pipeline Stats",
    "Scenario Log",
    "Report Comparison",
    "Terminology",
]

# Shorter labels shown in the top-nav strip. The st.radio *options* stay the full
# page titles (routing + st.switch_page key on those), but the full labels don't
# all fit on one line at desktop width with the sidebar open — they overflowed by
# ~180px and clipped "Report Comparison" behind a scrollbar. format_func only
# changes the displayed text node, so routing and the folio numerals are untouched.
# "Terminology" is left in full because the Briefing footer cross-references it by
# name ("see the Terminology tab").
_NAV_LABELS = {
    "Signal Tracker": "Tracker",
    "Retrospective": "Review",
    "Pipeline Stats": "Pipeline",
    "Scenario Log": "Scenarios",
    "Report Comparison": "Compare",
}


def render_masthead_and_nav(current: str) -> str:
    """Render the masthead + top-nav radio. Returns the selected page title.

    ``current`` is the active ``st.navigation`` page title. The caller compares
    the returned selection against it and issues ``st.switch_page`` — the radio
    is a mirror of the navigation state, not the state itself.
    """
    # The masthead renders on every page/rerun but only needs the date list
    # (from filenames) and the latest report's market_date — so it reads dates
    # cheaply and loads just the one report, never the whole corpus.
    dates = list_report_dates()
    latest = dates[-1] if dates else "—"
    market_date = _escape_dollars(
        load_report(latest).get("meta", {}).get("market_date", "—")
    )
    try:
        long_date = date.fromisoformat(latest).strftime("%A, %B %d, %Y")
    except ValueError:
        long_date = latest

    st.markdown(
        f'<div class="masthead">'
        f'<div>'
        f'<div class="kicker">Morning Briefing · Signal Intelligence Daily</div>'
        f'<h1 class="title">The <em>Market</em> Report</h1>'
        f'</div>'
        f'<div class="right">'
        f'<div class="date">{long_date}</div>'
        f'<div>Singapore · 11:30 SGT · Last close {market_date}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # The radio mirrors st.navigation. When navigation changed OUTSIDE the
    # radio (deep link, browser back/forward, first load of a pathed URL),
    # resync the widget to the real page. When the change came FROM the radio
    # (user click), leave the widget value alone so the click isn't clobbered —
    # the caller sees selection != current and switches page.
    if st.session_state.get("_nav_last") != current:
        st.session_state.page_nav = current
        st.session_state._nav_last = current

    st.markdown('<div class="topnav-wrap">', unsafe_allow_html=True)
    page = st.radio(
        "Navigate",
        _NAV_PAGES,
        format_func=lambda p: _NAV_LABELS.get(p, p),
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return page
