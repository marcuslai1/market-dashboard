"""Security regression tests for the hand-built HTML sinks.

Push hostile payloads (LLM/web-sourced fields) through the real string builders
and assert they're neutralized — text nodes escaped, URLs sanitized, no attribute
breakout. Guards the escaping contract end-to-end, not just the helpers.
"""
from components.briefing.calendar import calendar_card_html
from components.briefing.macro import macro_card_html
from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.row import render_ticker_details_html

XSS = "<script>alert(1)</script>"


def test_writeup_text_is_escaped_in_row():
    d = {
        "signal": "BUY", "currency": "USD", "price": 100.0,
        "writeup": {"headline": XSS, "what_to_do": "<img src=x onerror=alert(1)>"},
    }
    out = render_ticker_details_html("AMD", d)
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out


def test_catalyst_javascript_url_is_dropped():
    d = {"currency": "USD",
         "catalyst": {"catalyst_event": "E", "url": "javascript:alert(1)"}}
    out = render_drilldown_detail_html("AMD", d)
    assert "javascript:" not in out


def test_catalyst_url_attribute_breakout_is_neutralized():
    d = {"currency": "USD",
         "catalyst": {"catalyst_event": "E",
                      "url": 'https://evil.com/"><script>alert(1)</script>'}}
    out = render_drilldown_detail_html("AMD", d)
    assert '"><script>' not in out
    assert "<script>" not in out


def test_support_legs_escaped_in_drilldown():
    d = {"currency": "USD", "support_legs": ["<img src=x onerror=alert(1)>"]}
    out = render_drilldown_detail_html("AMD", d)
    assert "<img" not in out


def test_avoid_source_fields_escaped():
    d = {"currency": "USD",
         "avoid_source": {"publication": "<b>x</b>", "headline_fragment": XSS}}
    out = render_drilldown_detail_html("AMD", d)
    assert "<script>" not in out
    assert "<b>x</b>" not in out


def test_macro_summary_escaped():
    out = macro_card_html(XSS, {}, "", {})
    assert "<script>" not in out


def test_calendar_event_escaped():
    out = calendar_card_html([{"date": "2026-07-01", "event": XSS, "impact": "HIGH"}])
    assert "<script>" not in out
