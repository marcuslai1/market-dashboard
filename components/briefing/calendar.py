"""Briefing · Week-ahead calendar (Context band, right column).

Renders this-week catalysts grouped by date, plus a muted forward-catalysts
section below a hairline divider. Extracted from dashboard.py during the
Day-2 modularization pass.

Visual Step 5 (ContextBand split): exposes ``calendar_card_html`` as a
string-returning helper so the Briefing band can be composed as a single
``st.markdown`` emission inside a lane wrapper.
"""
from __future__ import annotations

from datetime import datetime as _dt

import streamlit as st

from lib.cards import card_container
from lib.formatters import _escape_dollars


def _group_html(group: list, muted: bool = False) -> str:
    """Return day-grouped events markup as a string."""
    grouped: dict[str, list] = {}
    for e in group:
        grouped.setdefault(e.get("date", "—"), []).append(e)
    style = "opacity:0.72;" if muted else ""
    out = ""
    for date_str in sorted(grouped.keys()):
        try:
            d = _dt.strptime(date_str, "%Y-%m-%d")
            short, dow = d.strftime("%b %d"), d.strftime("%a").upper()
        except (ValueError, TypeError):
            short, dow = date_str, ""
        events_html = ""
        for e in grouped[date_str]:
            impact = (e.get("impact") or "LOW").upper()
            events_html += (
                f'<div class="cal-event" style="{style}">'
                f'<span class="cal-impact {impact}">{impact}</span>'
                f'<span class="cal-text">{_escape_dollars(e.get("event", ""))}</span>'
                f'</div>'
            )
        out += (
            f'<div class="cal-day">'
            f'<div class="cal-date">{short}<span class="dow">{dow}</span></div>'
            f'<div>{events_html}</div></div>'
        )
    return out


def calendar_card_html(events: list) -> str:
    """Return the Week-Ahead card markup (ledger lane).

    Body contains the day-grouped this-week events plus a Forward Catalysts
    sub-section below a hairline divider. Empty input → empty-state body.
    """
    if not events:
        body = '<p style="color:var(--ink-3);font-size:13px;">No catalysts logged.</p>'
        return card_container(
            eyebrow="THE WEEK AHEAD",
            headline="Catalysts that move signals",
            body_html=body,
            lane="ledger",
        )

    this_week = [e for e in events if (e.get("type") or "this_week") != "forward_catalyst"]
    forward = [e for e in events if (e.get("type") or "") == "forward_catalyst"]

    body = _group_html(this_week)

    if forward:
        body += (
            '<div style="border-top:1px solid var(--rule);margin:10px 0 8px;'
            'font-family:var(--mono);font-size:10px;letter-spacing:0.12em;'
            'text-transform:uppercase;color:var(--ink-3);padding-top:8px;">'
            'Forward Catalysts</div>'
        )
        body += _group_html(forward, muted=True)

    return card_container(
        eyebrow="THE WEEK AHEAD",
        headline="Catalysts that move signals",
        body_html=body,
        lane="ledger",
    )


def render_calendar(events: list) -> None:
    """Thin wrapper that emits the Week-Ahead card.

    Used by ``render_briefing`` and any caller that doesn't compose the
    lane-wrapper itself.
    """
    st.markdown(calendar_card_html(events), unsafe_allow_html=True)
