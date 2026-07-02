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


# ── Nav persistence: ?page= deep links survive a browser refresh ──
def test_query_param_deep_links_to_page():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.query_params["page"] = "Signal Tracker"
    at.run()
    assert not at.exception
    assert at.radio(key="page_nav").value == "Signal Tracker"


def test_invalid_query_param_falls_back_to_briefing():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.query_params["page"] = "NotAPage"
    at.run()
    assert not at.exception
    assert at.radio(key="page_nav").value == "Briefing"


def test_nav_selection_written_back_to_query_params():
    at = _boot()
    at.radio(key="page_nav").set_value("Terminology").run()
    assert not at.exception
    # AppTest surfaces query params in their multi-valued form (a list).
    assert at.query_params.get("page") in ("Terminology", ["Terminology"])
