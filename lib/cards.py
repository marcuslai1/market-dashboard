"""Shared editorial card primitives.

Currently exposes ``render_section_head`` — the eyebrow + headline header
used by almost every editorial section. Other card primitives
(``card_container``, density helpers) land here during Part 2.
"""
from __future__ import annotations

import streamlit as st


def render_section_head(title: str, sub: str = "") -> None:
    """Editorial section header: serif <h2> on the left, mono sub on the right."""
    st.markdown(
        f'<div class="section-head"><h2>{title}</h2>'
        f'<span class="sub">{sub}</span></div>',
        unsafe_allow_html=True,
    )


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
