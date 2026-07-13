"""Briefing · Pulse Tape composite indicator.

Renders the 8-cell strip of benchmark snapshots (SPY / QQQ / VIX / WTI /
Gold / DXY / US10Y / SOXX) below the stance band. Extracted from
dashboard.py during the Day-2 modularization pass.
"""
from __future__ import annotations

import streamlit as st

from lib.catalog import PULSE_ORDER
from lib.formatters import _delta_class, _escape_attr, _fmt_num, _sign


def render_pulse(benchmarks: dict) -> None:
    cells = ""
    for key, label, inverse in PULSE_ORDER:
        b = benchmarks.get(key, {}) or {}
        price = b.get("price")
        chg = b.get("chg_pct")
        decimals = 0 if (price is not None and price > 1000) else 2
        # Screen-reader label: the div-grid carries no table semantics, so give
        # each cell a self-describing name ("SPY S&P 500: 5,800, +0.50%").
        session = b.get("live_session")
        ext_tag = f'<span class="ext-tag">{_escape_attr(session)}</span>' if session else ""
        aria = _escape_attr(
            f"{key} {label}: {_fmt_num(price, decimals)}, "
            f"{_sign(chg)}{_fmt_num(chg, 2)}%"
            + (f" ({session}-market)" if session else "")
        )
        cells += (
            f'<div class="pulse-cell" role="group" aria-label="{aria}">'
            f'<div class="plabel">{key} · {label}</div>'
            f'<div class="pprice">{_fmt_num(price, decimals)}</div>'
            f'<div class="pdelta {_delta_class(chg, inverse)}">'
            f'{_sign(chg)}{_fmt_num(chg, 2)}%{ext_tag}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div class="pulse-grid" role="group" aria-label="Market pulse — 8 benchmarks">'
        f'{cells}</div>',
        unsafe_allow_html=True,
    )
