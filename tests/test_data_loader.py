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
