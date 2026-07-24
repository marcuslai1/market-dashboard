"""Briefing · Changes-since-last-report ribbon.

Renders a one-row ribbon showing every watchlist ticker whose signal moved
between the prior report and today, plus an optional expander with the
rationale for each move. Extracted from dashboard.py during the Day-2
modularization pass.
"""
from __future__ import annotations

import streamlit as st

from lib.catalog import SIGNAL_BULLISHNESS
from lib.formatters import _escape_dollars, _writeup_for_render, display_ticker
from lib.pills import _signal_pill_html


def render_changes(today_wl: dict, prev_wl: dict) -> None:
    if not prev_wl:
        return
    items = []
    rationales: dict[str, str] = {}
    for tk in sorted(set(today_wl) | set(prev_wl)):
        old = prev_wl.get(tk, {}).get("signal", "—")
        new = today_wl.get(tk, {}).get("signal", "—")
        if old == new or new == "—" or old == "—":
            continue
        direction = "up" if SIGNAL_BULLISHNESS.get(new, 0) > SIGNAL_BULLISHNESS.get(old, 0) else "down"
        # Direction arrow uses the price-delta up/down palette, not a signal hue.
        arrow_color = "var(--up)" if direction == "up" else "var(--down)"
        display_tk = display_ticker(tk)
        items.append(
            f'<span style="display:inline-flex;align-items:center;gap:8px;">'
            f'<strong style="color:var(--ink);">{_escape_dollars(display_tk)}</strong>'
            f'{_signal_pill_html(old, small=True)}'
            f'<span style="color:{arrow_color};font-weight:700;">'
            f'{"↑" if direction == "up" else "↓"}</span>'
            f'{_signal_pill_html(new, small=True)}'
            f'</span>'
        )
        wu = _writeup_for_render(today_wl.get(tk, {}))
        note = wu["headline"] or (wu["what_to_do"] or "").split(". ", 1)[0]
        if note:
            rationales[display_tk] = note
    if not items:
        return
    body = '<span class="clabel">Since yesterday</span>' + " ".join(items)
    st.markdown(f'<div class="changes-ribbon">{body}</div>', unsafe_allow_html=True)
    if rationales:
        with st.expander("Why the signals moved", expanded=False):
            for tk, txt in rationales.items():
                st.markdown(f"**{tk}** — {_escape_dollars(txt)}")
