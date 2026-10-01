"""Security regression tests for the hand-built HTML sinks.

Push hostile payloads (pipeline / web-sourced fields) through the real string
builders and assert they're neutralized — text nodes escaped, URLs sanitized, no
attribute breakout. Guards the escaping contract end-to-end, not just the helpers.
"""
from components.briefing.daily_briefing import briefing_card_html
from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.row import render_ticker_details_html

XSS = "<script>alert(1)</script>"


def test_report_text_is_escaped_in_row_and_card():
    d = {"currency": "USD", "price": 100.0, "cluster": XSS,
         "thesis_highlights": ["<img src=x onerror=alert(1)>"],
         "data_anomaly": XSS}
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


def test_catalyst_and_earnings_result_text_escaped():
    d = {"currency": "USD",
         "catalyst": {"catalyst_event": XSS, "catalyst_source": "<b>x</b>"},
         "earnings_results_in_news": {"headline": XSS, "source": "<b>y</b>"}}
    out = render_drilldown_detail_html("AMD", d)
    assert "<script>" not in out
    assert "<b>x</b>" not in out and "<b>y</b>" not in out


def test_further_out_row_escaped():
    # numbers.further_out carries pipeline calendar text (event names) into the card.
    payload = {"latest": {"schema": 2, "data_date": "2026-09-29",
                          "what_matters": [{"kind": "data", "head": "x"}],
                          "numbers": {"further_out": [
                              {"date": "2026-10-14", "kind": "event", "what": XSS, "later": False},
                              {"date": "2026-11-14", "kind": "earnings", "what": XSS, "later": True,
                               "read_across": ["<b>NVDA</b>"]}]}}}
    out = briefing_card_html(payload, "2026-09-29")
    assert "<script>" not in out and "<b>NVDA</b>" not in out
