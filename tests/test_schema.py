"""Schema guard (P1-6): fail loudly if the latest report drops a core field.

Every reader tolerates missing keys via ``.get()``, so schema drift otherwise
renders silently as "—". This validates the newest report against the fields the
dashboard actually depends on.
"""
import glob
import json

import pytest

_REQUIRED_TOP = {
    "meta", "benchmarks", "watchlist", "geopolitical",
    "events_this_week", "portfolio_snapshot",
}
_REQUIRED_META = {"report_date", "market_date"}
_REQUIRED_ENTRY = {"price", "currency", "signal"}


def _latest_report():
    files = sorted(glob.glob("data/morning_report_*.json"))
    if not files:
        pytest.skip("no report data checked out")
    with open(files[-1], encoding="utf-8") as fh:
        return files[-1], json.load(fh)


def test_latest_report_has_core_top_level_keys():
    name, rpt = _latest_report()
    missing = _REQUIRED_TOP - set(rpt)
    assert not missing, f"{name} missing top-level keys: {sorted(missing)}"


def test_latest_report_meta_keys():
    name, rpt = _latest_report()
    missing = _REQUIRED_META - set(rpt.get("meta", {}))
    assert not missing, f"{name} meta missing: {sorted(missing)}"


def test_latest_watchlist_entries_have_core_fields():
    name, rpt = _latest_report()
    wl = rpt.get("watchlist", {})
    assert wl, f"{name} has empty watchlist"
    for tk, e in wl.items():
        missing = _REQUIRED_ENTRY - set(e)
        assert not missing, f"{name} entry {tk} missing: {sorted(missing)}"
