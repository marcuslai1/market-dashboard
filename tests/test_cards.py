"""Section-head primitive — the masthead variant must stay opt-in.

``masthead=True`` is the site's marker for a top-level document surface: the 2px
full-strength rule that the Signal Tracker's four peer sections (spec 2026-07-25
§3.5), the Review head, and the Watchlist head (spec 2026-07-25 §3) share. Every
other section head on the site keeps the 1px hairline, so the variant is a flag,
never the default.
"""
from lib.cards import _section_head_html


def test_section_head_default_is_not_masthead():
    html = _section_head_html("Paper book", "no real money")
    assert 'class="section-head"' in html
    assert "masthead" not in html
    assert "Paper book" in html and "no real money" in html


def test_section_head_default_markup_is_exact():
    assert _section_head_html("The Watchlist", "sub") == (
        '<div class="section-head"><h2>The Watchlist</h2>'
        '<span class="sub">sub</span></div>'
    )


def test_section_head_masthead_variant_adds_the_class():
    html = _section_head_html("Signal tracker", "track record", masthead=True)
    assert 'class="section-head masthead"' in html


def test_masthead_flag_adds_the_class_for_the_watchlist_head_too():
    html = _section_head_html("The Watchlist", "sub", masthead=True)
    assert 'class="section-head masthead"' in html


def test_section_head_without_sub_still_renders():
    assert "<h2>Terminology</h2>" in _section_head_html("Terminology")
