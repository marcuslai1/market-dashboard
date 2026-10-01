"""AppTest smoke-walk of every page (review finding P5-2, now a committed test).

The review verified rerun determinism with an ad-hoc AppTest drive that was
never committed — so CI could not catch a crash in the render-only components
(terminology, masthead, watchlist drilldown). This walk boots the real
dashboard.py and visits all 3 nav targets (three tabs removed 2026-09-29; the
Signal Tracker and Review pages 2026-10-01 with the signal labels, MarketReport
spec 2026-10-01-info-only-watchlist O7). Live quotes are stubbed: no network in CI.
"""
import glob
import re

import pytest
from streamlit.testing.v1 import AppTest

import live_prices

PAGES = [
    "Briefing",
    "Watchlist",
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


def test_nav_is_exactly_the_three_pages():
    at = _boot()
    assert list(at.radio(key="page_nav").options) == PAGES


def test_sidebar_counts_tickers_from_the_watchlist_and_shows_no_signals():
    at = _boot()
    side = " ".join(str(m.value) for m in at.sidebar.markdown)
    assert re.search(r'Tickers</span><span class="status-value">\d+<', side)
    assert "Signals" not in side and "●" not in side
    assert not at.sidebar.date_input           # the Tracker-only range filter is gone


def test_masthead_kicker_drops_signal_intelligence():
    at = _boot()
    page = " ".join(str(m.value) for m in at.markdown)
    assert "Signal Intelligence" not in page
    assert "Market Data Daily" in page


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


def _terminology_page_app():
    """Boot ONLY the Terminology page. Widget interactions on a non-default
    page can't be driven through dashboard.py under AppTest: st.navigation
    resets to the default page on every rerun (an AppTest artifact - real
    sessions persist it), so the masthead resyncs any interaction back to
    Briefing.

    NOTE: keep this function's source ASCII-only. AppTest.from_function
    re-writes the extracted source to a temp script with the LOCALE encoding
    on older Streamlit (cp1252 on Windows) and reads it back as UTF-8, so any
    non-ASCII char here breaks script compilation on Windows."""
    from components.terminology import render_terminology_page

    render_terminology_page()


# ── Terminology (redesign spec 2026-07-25; facts only since 2026-10-01) ──
# The page is built for finding, so the tests are about finding: the index can
# never drift from the sections, and search must actually remove sections rather
# than merely highlight them. page_html/section_html are pure, so most of this
# needs no AppTest run.


def test_terminology_index_and_sections_cannot_drift():
    """One array drives the rail and the body."""
    from components.terminology import SECTIONS, page_html

    ids = [s["id"] for s in SECTIONS]
    assert len(set(ids)) == len(ids), f"duplicate section ids: {ids}"

    html = page_html(SECTIONS, set(ids))
    for sid in ids:
        assert html.count(f'id="{sid}"') == 1, f"{sid}: not exactly one anchor target"
        assert html.count(f'href="#{sid}"') == 1, f"{sid}: not exactly one index link"


def test_terminology_every_section_has_a_plain_answer_and_keywords():
    """Layer 1 is the whole premise: if a section has no plain answer, the
    reader who arrived for one term has nothing to read. The keyword string IS
    the search index — a section without one is unfindable."""
    from components.terminology import SECTIONS

    for sec in SECTIONS:
        assert sec["answer"].strip(), f"{sec['id']}: no plain-language answer"
        assert len(sec["kw"].split()) >= 4, f"{sec['id']}: keyword list too thin"


def test_terminology_defines_no_signal_label():
    """The sections that defined the labels went with them (spec O7)."""
    from components.terminology import SECTIONS

    ids = {s["id"] for s in SECTIONS}
    assert not ids & {"signals", "rr", "episodes", "calibration", "macro", "entry-block"}
    assert {"order", "levels", "technicals", "valuation", "earnings", "pulse",
            "limitations"} <= ids
    body = " ".join(s["answer"] + s["body"] for s in SECTIONS)
    for gone in ("ACCUMULATE", "CAUTION", "R:R", "entry block", "blocked"):
        assert gone not in body, gone


def test_terminology_history_doors_are_dated():
    """Method history is shelved separately from definition, and the date rides
    in the summary so a reader can judge relevance without opening it."""
    from components.terminology import SECTIONS, section_html

    dated = 0
    for sec in SECTIONS:
        html = section_html(sec)
        for date, label, _ in sec["history"]:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), f"{sec['id']}: {date!r}"
            assert f"Method history · {label} · {date}" in html
            dated += 1
    assert dated >= 3


def test_terminology_search_removes_non_matching_sections():
    """Section-level and decisive."""
    from components.terminology import SECTIONS

    at = AppTest.from_function(_terminology_page_app, default_timeout=30)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"

    at.text_input(key="term_search").set_value("peg").run()
    assert not at.exception, f"search: {[e.value for e in at.exception]}"
    page = " ".join(str(m.value) for m in at.markdown)
    assert 'id="valuation"' in page, "the matching section was dropped"
    assert 'id="levels"' not in page, "a non-matching section still rendered"
    assert f"1 of {len(SECTIONS)} sections matches" in page
    # The rail still lists everything: it is how a reader learns what exists.
    assert page.count("term-index-item") == len(SECTIONS)


def test_terminology_no_match_says_so():
    from components.terminology import SECTIONS

    at = AppTest.from_function(_terminology_page_app, default_timeout=30)
    at.run()
    at.text_input(key="term_search").set_value("zzzz").run()
    assert not at.exception, f"no-match: {[e.value for e in at.exception]}"
    page = " ".join(str(m.value) for m in at.markdown)
    assert "No section matches that term" in page
    assert f"0 of {len(SECTIONS)} sections match" in page


def test_terminology_carries_the_dated_era_line():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_terminology_page_app, default_timeout=30)
    at.run()
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown)
    assert 'class="term-era"' in page
    assert "this site shows facts only" in page
    for claim in ("inaccurate", "proven", "accurate", "failed", "did not work"):
        assert claim not in page.split('class="term-era"', 1)[1].split("</div>", 1)[0], claim


def test_label_era_finds_the_cutover_by_binary_search():
    from components.terminology import label_era

    dates = [f"2026-0{m}-01" for m in range(1, 10)]
    labelled = {d: d <= "2026-06-01" for d in dates}
    calls = []

    def probe(d):
        calls.append(d)
        return labelled[d]

    assert label_era(dates, probe) == ("2026-01-01", "2026-06-01", "2026-07-01")
    assert len(calls) <= 6                       # not one read per report


def test_label_era_before_the_cutover_has_no_end():
    from components.terminology import label_era

    dates = ["2026-03-12", "2026-10-01"]
    assert label_era(dates, lambda d: True) == ("2026-03-12", "2026-10-01", None)
    assert label_era([], lambda d: True) == (None, None, None)


def test_era_line_states_both_dates_and_makes_no_claim():
    from components.terminology_content import era_line_html

    before = era_line_html("2026-03-12", "2026-10-01", None)
    after = era_line_html("2026-03-12", "2026-10-02", "2026-10-05")
    assert "since 2026-03-12" in before and "2026-04-01" in before
    assert "from 2026-03-12 to 2026-10-02" in after and "from 2026-10-05" in after
    for line in (before, after):
        assert "not a finding about the labels" in line


def test_briefing_is_pulse_briefing_and_market_read_only():
    """Since 2026-09-29 the Briefing tab is the pulse strip, the daily briefing
    card and the market read. The signal blocks and the cards the report LLM
    used to write (off since 09-28) were removed — pin that they stay gone."""
    at = _boot()
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown)
    for gone in ("IF YOU ONLY DO ONE THING TODAY", "ACTIVE RISKS", "Catalysts that move signals",
                 "where each group stands", "the cycle cross-check", "THE MACRO NOTE"):
        assert gone not in page, gone
    assert "DAILY BRIEFING" in page


def _watchlist_latest_app():
    """Boot ONLY the Watchlist grid on the newest report. ASCII-only source."""
    import glob
    import json

    from components.watchlist import render_watchlist

    files = sorted(glob.glob("data/morning_report_*.json"))
    with open(files[-1], encoding="utf-8") as fh:
        report = json.load(fh)
    render_watchlist(report.get("watchlist", {}),
                     report_date=(report.get("meta") or {}).get("report_date"))


def _watchlist_oldest_app():
    """Boot ONLY the Watchlist grid on the oldest report. ASCII-only source."""
    import glob
    import json

    from components.watchlist import render_watchlist

    files = sorted(glob.glob("data/morning_report_*.json"))
    with open(files[0], encoding="utf-8") as fh:
        report = json.load(fh)
    render_watchlist(report.get("watchlist", {}),
                     report_date=(report.get("meta") or {}).get("report_date"))


@pytest.mark.parametrize("app", [_watchlist_latest_app, _watchlist_oldest_app],
                         ids=["latest", "oldest"])
def test_watchlist_renders_facts_only_on_any_report_date(app):
    """Every report date renders the same facts-only grid (spec O6): cluster
    groups, the gauge, the footer and the sort line — and no rating anywhere."""
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(app, default_timeout=60)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    blob = " ".join(str(m.value) for m in at.markdown)
    assert 'class="tk-group"' in blob
    assert 'class="tk-ext-track"' in blob
    assert 'class="tk-foot"' in blob
    assert 'class="tk-sortline"' in blob
    assert 'class="tk-earn"' in blob
    for gone in ("sig-pill", "data-signal", "tk-changed", "tk-rr", "dd-entry-block",
                 "dd-verdict", "dd-levels"):
        assert gone not in blob, gone
    assert not at.pills                          # no signal filter chips
