"""Briefing · Week-ahead calendar (Context band, right column).

Renders this-week catalysts grouped by date, plus a muted forward-catalysts
section below a hairline divider. Extracted from dashboard.py during the
Day-2 modularization pass.

Visual Step 5 (ContextBand split): exposes ``calendar_card_html`` as a
string-returning helper so the Briefing band can be composed as a single
``st.markdown`` emission inside a lane wrapper.
"""
from __future__ import annotations

import re
from datetime import datetime as _dt

from lib.cards import card_container
from lib.charts import SURFACE_2_FALLBACK
from lib.formatters import _escape_attr, _escape_dollars, display_ticker


def _ticker_chips_html(tickers: list, *, limit: int = 3, size: str = "10px",
                       pad: str = "1px 5px", gap: str = "margin-right:3px") -> str:
    """Up to ``limit`` ticker chips, then a single ``+N`` overflow chip.

    Dense catalyst rows used to fan out into a wall of 5–6 tickers. Capping the
    visible chips keeps the row scannable; the overflow chip carries a native
    ``title`` tooltip listing the hidden tickers, so the full set stays
    reachable on hover without any JS. Returns "" for an empty list.
    """
    disp = [display_ticker(t) for t in tickers]
    if not disp:
        return ""
    base = (f'font-family:var(--mono);font-size:{size};'
            f'background:var(--surface-2,{SURFACE_2_FALLBACK});border-radius:3px;'
            f'padding:{pad};{gap}')
    chips = "".join(
        f'<span style="{base};color:var(--ink-2);">{_escape_dollars(t)}</span>'
        for t in disp[:limit]
    )
    extra = disp[limit:]
    if extra:
        chips += (
            f'<span title="{_escape_attr(", ".join(extra))}" '
            f'style="{base};color:var(--ink-3);cursor:default;">+{len(extra)}</span>'
        )
    return chips


def _bucket_pill_html(e: dict) -> str:
    """Inline 'when-for-you' SG-day badge, e.g. [DURING SG MORNING].

    Brighter ink when the event lands during the SG session (the reader is
    awake / markets-adjacent), muted otherwise. Empty when absent (old reports
    exported before the pipeline timing layer existed)."""
    bucket = e.get("sg_bucket")
    if not bucket:
        return ""
    # Logistical metadata, so it is the LIGHTEST chip on the row — quieter than
    # the steel severity chip it sits beside, and square like everything else.
    # data-active keeps the one bit that actually matters (the print lands while
    # the reader is awake) as a single muted step up, not a colour change.
    active = ' data-active="1"' if bucket.startswith("DURING") else ""
    return f'<span class="cal-timing"{active}>{_escape_dollars(bucket)}</span>'


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
        f'font-size:10px;color:var(--ink-3);">'
        f'{_escape_dollars(left)}{sep}{_escape_dollars(sgt_disp)}</span>'
    )


def _cascade_block_html(event_text: str, cascades: dict | None) -> str:
    """Pre-wired bull/bear reads for an earnings event ('' when unmatched).

    Match rule: the event text mentions earnings AND a whole-word,
    case-insensitive hit on a curated alias. Matching is alias-based because
    ``events_this_week`` entries are free text ("TSMC Earnings") with no ticker
    field — the aliases are part of the hand-maintained cascade config.
    """
    text = event_text or ""
    if not cascades or "earning" not in text.lower():
        return ""
    for cfg in cascades.values():
        cfg = cfg or {}
        aliases = cfg.get("aliases") or []
        if not any(re.search(rf"\b{re.escape(a)}\b", text, re.IGNORECASE)
                   for a in aliases):
            continue
        rows = ""
        for side, color, mark in (("bull", "var(--up)", "▲"),
                                  ("bear", "var(--down)", "▼")):
            d = cfg.get(side) or {}
            if not d.get("read"):
                continue
            chips = _ticker_chips_html(
                d.get("tickers") or [], limit=3, size="9px",
                pad="1px 4px", gap="margin-left:3px")
            hint = f' · {d["scenario_hint"]}' if d.get("scenario_hint") else ""
            rows += (
                f'<div style="margin-top:3px;padding-left:8px;'
                f'border-left:2px solid {color};font-size:11px;'
                f'color:var(--ink-3);line-height:1.45;">'
                f'<span style="color:{color};font-family:var(--mono);">'
                f'{mark} {side.upper()}</span> {_escape_dollars(d["read"])}'
                f'{_escape_dollars(hint)}{chips}</div>'
            )
        if not rows:
            return ""
        why = cfg.get("why") or ""
        why_html = (f'<div class="cal-scen-setup">{_escape_dollars(why)}</div>'
                    if why else "")
        # Collapsed by default: glance-vs-study in one control. The calendar
        # stays scannable and the bull/bear depth is one click away instead of a
        # wall of text on every marquee row.
        return (
            '<details class="cal-scen">'
            '<summary class="cal-scen-toggle">Scenario read</summary>'
            f'<div class="cal-scen-body">{why_html}{rows}</div>'
            '</details>'
        )
    return ""


def _why_line_html(e: dict) -> str:
    """Read-across rationale — why a company the reader does NOT hold is on a
    card about their own book. Empty for every other event class.

    Mandatory in spirit: the builder drops a read-across row that cannot name
    the holdings it moves, so this line and the ticker chips beneath it are the
    row's entire justification for the slot it occupies.
    """
    why = e.get("why")
    if not why:
        return ""
    return f'<div class="cal-why">{_escape_dollars(why)}</div>'


def _group_html(group: list, muted: bool = False, cascades: dict | None = None) -> str:
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
                tags = _ticker_chips_html(tickers, limit=3, size="10px",
                                          pad="1px 5px", gap="margin-right:3px")
                ticker_html = f'<div style="margin-top:3px;{style}">{tags}</div>'
            # Bucket pill + timing line live INSIDE the .cal-text (1fr) column so
            # they stay aligned under the title — the .cal-event grid has a fixed
            # column count and must not gain extra direct children.
            text_html = (
                f'{_escape_dollars(e.get("event", ""))}'
                f'{_bucket_pill_html(e)}'
                f'{_timing_line_html(e)}'
                f'{_why_line_html(e)}'
                f'{_cascade_block_html(e.get("event", ""), cascades)}'
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


def _subhead_html(label: str) -> str:
    """Hairline divider + uppercase mono label introducing a calendar section."""
    return (
        '<div style="border-top:1px solid var(--rule);margin:10px 0 8px;'
        'font-family:var(--mono);font-size:10px;letter-spacing:0.12em;'
        'text-transform:uppercase;color:var(--ink-3);padding-top:8px;">'
        f'{label}</div>'
    )


# The eyebrow used to read "THE WEEK AHEAD" while the body routinely listed
# events six weeks out — the card's own label contradicted its content. The
# horizon is not a week and never was reliably one (upstream CAL-01), so the
# eyebrow now names the job instead of a timeframe the card cannot honour.
_EYEBROW = "WHAT'S COMING"
_HEADLINE = "Catalysts that move signals"


def calendar_card_html(events: list, lane: str = "ledger",
                       cascades: dict | None = None) -> str:
    """Return the catalysts card markup.

    Three sections, each below its own hairline: the day-grouped this-week
    events, then Forward Catalysts, then Read-Across — prints by companies the
    book does NOT hold that move names it does. Empty input → empty-state body.

    The sections are ordered by ownership before time: your week, your horizon,
    then everyone else's. A read-across print two days out therefore sits below
    a forward catalyst forty days out, which is deliberate — "is this mine?" is
    the first question the reader asks of a calendar row, and mixing an
    unheld supplier into the this-week list answers it wrong.

    ``lane`` controls grid placement inside a ``.lane-wrapper``. The Briefing
    band passes ``"strip"`` so the (often long) catalyst list spans full width
    below the Macro/Risks row instead of stacking in the right column and
    leaving a tall empty void beside the short Macro note.
    """
    if not events:
        body = '<p style="color:var(--ink-3);font-size:13px;">No catalysts logged.</p>'
        return card_container(
            eyebrow=_EYEBROW,
            headline=_HEADLINE,
            body_html=body,
            lane=lane,
        )

    # Explicit allow-list per section. The old partition treated "anything not
    # forward_catalyst" as this-week, which would have swept a read-across row
    # into the reader's own week the moment the pipeline started emitting one.
    this_week = [e for e in events
                 if (e.get("type") or "this_week") not in ("forward_catalyst",
                                                           "read_across")]
    forward = [e for e in events if e.get("type") == "forward_catalyst"]
    read_across = [e for e in events if e.get("type") == "read_across"]

    body = _group_html(this_week, cascades=cascades)

    if forward:
        body += _subhead_html("Forward Catalysts")
        body += _group_html(forward, muted=True, cascades=cascades)

    if read_across:
        # "Not held" is the whole point of the section, so it is said in the
        # label rather than left to be inferred from unfamiliar tickers. These
        # rows are NOT muted: unlike forward catalysts they are mostly near-term
        # and directly actionable, and dimming them would conflate "far away"
        # with "not yours".
        body += _subhead_html("Read-Across · not held")
        body += _group_html(read_across, cascades=cascades)

    return card_container(
        eyebrow=_EYEBROW,
        headline=_HEADLINE,
        body_html=body,
        lane=lane,
    )
