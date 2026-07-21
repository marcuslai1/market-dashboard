"""Macro Trigger Map — bull/bear playbook per upcoming macro event."""
from __future__ import annotations

import streamlit as st

from lib.cards import render_section_head
from lib.catalog import SIGNAL_COLORS
from lib.formatters import _escape_dollars


def _paths_html(ev: dict) -> str:
    """The two-column bull/bear body for one event (unchanged content)."""
    bull_color = SIGNAL_COLORS["BUY"]
    bear_color = SIGNAL_COLORS["CAUTION"]
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
    return (
        f'<div class="tm-paths">'
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
    )


def _event_details_html(ev: dict) -> str:
    """One collapsible row per event: name + date + signal-move counts on the
    summary line, the full bull/bear playbook in the body."""
    name = ev.get("event", "—")
    when = ev.get("date", "")
    n_up = len(ev.get("bullish_upgrades") or [])
    n_down = len(ev.get("bearish_impact") or [])
    chips = ""
    if n_up:
        moves = "move" if n_up == 1 else "moves"
        chips += f'<span class="tm-chip tm-bull">▲ {n_up} {moves}</span>'
    if n_down:
        moves = "move" if n_down == 1 else "moves"
        chips += f'<span class="tm-chip tm-bear">▼ {n_down} {moves}</span>'
    date_html = f'<span class="tm-date">{_escape_dollars(when)}</span>' if when else ""
    return (
        '<details class="tm-details"><summary class="tm-summary">'
        f'<span class="tm-name">{_escape_dollars(name)}</span>'
        f'{date_html}{chips}'
        f'</summary><div class="tm-body">{_paths_html(ev)}</div></details>'
    )


def render_catalyst_playbook(trigger_map: list) -> None:
    """Render `macro_trigger_map` — bull/bear playbook per upcoming macro event.

    Each entry has {event, date, bullish_outcome, bullish_upgrades[],
    bearish_outcome, bearish_impact[]}. Renders nothing when the list is
    empty. Defensive against the legacy nested-array shape (the pipeline
    flattens, but old reports may still carry [[…]] structure).

    Collapsed-by-default rows (declutter pass 2026-07-21): three always-open
    cards cost ~850px — a full screen — for pre-event conditionals most reads
    skip. The summary keeps the scannable part (which event, when, how many
    signals move each way); the full playbook is one click away, mirroring the
    Clusters/Calibration disclosure idiom.
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
    blocks = "".join(
        _event_details_html(ev) for ev in trigger_map if isinstance(ev, dict)
    )
    if blocks:
        st.markdown(f'<div class="tm-band">{blocks}</div>', unsafe_allow_html=True)
