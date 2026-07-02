"""Tests for components.briefing.macro.macro_prints_html — FRED Core-5 strip."""
from components.briefing.macro import macro_prints_html


def _ind():
    return {
        "CPI (YoY)": {"value": 3.9, "prior": 3.3, "chg": 0.6, "units": "% YoY",
                      "asof": "2026-04-01", "age_days": 68, "is_stale": True},
        "Unemployment": {"value": 4.3, "prior": 4.3, "chg": 0.0, "units": "%",
                         "asof": "2026-05-01", "age_days": 38, "is_stale": False},
        "Nonfarm payrolls": {"value": 172.0, "prior": 179.0, "chg": -7.0,
                             "units": "k jobs (MoM)", "asof": "2026-05-01",
                             "age_days": 38, "is_stale": False},
    }


def test_renders_payroll_and_pct():
    html = macro_prints_html(_ind())
    assert "+172k" in html          # payroll formatting
    assert "3.9%" in html           # pct formatting
    assert "4.3%" in html


def test_stale_flag_shown():
    html = macro_prints_html(_ind())
    assert "STALE" in html          # CPI is_stale


def test_delta_arrows():
    html = macro_prints_html(_ind())
    assert "▼7k" in html            # payroll chg -7.0
    assert "▲0.6" in html           # CPI chg +0.6


def test_gap_row_renders_na():
    html = macro_prints_html({"CPI (YoY)": {"status": "gap", "series_id": "CPIAUCSL"}})
    assert "n/a" in html.lower()


def test_empty_returns_blank():
    assert macro_prints_html({}) == ""
    assert macro_prints_html(None) == ""


# --- Release-aware freshness (known series_id) -------------------------------
# Upstream computes age_days from the FRED *observation* date (1st of the
# observation month), so a monthly print is ~40d "old" the day it is released.
# The dashboard must not parrot that as STALE: a known monthly series is stale
# only once the *next* release should already exist.

def _row(label, series_id, age_days, is_stale, asof="2026-05-01", value=4.3):
    return {label: {"value": value, "prior": value, "chg": 0.1, "units": "%",
                    "asof": asof, "age_days": age_days,
                    "series_id": series_id, "is_stale": is_stale}}


def test_monthly_fresh_print_not_stale_despite_upstream_flag():
    # May CPI viewed on Jul 2: 62d from obs date but released Jun 10 — the
    # freshest print that exists. Upstream flags it stale; dashboard must not.
    html = macro_prints_html(_row("CPI (YoY)", "CPIAUCSL", 62, True))
    assert "STALE" not in html


def test_monthly_hides_observation_age_day_count():
    html = macro_prints_html(_row("CPI (YoY)", "CPIAUCSL", 62, True))
    assert "May" in html
    assert "62d" not in html


def test_monthly_superseded_is_stale_even_if_upstream_says_fresh():
    # 80d past a May observation: the June CPI (released ~Jul 14) exists and
    # the report missed it — genuinely stale.
    html = macro_prints_html(_row("CPI (YoY)", "CPIAUCSL", 80, False))
    assert "STALE" in html


def test_pce_longer_release_lag_not_stale_at_85d():
    # PCE releases ~90d after the observation date (May print lands Jun 25;
    # June print not until Jul 30) — 85d-old May data is still the latest.
    html = macro_prints_html(_row("Core PCE (YoY)", "PCEPILFE", 85, True))
    assert "STALE" not in html


def test_daily_series_keeps_day_count():
    html = macro_prints_html(
        _row("Fed funds (eff.)", "DFF", 2, False, asof="2026-06-30", value=3.63))
    assert "2d" in html
    assert "STALE" not in html


def test_daily_series_stale_when_feed_quiet():
    html = macro_prints_html(
        _row("Fed funds (eff.)", "DFF", 12, False, asof="2026-06-20", value=3.63))
    assert "STALE" in html


def test_unknown_series_falls_back_to_upstream_flag_and_age():
    html = macro_prints_html(_row("CPI (YoY)", "NEW_SERIES_XYZ", 40, True))
    assert "STALE" in html
    assert "40d" in html
