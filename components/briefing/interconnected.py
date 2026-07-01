"""Interconnected Names — model-selected read-through tickers."""
from __future__ import annotations

import streamlit as st

from lib.cards import render_section_head
from lib.catalog import TICKER_DISPLAY
from lib.formatters import _escape_dollars, _fmt_num, _sign


def render_interconnected(stocks: list) -> None:
    """Render `interconnected` — model-selected read-through tickers outside the watchlist."""
    if not stocks:
        return
    render_section_head(
        "Interconnected Names",
        "Read-throughs outside the watchlist — not buy signals",
    )
    for s in stocks:
        if not isinstance(s, dict):
            continue
        ticker = (s.get("ticker") or "—").upper()
        display = _escape_dollars(TICKER_DISPLAY.get(ticker, ticker))
        name = s.get("name", "")
        reason = s.get("reason") or ""
        entry_note = s.get("entry_note") or ""
        price = s.get("price")
        chg = s.get("chg_pct")
        price_str = ""
        if price is not None:
            chg_color = "#22c55e" if (chg or 0) >= 0 else "#ef4444"
            chg_str = f'<span style="color:{chg_color};margin-left:6px;">{_sign(chg)}{abs(chg or 0):.1f}%</span>' if chg is not None else ""
            price_str = (
                f'<span style="font-family:var(--mono);font-size:11px;color:var(--ink-3);">'
                f'{_fmt_num(price, 2)}{chg_str}</span>'
            )
        st.markdown(
            f'<div style="border-left:3px solid var(--ink-4);background:var(--paper-2);'
            f'padding:12px 16px;margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;margin-bottom:5px;">'
            f'<span style="font-family:var(--mono);font-weight:600;'
            f'color:var(--ink);font-size:13px;">{display}'
            + (f' <span style="color:var(--ink-3);font-weight:400;font-size:11px;">{_escape_dollars(name)}</span>' if name and name != display else "")
            + f'</span>{price_str}</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.55;">'
            f'{_escape_dollars(reason)}</div>'
            + (
                f'<div style="margin-top:6px;font-family:var(--mono);font-size:11px;'
                f'color:var(--ink-3);">Entry note · {_escape_dollars(entry_note)}</div>'
                if entry_note else ""
            )
            + '</div>',
            unsafe_allow_html=True,
        )
