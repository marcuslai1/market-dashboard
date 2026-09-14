"""Briefing · Market Read card (EXPERIMENTAL).

The on-demand forward adviser from the MarketReport repo's `market-read` skill:
a qualitative, cluster-level lean written *before* the tape resolves and graded
afterwards. The payload is written by `scripts/market_read.py publish` into
``data/market_reads.json``; this module only renders it.

Three deliberate constraints, all owner decisions on 2026-09-09:

1. **No score on this card.** The read's record is a *local* hit rate, and
   CLAUDE.md carries a standing "never reintroduce a local hit-rate headline"
   guard — the Signal Tracker's tiles read pipeline alpha, and a 62.5%-on-8-rows
   number rendered beside them invites exactly that comparison. The card shows
   the progress counter instead; whether the scorecard is ever shown is decided
   at the 20-session exit review.
2. **No colour on the leans.** Green/red is a claim of proven good/bad. This
   adviser has passed no measurement bar, so every lean renders in neutral ink;
   direction is carried by an arrow glyph, never a hue. Colour on this card is
   *structural* only (owner decision 2026-09-14): each section carries its own
   accent from the non-verdict metric palette so the card scans as sections,
   and no hue ever attaches to a call.
3. **Staleness is stated, not implied.** Reads are logged on demand at irregular
   hours; a four-day-old "don't add" rendered as though it were current is worse
   than no card at all. ``read_state`` derives live / in-play / matured from the
   stamped target closes, and the header says which.

The card is inert: nothing here feeds a signal, a bucket, or the paper book.
"""
from __future__ import annotations

import datetime as _dt

from lib.cards import card_container
from lib.formatters import _escape_attr, _escape_dollars

# A matured read older than this many days stops being "the latest read" and
# starts being a stale artefact — the header says so rather than letting the
# reader infer currency from mere presence.
STALE_AFTER_DAYS = 2

# Display order, matching the order the skill's read format uses. Clusters not
# listed here still render, after these, under their raw key.
_CLUSTER_ORDER = ("semis", "big_tech", "ai_power_infra", "sg_banks", "market")
_CLUSTER_LABEL = {
    "semis": "Chips",
    "big_tech": "Big tech",
    "ai_power_infra": "AI power",
    "sg_banks": "Singapore banks",
    "market": "Whole market",
}
# The log stores the enum; the reader gets the words the skill writes reads in.
_LEAN_WORD = {"firm": "slightly up", "soft": "slightly down", "neutral": "flat"}
_GUIDANCE_WORD = {
    "hold": "hold",
    "trim": "trim",
    "dont_add": "don't add",
    "add_ok": "ok to add",
    "avoid": "avoid",
}
# Direction as a glyph, not a colour — the lean chips stay neutral ink.
_LEAN_ARROW = {"firm": "↑", "soft": "↓", "neutral": "→"}
_STATE_LABEL = {
    "live": "IN PLAY",
    "in_play": "PARTLY RESOLVED",
    "matured": "MATURED",
    "unknown": "LOGGED",
}


def _parse_utc(s):
    """ISO-8601 → aware UTC datetime, tolerating the trailing ``Z`` (py3.9)."""
    if not s:
        return None
    try:
        d = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def read_state(payload: dict, now: _dt.datetime | None = None) -> dict:
    """Derive the freshness state of the published read. Pure; unit-tested.

    ``live``    — every target close is still ahead: the read is forward-looking.
    ``in_play`` — some targets closed, some have not (a US read whose SG-banks
                  leg targets the next SGX close spends about a day here).
    ``matured`` — every target close has passed; the read is history now.
    """
    latest = (payload or {}).get("latest") or {}
    now = now or _dt.datetime.now(_dt.timezone.utc)
    closes = sorted(
        c for c in (
            _parse_utc(t.get("target_close_utc"))
            for t in (latest.get("targets") or {}).values()
        ) if c is not None
    )
    if not closes:
        state = "unknown"
    elif now < closes[0]:
        state = "live"
    elif now >= closes[-1]:
        state = "matured"
    else:
        state = "in_play"
    logged = _parse_utc(latest.get("ts_utc"))
    age_days = (now - logged).days if logged else None
    return {
        "state": state,
        "age_days": age_days,
        "stale": state == "matured" and (age_days or 0) >= STALE_AFTER_DAYS,
        "next_close": closes[0].isoformat() if closes else None,
    }


def _age_text(when: str, state: dict) -> str:
    age = state["age_days"]
    if state["stale"]:
        tail = f" · {age} days ago" if age else ""
        return f"no read since {when} SGT{tail}"
    if age:
        return f"{when} SGT · {age} day{'s' if age != 1 else ''} ago"
    return f"{when} SGT"


def _txt(s) -> str:
    """Escape prose for the card; markdown emphasis from the reply is dropped."""
    return _escape_dollars(str(s or "").replace("**", ""))


def _section(kind: str, label: str, inner: str, aside: str = "") -> str:
    """One accented sub-panel. ``kind`` picks the structural hue in CSS."""
    return (
        f'<div class="mr-sec" data-sec="{_escape_attr(kind)}">'
        f'<div class="mr-sec-lab">{_txt(label)}{aside}</div>'
        f'{inner}</div>'
    )


def _bullets(items: list, limit: int) -> str:
    rows = "".join(f"<li>{_txt(i)}</li>" for i in (items or [])[:limit] if i)
    return f'<ul class="mr-list">{rows}</ul>' if rows else ""


def _list_block(kind: str, label: str, items: list, limit: int) -> str:
    """A labelled bullet-list section, or ``""`` when there is nothing to show."""
    body = _bullets(items, limit)
    return _section(kind, label, body) if body else ""


def _drawer(kind: str, label: str, inner: str, count: int | None = None) -> str:
    """A collapsed sub-panel — secondary material one click away, not a wall."""
    if not inner:
        return ""
    badge = f'<span class="mr-count">{count}</span>' if count else ""
    return (
        f'<details class="mr-sec mr-drawer" data-sec="{_escape_attr(kind)}">'
        f'<summary class="mr-sec-lab">{_txt(label)}{badge}</summary>{inner}</details>'
    )


def _source_links(sources: list, limit: int = 8) -> str:
    rows = ""
    for src in (sources or [])[:limit]:
        if not isinstance(src, dict) or not src.get("title"):
            continue
        url = str(src.get("url") or "")
        title = _txt(src["title"])
        if url.startswith(("https://", "http://")):
            title = (f'<a class="mr-link" href="{_escape_attr(url)}" target="_blank" '
                     f'rel="noopener noreferrer">{title}</a>')
        date = f' <span class="mr-date">{_txt(src["date"])}</span>' if src.get("date") else ""
        rows += f"<li>{title}{date}</li>"
    return f'<ul class="mr-list">{rows}</ul>' if rows else ""


def _lean_rows_html(leans: dict, sentences: dict | None = None) -> str:
    """Cluster | lean chip | advice chip | sentence.

    Lean and advice always come from the LOGGED record (the graded call); the
    sentence is the plain-language one from the summary when there is one, else
    the logged ``why``.
    """
    ordered = [c for c in _CLUSTER_ORDER if c in leans]
    ordered += [c for c in leans if c not in _CLUSTER_ORDER]
    rows = ""
    for cl in ordered:
        v = leans.get(cl) or {}
        label = _CLUSTER_LABEL.get(cl, cl.replace("_", " "))
        lean = _LEAN_WORD.get(v.get("lean"), v.get("lean") or "—")
        arrow = _LEAN_ARROW.get(v.get("lean"), "")
        arrow_html = f'<i class="mr-arrow" aria-hidden="true">{arrow}</i>' if arrow else ""
        guide = _GUIDANCE_WORD.get(v.get("guidance"), v.get("guidance") or "—")
        why = (sentences or {}).get(cl) or v.get("why") or ""
        rows += (
            '<div class="mr-row">'
            f'<span class="mr-cl">{_txt(label)}</span>'
            f'<span class="mr-lean">{arrow_html}{_txt(lean)}</span>'
            f'<span class="mr-guide">{_txt(guide)}</span>'
            f'<span class="mr-why">{_txt(why)}</span>'
            '</div>'
        )
    return _section("leans", "What I expect, per group", rows)


def _confidence_block(latest: dict, prose: str, cant_know: str, caveats: str) -> str:
    if not (latest.get("confidence") or prose or cant_know or caveats):
        return ""
    badge = (f'<span class="mr-badge">{_txt(latest["confidence"])}</span>'
             if latest.get("confidence") else "")
    inner = f'<div class="mr-prose">{_txt(prose)}</div>' if prose else ""
    if cant_know:
        inner += (f'<div class="mr-prose"><span class="mr-inline-lab">What I can’t know</span>'
                  f'{_txt(cant_know)}</div>')
    if caveats:
        inner += (f'<div class="mr-prose"><span class="mr-inline-lab">Caveats</span>'
                  f'{_txt(caveats)}</div>')
    return _section("confidence", "Confidence", inner, aside=badge)


def market_read_card_html(payload: dict, now: _dt.datetime | None = None) -> str:
    """Return the card markup, or ``""`` when there is nothing publishable.

    Silent (not an error state) when the file is absent: the read is on-demand,
    so "no read has ever been published" is a normal condition on a fresh clone.

    Two payload shapes share ONE layout, in the order of the plain-language reply
    the reader sees in the session (bottom line → where we are → what happened →
    per group → what would change it → confidence → the call → sources):

    * with ``latest.summary`` (from 2026-09-14) the sections carry that reply, and
      the terse logged grading fields move to a collapsed "as logged" drawer;
    * without one (older reads) the same sections are filled from the logged
      fields, and the sections only a summary can supply are omitted.
    """
    latest = (payload or {}).get("latest") or {}
    leans = latest.get("leans") or {}
    if not leans:
        return ""
    summary = latest.get("summary") if isinstance(latest.get("summary"), dict) else None

    state = read_state(payload, now)
    stale_attr = ' data-stale="1"' if state["stale"] else ""
    head = (
        '<div class="mr-head">'
        f'<span class="mr-state" data-state="{_escape_attr(state["state"])}"{stale_attr}>'
        f'{_STATE_LABEL.get(state["state"], "LOGGED")}</span>'
        f'<span class="mr-when">{_escape_dollars(_age_text(latest.get("ts_sgt") or "", state))}</span>'
        '</div>'
    )
    blurb = (
        '<p class="mr-blurb">A same-session view of the overnight tape, written '
        'before the US close and graded against it afterwards. It is deliberately '
        'independent of the morning report — it does not see the report’s '
        'signals, and is expected to disagree with them.</p>'
    )

    if summary:
        bottom = ""
        if summary.get("bottom_line"):
            bottom = _section("bottom", "Bottom line",
                              f'<div class="mr-lede">{_txt(summary["bottom_line"])}</div>')
        where_inner = ""
        if summary.get("where_we_are"):
            where_inner += f'<div class="mr-prose">{_txt(summary["where_we_are"])}</div>'
        if summary.get("macro_attribution"):
            where_inner += (f'<div class="mr-prose"><span class="mr-inline-lab">Macro</span>'
                            f'{_txt(summary["macro_attribution"])}</div>')
        where = _section("where", "Where we are", where_inner) if where_inner else ""
        happened = _list_block("happened", "What happened", summary.get("what_happened"), limit=8)
        groups = _lean_rows_html(leans, summary.get("per_group") or {})
        change = _list_block("tells", "What would change my mind",
                             summary.get("change_my_mind"), limit=6)
        conf = _confidence_block(latest, summary.get("confidence") or "",
                                 summary.get("cant_know") or "", "")
        call = ""
        if summary.get("the_call"):
            call = _section("call", "The call",
                            f'<div class="mr-lede">{_txt(summary["the_call"])}</div>')
        sources = _drawer("sources", "Sources", _source_links(summary.get("sources")),
                          count=len(summary.get("sources") or []))
        # The logged record, verbatim: what is actually graded. Kept one click away
        # so the plain reply never hides the evidence it was written from.
        logged_inner = ""
        if latest.get("confidence_why"):
            logged_inner += (f'<div class="mr-prose"><span class="mr-inline-lab">Confidence</span>'
                             f'{_txt(latest["confidence_why"])}</div>')
        why_rows = [f'{_CLUSTER_LABEL.get(cl, cl)}: {v.get("why")}'
                    for cl, v in leans.items() if (v or {}).get("why")]
        if why_rows:
            logged_inner += '<span class="mr-inline-lab">Why, per group</span>' + _bullets(why_rows, 10)
        if latest.get("tells"):
            logged_inner += '<span class="mr-inline-lab">Tells</span>' + _bullets(latest["tells"], 6)
        if latest.get("notes"):
            logged_inner += (f'<div class="mr-prose"><span class="mr-inline-lab">Caveats</span>'
                             f'{_txt(latest["notes"])}</div>')
        if latest.get("headline_context"):
            logged_inner += ('<span class="mr-inline-lab">Sources</span>'
                             + _bullets(latest["headline_context"], 10))
        logged = _drawer("logged", "Grading notes · as logged", logged_inner)
        body = (bottom + where + happened + groups + change + conf + call
                + sources + logged)
    else:
        groups = _lean_rows_html(leans)
        change = _list_block("tells", "What would change my mind", latest.get("tells"), limit=4)
        conf = _confidence_block(latest, latest.get("confidence_why") or "", "",
                                 latest.get("notes") or "")
        sources = _drawer("sources", "Sources",
                          _bullets(latest.get("headline_context"), 8),
                          count=len([h for h in (latest.get("headline_context") or [])[:8] if h]))
        body = groups + change + conf + sources

    foot = ""
    sessions, target = (payload or {}).get("sessions_read"), (payload or {}).get("exit_review_at")
    if sessions is not None and target:
        foot = (
            '<div class="mr-foot">'
            f'Experimental — session {sessions} of {target}, <b>not yet scored</b>. '
            'Every read is graded against its benchmark close in a separate log; the '
            f'record is reviewed at {target} sessions and the adviser is retired if it '
            'has not beaten a naive always-up call. Nothing here feeds a signal, a '
            'bucket or the paper book.'
            '</div>'
        )

    return card_container(
        eyebrow="MARKET READ · EXPERIMENTAL",
        headline="",
        body_html=head + blurb + body + foot,
        lane="lede",
    )
