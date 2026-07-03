"""AppTest smoke-walk of every page (review finding P5-2, now a committed test).

The review verified rerun determinism with an ad-hoc AppTest drive that was
never committed — so CI could not catch a crash in the render-only components
(pipeline_stats, terminology, masthead, watchlist drilldown). This walk boots
the real dashboard.py and visits all 7 nav targets. Live quotes are stubbed:
no network in CI.
"""
import glob

import pytest
from streamlit.testing.v1 import AppTest

import live_prices

PAGES = [
    "Briefing",
    "Watchlist",
    "Signal Tracker",
    "Pipeline Stats",
    "Scenario Log",
    "Report Comparison",
    "Terminology",
]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """dashboard.py binds fetch_live_quotes from live_prices at each script run,
    so patching the module attribute keeps every AppTest run offline."""
    monkeypatch.setattr(live_prices, "fetch_live_quotes", lambda: {})


def _boot() -> AppTest:
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = _boot()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    if page != "Briefing":  # Briefing is the boot default
        at.radio(key="page_nav").set_value(page).run()
    assert not at.exception, f"{page}: {[e.value for e in at.exception]}"
    assert len(at.markdown) > 0  # something actually rendered


# ── Nav round-trip through st.navigation ──
# The masthead radio mirrors st.navigation and issues st.switch_page; deep
# links / back-forward are Streamlit-native URL paths (verified live — AppTest
# cannot boot function pages at a path). This pins the radio→switch_page→radio
# loop in both directions without the widget clobbering the click.
def test_nav_radio_round_trip_switches_pages():
    at = _boot()
    assert at.radio(key="page_nav").value == "Briefing"
    at.radio(key="page_nav").set_value("Terminology").run()
    assert not at.exception
    assert at.radio(key="page_nav").value == "Terminology"
    assert any("Terminology" in str(m.value) for m in at.markdown)
    at.radio(key="page_nav").set_value("Briefing").run()
    assert not at.exception
    assert at.radio(key="page_nav").value == "Briefing"


def test_briefing_renders_capex_pulse_band():
    at = _boot()
    assert not at.exception
    assert any("AI Capex Pulse" in str(m.value) for m in at.markdown)


def test_briefing_capex_pulse_shows_a_verdict():
    at = _boot()
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown)
    assert any(v in page for v in
               ("INTACT", "DIGESTING", "CRACKING", "INSUFFICIENT DATA"))
