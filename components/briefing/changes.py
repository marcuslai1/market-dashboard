"""Briefing · Overnight signal-change chips.

Design revision 2026-07-24 (ref docs/briefing.jpg): a verdict-first lead
("▼ 10 downgrades — all to CAUTION") followed by one compact chip per name —
a seamless row, not a bordered ribbon. The old "Why the signals moved" expander
is gone: the per-name rationale already lives on the Watchlist.
"""
from __future__ import annotations

import streamlit as st

from lib.catalog import SIGNAL_BULLISHNESS
from lib.formatters import _escape_dollars, display_ticker
from lib.pills import signal_text_color


def _lead_label(ups: list, downs: list) -> str:
    """Verdict-first summary of the night's moves.

    "10 downgrades — all to CAUTION" when they land on one signal; otherwise
    just the counts, and both arms when the night moved in both directions.
    """
    def _all_to(moves: list) -> str:
        targets = {m[2] for m in moves}
        return f" — all to {targets.pop()}" if len(targets) == 1 else ""

    parts = []
    if downs:
        word = "downgrade" if len(downs) == 1 else "downgrades"
        parts.append(
            f'<span class="chg-lead-down">▼ {len(downs)} {word}'
            f'{_all_to(downs) if not ups else ""}</span>'
        )
    if ups:
        word = "upgrade" if len(ups) == 1 else "upgrades"
        parts.append(
            f'<span class="chg-lead-up">▲ {len(ups)} {word}'
            f'{_all_to(ups) if not downs else ""}</span>'
        )
    return '<span class="chg-lead">' + " · ".join(parts) + "</span>"


def render_changes(today_wl: dict, prev_wl: dict) -> None:
    """Emit the overnight signal-change row. Silent on the first report of a
    corpus (no prior) and on days when nothing moved."""
    if not prev_wl:
        return
    moves = []
    for tk in sorted(set(today_wl) | set(prev_wl)):
        old = prev_wl.get(tk, {}).get("signal", "—")
        new = today_wl.get(tk, {}).get("signal", "—")
        # Tickers that newly appeared / disappeared aren't analytical moves.
        if old == new or new == "—" or old == "—":
            continue
        direction = (
            "up" if SIGNAL_BULLISHNESS.get(new, 0) > SIGNAL_BULLISHNESS.get(old, 0)
            else "down"
        )
        moves.append((display_ticker(tk), old, new, direction))
    if not moves:
        return

    ups = [m for m in moves if m[3] == "up"]
    downs = [m for m in moves if m[3] == "down"]

    chips = "".join(
        f'<span class="chg-chip" style="border-left-color:{signal_text_color(new)};">'
        f'<b>{_escape_dollars(tk)}</b>'
        f'<span class="chg-sig" style="color:{signal_text_color(new)};">'
        f'{_escape_dollars(new)}</span>'
        f'</span>'
        for tk, _old, new, _dir in moves
    )
    st.markdown(
        f'<div class="changes-row">{_lead_label(ups, downs)}{chips}</div>',
        unsafe_allow_html=True,
    )
