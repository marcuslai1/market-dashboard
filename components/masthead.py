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
    "Signal Tracker",
    "Pipeline Stats",
    "Scenario Log",
    "Report Comparison",
    "Terminology",
]


def render_masthead_and_nav() -> str:
    """Render the masthead + top-nav radio. Returns the selected page name."""
    # The masthead renders on every page/rerun but only needs the date list
    # (from filenames) and the latest report's market_date — so it reads dates
    # cheaply and loads just the one report, never the whole corpus.
    dates = list_report_dates()
    latest = dates[-1] if dates else "—"
    first = dates[0] if dates else None
    issue = "—"
    if first:
        try:
            first_d = date.fromisoformat(first)
            last_d = date.fromisoformat(latest)
            issue = f"No. {(last_d - first_d).days + 1}"
        except ValueError:
            pass
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
        f'</div>'
        f'<div class="masthead-strip">'
        f'<span>Issue {issue}</span>'
        f'<span>The Signal Desk</span>'
        f'<span>Updated 11:30 SGT</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="topnav-wrap">', unsafe_allow_html=True)
    page = st.radio(
        "Navigate",
        _NAV_PAGES,
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return page
