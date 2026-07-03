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


from lib.capex import core_capex_yoy, pending_quarter


def _two_spender_capex(msft, goog):
    """Build parsed capex for core=[MSFT, GOOG] from {cq: capex_b} dicts."""
    def rows(m):
        return [{"cq": cq, "reported": "2026-04-29", "capex_usd_b": v}
                for cq, v in m.items()]
    return parse_capex(_raw({"MSFT": rows(msft), "GOOG": rows(goog)}))


def test_core_capex_yoy_computes_only_complete_quarters():
    capex = _two_spender_capex(
        {"2025Q1": 10.0, "2026Q1": 15.0},
        {"2025Q1": 10.0},  # GOOG missing 2026Q1 → that quarter incomplete
    )
    out = core_capex_yoy(capex)
    assert [r["cq"] for r in out] == ["2025Q1"]
    assert out[0]["total_b"] == 20.0
    assert out[0]["yoy_pct"] is None  # no 2024Q1 anywhere


def test_core_capex_yoy_pct_math():
    capex = _two_spender_capex(
        {"2025Q1": 10.0, "2026Q1": 15.0},
        {"2025Q1": 10.0, "2026Q1": 19.0},
    )
    out = core_capex_yoy(capex)
    latest = out[-1]
    assert latest["cq"] == "2026Q1"
    assert latest["total_b"] == 34.0 and latest["prior_b"] == 20.0
    assert latest["yoy_pct"] == 70.0


def test_pending_quarter_reports_missing_spenders():
    capex = _two_spender_capex(
        {"2025Q1": 10.0, "2026Q1": 15.0},
        {"2025Q1": 10.0},
    )
    assert pending_quarter(capex) == {"cq": "2026Q1", "have": ["MSFT"],
                                      "missing": ["GOOG"]}


def test_pending_quarter_none_when_complete():
    capex = _two_spender_capex({"2025Q1": 10.0}, {"2025Q1": 10.0})
    assert pending_quarter(capex) is None


import math

from lib.capex import fundamentals_history


def _report(entries):
    return {"watchlist": entries}


SYNTH_REPORTS = {
    "2026-06-01": _report({
        "NVDA": {"valuation": {"revenue_growth_pct": 80.0, "fcf_yield_pct": 1.0,
                               "forward_pe": 30.0, "peg_ratio": 0.6,
                               "cluster_name": "Semis",
                               "analyst_consensus": {"earnings_growth_pct": 200.0}}},
        "MU": {"valuation": {"revenue_growth_pct": 40.0, "forward_pe": 12.0,
                             "cluster_name": "Semis"}},
        "D05_SI": {"no_valuation_here": True},
    }),
    "2026-07-01": _report({
        "NVDA": {"valuation": {"revenue_growth_pct": 85.2, "forward_pe": 15.5,
                               "cluster_name": "Semis"}},
    }),
}


def test_fundamentals_history_shape_and_order():
    df = fundamentals_history(SYNTH_REPORTS)
    assert list(df.columns) == ["date", "ticker", "cluster", "revenue_growth_pct",
                                "fcf_yield_pct", "forward_pe", "peg_ratio",
                                "earnings_growth_pct"]
    assert len(df) == 3  # D05_SI has no valuation dict → skipped
    assert list(df["date"]) == sorted(df["date"])


def test_fundamentals_history_values_and_nans():
    df = fundamentals_history(SYNTH_REPORTS)
    nvda_jun = df[(df["ticker"] == "NVDA") & (df["date"] == "2026-06-01")].iloc[0]
    assert nvda_jun["earnings_growth_pct"] == 200.0
    mu = df[df["ticker"] == "MU"].iloc[0]
    assert math.isnan(mu["peg_ratio"]) and math.isnan(mu["earnings_growth_pct"])
    assert mu["cluster"] == "Semis"


def test_fundamentals_history_empty_input():
    df = fundamentals_history({})
    assert df.empty and "revenue_growth_pct" in df.columns


from lib.capex import coverage_gap_series, current_read


def _capex_with_yoy(rep_2026q1="2026-05-01"):
    """core=[MSFT,GOOG]; 2026Q1 complete with YoY (2025Q1 present)."""
    return parse_capex(_raw({
        "MSFT": [{"cq": "2025Q1", "reported": "2025-04-30", "capex_usd_b": 10.0},
                 {"cq": "2026Q1", "reported": rep_2026q1, "capex_usd_b": 15.0}],
        "GOOG": [{"cq": "2025Q1", "reported": "2025-04-24", "capex_usd_b": 10.0},
                 {"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 19.0}],
    }))


GAP_REPORTS = {
    "2026-04-15": _report({"NVDA": {"valuation": {"revenue_growth_pct": 90.0}},
                           "MU": {"valuation": {"revenue_growth_pct": 50.0}}}),
    "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                           "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
    "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 70.0}},
                           "MU": {"valuation": {"revenue_growth_pct": 30.0}}}),
}


def test_gap_anchors_revenue_at_first_report_after_quarter_complete():
    fund = fundamentals_history(GAP_REPORTS)
    gaps = coverage_gap_series(_capex_with_yoy(), fund)
    assert len(gaps) == 1
    g = gaps[0]
    # quarter complete 2026-05-01 (last core report) → first report on/after = 05-02
    assert g["rev_asof"] == "2026-05-02"
    assert g["rev_growth_pct"] == 60.0          # median(80, 40)
    assert g["capex_yoy_pct"] == 70.0
    assert g["gap_pp"] == -10.0                 # 60 − 70: capex outrunning revenue


def test_gap_falls_back_to_latest_report_when_none_after_anchor():
    fund = fundamentals_history(GAP_REPORTS)
    gaps = coverage_gap_series(_capex_with_yoy(rep_2026q1="2026-08-01"), fund)
    assert gaps[0]["rev_asof"] == "2026-07-01"  # latest available


def test_gap_empty_when_no_beneficiary_data():
    gaps = coverage_gap_series(_capex_with_yoy(), fundamentals_history({}))
    assert gaps == []


def test_current_read_uses_latest_report():
    fund = fundamentals_history(GAP_REPORTS)
    cr = current_read(_capex_with_yoy(), fund)
    assert cr["rev_asof"] == "2026-07-01"
    assert cr["rev_growth_pct"] == 50.0         # median(70, 30)
    assert cr["capex_cq"] == "2026Q1" and cr["gap_pp"] == -20.0


def test_current_read_none_without_yoy():
    capex = _two_spender_capex({"2026Q1": 15.0}, {"2026Q1": 19.0})  # no prior year
    assert current_read(capex, fundamentals_history(GAP_REPORTS)) is None


def test_seed_file_parses_clean():
    raw = json.loads(Path("data/capex_quarterly.json").read_text(encoding="utf-8"))
    out = parse_capex(raw)
    assert out["core"] == ["MSFT", "GOOG", "AMZN", "META"]
    assert out["fragile"] == ["CRWV"]
    assert out["warnings"] == []
    assert all(len(out["series"][tk]) == 9 for tk in out["core"])
