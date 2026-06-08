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
