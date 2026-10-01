"""lib.next_earnings — the Earnings column on both report shapes.

Post-cutover reports carry ``next_earnings{date, days_until, status}``; earlier
ones only the gate block's day count and, within 14 days, the pre-earnings band.
The pipeline computes ``days_until`` as earnings date − run date in calendar
days, and the run date is ``meta.report_date``, so the derived date is exact.
"""
from datetime import date

from lib.next_earnings import (
    REPORTED,
    SCHEDULED,
    TODAY,
    UNAVAILABLE,
    days_phrase,
    next_earnings,
    short_date,
)


def test_day_count_is_dated_from_the_report_date():
    ne = next_earnings({"accumulate_gates": {"earnings_days_until": 47}}, "2026-10-01")
    assert ne.when == date(2026, 11, 17) and ne.days_until == 47 and ne.status == SCHEDULED


def test_the_band_date_wins_over_the_day_count():
    d = {"pre_earnings_band": {"earnings_date": "2026-10-14", "days_until": 13},
         "accumulate_gates": {"earnings_days_until": 13}}
    assert next_earnings(d, "2026-10-01").when == date(2026, 10, 14)


def test_released_overnight_is_reported():
    d = {"pre_earnings_band": {"earnings_date": "2026-09-30", "days_until": -1,
                               "temporal_status": "released_overnight"}}
    ne = next_earnings(d, "2026-10-01")
    assert ne.status == REPORTED and ne.when == date(2026, 9, 30)
    assert days_phrase(ne) == "reported"


def test_day_zero_is_today():
    ne = next_earnings({"accumulate_gates": {"earnings_days_until": 0}}, "2026-10-01")
    assert ne.status == TODAY and days_phrase(ne) == "today"


def test_post_cutover_field_is_read_first():
    d = {"next_earnings": {"date": "2026-11-17", "days_until": 47, "status": "scheduled"},
         "accumulate_gates": {"earnings_days_until": 3}}
    ne = next_earnings(d, "2026-10-01")
    assert ne.when == date(2026, 11, 17) and ne.days_until == 47


def test_post_cutover_unavailable_and_released():
    assert next_earnings({"next_earnings": {"status": "unavailable"}}, None).status == UNAVAILABLE
    d = {"next_earnings": {"date": "2026-09-30", "days_until": -1,
                           "status": "released_overnight"}}
    assert next_earnings(d, None).status == REPORTED


def test_pre_cutover_calendar_failure_is_unavailable_not_none():
    d = {"accumulate_gates": {"earnings_days_until": None, "abstained": [
        {"gate": "g5_no_earnings_7d",
         "reason": "earnings calendar unavailable — proximity unverifiable"}]}}
    ne = next_earnings(d, "2026-10-01")
    assert ne.status == UNAVAILABLE and days_phrase(ne) == "no calendar"


def test_released_abstention_is_not_mistaken_for_unavailable():
    d = {"accumulate_gates": {"earnings_days_until": None, "abstained": [
        {"gate": "g5_no_earnings_7d",
         "reason": "reported after the close last session — entry levels predate the print"}]}}
    assert next_earnings(d, "2026-10-01") is None


def test_no_date_at_all_is_none():
    assert next_earnings({}, "2026-10-01") is None
    assert next_earnings({"accumulate_gates": {}}, None) is None


def test_short_date_has_no_leading_zero():
    assert short_date(date(2026, 11, 5)) == "5 Nov"
    assert short_date(None) == "—"
