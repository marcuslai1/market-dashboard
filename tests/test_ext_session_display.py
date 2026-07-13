"""Extended-hours (PRE/POST) tags across the display surfaces.

Captures st.markdown output rather than driving AppTest: these components are
pure emitters and the tag is a string-presence check.
"""
import pytest
import streamlit as st


@pytest.fixture
def markdown_capture(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        st, "markdown", lambda body, **kw: calls.append(str(body))
    )
    return calls


def test_pulse_cell_tags_extended_session(markdown_capture):
    from components.briefing.pulse import render_pulse
    render_pulse({
        "SPY": {"price": 752.1, "chg_pct": -0.4, "live_session": "PRE"},
        "VIX": {"price": 16.27, "chg_pct": 8.25},
    })
    html = "".join(markdown_capture)
    assert 'class="ext-tag"' in html
    assert ">PRE</span>" in html
    assert html.count("ext-tag") == 1      # only the tagged benchmark


def test_pulse_no_session_no_tag(markdown_capture):
    from components.briefing.pulse import render_pulse
    render_pulse({"SPY": {"price": 754.95, "chg_pct": 0.01}})
    assert "ext-tag" not in "".join(markdown_capture)


def test_action_card_delta_suffix_reflects_session(markdown_capture):
    from components.briefing.action_card import render_action_card
    wl = {"NVDA": {"signal": "WATCH", "price": 208.0, "chg_pct": -1.4,
                   "currency": "USD", "live_session": "PRE"}}
    render_action_card(wl, [])
    html = "".join(markdown_capture)
    assert "pre-mkt" in html
    assert "% today" not in html


def test_action_card_delta_suffix_regular_session(markdown_capture):
    from components.briefing.action_card import render_action_card
    wl = {"NVDA": {"signal": "WATCH", "price": 210.96, "chg_pct": 0.19,
                   "currency": "USD"}}
    render_action_card(wl, [])
    html = "".join(markdown_capture)
    assert "today" in html
    assert "pre-mkt" not in html and "after-hrs" not in html


def test_live_caption_names_the_session(markdown_capture):
    from lib.pills import _render_live_caption
    live = {"__meta__": {"fetched_at": "2026-07-13T09:30:00+00:00",
                         "n_ok": 38, "n_total": 39, "session": "PRE"}}
    _render_live_caption(live, enabled=True)
    html = "".join(markdown_capture)
    assert "PRE-MARKET" in html


def test_live_caption_regular_session_unchanged(markdown_capture):
    from lib.pills import _render_live_caption
    live = {"__meta__": {"fetched_at": "2026-07-13T09:30:00+00:00",
                         "n_ok": 38, "n_total": 39, "session": None}}
    _render_live_caption(live, enabled=True)
    html = "".join(markdown_capture)
    assert "38/39 quotes" in html
    assert "PRE-MARKET" not in html and "AFTER-HOURS" not in html
