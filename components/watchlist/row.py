"""Watchlist single-row HTML builder.

``render_ticker_details_html`` builds one ``<details>`` block: the row as
``<summary>``, writeup + drill-down as the expandable body. Pure HTML — no
Streamlit calls. Drives the click-to-expand watchlist grid in
``components.watchlist.watchlist``.
"""
from __future__ import annotations

from components.watchlist.drilldown import render_drilldown_detail_html
from lib.catalog import CLUSTER_MAP
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _delta_class,
    _escape_attr,
    _escape_dollars,
    _fmt_num,
    _sign,
    _writeup_for_render,
    display_ticker,
    rr_display,
)
from lib.pills import _signal_pill_html


def _pct_cell(value, decimals: int) -> str:
    """Signed percent for a summary cell, or a bare '—' when missing.

    ``_fmt_num(None)`` already yields the em-dash; appending the unit
    unconditionally printed "—%" for absent values (UX review 2026-07-07).
    """
    if value is None:
        return "—"
    return f"{_sign(value)}{_fmt_num(value, decimals)}%"


def render_ticker_details_html(tk: str, d: dict, signal_changed: bool = False,
                               earnings_hist=None) -> str:
    """Build a complete <details> block: row as summary, writeup+drilldown as body.

    ``signal_changed=True`` adds ``data-signal-changed="true"`` to the
    ``<details>`` element so the CSS first-mount signal-flash keyframe can
    target it (gated by ``.watchlist-route[data-first-mount="true"]``).

    ``earnings_hist`` (optional) is passed straight through to the drill-down for
    the quarter-on-quarter earnings-history table.
    """
    sig = d.get("signal", "HOLD")
    display_tk = _escape_dollars(display_ticker(tk))
    ccy = d.get("currency", "USD")
    pfx = _ccy_prefix(ccy)
    dec = _ccy_decimals(ccy)
    price = d.get("price")
    chg = d.get("chg_pct")
    m1 = d.get("1mo_pct")
    vs50 = d.get("vs_sma50_pct")
    rsi = d.get("rsi_14")
    rr_label, _, rr_adjusted = rr_display(d.get("risk_reward"))
    # Dense table: show the tight-stop-corrected ratio (matches the action card
    # + drilldown); a hover title carries the raw headline for the few adjusted
    # names, since there's no room for an inline marker (UX-BR-2).
    _rr_raw = (d.get("risk_reward") or {}).get("ratio_label", "")
    rr_title = f' title="tight-stop adjusted (raw {_escape_attr(_rr_raw)})"' if rr_adjusted else ""
    # PRE/POST tag when the live overlay swapped in an extended-hours print
    # (overlay_live sets live_session only in that case).
    session = d.get("live_session")
    ext_tag = f'<span class="ext-tag">{_escape_attr(session)}</span>' if session else ""

    summary = (
        '<summary>'
        f'<div style="font-weight:600;color:var(--ink);">{display_tk}</div>'
        f'<div class="name">{CLUSTER_MAP.get(tk, "")}</div>'
        f'<div>{_signal_pill_html(sig)}</div>'
        f'<div style="text-align:right;">'
        f'{f"{pfx}{_fmt_num(price, dec)}" if price is not None else "—"}'
        f'<div class="{_delta_class(chg)}" style="font-size:10.5px;">'
        f'{_pct_cell(chg, 2)}{ext_tag}</div></div>'
        f'<div class="{_delta_class(m1)}" style="text-align:right;">'
        f'{_pct_cell(m1, 1)}</div>'
        f'<div style="text-align:right;">{_pct_cell(vs50, 1)}</div>'
        f'<div style="text-align:right;">{_fmt_num(rsi, 0)}</div>'
        f'<div style="text-align:right;"{rr_title}>{rr_label or "—"}</div>'
        '</summary>'
    )

    wu = _writeup_for_render(d)
    body_parts: list[str] = []
    if wu["entry_block"]:
        # F2 (2026-07-18, reader eval): prefer the pipeline's plain-language
        # entry_block_reader (top-level field, present from 2026-07-18 on);
        # older reports fall back to the raw rule string. The raw string
        # rides the title attr for grep-ability/hover.
        reader_text = d.get("entry_block_reader") or wu["entry_block"]
        body_parts.append(
            f'<div class="dd-entry-block" '
            f'title="{_escape_attr(wu["entry_block"])}">ENTRY BLOCK · '
            f'{_escape_dollars(reader_text)}</div>'
        )
    if wu["headline"]:
        body_parts.append(
            f'<div class="dd-headline">{_escape_dollars(wu["headline"])}</div>'
        )
    delta = wu.get("prior_period_delta_narrative")
    if delta:
        body_parts.append(
            f'<div class="dd-whatdo" style="opacity:0.85;font-style:italic;">{_escape_dollars(delta)}</div>'
        )
    if wu["what_to_do"]:
        body_parts.append(
            f'<div class="dd-whatdo">{_escape_dollars(wu["what_to_do"])}</div>'
        )
    body_parts.append(render_drilldown_detail_html(tk, d, earnings_hist=earnings_hist))
    body = f'<div class="tk-drilldown">{"".join(body_parts)}</div>'

    changed_attr = ' data-signal-changed="true"' if signal_changed else ''
    return (
        f'<details class="tk-details" data-signal="{_escape_attr(sig)}"{changed_attr}>'
        f'{summary}{body}</details>'
    )
