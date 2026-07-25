"""Watchlist single-row HTML builder.

``render_ticker_details_html`` builds one ``<details>`` block: the row as
``<summary>``, writeup + drill-down as the expandable body. Pure HTML — no
Streamlit calls. Drives the click-to-expand watchlist grid in
``components.watchlist.watchlist``.
"""
from __future__ import annotations

import re

from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.gauge import extension_gauge_html
from lib.catalog import CLUSTER_MAP
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _delta_class,
    _escape_attr,
    _escape_dollars,
    _fmt_num,
    _sign,
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


def _rr_cell(label: str, adjusted: bool) -> tuple[str, str]:
    """``(value, sub)`` for the R:R cell.

    Two cases need a sub-line. An *adjusted* ratio says so, because the visible
    figure is the tight-stop-corrected one and that is the difference between a
    1.5:1 that clears the gate and one that doesn't.

    And a *non-ratio* label — the pipeline's "N/A -- at or below invalidation"
    for a name sitting under its own stop — is a sentence, which wrapped to three
    lines in a 96px column and made its row visibly taller than its neighbours.
    On a scanning surface uniform row height is what lets the eye run a column,
    so the value collapses to "n/a" and the reason drops to the sub-line. Not a
    hover title: a title is invisible on touch, which is the bug this cell's
    other half exists to fix.
    """
    if not label:
        return "—", ""
    if ":" in label:
        return label, "tight-stop adj." if adjusted else ""
    # "N/A -- reason" / "N/A — reason" / bare "N/A"
    reason = re.split(r"\s*(?:--|—|-)\s*", label, maxsplit=1)
    return "n/a", reason[1].strip() if len(reason) > 1 else ""


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

    # Steel, not a signal colour: "something changed today" is a structural fact
    # about the row, not a rating — and it must not compete with the pill sitting
    # 100px to its right. Same steel as the ● Changed filter chip.
    changed_dot = (
        '<span class="tk-changed" '
        'title="Signal changed since the prior report"></span>'
        if signal_changed else ''
    )
    # The threshold is what matters, not the value, so the colour does the
    # interpreting. Terracotta, not red: an overbought reading is a data
    # condition — 77 on a name that happens to carry CAUTION is not a rating.
    rsi_zone = (
        "hot" if rsi is not None and rsi >= 70
        else "cold" if rsi is not None and rsi <= 30
        else ""
    )
    rr_val, rr_sub_text = _rr_cell(rr_label, rr_adjusted)
    rr_sub = (f'<div class="tk-rr-sub">{_escape_dollars(rr_sub_text)}</div>'
              if rr_sub_text else '')

    summary = (
        '<summary>'
        f'<div class="tk-tick">'
        f'<div class="tk-tick-id"><span class="tk-tick-tk">{display_tk}</span>'
        f'{changed_dot}</div>'
        f'<div class="tk-tick-cluster">{CLUSTER_MAP.get(tk, "")}</div></div>'
        f'<div>{_signal_pill_html(sig)}</div>'
        f'<div class="tk-last">'
        f'<div class="tk-last-px">'
        f'{f"{pfx}{_fmt_num(price, dec)}" if price is not None else "—"}</div>'
        f'<div class="tk-last-chg {_delta_class(chg)}">'
        f'{_pct_cell(chg, 2)}{ext_tag}</div></div>'
        f'<div class="tk-1mo {_delta_class(m1)}">{_pct_cell(m1, 1)}</div>'
        f'{extension_gauge_html(vs50)}'
        f'<div class="tk-rsi" data-zone="{rsi_zone}">{_fmt_num(rsi, 0)}</div>'
        f'<div class="tk-rr"{rr_title}>'
        f'<div class="tk-rr-val">{rr_val}</div>{rr_sub}</div>'
        '</summary>'
    )

    # The writeup used to be assembled here and the drill-down appended beneath
    # it. It now lives inside the drill-down card, where the reading order can be
    # enforced end-to-end (entry block before verdict before instruction) and the
    # whole body carries one signal rail — see components/watchlist/drilldown.py.
    body = (
        '<div class="tk-drilldown">'
        f'{render_drilldown_detail_html(tk, d, earnings_hist=earnings_hist)}'
        '</div>'
    )

    changed_attr = ' data-signal-changed="true"' if signal_changed else ''
    return (
        f'<details class="tk-details" data-signal="{_escape_attr(sig)}"{changed_attr}>'
        f'{summary}{body}</details>'
    )
