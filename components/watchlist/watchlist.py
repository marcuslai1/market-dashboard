"""Watchlist grid renderer.

``render_watchlist`` emits the table header and one ``<details>`` block per
ticker, sorted by signal rank then 1-month return. HOLD tickers are still
listed but their drill-down body collapses to nothing actionable.
"""
from __future__ import annotations

import streamlit as st

from lib.catalog import RETIRED_TICKERS

from components.watchlist.row import render_ticker_details_html


def render_watchlist(
    watchlist: dict, changed_tickers: set[str] | None = None
) -> None:
    """Editorial watchlist with click-to-expand drill-down per ticker.

    HOLD tickers do NOT get an expander (no actionable content).

    ``changed_tickers`` is the set of tickers whose signal differs from the
    prior report; row.py emits ``data-signal-changed="true"`` for those so
    CSS can flash them on first mount.
    """
    changed_set = changed_tickers or set()
    rank = {"BUY": 0, "ACCUMULATE": 1, "WATCH": 2, "HOLD": 3, "CAUTION": 4}
    items = sorted(
        [(tk, d) for tk, d in watchlist.items() if tk not in RETIRED_TICKERS],
        key=lambda x: (
            rank.get(x[1].get("signal", "HOLD"), 5),
            -(x[1].get("1mo_pct") or 0),
        ),
    )
    # The whole table (header + every row) is emitted in ONE st.markdown so the
    # .tk-scroll wrapper genuinely contains the rows in the DOM — a div opened in
    # one st.markdown and closed in another does NOT wrap sibling Streamlit
    # blocks (the browser auto-closes it). .tk-scroll lets the fixed-column grid
    # swipe horizontally on phones instead of clipping columns off the edge.
    head = (
        '<div class="tk-row head">'
        '<div>Ticker</div><div>Name</div><div>Signal</div>'
        '<div style="text-align:right;">Last · Δ</div>'
        '<div style="text-align:right;">1mo</div>'
        '<div style="text-align:right;">vs 50-day</div>'
        '<div style="text-align:right;">RSI</div>'
        '<div style="text-align:right;">R:R</div>'
        '</div>'
    )
    rows = "".join(
        render_ticker_details_html(tk, d, signal_changed=(tk in changed_set))
        for tk, d in items
    )
    st.markdown(
        f'<div class="tk-scroll">{head}{rows}</div>',
        unsafe_allow_html=True,
    )
