"""Tests for lib.capex — pure computations behind the AI Capex Pulse band."""
import json
from datetime import date
from pathlib import Path

import pytest

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


from lib.capex import coverage_gap_series


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


from datetime import date as _date

from lib.capex import build_chips


def _chip(chips, key):
    return next(c for c in chips if c["key"] == key)


def _capex_three_yoy(y1, y2):
    """core=[MSFT,GOOG]; two YoY points: 2025Q4 (y1%) and 2026Q1 (y2%)."""
    def q(cq, rep, v):
        return {"cq": cq, "reported": rep, "capex_usd_b": v}
    base = 10.0
    return parse_capex(_raw({
        "MSFT": [q("2024Q4", "2025-01-29", base), q("2025Q1", "2025-04-30", base),
                 q("2025Q4", "2026-01-29", base * (1 + y1 / 100)),
                 q("2026Q1", "2026-04-29", base * (1 + y2 / 100))],
        "GOOG": [q("2024Q4", "2025-02-04", base), q("2025Q1", "2025-04-24", base),
                 q("2025Q4", "2026-02-03", base * (1 + y1 / 100)),
                 q("2026Q1", "2026-04-28", base * (1 + y2 / 100))],
    }))


def test_chips_always_five_in_order_even_on_empty_inputs():
    chips = build_chips(parse_capex({}), fundamentals_history({}), _date(2026, 7, 3))
    assert [c["key"] for c in chips] == ["capex", "gap", "rev", "val", "fragile"]
    assert all(c["tone"] == "na" for c in chips)
    assert _chip(chips, "gap")["detail"] == "needs capex data"


def _capex_fixture_two_quarters():
    """core=[MSFT,GOOG] at the ACCEL_PP threshold: 2025Q4 +50.0% -> 2026Q1
    +52.0%. Shared by the accelerating-tone test and the value/remark test."""
    return _capex_three_yoy(50.0, 52.0)


def _empty_fund_df():
    """No fundamentals reports at all — shared wherever a chip test only cares
    about the capex side."""
    return fundamentals_history({})


def test_capex_chip_accelerating_at_threshold():
    chips = build_chips(_capex_fixture_two_quarters(), _empty_fund_df(),
                        _date(2026, 7, 3))
    c = _chip(chips, "capex")
    assert c["tone"] == "neutral" and c["arrow"] == "up"   # +2.0pp = ACCEL_PP


def test_capex_chip_decelerating_warns():
    chips = build_chips(_capex_three_yoy(60.0, 40.0), fundamentals_history({}),
                        _date(2026, 7, 3))
    c = _chip(chips, "capex")
    assert c["tone"] == "neutral" and c["arrow"] == "down" and "decelerating" in c["detail"]


def test_gap_chip_warns_when_negative():
    fund = fundamentals_history(GAP_REPORTS)          # medians 60/50 range
    chips = build_chips(_capex_three_yoy(60.0, 70.0), fund, _date(2026, 7, 3))
    assert _chip(chips, "gap")["tone"] == "watch"     # rev ~60 < capex 70


def _rev_fixture_falling():
    """Beneficiary revenue-growth median falling from Apr (75%) to Jul (50%).
    Shared by the falling-tone test and the value/remark/banned-vocabulary
    tests — named for what it does, not the brief's working title
    (``_rev_fixture_flat``), since the trend here is a fall, not a flatline."""
    reports = {
        "2026-04-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 90.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 60.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 70.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 30.0}}}),
    }
    return parse_capex(_raw()), fundamentals_history(reports)


def test_rev_chip_falling_warns():
    capex, fund = _rev_fixture_falling()
    chips = build_chips(capex, fund, _date(2026, 7, 3))
    c = _chip(chips, "rev")
    assert c["tone"] == "watch" and "falling" in c["detail"]


def test_valuation_chip_needs_five_reports():
    chips = build_chips(parse_capex(_raw()), fundamentals_history(SYNTH_REPORTS),
                        _date(2026, 7, 3))
    assert _chip(chips, "val")["tone"] == "na"


def _capex_fixture_with_amber_fragile():
    """fragile=[CRWV], amber-flagged with a note; core/beneficiaries unused.
    Shared by the flag/note surfacing test and the plain-English
    measure/remark test."""
    return parse_capex(_raw({"CRWV": [
        {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 6.8,
         "flag": "amber", "note": "debt-funded ramp"},
    ]}))


def test_fragile_chip_surfaces_flag_and_note():
    capex = _capex_fixture_with_amber_fragile()
    c = _chip(build_chips(capex, fundamentals_history({}), _date(2026, 7, 3)),
              "fragile")
    assert c["tone"] == "watch"
    assert "CRWV" in c["detail"] and "amber" in c["detail"] and "debt-funded ramp" in c["detail"]


def test_seed_file_parses_clean():
    raw = json.loads(Path("data/capex_quarterly.json").read_text(encoding="utf-8"))
    out = parse_capex(raw)
    assert out["core"] == ["MSFT", "GOOG", "AMZN", "META"]
    assert out["fragile"] == ["CRWV"]
    assert out["warnings"] == []
    assert all(len(out["series"][tk]) == 9 for tk in out["core"])


def test_chips_carry_tone_arrow_and_sub():
    chips = build_chips(_capex_three_yoy(50.0, 52.0),
                        fundamentals_history(GAP_REPORTS), _date(2026, 7, 3))
    capex = _chip(chips, "capex")
    assert capex["tone"] == "neutral" and capex["arrow"] == "up"   # accel = direction only
    assert all(c["sub"] for c in chips)                            # every chip self-labels


def test_capex_tone_neutral_even_when_decelerating():
    chips = build_chips(_capex_three_yoy(60.0, 40.0), fundamentals_history({}),
                        _date(2026, 7, 3))
    c = _chip(chips, "capex")
    assert c["tone"] == "neutral" and c["arrow"] == "down"


def test_rev_falling_is_watch_tone_and_down_arrow():
    reports = {
        "2026-04-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 90.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 60.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 70.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 30.0}}}),
    }
    c = _chip(build_chips(parse_capex(_raw()), fundamentals_history(reports),
                          _date(2026, 7, 3)), "rev")
    assert c["tone"] == "watch" and c["arrow"] == "down"


def test_fragile_red_is_stress_tone():
    capex = parse_capex(_raw({"CRWV": [
        {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 9.9, "flag": "red"}]}))
    c = _chip(build_chips(capex, fundamentals_history({}), _date(2026, 7, 3)), "fragile")
    assert c["tone"] == "stress"


from lib.capex import compute_verdict, pulse_verdict


def test_verdict_insufficient_when_no_gap():
    v = pulse_verdict(False, 0.0, False, False)
    assert v["state"] == "insufficient" and v["label"] == "INSUFFICIENT DATA"


def test_verdict_intact_when_gap_nonneg_and_calm():
    assert pulse_verdict(True, 0.0, False, False)["state"] == "intact"   # boundary gap == 0
    assert pulse_verdict(True, 5.0, False, False)["state"] == "intact"


def test_verdict_digesting_when_gap_negative_but_revenue_holds():
    v = pulse_verdict(True, -18.6, False, False)
    assert v["state"] == "digesting" and v["tone"] == "watch"


def test_verdict_cracking_via_fragile_red():
    assert pulse_verdict(True, 5.0, False, True)["state"] == "cracking"


def test_verdict_cracking_via_negative_gap_and_falling_revenue():
    assert pulse_verdict(True, -3.0, True, False)["state"] == "cracking"


def test_verdict_cracking_fragile_only_does_not_claim_gap_opening():
    v = pulse_verdict(True, 5.0, False, True)   # fragile red, gap positive
    assert v["state"] == "cracking"
    assert "gap is opening" not in v["gloss"]
    assert "fragile" in v["gloss"].lower()


def test_verdict_cracking_gap_driven_mentions_gap_opening():
    v = pulse_verdict(True, -5.0, True, False)  # gap negative + revenue falling
    assert v["state"] == "cracking"
    assert "gap is opening" in v["gloss"]


def test_verdict_digesting_when_gap_nonneg_but_revenue_falling():
    assert pulse_verdict(True, 5.0, True, False)["state"] == "digesting"


def test_compute_verdict_fragile_red_forces_cracking():
    fund = fundamentals_history(GAP_REPORTS)
    capex = parse_capex({
        "core_spenders": ["MSFT", "GOOG"], "fragile_tier": ["CRWV"],
        "beneficiaries": ["NVDA", "MU"],
        "series": {
            "MSFT": [{"cq": "2025Q1", "reported": "2025-04-30", "capex_usd_b": 10.0},
                     {"cq": "2026Q1", "reported": "2026-05-01", "capex_usd_b": 15.0}],
            "GOOG": [{"cq": "2025Q1", "reported": "2025-04-24", "capex_usd_b": 10.0},
                     {"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 19.0}],
            "CRWV": [{"cq": "2026Q1", "reported": "2026-05-14", "capex_usd_b": 9.9,
                      "flag": "red"}],
        },
    })
    chips = build_chips(capex, fund, _date(2026, 7, 3))
    assert compute_verdict(capex, fund, chips)["state"] == "cracking"


from lib.capex import forward_revenue_note


def test_forward_note_risen_since_quarter_says_narrow():
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 55.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 45.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 95.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 75.0}}}),
    }
    note = forward_revenue_note(_capex_with_yoy(), fundamentals_history(reports))
    assert note["direction"] == "risen" and note["hint"] == "narrow"
    assert note["now_asof"] == "2026-07-01" and note["now_pct"] == 85.0  # median(95,75)


def test_forward_note_fallen_since_quarter_says_widen():
    # GAP_REPORTS: anchored median at 05-02 is 60; latest 07-01 median is 50 → fell
    note = forward_revenue_note(_capex_with_yoy(), fundamentals_history(GAP_REPORTS))
    assert note["direction"] == "fallen" and note["hint"] == "widen"


def test_forward_note_none_when_no_fresher_report():
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
    }
    assert forward_revenue_note(_capex_with_yoy(), fundamentals_history(reports)) is None


def test_forward_note_none_when_move_is_flat():
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.2}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.1}}}),
    }
    assert forward_revenue_note(_capex_with_yoy(), fundamentals_history(reports)) is None


import re

from lib.capex import _BANNED_REMARK_TERMS


def test_capex_chip_value_and_remark_when_accelerating():
    capex = _capex_fixture_two_quarters()
    chip = _chip(build_chips(capex, _empty_fund_df(), date(2026, 7, 22)), "capex")
    assert chip["measure"] == "Capex growth"
    assert chip["value"].endswith("%")
    assert "still building" in chip["remark"]
    assert "Up from" in chip["remark"]


def test_capex_chip_degraded_row_keeps_dash_value_and_explains():
    degraded = {"core": ["MSFT"], "series": {}, "fragile": [],
                "beneficiaries": [], "warnings": []}
    chip = _chip(build_chips(degraded, _empty_fund_df(), date(2026, 7, 22)), "capex")
    assert chip["value"] == "—"
    assert chip["remark"]  # never blank — the reader must learn why


def test_rev_chip_value_and_remark_name_the_reference_month():
    capex, fund = _rev_fixture_falling()
    chip = _chip(build_chips(capex, fund, date(2026, 7, 22)), "rev")
    assert chip["measure"] == "Customer sales"
    assert chip["value"].endswith("%")
    assert re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
                     chip["remark"])


def test_capex_chip_names_its_quarter_when_only_one_is_comparable():
    """One YoY-complete quarter: the growth figure EXISTS (the coverage-gap row
    quotes it), so row 01 must print it rather than claim it cannot be computed.
    What is missing is an earlier quarter to compare against."""
    capex, fund = _gap_fixture_negative_with_forward_note()
    chip = _chip(build_chips(capex, fund, date(2026, 7, 22)), "capex")
    assert chip["value"] == "+70.0%"        # not "—" — the figure is knowable
    assert "2026Q1" in chip["remark"]       # names its own measurement point
    assert chip["tone"] == "neutral"


def _gap_fixture_negative_with_forward_note():
    """Coverage-gap chip fixture: 2026Q1 gap is negative (capex outrunning
    revenue) and a forward note is available (sales have moved since the
    gap's own anchor report). Reuses _capex_with_yoy/GAP_REPORTS — the same
    pairing proven fresh/fallen by the coverage-gap and forward-note tests
    above — so this fixture's arithmetic is already covered elsewhere."""
    return _capex_with_yoy(), fundamentals_history(GAP_REPORTS)


def _gap_fixture_no_forward_note():
    """Same capex as above, but fundamentals stop at the gap's own anchor
    report — no fresher report to build a forward clause from (mirrors
    test_forward_note_none_when_no_fresher_report)."""
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
    }
    return _capex_with_yoy(), fundamentals_history(reports)


def test_gap_chip_remark_reconciles_with_current_sales():
    """The bug this rework exists for: the gap's revenue figure and the sales
    chip's disagree because they cover different periods. The remark must say so
    — and the numbers it cites must actually be the numbers they claim to be,
    not just plausible-looking text alongside the right keywords."""
    capex, fund = _gap_fixture_negative_with_forward_note()
    chips = build_chips(capex, fund, date(2026, 7, 22))
    chip = _chip(chips, "gap")
    rev_chip = _chip(chips, "rev")
    g = coverage_gap_series(capex, fund)[-1]

    assert chip["measure"].startswith("Coverage gap (")
    assert chip["value"].endswith("pp")
    assert "only" in chip["remark"]          # names the period limit
    assert "since" in chip["remark"]         # carries the forward clause

    # The backward-looking figures must be the gap's own numbers, as formatted
    # — not just any percentage, and not each other's.
    assert f"{g['capex_yoy_pct']:+.1f}%" in chip["remark"]
    assert f"{g['rev_growth_pct']:+.1f}%" in chip["remark"]

    # The forward clause's sales figure must equal the sibling `rev` chip's
    # value — that equality is the whole point of the reconciliation.
    assert rev_chip["value"] in chip["remark"]


def test_gap_chip_remark_omits_forward_clause_when_note_absent():
    capex, fund = _gap_fixture_no_forward_note()
    chip = _chip(build_chips(capex, fund, date(2026, 7, 22)), "gap")
    g = coverage_gap_series(capex, fund)[-1]
    assert "since" not in chip["remark"]
    assert chip["remark"]
    # Even without a forward clause, the two backward-looking figures must
    # still match the gap's own numbers, as formatted.
    assert f"{g['capex_yoy_pct']:+.1f}%" in chip["remark"]
    assert f"{g['rev_growth_pct']:+.1f}%" in chip["remark"]


def test_gap_chip_degraded_keeps_dash_value():
    chip = _chip(build_chips({"core": [], "series": {}, "fragile": [],
                              "beneficiaries": [], "warnings": []},
                             _empty_fund_df(), date(2026, 7, 22)), "gap")
    assert chip["value"] == "—"
    assert chip["remark"] == "Needs at least one complete spending quarter"


def _empty_capex():
    """No capex data at all — shared wherever a chip test only cares about
    the fundamentals side."""
    return parse_capex({})


def _fund_fixture_five_reports():
    """Five reports' worth of Semis forward-PE, one ticker, each on its own
    date, so the valuation chip clears its >=5-report floor. Values climb
    across the run so the final print sits above its own 80th-percentile
    range (a hot-valuation regime) — exercises the `rich` branch."""
    dates = ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01"]
    pes = [20.0, 21.0, 22.0, 23.0, 30.0]
    reports = {d: _report({"NVDA": {"valuation": {"forward_pe": pe,
                                                  "cluster_name": "Semis"}}})
              for d, pe in zip(dates, pes, strict=True)}
    return fundamentals_history(reports)


def _fund_fixture_five_reports_within_range():
    """Same shape as ``_fund_fixture_five_reports`` but the final print sits
    INSIDE its own range — the valuation chip's healthy branch. Its remark was
    never exercised before (the banned-vocabulary test ran on a fixture that
    never cleared the five-report floor at all)."""
    dates = ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01"]
    pes = [20.0, 21.0, 22.0, 23.0, 20.5]
    reports = {d: _report({"NVDA": {"valuation": {"forward_pe": pe,
                                                  "cluster_name": "Semis"}}})
               for d, pe in zip(dates, pes, strict=True)}
    return fundamentals_history(reports)


def _fund_fixture_growth_adjusted_rich():
    """The regression fixture for the row that contradicted its own Value.

    Five Semis reports: forward P/E 20/26/28/30/21 (so the latest print, 21.0x,
    sits SEVEN POINTS BELOW its own 80th-percentile 28.4x) while the
    growth-adjusted ratio spikes on the last date (1/1/1/1/9). Only the
    growth-adjusted test fires — and the remark used to narrate the P/E range
    regardless, printing "Above its own recent range — 28.4x is the usual high"
    beside a Value of 21.0x."""
    dates = ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01"]
    pes = [20.0, 26.0, 28.0, 30.0, 21.0]
    pegs = [1.0, 1.0, 1.0, 1.0, 9.0]
    reports = {d: _report({"NVDA": {"valuation": {"forward_pe": pe,
                                                  "peg_ratio": peg,
                                                  "cluster_name": "Semis"}}})
               for d, pe, peg in zip(dates, pes, pegs, strict=True)}
    return fundamentals_history(reports)


def _capex_fixture_unflagged_fragile():
    """fragile=[CRWV] with no flag — the borrower chip's healthy branch."""
    return parse_capex(_raw({"CRWV": [
        {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 6.8},
    ]}))


def _capex_fixture_red_fragile():
    return parse_capex(_raw({"CRWV": [
        {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 9.9,
         "flag": "red"},
    ]}))


def _capex_fixture_pending_quarter():
    """core=[MSFT,GOOG] with GOOG yet to report the newest quarter — no YoY
    figure at all, so row 01 legitimately shows '—'."""
    return _two_spender_capex({"2025Q1": 10.0, "2026Q1": 15.0}, {"2025Q1": 10.0})


def test_val_chip_remark_avoids_percentile_and_peg_jargon():
    fund = _fund_fixture_five_reports()
    chip = _chip(build_chips(_empty_capex(), fund, date(2026, 7, 22)), "val")
    assert chip["measure"] == "Chip valuations"
    assert chip["value"].endswith("x")
    assert "range" in chip["remark"]


def test_val_chip_remark_matches_the_test_that_actually_fired():
    """`rich` is an OR of two independent tests; the remark must narrate the one
    that fired. Here the price is comfortably inside its range and only the
    growth-adjusted test trips, so the row may not claim the value is above a
    ceiling it prints seven points below."""
    fund = _fund_fixture_growth_adjusted_rich()
    chip = _chip(build_chips(_empty_capex(), fund, date(2026, 7, 22)), "val")
    assert chip["value"] == "21.0x"
    assert chip["tone"] == "watch"                     # the row still warns
    assert "Above" not in chip["remark"]               # ...but not about price
    assert "28.4x" not in chip["remark"]               # the unquoted ceiling
    assert "growth" in chip["remark"]
    # ...and the detail behind it (History panel) still carries both figures.
    assert "80th pct 28.4" in chip["detail"] and "PEG 9.00" in chip["detail"]


def test_val_chip_remark_narrates_price_when_price_is_what_is_rich():
    fund = _fund_fixture_five_reports()                # 20/21/22/23/30
    chip = _chip(build_chips(_empty_capex(), fund, date(2026, 7, 22)), "val")
    assert chip["tone"] == "watch"
    assert chip["remark"].startswith("Above its own recent range")


def test_fragile_chip_measure_is_plain_english():
    capex = _capex_fixture_with_amber_fragile()
    chip = _chip(build_chips(capex, _empty_fund_df(), date(2026, 7, 22)),
                "fragile")
    assert chip["measure"] == "Weakest borrower"
    assert chip["value"] == "CRWV"
    assert "Borrows" in chip["remark"]


def test_capex_and_gap_rows_do_not_contradict_each_other():
    """Spec §2 rule 4 across a PAIR of rows, not each chip alone: with exactly
    one YoY-complete quarter, row 01 used to say the capex figure could not be
    computed while row 03 quoted that very figure in its own remark."""
    capex, fund = _gap_fixture_negative_with_forward_note()
    chips = build_chips(capex, fund, date(2026, 7, 22))
    capex_chip, gap_chip = _chip(chips, "capex"), _chip(chips, "gap")
    g = coverage_gap_series(capex, fund)[-1]
    quoted = f"{g['capex_yoy_pct']:+.1f}%"

    assert quoted in gap_chip["remark"]        # row 03 quotes the figure...
    assert capex_chip["value"] == quoted       # ...and row 01 prints the same
    assert capex_chip["value"] != "—"
    # Both rows name the quarter they measure, so the reader can pair them.
    assert g["cq"] in capex_chip["remark"] and g["cq"] in gap_chip["measure"]


def test_capex_row_still_shows_a_dash_when_no_quarter_is_comparable():
    """The honest '—' survives: with no YoY-complete quarter there is no figure
    to print, and the remark says which spenders are outstanding."""
    chip = _chip(build_chips(_capex_fixture_pending_quarter(), _empty_fund_df(),
                             date(2026, 7, 22)), "capex")
    assert chip["value"] == "—" and chip["tone"] == "na"
    assert "Waiting on 1 of 2" in chip["remark"] and "2026Q1" in chip["remark"]


def test_rev_chip_remark_names_its_baseline_to_the_day():
    """Rows 02 and 03 measure from different points; row 02 must say which one,
    the way row 03 names its quarter — otherwise 'Unchanged since May' beside
    'Sales have since reached +85.2%' reads as a contradiction."""
    capex, fund = _rev_fixture_falling()
    chip = _chip(build_chips(capex, fund, date(2026, 7, 22)), "rev")
    assert "Apr 1, 2026" in chip["remark"]


# Every chip's healthy AND degraded remark, not one fixture's worth. The
# valuation and borrower chips' healthy branches went unchecked under the old
# single-fixture test (that fixture never cleared the five-report floor and
# carried no borrower rows), which is exactly how the valuation row's
# self-contradicting remark reached review.
_REMARK_FIXTURES = [
    ("all-degraded", _empty_capex, _empty_fund_df),
    ("capex-accelerating", _capex_fixture_two_quarters, _empty_fund_df),
    ("capex-decelerating", lambda: _capex_three_yoy(60.0, 40.0), _empty_fund_df),
    ("capex-steady", lambda: _capex_three_yoy(50.0, 50.5), _empty_fund_df),
    ("capex-pending-quarter", _capex_fixture_pending_quarter, _empty_fund_df),
    ("capex-one-comparable-quarter", _capex_with_yoy,
     lambda: fundamentals_history(GAP_REPORTS)),
    ("rev-falling", lambda: _rev_fixture_falling()[0],
     lambda: _rev_fixture_falling()[1]),
    ("gap-without-forward-note", lambda: _gap_fixture_no_forward_note()[0],
     lambda: _gap_fixture_no_forward_note()[1]),
    ("val-rich-on-price", _empty_capex, _fund_fixture_five_reports),
    ("val-rich-on-growth", _empty_capex, _fund_fixture_growth_adjusted_rich),
    ("val-within-range", _empty_capex, _fund_fixture_five_reports_within_range),
    ("fragile-amber", _capex_fixture_with_amber_fragile, _empty_fund_df),
    ("fragile-red", _capex_fixture_red_fragile, _empty_fund_df),
    ("fragile-unflagged", _capex_fixture_unflagged_fragile, _empty_fund_df),
]


@pytest.mark.parametrize(("capex_fx", "fund_fx"),
                         [(c, f) for _, c, f in _REMARK_FIXTURES],
                         ids=[name for name, _, _ in _REMARK_FIXTURES])
def test_no_remark_uses_banned_vocabulary(capex_fx, fund_fx):
    # All five chip builders carry `remark` — index directly (not .get) so a
    # builder that regresses and drops the key fails loudly instead of silently
    # satisfying "no banned term present".
    for chip in build_chips(capex_fx(), fund_fx(), date(2026, 7, 22)):
        remark = chip["remark"]
        assert isinstance(remark, str) and remark
        for pattern in _BANNED_REMARK_TERMS:
            assert not re.search(pattern, remark, re.I), (
                f"{chip['key']} remark uses banned term {pattern}: {remark}")


@pytest.mark.parametrize(("capex_fx", "fund_fx"),
                         [(c, f) for _, c, f in _REMARK_FIXTURES],
                         ids=[name for name, _, _ in _REMARK_FIXTURES])
def test_plate_fields_are_always_strings(capex_fx, fund_fx):
    """`measure` / `value` / `remark` are str on every return branch — the plate
    formats them straight into HTML."""
    for chip in build_chips(capex_fx(), fund_fx(), date(2026, 7, 22)):
        for field in ("measure", "value", "remark"):
            assert isinstance(chip[field], str) and chip[field], (
                f"{chip['key']}.{field}")
