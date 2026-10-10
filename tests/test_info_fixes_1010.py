"""MarketReport's 2026-10-10 information fixes (PIPELINE_FEATURES §127), as the
site shows them: Yahoo's estimated earnings dates, a date the company confirmed,
and the volume ratio on a market still trading when the report ran (SGX / KRX
at 12:05 SGT). Plain words, no colour."""
from __future__ import annotations

from components.briefing.daily_briefing_v2 import _vol
from components.terminology_content import INFO_FIXES_SINCE
from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.row import earnings_cell_html
from lib.next_earnings import next_earnings


def _ne(**kw):
    return {"next_earnings": {"date": "2026-10-28", "days_until": 19, "status": "scheduled", **kw}}


# ── earnings dates ─────────────────────────────────────────────────────────────

def test_an_estimated_date_says_so_in_the_cell_and_the_drawer():
    html = earnings_cell_html(_ne(date_estimated=True), "2026-10-09")
    assert '<div class="tk-earn-date">28 Oct</div>' in html
    assert '<div class="tk-earn-sub">est. · in 19 d</div>' in html
    drawer = render_drilldown_detail_html("META", _ne(date_estimated=True), report_date="2026-10-09")
    assert "28 Oct 2026 · est. · in 19 d — Yahoo's estimate; the company has not announced the date" in drawer


def test_a_confirmed_date_says_so_in_the_drawer_only():
    d = _ne(date_source="confirmed", date_confirmed_by="Samsung IR events page")
    assert '<div class="tk-earn-sub">in 19 d</div>' in earnings_cell_html(d, "2026-10-09")
    drawer = render_drilldown_detail_html("005930_KS", d, report_date="2026-10-09")
    assert "28 Oct 2026 · in 19 d — date confirmed by the company" in drawer


def test_old_reports_read_as_before():
    ne = next_earnings({"next_earnings": {"date": "2026-11-17", "days_until": 47,
                                          "status": "scheduled"}}, "2026-10-01")
    assert (ne.estimated, ne.confirmed) == (False, False)
    assert '<div class="tk-earn-sub">in 47 d</div>' in earnings_cell_html(
        {"next_earnings": {"date": "2026-11-17", "days_until": 47, "status": "scheduled"}},
        "2026-10-01")


def test_no_colour_on_the_new_markers():
    html = earnings_cell_html(_ne(date_estimated=True), "2026-10-09")
    assert "tone" not in html and "color" not in html


# ── volume ─────────────────────────────────────────────────────────────────────

def test_open_market_volume_reads_against_the_same_time_of_day():
    html = render_drilldown_detail_html("O39_SI", {"vol_ratio": 7.51, "vol_basis": "same_time_of_day"})
    assert "7.51× usual by this time of day" in html
    assert "10-session avg" not in html


def test_open_market_volume_withheld_says_why():
    html = render_drilldown_detail_html("O39_SI", {"vol_ratio": None, "vol_basis": "session_open"})
    assert "— (market still open)" in html


def test_closed_market_volume_reads_as_before():
    assert "1.42× 10-session avg" in render_drilldown_detail_html("NVDA", {"vol_ratio": 1.42})


def test_briefing_card_labels_a_same_time_ratio():
    assert _vol({"vol_ratio": 7.51, "vol_basis": "same_time_of_day"}) == "7.51× usual so far"
    assert _vol({"vol_ratio": 1.94}) == "1.94×"


# ── definitions ────────────────────────────────────────────────────────────────

def test_terminology_defines_the_new_readings():
    from components.terminology_content import SECTIONS
    text = " ".join(str(s) for s in SECTIONS)
    assert "usual by this time of day" in text
    assert "“est.” means Yahoo itself marks the date as an estimate" in text
    assert "market roundups fill a slot only when nothing else is there" in text
    assert INFO_FIXES_SINCE == "2026-10-12"
