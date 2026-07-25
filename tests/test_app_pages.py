"""AppTest smoke-walk of every page (review finding P5-2, now a committed test).

The review verified rerun determinism with an ad-hoc AppTest drive that was
never committed — so CI could not catch a crash in the render-only components
(pipeline_stats, terminology, masthead, watchlist drilldown). This walk boots
the real dashboard.py and visits all 8 nav targets. Live quotes are stubbed:
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
    "Retrospective",
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


def _tracker_page_app():
    """Boot ONLY the Signal Tracker page. Widget interactions on a non-default
    page can't be driven through dashboard.py under AppTest: st.navigation
    resets to the default page on every rerun (an AppTest artifact - real
    sessions persist it), so the masthead resyncs any interaction back to
    Briefing. cache_key=None takes the uncached path.

    NOTE: keep this function's source ASCII-only. AppTest.from_function
    re-writes the extracted source to a temp script with the LOCALE encoding
    on older Streamlit (cp1252 on Windows) and reads it back as UTF-8, so any
    non-ASCII char here breaks script compilation on Windows."""
    from components.signal_tracker import render_signal_tracker_page
    from lib.data_loader import load_all_reports, load_sqlite_prices

    render_signal_tracker_page(load_all_reports(), load_sqlite_prices())


def test_tracker_scorecard_survives_empty_name_filter():
    """The scorecard is corpus-wide calibration; the name filter scopes only the
    by-name drawers. Emptying the filter must not blank the scorecard.

    Asserts on 'class="calib-grid"' (the emitted HTML) — bare 'calib-grid' would
    also match the injected theme.css on any page."""
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_tracker_page_app, default_timeout=30)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    assert 'class="calib-grid"' in " ".join(str(m.value) for m in at.markdown)

    at.multiselect[0].set_value([]).run()
    assert not at.exception, f"empty filter: {[e.value for e in at.exception]}"
    page = " ".join(str(m.value) for m in at.markdown)
    assert 'class="calib-grid"' in page, \
        "scorecard vanished when the name filter was emptied"


def _terminology_page_app():
    """Boot ONLY the Terminology page (see _tracker_page_app for why non-default
    pages can't be driven through dashboard.py). ASCII-only source, same reason."""
    from components.terminology import render_terminology_page

    render_terminology_page()


def test_terminology_defines_decay_half_life_and_shrinkage():
    """Methodology-copy rule: the calibration band's decayed/shrunk figures must
    have matching Terminology definitions (decay half-life, shrinkage)."""
    at = AppTest.from_function(_terminology_page_app, default_timeout=30)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    page = " ".join(str(m.value) for m in at.markdown)
    assert "half-life" in page
    assert "Shrinkage" in page
    assert "90" in page                # the pipeline's half-life knob, in days
    assert "50%" in page               # the skeptical hit-rate prior


def test_briefing_renders_action_card():
    """The single-action callout stays on the Briefing (design-spec §1 block 4).
    Post-overhaul it composes into the 1.55fr/1fr grid via action_card_html, so
    its eyebrow — not a separate 'Today's Trade' head — is the stable marker."""
    at = _boot()
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown)
    assert "IF YOU ONLY DO ONE THING TODAY" in page


def _capex_pulse_app():
    """Boot ONLY the AI Capex Pulse band, moved to the Fundamentals tab in the
    2026-07 overhaul. ASCII-only source (see _tracker_page_app for why)."""
    from components.briefing.capex_pulse import render_capex_pulse

    render_capex_pulse()


def test_fundamentals_renders_capex_pulse_band():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_capex_pulse_app, default_timeout=30)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    assert any("AI Capex Pulse" in str(m.value) for m in at.markdown)


def test_fundamentals_capex_pulse_shows_a_verdict():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_capex_pulse_app, default_timeout=30)
    at.run()
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown)
    assert any(v in page for v in
               ("INTACT", "DIGESTING", "CRACKING", "INSUFFICIENT DATA"))


def _watchlist_page_app():
    """Boot ONLY the Watchlist grid (see _tracker_page_app for why a non-default
    page can't be driven through dashboard.py). ASCII-only source, same reason.

    MU is fed in as a changed ticker so the Changed chip and the row's steel dot
    both have something to show regardless of which report is checked out."""
    import glob
    import json

    from components.watchlist import render_watchlist

    files = sorted(glob.glob("data/morning_report_*.json"))
    with open(files[-1], encoding="utf-8") as fh:
        report = json.load(fh)
    render_watchlist(report.get("watchlist", {}), changed_tickers={"MU"})


def test_watchlist_renders_chips_groups_gauge_and_footer():
    """The redesigned grid's four structural pieces (spec 2026-07-25)."""
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_watchlist_page_app, default_timeout=60)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    blob = " ".join(str(m.value) for m in at.markdown)
    assert 'class="tk-group"' in blob        # explicit signal groups
    assert 'class="tk-ext-track"' in blob    # the extension gauge
    assert 'class="tk-foot"' in blob         # the legend footer
    assert 'class="tk-sortline"' in blob     # the page states its own ordering
    # A real widget, so the filter survives the 60s live-price fragment rerun
    # instead of resetting to All once a minute.
    assert at.pills[0].label == "Show"


def test_watchlist_chip_actually_filters_the_book():
    """Filtering is Python-side: picking a signal must shrink the rendered rows
    AND leave exactly one group header, never an empty one."""
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_watchlist_page_app, default_timeout=60)
    at.run()
    before = " ".join(str(m.value) for m in at.markdown)
    n_groups_before = before.count('class="tk-group"')
    assert n_groups_before > 1, "fixture report has only one signal group"

    at.pills[0].set_value("HOLD").run()
    assert not at.exception, f"filtered: {[e.value for e in at.exception]}"
    after = " ".join(str(m.value) for m in at.markdown)
    assert after.count('class="tk-group"') == 1
    assert after.count('<details class="tk-details"') < \
        before.count('<details class="tk-details"')
