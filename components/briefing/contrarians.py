"""Contrarian Candidates — oversold names with a recovery thesis."""
from __future__ import annotations

import streamlit as st

from lib.cards import render_section_head
from lib.formatters import _escape_dollars, _fmt_num, display_ticker


def render_contrarian_candidates(contrarians: list) -> None:
    """Render `contrarian_candidates` (RSI < 38 oversold names with thesis).

    The pipeline emits these only when at least one watchlist or near-watchlist
    name is genuinely oversold and has a coherent recovery thesis. Empty most
    days; when it fires, surface it prominently so the contrarian setup isn't
    lost in the wall of CAUTION.
    """
    if not contrarians:
        return
    render_section_head(
        "Contrarian Candidates",
        "Oversold names with a setup, not just a falling knife",
    )
    for c in contrarians:
        if not isinstance(c, dict):
            continue
        ticker = c.get("ticker", "—")
        display = _escape_dollars(display_ticker(ticker))
        rsi = c.get("rsi")
        rsi_str = f"RSI {_fmt_num(rsi, 0)}" if rsi is not None else ""
        thesis = c.get("thesis") or c.get("rationale") or ""
        trigger = c.get("trigger") or c.get("entry_trigger") or ""
        st.markdown(
            f'<div style="border-left:3px solid #22c55e;background:var(--paper-2);'
            f'padding:12px 16px;margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;margin-bottom:6px;">'
            f'<span style="font-family:var(--mono);font-weight:600;'
            f'color:var(--ink);font-size:13px;">{display}</span>'
            f'<span style="font-family:var(--mono);font-size:11px;'
            f'color:var(--ink-3);">{rsi_str}</span>'
            f'</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.55;">'
            f'{_escape_dollars(thesis)}</div>'
            + (
                f'<div style="margin-top:6px;font-family:var(--mono);font-size:11px;'
                f'color:#22c55e;">Trigger · {_escape_dollars(trigger)}</div>'
                if trigger else ""
            )
            + '</div>',
            unsafe_allow_html=True,
        )
