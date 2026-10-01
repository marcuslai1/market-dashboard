"""Shared editorial card primitives.

Currently exposes ``render_section_head`` — the eyebrow + headline header
used by almost every editorial section. Other card primitives
(``card_container``, density helpers) land here during Part 2. ``help_tip``
(the click-to-open "?" popover) moved here from ``components/paper_book.py``
when the paper books were frozen and that module removed (2026-10-01).
``data_health_banners_html`` is the run-level trust caveat both pages show.
"""
from __future__ import annotations

import streamlit as st

from lib.formatters import _escape_dollars


def help_tip(text: str, label: str = "What this means") -> str:
    """A click-to-open "?" popover. Built on <details>, which Streamlit's
    sanitiser keeps (the watchlist drawers use it), so it opens on click and
    on keyboard, and needs no JavaScript. A title attribute alone only shows
    after a long hover and never on click/touch (owner report 2026-08-27).
    Styled by the ``.pb-tip`` rules in ``assets/theme.css``."""
    body = _escape_dollars(text)
    return (f'<details class="pb-tip"><summary aria-label="{label}">?</summary>'
            f'<div class="pb-tip-body">{body}</div></details>')


def _section_head_html(title: str, sub: str = "", masthead: bool = False) -> str:
    """Editorial section header markup: serif <h2> left, mono sub right.

    ``masthead=True`` gives a top-level document surface the heavier 2px
    full-strength rule — the Watchlist head (spec 2026-07-25 §3) and the
    Terminology head (the Signal Tracker's sections and the Review head used it
    too until those pages went on 2026-10-01) — without moving every other
    section head on the site. Pure so it can be
    tested without a Streamlit run.
    """
    cls = "section-head masthead" if masthead else "section-head"
    return (f'<div class="{cls}"><h2>{title}</h2>'
            f'<span class="sub">{sub}</span></div>')


def render_section_head(title: str, sub: str = "", masthead: bool = False) -> None:
    """Editorial section header: serif <h2> on the left, mono sub on the right."""
    st.markdown(_section_head_html(title, sub, masthead), unsafe_allow_html=True)


def card_container(*, eyebrow: str, headline: str = "", body_html: str, lane: str = "lede") -> str:
    """Blueprint card primitive — returns an HTML string.

    Blueprint aesthetic (design-spec §5): transparent fill, square corners, a
    single hairline border, and a small ``+`` registration mark at each of the
    four corners. The caller emits it via ``st.markdown(..., unsafe_allow_html
    =True)``. ``lane`` is the semantic attribute the lane grid consumes.
    """
    headline_html = f'<h2 class="card-headline">{headline}</h2>' if headline else ''
    return (
        f'<div class="card blueprint" data-lane="{lane}">'
        f'<i class="corner tl"></i><i class="corner tr"></i>'
        f'<i class="corner bl"></i><i class="corner br"></i>'
        f'<div class="card-head">'
        f'<span class="eyebrow">{eyebrow}</span>'
        f'{headline_html}'
        f'</div>'
        f'<div class="card-body">{body_html}</div>'
        f'</div>'
    )


def data_health_banners_html(meta: dict | None) -> str:
    """Run-level data-health banners for one report, or ``""`` on a clean run.

    Two facts about the RUN, never about a stock: the coverage banner (names the
    pipeline could not fetch, ``meta.data_coverage``) and the zero-news banner
    (``meta.news_coverage.zero_news``, from the pipeline cutover on — the whole
    run harvested no articles, so no drill-down carries headlines). Terracotta
    ``warn`` tone: "read what follows with care".
    """
    meta = meta or {}
    out: list[str] = []
    dc = meta.get("data_coverage") or {}
    if isinstance(dc, dict) and dc.get("coverage_degraded"):
        skipped = [str(s) for s in (dc.get("skipped") or [])]
        skip_note = f" Missing: {_escape_dollars(', '.join(skipped[:8]))}." if skipped else ""
        out.append(
            '<div class="briefing-banner" data-tone="warn">⚠ Data coverage degraded — '
            f'{_escape_dollars(str(dc.get("fetched")))}/{_escape_dollars(str(dc.get("expected")))} '
            f'names fetched.{skip_note}</div>'
        )
    nc = meta.get("news_coverage") or {}
    if isinstance(nc, dict) and nc.get("zero_news") is True:
        out.append(
            '<div class="briefing-banner" data-tone="warn">⚠ No news this run — the news '
            'feed returned no articles for any name, so no drill-down carries headlines '
            'for this report.</div>'
        )
    return "".join(out)
