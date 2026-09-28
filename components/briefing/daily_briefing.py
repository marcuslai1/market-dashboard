"""Briefing · Daily briefing card.

The information service that replaced the model-written report narrative (MarketReport
decisions D2–D5, 2026-09-28): Claude writes a short, sourced briefing in the terminal
from the day's data — moves and why, earnings out / coming, catalysts and calendar,
chart facts — and ``scripts/briefing.py publish`` writes ``data/briefings.json``. This
module only renders it.

Constraints, all upstream decisions:

1. **Information, not advice.** The briefing makes no directional call and names no
   signal label; the publish step refuses both. The card adds nothing on top.
2. **Structural colour only.** It reuses the market-read card's section primitives
   (``.mr-`` classes), whose CSS carries no verdict hue — a fact card must not look
   like a call.
3. **Staleness is stated.** When the newest briefing is for an older data date than
   the report on screen, the header says so instead of letting presence imply
   currency.
"""
from __future__ import annotations

from components.briefing.daily_briefing_v2 import briefing_v2_html
from components.briefing.market_read import _bullets, _drawer, _section, _source_links, _txt
from lib.cards import card_container
from lib.formatters import _escape_attr, _escape_dollars

# Upstream record keys → display label, in reading order. Unknown keys still render,
# after these, under a title-cased label (the publish step owns the schema).
_SECTIONS = (
    ("overnight", "Overnight", "happened"),
    ("earnings", "Earnings", "where"),
    ("catalysts_calendar", "Catalysts & calendar", "tells"),
    ("chart_facts", "Chart facts", "call"),
    ("data_notes", "Data notes", "logged"),
)


def _prose(value) -> str:
    if isinstance(value, list):
        return _bullets(value, 12)
    return f'<div class="mr-prose">{_txt(value)}</div>' if value else ""


def briefing_card_html(payload: dict, report_date: str | None = None) -> str:
    """Return the card markup, or ``""`` when nothing has been published.

    ``report_date`` is the date of the report on screen; a briefing written for an
    older data date is marked stale rather than hidden (the reader still gets it, and
    knows how old it is).
    """
    latest = (payload or {}).get("latest") or {}
    if latest.get("schema") == 2:
        return briefing_v2_html(latest, report_date)
    matters =[m for m in (latest.get("what_matters") or []) if m]
    sections = latest.get("sections") if isinstance(latest.get("sections"), dict) else {}
    if not matters and not sections:
        return ""

    data_date = str(latest.get("data_date") or "")
    stale = bool(report_date and data_date and data_date < str(report_date))
    state_attr = ' data-stale="1"' if stale else ""
    when = f"data of {data_date}" if data_date else "undated"
    if latest.get("ts_sgt"):
        when += f" · written {str(latest['ts_sgt'])[:16].replace('T', ' ')} SGT"
    if stale:
        when += f" · older than the report on screen ({report_date})"
    revised = ' <span class="mr-date">revised</span>' if latest.get("revises") else ""
    head = (
        '<div class="mr-head">'
        f'<span class="mr-state" data-state="{"matured" if stale else "live"}"{state_attr}>'
        f'{"STALE" if stale else "TODAY"}</span>'
        f'<span class="mr-when">{_escape_dollars(_txt(when))}</span>{revised}'
        '</div>'
    )

    body = ""
    if matters:
        body += _section("bottom", "What matters", _bullets(matters, 3))
    seen = set()
    for key, label, kind in _SECTIONS:
        seen.add(key)
        inner = _prose(sections.get(key))
        if inner:
            body += _section(kind, label, inner)
    for key, value in sections.items():
        if key not in seen:
            inner = _prose(value)
            if inner:
                body += _section("where", str(key).replace("_", " ").capitalize(), inner)
    srcs = latest.get("sources") or []
    body += _drawer("sources", "Sources", _source_links(srcs, limit=12),
                    count=len([s for s in srcs if isinstance(s, dict) and s.get("title")]))

    foot = (
        '<div class="mr-foot" data-kind="briefing">'
        'Information, not advice: no directional call and no signal labels. Written by '
        'Claude in the terminal from the day’s data; every load-bearing fact carries a '
        'source. Published briefings are never edited — a correction is a new, revised entry.'
        '</div>'
    )
    return card_container(
        eyebrow=f"DAILY BRIEFING · {_escape_attr(data_date) or 'LATEST'}",
        headline="",
        body_html=head + body + foot,
        lane="lede",
    )
