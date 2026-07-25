"""Terminology page: the site's reference document.

Design spec: docs/superpowers/specs/2026-07-25-terminology-redesign-design.md
Copy: components/terminology_content.py (this module holds no prose).

A reference page is arrived at, not read. Nobody scrolls six thousand words to
learn something — they land here from a Watchlist row wanting one term in ten
seconds. So the page is built for *finding* first: a sticky index rail, a search
that drops non-matching sections outright, and three visually distinct layers per
entry so the plain answer can be read without the rule underneath it.

Three host constraints shape the implementation (spec §4):

  * ``st.markdown`` strips ``<script>``, so search is a server-side filter on a
    ``st.text_input`` rather than a keystroke filter. Streamlit reruns on Enter
    or blur, which the placeholder says out loud.
  * The body is ONE markdown blob, not ``st.columns``. Nested Streamlit columns
    bring their own flex wrappers, and a content column with no flexible track
    collapses to its minimum — the bug that crushed the Review rows into a
    140px ribbon. One blob means the grid is ours.
  * Doors are raw ``<details>``: ``st.expander`` cannot live inside
    markdown-injected HTML. They wear the site's door grammar (see .dd-drawer,
    theme.css) so an expander looks the same everywhere.
"""
from __future__ import annotations

import re

import streamlit as st

from components.terminology_content import SECTIONS
from lib.cards import _section_head_html, render_section_head

_PLACEHOLDER = "Search terms — press Enter"

# Idle, the status line teaches the layout; with a query it reports results. One
# element doing both jobs, because a permanently-visible "how to read this page"
# note would be furniture the second time you visit.
_IDLE_NOTE = (
    f"{len(SECTIONS)} sections · plain definition first, the precise rule under "
    "it, the audit trail behind a door"
)


def matches(section: dict, query: str) -> bool:
    """True when every whitespace-separated token of ``query`` starts a word in
    the section's title, descriptor or keyword string.

    Token-AND rather than one substring, so "wide stop" finds the R:R section
    whether or not those words sit adjacent in the haystack. Word-START rather
    than anywhere-in-the-string, because the abbreviations people actually type
    are short and bare substring matching turns them into noise: "rr" otherwise
    matches "ca**rr**y forward" and "na**rr**owness" and the reader is handed
    three sections when one is correct. Prefixes still match, so "sma" finds
    sma50 and sma200 and "calib" finds calibration.

    The keyword list IS the search index. Colloquial spellings, abbreviations
    and both halves of a hyphenation belong in it, because a term that isn't in
    ``kw`` is a term the reader cannot find.
    """
    q = query.strip().lower()
    if not q:
        return True
    hay = f"{section['title']} {section['descriptor']} {section['kw']}".lower()
    return all(re.search(rf"(?<![a-z0-9]){re.escape(tok)}", hay) for tok in q.split())


def status_line(n_match: int, query: str) -> str:
    """The one line under the search box."""
    q = query.strip()
    if not q:
        return _IDLE_NOTE
    verb = "matches" if n_match == 1 else "match"
    return f"{n_match} of {len(SECTIONS)} sections {verb} “{q}”"


def _door_html(summary: str, body: str) -> str:
    """One audit-trail door. Raw <details> on the site's door grammar."""
    return (f'<details class="term-door"><summary>{summary}</summary>'
            f'<div class="term-door-body">{body}</div></details>')


def index_html(sections, matched_ids) -> str:
    """The sticky rail.

    Always lists all twelve, even while filtering: the index is how a reader
    learns what the page contains, and hiding entries would make a search look
    like the page shrank. Matching entries keep their anchor and take an accent
    tick; non-matching ones render as inert <span> — a link to a section that
    isn't on the page is worse than no link.
    """
    items = ""
    for sec in sections:
        hit = sec["id"] in matched_ids
        cls = "term-index-item is-match" if hit else "term-index-item is-dim"
        label = sec["title"]
        inner = (f'<a class="{cls}" href="#{sec["id"]}">{label}</a>' if hit
                 else f'<span class="{cls}">{label}</span>')
        items += inner
    return ('<nav class="term-index" aria-label="Sections">'
            '<div class="term-index-head">On this page</div>'
            f"{items}</nav>")


def section_html(sec: dict) -> str:
    """One section: head → plain answer → precise rule → doors.

    The three layers must LOOK different or the layering does nothing; the class
    names carry that (term-answer / term-grid+term-plate / term-door).
    """
    doors = "".join(_door_html(summary, body) for summary, body in sec["drawers"])
    # History summaries lead with the label and end with the date, so a reader
    # can tell whether a change is relevant to them without opening it.
    doors += "".join(
        _door_html(f"Method history · {label} · {date}", body)
        for date, label, body in sec["history"]
    )
    # The shared .section-head device (1px rule, right-aligned descriptor), one
    # step below the page's masthead variant (2px). On a twelve-section page
    # that step is load-bearing: at the page weight the scroll would read as
    # twelve separate documents.
    return (
        f'<section class="term-section" id="{sec["id"]}">'
        f'{_section_head_html(sec["title"], sec["descriptor"])}'
        f'<p class="term-answer">{sec["answer"]}</p>'
        f'{sec["body"]}'
        f'{doors}'
        f"</section>"
    )


def page_html(sections, matched_ids) -> str:
    """Index rail + body, as one grid. Rendered in a single st.markdown call."""
    body = "".join(section_html(s) for s in sections if s["id"] in matched_ids)
    if not body:
        body = ('<div class="term-empty">No section matches that term. Clear the '
                "search to see all twelve, or try a broader word — the index is "
                "keyed to concepts, not to every phrase on the page.</div>")
    return (f'<div class="term-layout">{index_html(sections, matched_ids)}'
            f'<div class="term-body">{body}</div></div>')


def render_terminology_page() -> None:
    """Render the Terminology page."""
    # masthead=True is the shared 30px/2px document head used by every top-level
    # page surface (Retrospective, Watchlist, the Tracker's peer sections). One
    # device, one implementation.
    render_section_head(
        "Terminology & Method",
        "How every number on this site is computed",
        masthead=True,
    )

    # Nothing else on the site needs search; this page does — it is the only
    # surface a reader arrives at with one specific term already in mind.
    query = st.text_input(
        "Search terminology",
        key="term_search",
        placeholder=_PLACEHOLDER,
        label_visibility="collapsed",
    )
    matched = [s for s in SECTIONS if matches(s, query)]
    matched_ids = {s["id"] for s in matched}

    st.markdown(
        f'<div class="term-status">{status_line(len(matched), query)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(page_html(SECTIONS, matched_ids), unsafe_allow_html=True)
