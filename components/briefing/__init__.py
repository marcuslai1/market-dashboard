"""Briefing-page sub-components.

Each section of the Briefing tab is a standalone module under
``components.briefing`` exporting a single ``render_*`` entry point.

``render_briefing`` is a thin orchestrator that calls them in the canonical
top-to-bottom order. Callers that need to interleave non-briefing content
(crisis flag, live-price caption, catalyst playbook, contrarians) can
still import and invoke the individual ``render_*`` functions directly.
"""
from __future__ import annotations

import streamlit as st

from components.briefing.action_card import (
    render_action_card,
    render_action_summary,
)
from components.briefing.calendar import render_calendar
from components.briefing.catalyst_playbook import render_catalyst_playbook
from components.briefing.changes import render_changes
from components.briefing.contrarians import render_contrarian_candidates
from components.briefing.interconnected import render_interconnected
from components.briefing.macro import render_macro
from components.briefing.pulse import render_pulse
from components.briefing.stance import render_stance
from lib.cards import render_section_head

__all__ = [
    "render_action_card",
    "render_action_summary",
    "render_briefing",
    "render_calendar",
    "render_catalyst_playbook",
    "render_changes",
    "render_contrarian_candidates",
    "render_interconnected",
    "render_macro",
    "render_pulse",
    "render_stance",
]


def render_briefing(
    snapshot: dict,
    watchlist: dict,
    prev_watchlist: dict,
    benchmarks: dict,
    events: list,
    macro_summary: str,
    geo: dict,
    commodities_note: str = "",
) -> None:
    """Render the Briefing tab in canonical order.

    Kept minimal — does NOT include the crisis-flag banner, live-price caption,
    catalyst playbook, contrarians, or methodology footer. Those remain in
    dashboard.py until the page-level extraction step.
    """
    render_stance(snapshot, len(watchlist))
    render_pulse(benchmarks)
    render_changes(watchlist, prev_watchlist)
    render_action_card(watchlist, events)

    macro_col, cal_col = st.columns([3, 2])
    with macro_col:
        render_macro(macro_summary, geo, commodities_note)
    with cal_col:
        render_section_head("The Week Ahead", "Catalysts that move signals")
        render_calendar(events)
