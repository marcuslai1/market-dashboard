"""Tests for lib.capex — pure computations behind the AI Capex Pulse band."""
import json
from datetime import date
from pathlib import Path

from lib.capex import curation_age_days, parse_capex


def _raw(series=None):
    return {
        "core_spenders": ["MSFT", "GOOG"],
        "fragile_tier": ["CRWV"],
        "beneficiaries": ["NVDA", "MU"],
        "series": series or {},
    }


def test_parse_capex_empty_input_returns_empty_structure():
    for bad in ({}, None, []):
        out = parse_capex(bad)
        assert out["core"] == [] and out["series"] == {} and out["warnings"] == []


def test_parse_capex_valid_row_normalized_and_sorted():
    out = parse_capex(_raw({"MSFT": [
        {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 30.88},
        {"cq": "2025Q4", "reported": "2026-01-29", "capex_usd_b": 37.5},
    ]}))
    rows = out["series"]["MSFT"]
    assert [r["cq"] for r in rows] == ["2025Q4", "2026Q1"]  # ascending
    assert rows[1]["reported"] == date(2026, 4, 29)
    assert rows[1]["capex_usd_b"] == 30.88
    assert out["warnings"] == []


def test_parse_capex_drops_bad_rows_with_warnings_never_raises():
    out = parse_capex(_raw({
        "MSFT": [
            {"cq": "bad", "reported": "2026-04-29", "capex_usd_b": 30.9},
            {"cq": "2026Q1", "reported": "not-a-date", "capex_usd_b": 30.9},
            {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": -3},
            "not-a-dict",
            {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 30.88},
        ],
        "UNKNOWN": [{"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 1.0}],
    }))
    assert [r["cq"] for r in out["series"]["MSFT"]] == ["2026Q1"]
    assert "UNKNOWN" not in out["series"]
    assert len(out["warnings"]) == 5


def test_curation_age_uses_newest_core_reported_date():
    out = parse_capex(_raw({
        "MSFT": [{"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 30.88}],
        "GOOG": [{"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 35.67}],
        "CRWV": [{"cq": "2026Q1", "reported": "2026-06-30", "capex_usd_b": 6.8}],
    }))
    # fragile-tier CRWV must NOT count toward core curation freshness
    assert curation_age_days(out, date(2026, 7, 3)) == 65


def test_curation_age_none_when_no_core_rows():
    assert curation_age_days(parse_capex(_raw()), date(2026, 7, 3)) is None


def test_seed_file_parses_clean():
    raw = json.loads(Path("data/capex_quarterly.json").read_text(encoding="utf-8"))
    out = parse_capex(raw)
    assert out["core"] == ["MSFT", "GOOG", "AMZN", "META"]
    assert out["fragile"] == ["CRWV"]
    assert out["warnings"] == []
    assert all(len(out["series"][tk]) == 9 for tk in out["core"])
