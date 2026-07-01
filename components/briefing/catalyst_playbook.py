"""Macro Trigger Map — bull/bear playbook per upcoming macro event."""
from __future__ import annotations

import streamlit as st

from lib.cards import render_section_head
from lib.catalog import SIGNAL_COLORS
from lib.formatters import _escape_dollars


def render_catalyst_playbook(trigger_map: list) -> None:
    """Render `macro_trigger_map` — bull/bear playbook per upcoming macro event.

    Each entry has {event, date, bullish_outcome, bullish_upgrades[],
    bearish_outcome, bearish_impact[]}. Renders nothing when the list is
    empty. Defensive against the legacy nested-array shape (the pipeline
    flattens, but old reports may still carry [[…]] structure).
    """
    if not trigger_map:
        return
    # Defensive flatten in case an old report carries the pre-fix nested shape.
    if all(isinstance(x, list) for x in trigger_map):
        trigger_map = [item for sub in trigger_map for item in sub]
    render_section_head(
        "Macro Trigger Map",
        "How signals shift on each upcoming high-impact event",
    )
    bull_color = SIGNAL_COLORS["BUY"]
    bear_color = SIGNAL_COLORS["CAUTION"]
    for ev in trigger_map:
        if not isinstance(ev, dict):
            continue
        name = ev.get("event", "—")
        when = ev.get("date", "")
        bull = ev.get("bullish_outcome") or ""
        bear = ev.get("bearish_outcome") or ""
        ups = ev.get("bullish_upgrades") or []
        impacts = ev.get("bearish_impact") or []

        ups_html = "".join(
            f'<li style="margin-bottom:3px;">{_escape_dollars(u)}</li>'
            for u in ups
        )
        impacts_html = "".join(
            f'<li style="margin-bottom:3px;">{_escape_dollars(i)}</li>'
            for i in impacts
        )
        st.markdown(
            f'<div style="border:1px solid var(--rule);background:var(--paper-2);'
            f'padding:14px 18px 12px;margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;border-bottom:1px solid var(--rule);'
            f'padding-bottom:8px;margin-bottom:10px;">'
            f'<span style="font-family:var(--serif);font-size:1.1rem;'
            f'font-weight:500;color:var(--ink);">{_escape_dollars(name)}</span>'
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.10em;text-transform:uppercase;color:var(--ink-3);">'
            f'{_escape_dollars(when)}</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">'
            f'<div>'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.14em;text-transform:uppercase;color:{bull_color};'
            f'font-weight:600;margin-bottom:4px;">▲ Bullish path</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.5;'
            f'margin-bottom:8px;">{_escape_dollars(bull)}</div>'
            f'<ul style="margin:0;padding-left:18px;font-family:var(--mono);'
            f'font-size:11.5px;color:var(--ink-2);line-height:1.5;">{ups_html}</ul>'
            f'</div>'
            f'<div>'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.14em;text-transform:uppercase;color:{bear_color};'
            f'font-weight:600;margin-bottom:4px;">▼ Bearish path</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.5;'
            f'margin-bottom:8px;">{_escape_dollars(bear)}</div>'
            f'<ul style="margin:0;padding-left:18px;font-family:var(--mono);'
            f'font-size:11.5px;color:var(--ink-2);line-height:1.5;">{impacts_html}</ul>'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
