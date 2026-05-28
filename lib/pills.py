"""Pill HTML + small caption helpers for the editorial Briefing surface."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib.catalog import SIGNAL_COLORS, SIGNAL_TINTS


def _signal_pill_html(sig: str, small: bool = False) -> str:
    color = SIGNAL_COLORS.get(sig, "#9F988B")
    tint = SIGNAL_TINTS.get(sig, "rgba(255,255,255,0.08)")
    pad = "1px 6px" if small else "3px 8px"
    fs = "9.5px" if small else "10.5px"
    return (
        f'<span class="sig-pill" style="color:{color};background:{tint};'
        f'padding:{pad};font-size:{fs};">{sig}</span>'
    )


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
    n_ok = max(0, meta.get("n_ok", 0) - 1)  # exclude __meta__ from count
    n_total = meta.get("n_total", 0)
    fetched = meta.get("fetched_at", "")
    try:
        ts = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
        when = ts.astimezone().strftime("%H:%M")
    except (ValueError, AttributeError):
        when = "—"
    dot = "#22c55e" if n_ok else "#ef4444"
    label = f"LIVE · {when} · {n_ok}/{n_total} quotes" if n_ok else "LIVE · FETCH FAILED — showing snapshot"
    st.markdown(
        f'<div style="font-family:var(--mono);font-size:10.5px;'
        f'letter-spacing:0.08em;color:var(--ink-3);text-transform:uppercase;'
        f'margin:6px 0 8px;">'
        f'<span style="color:{dot};">●</span> {label}</div>',
        unsafe_allow_html=True,
    )
