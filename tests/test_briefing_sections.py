"""Shared briefing section primitives (components/briefing/sections.py).

The CSS pin moved here from the market-read card's tests when that card was removed
(2026-10-03): the daily briefing card renders through the same ``.mr-`` classes, so the
structural-colour-only guarantee still has to hold.
"""
from __future__ import annotations

from components.briefing.sections import _drawer, _section, _source_links


def test_section_css_never_puts_a_verdict_colour_on_this_surface():
    # Colour lives in theme.css, not the markup, so the guard reads the stylesheet:
    # no .mr- rule may reference a good/bad token (structural colour only, 2026-09-14).
    import pathlib
    import re

    css = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(
        encoding="utf-8")
    rules = re.findall(r"([^{}]*\.mr-[^{}]*)\{([^}]*)\}", css)
    assert rules, "section CSS not found"
    banned = ("--up", "--down", "--buy", "--accumulate", "--watch", "--caution",
              "--avoid", "--stress", "#22c55e", "#ef4444", "#4ade80", "#f87171")
    for selector, body in rules:
        for token in banned:
            assert token not in body, f"{selector.strip()} uses {token}"


def test_source_links_are_http_only_and_escaped():
    html = _source_links([{"title": "a <b>", "url": "javascript:alert(1)", "date": "2026-10-03"},
                          {"title": "ok", "url": "https://example.com/x"}])
    assert "javascript:" not in html and "&lt;b&gt;" in html
    assert 'href="https://example.com/x"' in html


def test_empty_drawer_renders_nothing_and_section_carries_its_kind():
    assert _drawer("sources", "Sources", "") == ""
    assert 'data-sec="moves"' in _section("moves", "Moves", "<p>x</p>")
