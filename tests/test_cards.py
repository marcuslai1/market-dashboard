"""Tests for the shared editorial card primitives.

``masthead=True`` is the site's marker for a top-level document surface — the
2px full-strength rule that the Watchlist, Signal Tracker and Review heads
share. `.section-head` stays 1px everywhere else, so the flag must be opt-in.
"""
from lib.cards import _section_head_html


def test_section_head_default_has_no_masthead_class():
    assert _section_head_html("The Watchlist", "sub") == (
        '<div class="section-head"><h2>The Watchlist</h2>'
        '<span class="sub">sub</span></div>'
    )


def test_masthead_flag_adds_the_class():
    html = _section_head_html("The Watchlist", "sub", masthead=True)
    assert 'class="section-head masthead"' in html
