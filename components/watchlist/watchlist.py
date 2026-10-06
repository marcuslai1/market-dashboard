"""Watchlist grid renderer — the only Streamlit-touching watchlist module.

``render_watchlist`` emits the whole table (column header, cluster group headers,
one ``<details>`` per ticker) in a single ``st.markdown``, then the method note
and the footer. Every construction decision lives in
``components.watchlist.grid``, which is pure and unit-tested.

Information only since 2026-10-01 (MarketReport spec
2026-10-01-info-only-watchlist, O1 / O6): one fixed order, no ratings, no
signal filter. Every report date renders the same way.

Experimental since 2026-10-06 (owner; MarketReport PIPELINE_FEATURES §125): an
order control above the table can sort the rows by sales growth instead
(``components.watchlist.growth``). The default stays the fixed cluster order, and
the control only appears when ``data/growth.json`` holds figures.
"""
from __future__ import annotations

import streamlit as st

from components.watchlist.company_profile import profiles_by_key
from components.watchlist.grid import (
    build_grid_html,
    footer_html,
    method_note_html,
    ordered_groups,
)
from components.watchlist.growth import (
    ORDER_CLUSTERS,
    ORDERS,
    SORT_FIELD,
    growth_by_key,
    sorted_footer_html,
    sorted_grid_html,
    sorted_rows,
    sortline_html,
)
from components.watchlist.row import render_ticker_details_html
from lib.data_loader import (
    load_company_profiles,
    load_earnings_map,
    load_growth,
    load_price_history,
)


def render_watchlist(watchlist: dict, report_date: str | None = None) -> None:
    """The whole book in its fixed order (or, on request, sorted by sales growth),
    then the footnotes.

    ``report_date`` (the report's ``meta.report_date``) dates the Earnings
    column on reports that carry only a day count.
    """
    # Sales-growth figures (MarketReport growth_types.json, numbers only) → the
    # experimental sort; missing file → no control, the fixed order only.
    growth_data = load_growth()
    growth_map = growth_by_key(growth_data)
    order = ORDER_CLUSTERS
    if growth_map:
        order = st.radio("Order", ORDERS, index=0, horizontal=True, key="wl_order")
    field = SORT_FIELD.get(order)

    if not field:
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
    # Daily price + 50/200-day averages per name (market_data.csv) → the
    # drill-down's price chart; missing file → the chart stays silent.
    price_map = load_price_history()
    # Facts-only company cards (MarketReport company_profiles.json) → the
    # drill-down's Company profile drawer; missing file → no drawer.
    profile_map = profiles_by_key(load_company_profiles())

    if field:
        rows = sorted_rows(watchlist, growth_map, field)
        st.markdown(sortline_html(field, (growth_data.get("_meta") or {}).get("as_of")),
                    unsafe_allow_html=True)
        # ONE st.markdown for the whole table, as below.
        st.markdown(
            sorted_grid_html(rows, growth_map, field, eh_map, render_ticker_details_html,
                             report_date=report_date, price_map=price_map,
                             profile_map=profile_map),
            unsafe_allow_html=True,
        )
        st.markdown(method_note_html(), unsafe_allow_html=True)
        st.markdown(sorted_footer_html(len(rows)), unsafe_allow_html=True)
        return

    groups = ordered_groups(watchlist)

    # ONE st.markdown for the whole table: a div opened in one st.markdown and
    # closed in another does not wrap sibling Streamlit blocks (the browser
    # auto-closes it), and .tk-scroll must genuinely contain the rows so the
    # fixed-column grid can swipe horizontally on phones.
    st.markdown(
        build_grid_html(groups, eh_map, render_ticker_details_html, report_date=report_date,
                        price_map=price_map, profile_map=profile_map),
        unsafe_allow_html=True,
    )
    st.markdown(method_note_html(), unsafe_allow_html=True)
    st.markdown(footer_html(sum(len(rows) for _, rows in groups), len(groups)),
                unsafe_allow_html=True)
