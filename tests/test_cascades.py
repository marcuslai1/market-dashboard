"""Tests for the earnings-cascade annotations in the Week-Ahead calendar."""
from components.briefing.calendar import _cascade_block_html, calendar_card_html

CASCADES = {
    "TSM": {
        "aliases": ["TSMC", "Taiwan Semiconductor", "TSM"],
        "why": "The physical bottleneck.",
        "bull": {"read": "AI revenue guide up.", "tickers": ["NVDA", "000660_KS"],
                 "scenario_hint": "base holds"},
        "bear": {"read": "Capex trimmed — cycle-top signal.", "tickers": ["NVDA"],
                 "scenario_hint": "pessimistic up"},
    },
    "MU": {"aliases": ["Micron", "MU"], "why": "Memory cycle.",
           "bull": {"read": "HBM guide raise.", "tickers": []},
           "bear": {"read": "HBM ASPs soften.", "tickers": []}},
}


def test_cascade_matches_alias_in_earnings_event():
    html = _cascade_block_html("TSMC Earnings", CASCADES)
    assert "AI revenue guide up." in html
    assert "Capex trimmed — cycle-top signal." in html
    assert "BULL" in html and "BEAR" in html
    assert "000660.KS" in html          # raw key displayed via display_ticker
    assert "The physical bottleneck." in html


def test_cascade_requires_earnings_word():
    assert _cascade_block_html("TSMC Technology Symposium", CASCADES) == ""


def test_cascade_alias_is_whole_word():
    # 'MU' must not fire inside an unrelated word
    assert _cascade_block_html("Amusement Earnings", CASCADES) == ""


def test_cascade_unmatched_or_empty_config():
    assert _cascade_block_html("Nokia Earnings", CASCADES) == ""
    assert _cascade_block_html("TSMC Earnings", None) == ""
    assert _cascade_block_html("TSMC Earnings", {}) == ""


def test_calendar_card_renders_cascade_for_matching_event():
    events = [{"date": "2026-07-16", "event": "TSMC Earnings", "impact": "MEDIUM",
               "type": "forward_catalyst"}]
    html = calendar_card_html(events, lane="strip", cascades=CASCADES)
    assert "AI revenue guide up." in html


def test_calendar_card_unchanged_without_cascades():
    events = [{"date": "2026-07-16", "event": "TSMC Earnings", "impact": "MEDIUM"}]
    assert calendar_card_html(events) == calendar_card_html(events, cascades=None)
    assert "BULL" not in calendar_card_html(events)
