"""Tests for the cached asset/report loaders in ``lib.data_loader``.

These cover the performance-pass additions:
- ``load_text_asset`` — mtime-keyed cached read for large static assets (theme.css)
- ``list_report_dates`` / ``load_report`` — lazy per-date report access so hot-path
  pages (Briefing, Watchlist, masthead) don't parse all ~80 report files.
- the review-gap pass: every loader is mtime-keyed (no TTL), so a fresh pipeline
  run is visible on the next rerun instead of after a 5-minute TTL (P2-5).
"""
import glob
import json
import os
import time
from pathlib import Path

import pytest

import lib.data_loader as dl
from lib.data_loader import list_report_dates, load_report, load_text_asset


# ── P2: load_text_asset (mtime-keyed cached read) ──
def test_load_text_asset_returns_file_contents(tmp_path):
    f = tmp_path / "theme.css"
    f.write_text("body { color: red; }", encoding="utf-8")
    assert load_text_asset(f) == "body { color: red; }"


def test_load_text_asset_reflects_edits(tmp_path):
    """An edited file must not be served stale — the cache key includes mtime."""
    f = tmp_path / "theme.css"
    f.write_text("A", encoding="utf-8")
    assert load_text_asset(f) == "A"
    f.write_text("BB", encoding="utf-8")
    os.utime(f, (time.time() + 5, time.time() + 5))  # force a distinct mtime
    assert load_text_asset(f) == "BB"


# ── P3: list_report_dates / load_report (lazy per-date access) ──
def _disk_dates() -> list[str]:
    files = sorted(glob.glob("data/morning_report_*.json"))
    return [Path(f).stem.replace("morning_report_", "") for f in files]


def test_list_report_dates_matches_files_on_disk():
    expected = _disk_dates()
    if not expected:
        pytest.skip("no report data checked out")
    assert list_report_dates() == expected  # ascending, no JSON parsed


def test_load_report_returns_dict_for_existing_date():
    dates = _disk_dates()
    if not dates:
        pytest.skip("no report data checked out")
    rpt = load_report(dates[-1])
    assert isinstance(rpt, dict)
    assert "watchlist" in rpt


def test_load_report_missing_date_returns_empty_dict():
    assert load_report("1900-01-01") == {}


# ── P2-5: mtime-keyed caches — fresh pipeline output visible immediately ──
def _bump(path, seconds=5):
    """Force a distinct mtime (filesystem timestamp resolution can be coarse)."""
    t = time.time() + seconds
    os.utime(path, (t, t))


def test_load_report_reflects_rewritten_file(tmp_path, monkeypatch):
    """A regenerated report must show up without waiting out a TTL."""
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "morning_report_2026-01-01.json"
    f.write_text(json.dumps({"watchlist": {"A": {}}}), encoding="utf-8")
    assert "A" in dl.load_report("2026-01-01")["watchlist"]
    f.write_text(json.dumps({"watchlist": {"B": {}}}), encoding="utf-8")
    _bump(f)
    assert "B" in dl.load_report("2026-01-01")["watchlist"]


def test_list_report_dates_sees_new_file_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "morning_report_2026-01-01.json").write_text("{}", encoding="utf-8")
    _bump(tmp_path)
    assert dl.list_report_dates() == ["2026-01-01"]
    (tmp_path / "morning_report_2026-01-02.json").write_text("{}", encoding="utf-8")
    _bump(tmp_path, 10)
    assert dl.list_report_dates() == ["2026-01-01", "2026-01-02"]


def test_load_all_reports_reflects_rewritten_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "morning_report_2026-01-01.json"
    f.write_text(json.dumps({"meta": {"v": 1}}), encoding="utf-8")
    assert dl.load_all_reports()["2026-01-01"]["meta"]["v"] == 1
    f.write_text(json.dumps({"meta": {"v": 2}}), encoding="utf-8")
    _bump(f)
    assert dl.load_all_reports()["2026-01-01"]["meta"]["v"] == 2


def test_load_sqlite_prices_reflects_rewritten_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "market_data.csv"
    f.write_text("date,ticker\n2026-01-01,NVDA\n", encoding="utf-8")
    assert list(dl.load_sqlite_prices()["ticker"]) == ["NVDA"]
    f.write_text("date,ticker\n2026-01-01,AMD\n", encoding="utf-8")
    _bump(f)
    assert list(dl.load_sqlite_prices()["ticker"]) == ["AMD"]


# ── P7-2: data_fingerprint — the memoization cache key for derived frames ──
def test_data_fingerprint_changes_on_report_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "morning_report_2026-01-01.json"
    f.write_text("{}", encoding="utf-8")
    fp1 = dl.data_fingerprint()
    _bump(f)
    fp2 = dl.data_fingerprint()
    assert fp1 != fp2


def test_data_fingerprint_changes_on_prices_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    csv = tmp_path / "market_data.csv"
    csv.write_text("date,ticker\n", encoding="utf-8")
    fp1 = dl.data_fingerprint()
    _bump(csv)
    fp2 = dl.data_fingerprint()
    assert fp1 != fp2


def test_data_fingerprint_stable_when_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "morning_report_2026-01-01.json").write_text("{}", encoding="utf-8")
    assert dl.data_fingerprint() == dl.data_fingerprint()

# ── Macro print history (Briefing prints-grid sparklines) ──
# Reports carry no FRED series history, so the trend line is rebuilt from the
# archive: one report per calendar month, deduped by observation date.

def test_history_sample_takes_the_newest_date_in_each_ten_day_bucket():
    dates = ["2026-01-02", "2026-01-09", "2026-01-14", "2026-01-20",
             "2026-01-26", "2026-01-30"]
    assert dl._history_sample(dates, 12) == ["2026-01-09", "2026-01-20", "2026-01-30"]


def test_history_sample_is_bounded_and_keeps_the_newest_buckets():
    dates = [f"2026-{m:02d}-15" for m in range(1, 13)]
    assert dl._history_sample(dates, 3) == ["2026-10-15", "2026-11-15", "2026-12-15"]


def test_history_sample_always_keeps_the_newest_date():
    dates = [f"2026-03-{d:02d}" for d in range(1, 25)]
    assert dl._history_sample(dates, 30)[-1] == "2026-03-24"


def test_history_sample_handles_empty_corpus():
    assert dl._history_sample([], 12) == []


def _write_report(tmp_path, date_str, asof, value):
    (tmp_path / f"morning_report_{date_str}.json").write_text(
        json.dumps({"macro_indicators": {"CPI (YoY)": {"value": value, "asof": asof}}}),
        encoding="utf-8",
    )


def test_load_macro_history_dedupes_by_observation_date(tmp_path, monkeypatch):
    """Three months of reports carrying two distinct CPI observations yield two
    points — the archive stores the same print every day until the next one."""
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    _write_report(tmp_path, "2026-01-31", "2025-12-01", 3.1)
    _write_report(tmp_path, "2026-02-28", "2025-12-01", 3.1)
    _write_report(tmp_path, "2026-03-31", "2026-02-01", 3.5)
    _bump(tmp_path)
    assert dl.load_macro_history()["CPI (YoY)"] == [3.1, 3.5]


def test_load_macro_history_prefers_the_latest_revision(tmp_path, monkeypatch):
    """FRED revises prints. The newest report's value for an observation date
    wins, so the line shows what FRED says now, not what it said first."""
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    _write_report(tmp_path, "2026-01-31", "2025-12-01", 3.1)
    _write_report(tmp_path, "2026-02-28", "2025-12-01", 3.4)   # revised up
    _bump(tmp_path)
    assert dl.load_macro_history()["CPI (YoY)"] == [3.4]


def test_load_macro_history_caps_the_point_count(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    for i in range(1, 11):
        _write_report(tmp_path, f"2026-{i:02d}-28", f"2026-{i:02d}-01", float(i))
    _bump(tmp_path)
    assert dl.load_macro_history(points=4)["CPI (YoY)"] == [7.0, 8.0, 9.0, 10.0]


def test_load_macro_history_skips_gap_rows(tmp_path, monkeypatch):
    """A FRED gap row has no value; it must not enter the series as a zero."""
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "morning_report_2026-01-31.json").write_text(
        json.dumps({"macro_indicators": {"CPI (YoY)": {"status": "gap"}}}),
        encoding="utf-8",
    )
    _bump(tmp_path)
    assert dl.load_macro_history() == {}


def test_load_macro_history_empty_corpus_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    _bump(tmp_path)
    assert dl.load_macro_history() == {}


# ── Capex Pulse loaders (hand-maintained data files) ──
def test_load_capex_quarterly_returns_seeded_dict():
    d = dl.load_capex_quarterly()
    assert d.get("core_spenders") == ["MSFT", "GOOG", "AMZN", "META"]
    assert "MSFT" in d.get("series", {})


def test_load_earnings_cascades_returns_seeded_dict():
    d = dl.load_earnings_cascades()
    assert "MU" in d
    assert d["MU"]["bull"]["read"]
    assert isinstance(d["MU"]["aliases"], list)


def test_capex_loaders_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    assert dl.load_capex_quarterly() == {}
    assert dl.load_earnings_cascades() == {}


# ── Paper-book band: load_paper_nav (spec 2026-07-05-paper-book-band) ──
def test_load_paper_nav_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    df = dl.load_paper_nav()
    assert df.empty


def test_load_paper_nav_reads_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "paper_nav.csv").write_text(
        "policy_id,date,nav_units,cash_units,n_positions,spy_close,soxx_close\n"
        "v1_flat10,2026-04-19,1000000,1000000,0,522.1,201.3\n"
        "v1_flat10,2026-04-20,1004500,900000,1,524.0,203.9\n",
        encoding="utf-8",
    )
    df = dl.load_paper_nav()
    assert list(df.columns) == ["policy_id", "date", "nav_units", "cash_units",
                                "n_positions", "spy_close", "soxx_close"]
    assert len(df) == 2


# ── Trade history: load_paper_trades (spec 2026-07-17-paper-trade-history) ──
def test_load_paper_trades_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    df = dl.load_paper_trades()
    assert df.empty


def test_load_paper_trades_reads_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "paper_trades.csv").write_text(
        "policy_id,ticker,entry_date,avg_entry_price,tranches,"
        "exit_date,exit_price,exit_reason,pnl_pct,pnl_units\n"
        "v1_flat10,AMD,2026-04-20,203.43,1,2026-05-15,188.10,stop,-7.5,-7500\n"
        "v1_flat10,NVDA,2026-04-22,174.40,2,2026-06-03,216.10,stop,23.9,24100\n",
        encoding="utf-8",
    )
    df = dl.load_paper_trades()
    assert list(df.columns) == [
        "policy_id", "ticker", "entry_date", "avg_entry_price", "tranches",
        "exit_date", "exit_price", "exit_reason", "pnl_pct", "pnl_units",
    ]
    assert len(df) == 2


def test_load_paper_positions_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    assert dl.load_paper_positions().empty


def test_load_paper_positions_reads_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "paper_positions.csv").write_text(
        "policy_id,ticker,entry_date,avg_entry_price,tranches,qty,"
        "invested_units,last_close,fx_rate,stop_price,max_dd_pct\n"
        "v1_flat10,NVDA,2026-06-29,194.97,1,512.25,99874,207.40,1.0,190.43,4.9\n",
        encoding="utf-8",
    )
    df = dl.load_paper_positions()
    assert list(df.columns) == [
        "policy_id", "ticker", "entry_date", "avg_entry_price", "tranches",
        "qty", "invested_units", "last_close", "fx_rate", "stop_price",
        "max_dd_pct",
    ]
    assert len(df) == 1
