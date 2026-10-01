"""Section-head primitive — the masthead variant must stay opt-in.

``masthead=True`` is the site's marker for a top-level document surface: the 2px
full-strength rule that the Signal Tracker's four peer sections (spec 2026-07-25
§3.5), the Review head, and the Watchlist head (spec 2026-07-25 §3) share. Every
other section head on the site keeps the 1px hairline, so the variant is a flag,
never the default.
"""
from lib.cards import _section_head_html, data_health_banners_html


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


# ── Run-level data-health banners ──
def test_banners_silent_on_a_clean_run():
    assert data_health_banners_html(None) == ""
    assert data_health_banners_html({}) == ""
    assert data_health_banners_html({
        "data_coverage": {"coverage_degraded": False, "fetched": 31, "expected": 31},
        "news_coverage": {"articles": 40, "tickers_with_news": 12, "tickers": 31,
                          "zero_news": False},
    }) == ""


def test_zero_news_banner_states_the_run_fact():
    out = data_health_banners_html({"news_coverage": {"articles": 0, "zero_news": True}})
    assert out.count('class="briefing-banner"') == 1
    assert "No news this run" in out and 'data-tone="warn"' in out


def test_zero_news_needs_a_literal_true():
    assert data_health_banners_html({"news_coverage": {"zero_news": "false"}}) == ""


def test_coverage_banner_names_the_missing_and_escapes():
    out = data_health_banners_html({"data_coverage": {
        "coverage_degraded": True, "fetched": 29, "expected": 31,
        "skipped": ["<b>X</b>", "D05.SI"]}})
    assert "29/31 names fetched" in out and "D05.SI" in out
    assert "<b>" not in out and "&lt;b&gt;" in out


def test_both_banners_stack_coverage_first():
    out = data_health_banners_html({
        "data_coverage": {"coverage_degraded": True, "fetched": 30, "expected": 31},
        "news_coverage": {"zero_news": True}})
    assert out.index("coverage degraded") < out.index("No news this run")
