"""Briefing · Daily briefing card + the null-safety a data-only report needs.

The card renders MarketReport's hand-written daily briefing (``data/briefings.json``,
``scripts/briefing.py publish``). Pins: silent when absent, sections in reading order,
sources linked, staleness stated, escaping. The null-safety tests pin the pages that
used to crash when a report carried ``geopolitical`` / ``interconnected`` as null.
"""
from __future__ import annotations

from components.briefing.daily_briefing import briefing_card_html
from components.briefing.macro import macro_card_html, risks_card_html
from components.scenario_log import _get_probs, extract_scenario_history


def _payload(**over):
    latest = {
        "id": "20260925T010000Z", "ts_sgt": "2026-09-25T13:10:00+08:00", "data_date": "2026-09-25",
        "what_matters": ["10-year yield 5.16% (+5bp).", "Micron reports Wed 30 Sep after the close."],
        "sections": {"data_notes": "Coverage 33/33.", "overnight": "META +4.5% (1.7 sigma).",
                     "earnings": "None out.", "extra_bit": "An unlisted section."},
        "sources": [{"title": "Yahoo Finance live", "url": "https://finance.yahoo.com/x", "date": "2026-09-24"},
                    {"title": "Shipped report", "url": "file:market_data/morning_report_2026-09-25.json"}],
    }
    latest.update(over)
    return {"schema": 1, "latest": latest, "recent": []}


def test_silent_when_nothing_published():
    assert briefing_card_html({}) == ""
    assert briefing_card_html({"latest": {"what_matters": [], "sections": {}}}) == ""


def test_sections_render_in_reading_order_with_sources():
    html = briefing_card_html(_payload(), "2026-09-25")
    assert "DAILY BRIEFING · 2026-09-25" in html and "TODAY" in html and "STALE" not in html
    order = [html.index(s) for s in ("What matters", "Overnight", "Earnings", "Data notes", "Extra bit")]
    assert order == sorted(order)
    assert 'href="https://finance.yahoo.com/x"' in html
    assert "Shipped report" in html and 'href="file:' not in html        # repo paths are not links
    assert "Information, not advice" in html


def test_staleness_is_stated_not_implied():
    html = briefing_card_html(_payload(), "2026-09-28")
    assert "STALE" in html and "older than the report on screen (2026-09-28)" in html
    assert 'data-stale="1"' in html


def test_revision_is_marked():
    assert "revised" in briefing_card_html(_payload(revises="20260925T000000Z"), "2026-09-25")


def test_text_is_escaped():
    html = briefing_card_html(_payload(what_matters=["<script>alert(1)</script>"]), "2026-09-25")
    assert "<script>" not in html


def test_null_geopolitical_does_not_crash_the_briefing_cards():
    assert isinstance(macro_card_html("", None), str)
    assert isinstance(risks_card_html(None), str)


def test_null_geopolitical_does_not_crash_the_scenario_log():
    assert _get_probs({"geopolitical": None}) is not None
    df = extract_scenario_history({"2026-09-29": {"geopolitical": None}})
    assert len(df) == 0
