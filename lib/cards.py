"""Shared editorial card primitives.

Currently exposes ``render_section_head`` — the eyebrow + headline header
used by almost every editorial section. Other card primitives
(``card_container``, density helpers) land here during Part 2.
"""
from __future__ import annotations

import streamlit as st


def _section_head_html(title: str, sub: str = "", masthead: bool = False) -> str:
    """Editorial section header markup: serif <h2> left, mono sub right.

    ``masthead=True`` gives the Signal Tracker's four peer sections the heavier
    2px full-strength rule (spec 2026-07-25 §3.5) without moving every other
    section head on the site. Pure so it can be tested without a Streamlit run.
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
