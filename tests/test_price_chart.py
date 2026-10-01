"""Drill-down price chart — numbers only, no threshold marks (spec O2)."""
import re

import pandas as pd

from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.price_chart import (
    basis_note,
    nice_ticks,
    price_chart_html,
    series_until,
)
from lib import data_loader


def _rows(n=30, start=100.0):
    days = pd.bdate_range("2026-08-03", periods=n)
    return [{"date": d.strftime("%Y-%m-%d"), "price": start + i,
             "sma50": start + i / 2 if i >= 5 else None, "sma200": start - 10}
            for i, d in enumerate(days)]


def _usd(v):
    return f"&#36;{v:,.2f}"


def test_series_until_cuts_at_the_report_date_sorts_and_drops_priceless_rows():
    rows = [*reversed(_rows(10)), {"date": "2026-08-20", "price": None}]
    out = series_until(rows, "2026-08-07")
    assert [r["date"] for r in out] == ["2026-08-03", "2026-08-04", "2026-08-05",
                                        "2026-08-06", "2026-08-07"]
    assert len(series_until(rows, None)) == 10


def test_silent_with_fewer_than_two_points():
    assert price_chart_html("MU", None, None, _usd) == ""
    assert price_chart_html("MU", _rows(1), None, _usd) == ""
    assert price_chart_html("MU", _rows(5), "2026-08-01", _usd) == ""   # all after the report


def test_facts_state_first_last_change_high_and_low():
    html = price_chart_html("MU", _rows(30), None, _usd)
    assert "3 Aug → 11 Sep: &#36;100.00 → &#36;129.00 (+29.0%)" in html
    assert "high &#36;129.00 · 11 Sep" in html and "low &#36;100.00 · 3 Aug" in html


def test_three_series_with_a_legend_and_no_threshold_marks():
    html = price_chart_html("MU", _rows(30), None, _usd)
    for cls, label in (("pc-price", "Price"), ("pc-sma50", "50-day avg"),
                       ("pc-sma200", "200-day avg")):
        assert f'class="{cls}"' in html and f"{label}</span>" in html
    for gone in ("Support", "Resistance", "stop", "target", "Trigger", "70", "R:R"):
        assert gone not in re.sub(r'points="[^"]*"', "", html), gone


def test_a_missing_average_breaks_its_line_instead_of_dropping_to_zero():
    html = price_chart_html("MU", _rows(30), None, _usd)
    sma50 = re.findall(r'<polyline class="pc-sma50" points="([^"]*)"', html)
    assert len(sma50) == 1 and len(sma50[0].split()) == 25      # first 5 rows had none


def test_an_absent_series_is_left_out_of_the_legend():
    rows = [{**r, "sma200": None} for r in _rows(10)]
    html = price_chart_html("MU", rows, None, _usd)
    assert "200-day avg" not in html and "pc-sma200" not in html


def test_basis_note_names_intraday_points_for_singapore_and_korea():
    assert "inside that day's session" in basis_note("D05_SI")
    assert "inside that day's session" in basis_note("000660_KS")
    assert basis_note("NVDA").endswith("the last close.")


def test_nice_ticks_are_round_and_inside_the_range():
    assert nice_ticks(95.3, 131.2) == [100, 120]
    assert nice_ticks(1_200_000, 3_100_000) == [2_000_000, 3_000_000]
    assert nice_ticks(5, 5) == [5]


def test_drilldown_places_the_chart_between_the_chips_and_the_columns():
    html = render_drilldown_detail_html(
        "MU", {"price": 129.0, "data_anomaly": "x", "rsi_14": 50},
        report_date="2026-09-11", price_hist=_rows(30))
    assert html.index("dd-chips") < html.index('class="pc"') < html.index(">Technicals<")


def test_drilldown_without_history_has_no_chart():
    assert 'class="pc"' not in render_drilldown_detail_html("MU", {"price": 1.0})


def test_loader_keys_like_the_report_and_never_keeps_the_signal(tmp_path, monkeypatch):
    (tmp_path / "market_data.csv").write_text(
        "date,ticker,last_price,rsi_14,sma_50,sma_200,chg_pct_5d,chg_pct_1mo,signal\n"
        "2026-09-02,000660.KS,1630500,50,1881930.77,,1,2,WATCH\n"
        "2026-09-01,000660.KS,1688000,50,1907588.12,1290241.3,1,2,CAUTION\n"
        "2026-09-01,NVDA,170.5,50,180,150,1,2,WATCH\n", encoding="utf-8")
    monkeypatch.setattr(data_loader, "DATA_DIR", tmp_path)
    out = data_loader.load_price_history()
    assert set(out) == {"000660_KS", "NVDA"}
    assert [r["date"] for r in out["000660_KS"]] == ["2026-09-01", "2026-09-02"]
    assert out["000660_KS"][1] == {"date": "2026-09-02", "price": 1630500.0,
                                   "sma50": 1881930.77, "sma200": None}
    assert all("signal" not in r for rows in out.values() for r in rows)


def test_loader_is_empty_on_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(data_loader, "DATA_DIR", tmp_path)
    assert data_loader.load_price_history() == {}
