"""Briefing · Week-ahead calendar (Context band, right column).

Renders catalysts grouped by date: this-week rows, then a muted
forward-catalysts section below a hairline divider. Read-across prints (by
companies the book does NOT hold) sit inline in date order with a NOT HELD
chip — until 2026-09-03 they had their own section below the forward
horizon, which put an Oracle print 8 days out under a TSMC print 6 weeks out.
Extracted from dashboard.py during the Day-2 modularization pass.

Visual Step 5 (ContextBand split): exposes ``calendar_card_html`` as a
string-returning helper so the Briefing band can be composed as a single
``st.markdown`` emission inside a lane wrapper.
"""
from __future__ import annotations

import re
from datetime import datetime as _dt
from datetime import timedelta as _td

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


def _not_held_chip_html(e: dict) -> str:
    """Ownership chip for a read-across row: the company is NOT in the book.

    Since the rows sit inline with the reader's own catalysts (2026-09-03),
    this chip is the one thing that answers "is this mine?" on the row itself.
    Same quiet outline register as the timing chip — ownership is a fact, not
    a verdict, so it carries no colour."""
    if e.get("type") != "read_across":
        return ""
    return '<span class="cal-notheld">NOT HELD</span>'


def _run_chip_html(e: dict) -> str:
    """Span chip for a multi-day event: the range, and which day of it today is.

    A conference is a WEEK, not a date, and the card used to show only its
    start date — a reader looking at "SEP 20 · ECOC 2026" on Sep 22 could not
    tell whether it had happened, was happening, or which of its five days
    carried the news (ECOC's exhibition opened Sep 21, its AI-networks panel
    ran Sep 23). Upstream (`merge._build_events_this_week`) now keeps the row
    alive through `end_date` and stamps `running`; this chip is where the
    reader sees it.

    No colour, by the standing rule: a date range and a day counter are facts,
    not verdicts. Same outline register as the timing and ownership chips; the
    running one sits one step brighter because "happening now" is the thing
    the reader is scanning for.
    """
    end = e.get("end_date")
    if not end:
        return ""
    try:
        start_d = _dt.strptime(e.get("date", ""), "%Y-%m-%d")
        end_d = _dt.strptime(end, "%Y-%m-%d")
    except (ValueError, TypeError):
        return ""
    if end_d <= start_d:
        return ""
    # "SEP 20–24", or "SEP 30–OCT 2" when it crosses a month.
    tail = (end_d.strftime("%d") if end_d.month == start_d.month
            else end_d.strftime("%b %d").upper())
    span = f'{start_d.strftime("%b %d").upper()}–{tail}'
    if not e.get("running"):
        return f'<span class="cal-run">{span}</span>'
    # day_index / day_total are stamped upstream against the REPORT date, so
    # the counter reads off the same clock as the rest of the report — never
    # the viewer's browser, which drifts from the report it annotates. A
    # running row that predates the stamp shows the range alone.
    day, total = e.get("day_index"), e.get("day_total")
    counter = (f'<span class="cal-run" data-active="1">DAY {day} OF {total}</span>'
               if day and total else "")
    return f'<span class="cal-run" data-active="1">{span}</span>{counter}'


def _programme_html(e: dict) -> str:
    """What a multi-day event is doing TODAY, and its day-by-day in a drawer.

    "DAY 4 OF 5" says where in the run the report is; it does not say that
    day 4 is the panel day — the one the reader actually watches. Upstream
    resolves `programme_today` against the report date, so the TODAY line is
    the report's claim, not the browser's. The drawer reuses the scenario-read
    toggle: steel = navigation, never a signal. Days the organizer page does
    not itemise have no entry and are not padded in.
    """
    prog = [p for p in (e.get("programme") or [])
            if isinstance(p, dict) and p.get("date") and p.get("what")]
    if not prog:
        return ""
    today_txt = e.get("programme_today")
    today_html = ""
    if today_txt:
        today_html = (
            '<div class="cal-prog-today">'
            '<span class="cal-prog-label">TODAY</span>'
            f'{_escape_dollars(today_txt)}</div>'
        )
    rows = ""
    for p in sorted(prog, key=lambda p: p["date"]):
        try:
            label = _dt.strptime(p["date"], "%Y-%m-%d").strftime("%a %b %d").upper()
        except (ValueError, TypeError):
            label = p["date"]
        is_today = bool(today_txt) and p["what"] == today_txt
        today_attr = ' data-today="1"' if is_today else ""
        rows += (
            f'<div class="cal-prog-row"{today_attr}>'
            f'<span class="cal-prog-date">{label}</span>'
            f'{_escape_dollars(p["what"])}</div>'
        )
    return (
        f'{today_html}'
        '<details class="cal-scen">'
        '<summary class="cal-scen-toggle">Day by day</summary>'
        f'<div class="cal-scen-body">{rows}</div>'
        '</details>'
    )


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


def _group_date(e: dict) -> str:
    """The date gutter a row files under: its own date, except a RUNNING
    multi-day event files under the report day it is on.

    A running event keeps `date` = its start so upstream sort order and the
    range chip stay truthful, but the gutter is the card's anchor and "WHAT'S
    COMING" must not open with a date that has already passed — the first cut
    of this feature put ECOC under "SEP 20 · SUN" on the Sep 22 card, which
    read as a stale row. The current day is start + (day_index - 1), both
    stamped upstream against the report date, so this derives from the report's
    clock, not the browser's."""
    date_str = e.get("date", "—")
    day = e.get("day_index")
    if not e.get("running") or not day:
        return date_str
    try:
        start = _dt.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return date_str
    return (start + _td(days=int(day) - 1)).strftime("%Y-%m-%d")


def _group_html(group: list, muted: bool = False, cascades: dict | None = None) -> str:
    """Return day-grouped events markup as a string.

    ``muted`` dims the group's forward_catalyst rows only. A read-across row
    that lands in the forward group by date keeps full ink: muting would
    conflate "far away" with "not yours", and the NOT HELD chip already says
    the latter."""
    grouped: dict[str, list] = {}
    for e in group:
        grouped.setdefault(_group_date(e), []).append(e)
    out = ""
    for date_str in sorted(grouped.keys()):
        try:
            d = _dt.strptime(date_str, "%Y-%m-%d")
            short, dow = d.strftime("%b %d"), d.strftime("%a").upper()
        except (ValueError, TypeError):
            short, dow = date_str, ""
        events_html = ""
        for e in grouped[date_str]:
            style = ("opacity:0.72;"
                     if muted and e.get("type") != "read_across" else "")
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
                f'{_run_chip_html(e)}'
                f'{_not_held_chip_html(e)}'
                f'{_bucket_pill_html(e)}'
                f'{_timing_line_html(e)}'
                f'{_programme_html(e)}'
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

    Two sections below their own hairlines: the day-grouped this-week events,
    then the muted Forward Catalysts. Read-across prints — by companies the
    book does NOT hold that move names it does — are interleaved by date and
    carry a NOT HELD chip. Empty input → empty-state body.

    Time before ownership (2026-09-03, reversing the CAL-01 layout): the reader
    scans the card as a timeline, so an Oracle print 8 days out sitting under a
    TSMC print 6 weeks out read as broken. Ownership is answered on the row
    (chip + why-line + affected-holding chips) rather than by section. The
    split still exists upstream — read-across is its own capped pool in the
    pipeline so it can never evict a holding's print — only the rendering
    merged. A read-across row goes above the hairline when it precedes the
    earliest forward catalyst, below it otherwise, so date order holds across
    the divider.

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

    # Interleave read-across by date. The hairline marks the start of the
    # forward horizon, so a read-across row dated before the earliest forward
    # catalyst belongs above it; with no forward rows everything is "now".
    horizon = min((e.get("date") or "9999-99-99" for e in forward),
                  default="9999-99-99")
    this_week += [e for e in read_across if (e.get("date") or "") < horizon]
    forward += [e for e in read_across if (e.get("date") or "") >= horizon]

    body = _group_html(this_week, cascades=cascades)

    if forward:
        body += _subhead_html("Forward Catalysts")
        body += _group_html(forward, muted=True, cascades=cascades)

    return card_container(
        eyebrow=_EYEBROW,
        headline=_HEADLINE,
        body_html=body,
        lane=lane,
    )
