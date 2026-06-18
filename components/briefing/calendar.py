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


def _bucket_pill_html(e: dict) -> str:
    """Inline 'when-for-you' SG-day badge, e.g. [DURING SG MORNING].

    Brighter ink when the event lands during the SG session (the reader is
    awake / markets-adjacent), muted otherwise. Empty when absent (old reports
    exported before the pipeline timing layer existed)."""
    bucket = e.get("sg_bucket")
    if not bucket:
        return ""
    active = bucket.startswith("DURING")
    color = "var(--ink-2)" if active else "var(--ink-3)"
    return (
        f'<span style="font-family:var(--mono);font-size:9px;'
        f'letter-spacing:0.08em;border:1px solid var(--rule);border-radius:3px;'
        f'padding:1px 5px;margin-left:7px;color:{color};white-space:nowrap;'
        f'vertical-align:1px;">{bucket}</span>'
    )


def _timing_line_html(e: dict) -> str:
    """Sub-line under the event title: '<local/relation> · <SGT clock>'.

    Left side prefers the relation phrase when the local clock is uninformative
    (US after-close/before-open, or an SG-domiciled name whose local clock IS
    the SGT clock); otherwise the local clock. '~' marks the approximate
    earnings window. Empty when the event carries no resolved timing."""
    t = e.get("timing")
    if not t:
        return ""
    approx = bool(t.get("approx"))
    tilde = "~" if approx else ""
    sgt = t.get("sgt_label", "")
    relation = t.get("relation")
    local = t.get("local_label", "")
    if relation and (relation in ("after US close", "before US open")
                     or local == sgt):
        left = relation                       # phrase — no tilde
    elif local:
        left = f"{tilde}{local}"              # clock — tilde when approx
    else:
        left = relation or ""
    sgt_disp = f"{tilde}{sgt}" if sgt else ""
    sep = " · " if left and sgt_disp else ""
    return (
        f'<span style="display:block;margin-top:3px;font-family:var(--mono);'
        f'font-size:10px;color:var(--ink-3);">{left}{sep}{sgt_disp}</span>'
    )


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
            tickers = e.get("tickers_affected") or []
            ticker_html = ""
            if tickers:
                tags = "".join(
                    f'<span style="font-family:var(--mono);font-size:10px;'
                    f'background:var(--surface-2,#1e1e2e);border-radius:3px;'
                    f'padding:1px 5px;margin-right:3px;color:var(--ink-2);">'
                    f'{t}</span>'
                    for t in tickers[:5]
                )
                ticker_html = f'<div style="margin-top:3px;{style}">{tags}</div>'
            # Bucket pill + timing line live INSIDE the .cal-text (1fr) column so
            # they stay aligned under the title — the .cal-event grid has a fixed
            # column count and must not gain extra direct children.
            text_html = (
                f'{_escape_dollars(e.get("event", ""))}'
                f'{_bucket_pill_html(e)}'
                f'{_timing_line_html(e)}'
            )
            events_html += (
                f'<div class="cal-event" style="{style}">'
                f'<span class="cal-impact {impact}">{impact}</span>'
                f'<span class="cal-text">{text_html}</span>'
                f'</div>'
                f'{ticker_html}'
            )
        out += (
            f'<div class="cal-day">'
            f'<div class="cal-date">{short}<span class="dow">{dow}</span></div>'
            f'<div>{events_html}</div></div>'
        )
    return out


def calendar_card_html(events: list, lane: str = "ledger") -> str:
    """Return the Week-Ahead card markup.

    Body contains the day-grouped this-week events plus a Forward Catalysts
    sub-section below a hairline divider. Empty input → empty-state body.

    ``lane`` controls grid placement inside a ``.lane-wrapper``. The Briefing
    band passes ``"strip"`` so the (often long) catalyst list spans full width
    below the Macro/Risks row instead of stacking in the right column and
    leaving a tall empty void beside the short Macro note.
    """
    if not events:
        body = '<p style="color:var(--ink-3);font-size:13px;">No catalysts logged.</p>'
        return card_container(
            eyebrow="THE WEEK AHEAD",
            headline="Catalysts that move signals",
            body_html=body,
            lane=lane,
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
        lane=lane,
    )


def render_calendar(events: list) -> None:
    """Thin wrapper that emits the Week-Ahead card.

    Used by ``render_briefing`` and any caller that doesn't compose the
    lane-wrapper itself.
    """
    st.markdown(calendar_card_html(events), unsafe_allow_html=True)
