"""Watchlist single-row HTML builder.

``render_ticker_details_html`` builds one ``<details>`` block: the row as
``<summary>``, the drill-down as the expandable body. Pure HTML — no Streamlit
calls. Drives the click-to-expand watchlist grid in
``components.watchlist.watchlist``.

Seven cells, facts only (MarketReport spec 2026-10-01-info-only-watchlist §8,
O6): Ticker (+ cluster) · Last · Δ · 5 d · 1 mo · vs 50-day · RSI · Earnings.
The signal pill, "day N", the changed dot, the R:R column and the per-signal
rail / tint went on 2026-10-01 (tag ``pre-label-removal``). A report that still
carries those keys renders the same row as one that does not.
"""
from __future__ import annotations

from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.gauge import extension_gauge_html
from components.watchlist.grid import cluster_of
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _delta_class,
    _escape_attr,
    _escape_dollars,
    _fmt_num,
    _sign,
    display_ticker,
)
from lib.next_earnings import days_phrase, next_earnings, short_date


def _pct_cell(value, decimals: int) -> str:
    """Signed percent for a summary cell, or a bare '—' when missing.

    ``_fmt_num(None)`` already yields the em-dash; appending the unit
    unconditionally printed "—%" for absent values (UX review 2026-07-07).
    """
    if value is None:
        return "—"
    return f"{_sign(value)}{_fmt_num(value, decimals)}%"


def earnings_cell_html(d: dict, report_date: str | None) -> str:
    """Date over the distance to it — ``17 Nov`` / ``in 47 d``. Neutral ink at
    every distance: a report date is a fact, not a warning. A name with no date
    on file keeps its dash in the table's column and marks the cell
    (``data-none``), so the two-line phone row can leave the empty cell out
    (layout review 2026-11-24, P2)."""
    ne = next_earnings(d, report_date)
    if ne is None:
        return '<div class="tk-earn" data-none="1"><div class="tk-earn-date">—</div></div>'
    top = "n/a" if ne.when is None else short_date(ne.when)
    sub = days_phrase(ne)
    return (
        '<div class="tk-earn">'
        f'<div class="tk-earn-date">{top}</div>'
        + (f'<div class="tk-earn-sub">{sub}</div>' if sub else "")
        + '</div>'
    )


def render_ticker_details_html(tk: str, d: dict, earnings_hist=None,
                               report_date: str | None = None,
                               price_hist=None, profile=None,
                               growth_html: str = "") -> str:
    """Build a complete <details> block: row as summary, drill-down as body.

    ``earnings_hist`` (optional) is passed straight through to the drill-down for
    the quarter-on-quarter earnings-history table. ``report_date`` (the report's
    ``meta.report_date``) dates the Earnings cell on reports that carry only a
    day count. ``price_hist`` (optional) feeds the drill-down's price chart,
    ``profile`` (optional) its Company profile drawer. ``growth_html`` (the
    experimental growth sort's line, ``components.watchlist.growth``) is an eighth
    child of the summary that spans the row under its seven cells; the default
    order passes none.
    """
    display_tk = _escape_dollars(display_ticker(tk))
    ccy = d.get("currency", "USD")
    pfx = _ccy_prefix(ccy)
    dec = _ccy_decimals(ccy)
    price = d.get("price")
    chg = d.get("chg_pct")
    d5 = d.get("5d_pct")
    m1 = d.get("1mo_pct")
    # PRE/POST tag when the live overlay swapped in an extended-hours print
    # (overlay_live sets live_session only in that case).
    session = d.get("live_session")
    ext_tag = f'<span class="ext-tag">{_escape_attr(session)}</span>' if session else ""

    summary = (
        '<summary>'
        '<div class="tk-tick">'
        f'<div class="tk-tick-id"><span class="tk-tick-tk">{display_tk}</span></div>'
        f'<div class="tk-tick-cluster">{_escape_dollars(cluster_of(tk, d))}</div></div>'
        '<div class="tk-last">'
        '<div class="tk-last-px">'
        f'{f"{pfx}{_fmt_num(price, dec)}" if price is not None else "—"}</div>'
        f'<div class="tk-last-chg {_delta_class(chg)}">'
        f'{_pct_cell(chg, 2)}{ext_tag}</div></div>'
        f'<div class="tk-5d {_delta_class(d5)}">{_pct_cell(d5, 1)}</div>'
        f'<div class="tk-1mo {_delta_class(m1)}">{_pct_cell(m1, 1)}</div>'
        f'{extension_gauge_html(d.get("vs_sma50_pct"))}'
        f'<div class="tk-rsi">{_fmt_num(d.get("rsi_14"), 0)}</div>'
        f'{earnings_cell_html(d, report_date)}'
        f'{growth_html}'
        '</summary>'
    )
    body = (
        '<div class="tk-drilldown">'
        f'{render_drilldown_detail_html(tk, d, earnings_hist=earnings_hist, report_date=report_date, price_hist=price_hist, profile=profile)}'
        '</div>'
    )
    # No shared ``name`` on the rows, on purpose. The layout review of 2026-11-24 (P3)
    # asked for one row open at a time, which a shared name gives without script. It
    # was built and measured, then left out: when the row that closes sits above the
    # one just tapped, the page loses that panel's height and the tapped row jumps
    # (277px from the top to 0, its panel's start scrolled out of view, in Chrome at
    # 768 and 1440px; a browser without scroll anchoring would do it every time).
    # Holding the page still needs script, which this page does not use.
    return f'<details class="tk-details">{summary}{body}</details>'
