"""Briefing · Pulse Tape composite indicator.

Renders the strip of benchmark snapshots (``lib.catalog.PULSE_ORDER``: SPY /
QQQ / VIX / US10Y / SOXX / USD/SGD) at the top of the Briefing and Watchlist.
Extracted from dashboard.py during the Day-2 modularization pass.
"""
from __future__ import annotations

import streamlit as st

from lib.catalog import PULSE_ORDER
from lib.formatters import _delta_class, _escape_attr, _fmt_num, _sign

# Report key -> how the cell names it, and FX levels that need 4 decimals (1.2776).
_DISPLAY = {"USDSGD": "USD/SGD"}
_DECIMALS = {"USDSGD": 4}
# Cells drawn only when the report carries the benchmark: USD/SGD is absent from
# reports before 2026-09-30 and withheld on a day without US-close marks. A core
# benchmark still draws "—" when missing — there the dash reports a failed fetch.
_OPTIONAL = {"USDSGD"}


def render_pulse(benchmarks: dict) -> None:
    cells = ""
    n = 0
    for key, label, inverse in PULSE_ORDER:
        if key in _OPTIONAL and not benchmarks.get(key):
            continue
        n += 1
        b = benchmarks.get(key, {}) or {}
        price = b.get("price")
        chg = b.get("chg_pct")
        decimals = _DECIMALS.get(key, 0 if (price is not None and price > 1000) else 2)
        name = _DISPLAY.get(key, key)
        tone = "flat" if inverse is None else _delta_class(chg, inverse)
        # Screen-reader label: the div-grid carries no table semantics, so give
        # each cell a self-describing name ("SPY S&P 500: 5,800, +0.50%").
        session = b.get("live_session")
        ext_tag = f'<span class="ext-tag">{_escape_attr(session)}</span>' if session else ""
        aria = _escape_attr(
            f"{name} {label}: {_fmt_num(price, decimals)}, "
            f"{_sign(chg)}{_fmt_num(chg, 2)}%"
            + (f" ({session}-market)" if session else "")
        )
        cells += (
            f'<div class="pulse-cell" role="group" aria-label="{aria}">'
            f'<div class="plabel">{name} · {label}</div>'
            f'<div class="pprice">{_fmt_num(price, decimals)}</div>'
            f'<div class="pdelta {tone}">'
            f'{_sign(chg)}{_fmt_num(chg, 2)}%{ext_tag}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div class="pulse-grid" role="group" aria-label="Market pulse — {n} benchmarks" '
        f'style="--pulse-n:{n}">'
        f'{cells}</div>',
        unsafe_allow_html=True,
    )
