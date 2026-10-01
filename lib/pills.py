"""Small caption helpers for the editorial Briefing / Watchlist surfaces.

The signal pill and its text colours left on 2026-10-01 with the labels
(MarketReport spec 2026-10-01-info-only-watchlist; tag ``pre-label-removal``).
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib.catalog import TONE_COLORS


def _render_live_caption(live: dict, enabled: bool) -> None:
    """Tiny one-line caption above the pulse strip showing live-quote status."""
    if not enabled:
        st.markdown(
            '<div style="font-family:var(--mono);font-size:10.5px;'
            'letter-spacing:0.08em;color:var(--ink-4);text-transform:uppercase;'
            'margin:6px 0 8px;">Snapshot · report-date values</div>',
            unsafe_allow_html=True,
        )
        return
    meta = (live or {}).get("__meta__", {})
    # meta["n_ok"] is already the successful-quote count (computed before the
    # __meta__ key was added), so use it directly — the old `- 1` under-counted
    # by one and flipped the caption to "FETCH FAILED" when exactly one quote
    # succeeded.
    n_ok = max(0, meta.get("n_ok", 0))
    n_total = meta.get("n_total", 0)
    fetched = meta.get("fetched_at", "")
    try:
        ts = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
        when = ts.astimezone().strftime("%H:%M")
    except (ValueError, AttributeError):
        when = "—"
    # A status light for the quote fetch (worked / failed), not a market reading.
    dot = TONE_COLORS["pos"] if n_ok else TONE_COLORS["neg"]
    # Name the US extended session so a Singapore-evening reader knows the US
    # rows are pre/post-market prints, not the regular session.
    session_label = {"PRE": " · PRE-MARKET", "POST": " · AFTER-HOURS"}.get(
        meta.get("session"), ""
    )
    label = (
        f"LIVE{session_label} · {when} · {n_ok}/{n_total} quotes"
        if n_ok else "LIVE · FETCH FAILED — showing snapshot"
    )
    st.markdown(
        f'<div style="font-family:var(--mono);font-size:10.5px;'
        f'letter-spacing:0.08em;color:var(--ink-3);text-transform:uppercase;'
        f'margin:6px 0 8px;">'
        f'<span style="color:{dot};">●</span> {label}</div>',
        unsafe_allow_html=True,
    )
