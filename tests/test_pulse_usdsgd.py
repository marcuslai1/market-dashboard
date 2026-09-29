"""USD/SGD in the Markets row (owner 2026-09-29: USD assets, lives in SGD).

The pulse cell names the pair, shows 4 decimals (1.2776, not 1.28) and stays
neutral ink — a currency move is good for some readers and bad for others, so
green/red would be a claim. The briefing card's tile carries a plain label.
"""
import pytest
import streamlit as st


@pytest.fixture
def markdown_capture(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(st, "markdown", lambda body, **kw: calls.append(str(body)))
    return calls


def test_pulse_cell_names_the_pair_with_four_decimals_and_no_verdict_colour(markdown_capture):
    from components.briefing.pulse import render_pulse
    render_pulse({"USDSGD": {"price": 1.2776, "chg_pct": 0.42},
                  "SPY": {"price": 752.1, "chg_pct": 0.42}})
    html = "".join(markdown_capture)
    assert '<div class="plabel">USD/SGD · S$ per US$</div>' in html
    assert '<div class="pprice">1.2776</div>' in html
    cell = html[html.index("USD/SGD · S$ per US$"):]
    assert '<div class="pdelta flat">+0.42%' in cell[:300]
    assert '<div class="pdelta up">+0.42%' in html                  # SPY keeps its sign colour
    assert "Market pulse — 6 benchmarks" in html


def test_briefing_tile_label_says_whose_currency():
    from components.briefing.daily_briefing_v2 import _BENCH_LABEL
    assert _BENCH_LABEL["USDSGD"] == "US$ vs S$ · USD/SGD"


def test_pulse_draws_no_usdsgd_cell_for_a_report_without_it(markdown_capture):
    from components.briefing.pulse import render_pulse
    render_pulse({"SPY": {"price": 752.1, "chg_pct": 0.42}})
    html = "".join(markdown_capture)
    assert "USD/SGD" not in html and "--pulse-n:5" in html
    assert html.count('class="pulse-cell"') == 5                  # a missing core benchmark still draws "—"
