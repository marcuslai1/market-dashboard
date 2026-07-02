"""Tests for the cached asset/report loaders in ``lib.data_loader``.

These cover the performance-pass additions:
- ``load_text_asset`` — mtime-keyed cached read for large static assets (theme.css)
- ``list_report_dates`` / ``load_report`` — lazy per-date report access so hot-path
  pages (Briefing, Watchlist, masthead) don't parse all ~80 report files.
"""
import glob
import os
import time
from pathlib import Path

import pytest

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
