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


def _section(kind: str, label: str, inner: str, aside: str = "") -> str:
    """One accented sub-panel. ``kind`` picks the structural hue in CSS."""
    return (
        f'<div class="mr-sec" data-sec="{_escape_attr(kind)}">'
        f'<div class="mr-sec-lab">{_escape_dollars(label)}{aside}</div>'
        f'{inner}</div>'
    )


def _list_block(kind: str, label: str, items: list, limit: int) -> str:
    """A labelled bullet-list section, or ``""`` when there is nothing to show."""
    rows = "".join(f"<li>{_escape_dollars(i)}</li>" for i in items[:limit] if i)
    if not rows:
        return ""
    return _section(kind, label, f'<ul class="mr-list">{rows}</ul>')


def _sources_block(items: list, limit: int) -> str:
    """Sources as a collapsed drawer — attribution one click away, not a wall."""
    shown = [i for i in items[:limit] if i]
    if not shown:
        return ""
    rows = "".join(f"<li>{_escape_dollars(i)}</li>" for i in shown)
    return (
        '<details class="mr-sec mr-src" data-sec="sources">'
        f'<summary class="mr-sec-lab">Sources<span class="mr-count">{len(shown)}</span></summary>'
        f'<ul class="mr-list">{rows}</ul></details>'
    )


def _lean_rows_html(leans: dict) -> str:
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
        rows += (
            '<div class="mr-row">'
            f'<span class="mr-cl">{_escape_dollars(label)}</span>'
            f'<span class="mr-lean">{arrow_html}{_escape_dollars(lean)}</span>'
            f'<span class="mr-guide">{_escape_dollars(guide)}</span>'
            f'<span class="mr-why">{_escape_dollars(v.get("why") or "")}</span>'
            '</div>'
        )
    return _section("leans", "The leans · into the next close", rows)


def market_read_card_html(payload: dict, now: _dt.datetime | None = None) -> str:
    """Return the card markup, or ``""`` when there is nothing publishable.

    Silent (not an error state) when the file is absent: the read is on-demand,
    so "no read has ever been published" is a normal condition on a fresh clone.
    """
    latest = (payload or {}).get("latest") or {}
    leans = latest.get("leans") or {}
    if not leans:
        return ""

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

    conf_html = ""
    if latest.get("confidence"):
        why = latest.get("confidence_why") or ""
        badge = f'<span class="mr-badge">{_escape_dollars(latest["confidence"])}</span>'
        body = f'<div class="mr-prose">{_escape_dollars(why)}</div>' if why else ""
        conf_html = _section("confidence", "Confidence", body, aside=badge)

    tells_html = _list_block("tells", "What would change it", latest.get("tells") or [], limit=4)

    # The caveats and the sources are the half of the read that argues AGAINST
    # its own leans — what could not be verified, and who said the rest. The
    # card asserted "Europe led down on a MS downgrade" with the source sitting
    # unrendered in the payload until 2026-09-09; a lean without its attribution
    # is the failure mode this instrument exists to expose.
    notes_html = ""
    if latest.get("notes"):
        notes_html = _section(
            "caveats", "Caveats",
            f'<div class="mr-prose">{_escape_dollars(latest["notes"])}</div>',
        )
    sources_html = _sources_block(latest.get("headline_context") or [], limit=8)

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
        body_html=(head + blurb + _lean_rows_html(leans) + conf_html
                   + tells_html + notes_html + sources_html + foot),
        lane="lede",
    )
