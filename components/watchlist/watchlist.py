"""Watchlist grid renderer — the only Streamlit-touching watchlist module.

``render_watchlist`` emits the Show chips, then the whole table (column header,
group headers, one ``<details>`` per ticker) in a single ``st.markdown``, then
the method note and the legend footer. Every construction decision lives in
``components.watchlist.grid``, which is pure and unit-tested.
"""
from __future__ import annotations

import streamlit as st

from components.watchlist.grid import (
    FILTER_ALL,
    build_filter_options,
    build_grid_html,
    filter_items,
    footer_html,
    method_note_html,
)
from components.watchlist.row import render_ticker_details_html
from lib.catalog import RETIRED_TICKERS, SIGNAL_SORT_RANK
from lib.data_loader import load_earnings_history


def render_watchlist(
    watchlist: dict, changed_tickers: set[str] | None = None
) -> None:
    """The whole book: filter chips, the dense grid, the footnotes.

    ``changed_tickers`` is the set of tickers whose signal differs from the prior
    report. They drive both the persistent ● Changed chip and the steel dot on
    the row. In the shipped version this information lived only in a first-mount
    CSS flash, so it expired seconds after you landed — promoting it to a filter
    turns "what moved today" from something you must catch into something you can
    ask for.

    ``st.pills`` rather than a CSS-only filter on purpose: the page body is an
    ``st.fragment(run_every=60)`` for live prices, so DOM-only filter state would
    silently reset to All once a minute. Session state survives the rerun.
    """
    changed_set = changed_tickers or set()
    _rank_last = len(SIGNAL_SORT_RANK)
    items = sorted(
        [(tk, d) for tk, d in watchlist.items() if tk not in RETIRED_TICKERS],
        key=lambda x: (
            SIGNAL_SORT_RANK.get(x[1].get("signal", "HOLD"), _rank_last),
            -(x[1].get("1mo_pct") or 0),
        ),
    )

    keys, labels = build_filter_options(items, changed_set)
    selected = st.pills(
        "Show",
        keys,
        selection_mode="single",
        default=FILTER_ALL,
        format_func=lambda k: labels[k],
        key="wl_filter",
    )
    # A chip clicked off returns None; the whole book is the right fallback.
    shown = filter_items(items, changed_set, selected)

    # The page's only statement of its own ordering AND its survivorship-bias
    # exclusion. On a dense table this matters: without it a reader cannot tell
    # whether row order means anything.
    st.markdown(
        '<div class="tk-sortline">Grouped by signal · then by one-month return '
        '· retired names excluded</div>',
        unsafe_allow_html=True,
    )

    # Quarter-on-quarter earnings history (separate CSV export) → per-ticker
    # records, newest quarter first (as exported). groupby(sort=False) preserves
    # that order; missing file → empty map → the drawer stays silent.
    eh_df = load_earnings_history()
    eh_map: dict[str, list] = {}
    if not eh_df.empty and "ticker" in eh_df.columns:
        for tkey, grp in eh_df.groupby("ticker", sort=False):
            eh_map[tkey] = grp.to_dict("records")

    # ONE st.markdown for the whole table: a div opened in one st.markdown and
    # closed in another does not wrap sibling Streamlit blocks (the browser
    # auto-closes it), and .tk-scroll must genuinely contain the rows so the
    # fixed-column grid can swipe horizontally on phones.
    st.markdown(
        build_grid_html(shown, changed_set, eh_map, render_ticker_details_html),
        unsafe_allow_html=True,
    )
    st.markdown(method_note_html(), unsafe_allow_html=True)
    st.markdown(footer_html(len(shown), len(items)), unsafe_allow_html=True)
