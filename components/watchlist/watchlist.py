"""Watchlist grid renderer — the only Streamlit-touching watchlist module.

``render_watchlist`` emits the whole table (column header, cluster group headers,
one ``<details>`` per ticker) in a single ``st.markdown``, then the method note
and the footer. Every construction decision lives in
``components.watchlist.grid``, which is pure and unit-tested.

Information only since 2026-10-01 (MarketReport spec
2026-10-01-info-only-watchlist, O1 / O6): one fixed order, no ratings, no
signal filter. Every report date renders the same way.
"""
from __future__ import annotations

import streamlit as st

from components.watchlist.grid import (
    build_grid_html,
    footer_html,
    method_note_html,
    ordered_groups,
)
from components.watchlist.row import render_ticker_details_html
from lib.data_loader import load_earnings_map


def render_watchlist(watchlist: dict, report_date: str | None = None) -> None:
    """The whole book in its fixed order, then the footnotes.

    ``report_date`` (the report's ``meta.report_date``) dates the Earnings
    column on reports that carry only a day count.
    """
    groups = ordered_groups(watchlist)

    # The page's only statement of its own ordering. On a dense table a reader
    # otherwise cannot tell whether row order means anything.
    st.markdown(
        '<div class="tk-sortline">Grouped by cluster, largest first · names A–Z '
        '· the same order every day</div>',
        unsafe_allow_html=True,
    )

    # Quarter-on-quarter earnings history (separate CSV export) → per-ticker
    # records, newest quarter first; missing file → the drawer's history half
    # stays silent.
    eh_map = load_earnings_map()          # CSV + the sourced revenue backfill (2026-09-29)

    # ONE st.markdown for the whole table: a div opened in one st.markdown and
    # closed in another does not wrap sibling Streamlit blocks (the browser
    # auto-closes it), and .tk-scroll must genuinely contain the rows so the
    # fixed-column grid can swipe horizontally on phones.
    st.markdown(
        build_grid_html(groups, eh_map, render_ticker_details_html, report_date=report_date),
        unsafe_allow_html=True,
    )
    st.markdown(method_note_html(), unsafe_allow_html=True)
    st.markdown(footer_html(sum(len(rows) for _, rows in groups), len(groups)),
                unsafe_allow_html=True)
