"""Unit tests for the Pipeline health page's derived figures.


The arithmetic is what this page has historically got wrong — a cumulative cost
that spanned two pricing regimes while the tile above it claimed to be
post-cutover only — so the arithmetic is what gets tested. Everything here is
pure pandas; no AppTest, no browser.
"""
import json

import pandas as pd
import pytest

from lib.pipeline_metrics import (
    CUTOVER,
    THRESHOLDS,
    breached,
    cache_stats,
    cost_stats,
    overall_status,
    post_cutover,
    prompt_composition,
    reliability,
)


def _frame(rows):
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# Two pre-cutover rows priced ~10x too high, three honest post-cutover rows.
_MIXED = _frame([
    {"date": "2026-04-01", "computed_cost_usd": 0.50,
     "cache_hit_tokens": 0, "cache_miss_tokens": 100_000},
    {"date": "2026-04-02", "computed_cost_usd": 0.60,
     "cache_hit_tokens": 0, "cache_miss_tokens": 100_000},
    {"date": "2026-05-06", "computed_cost_usd": 0.04,
     "cache_hit_tokens": 70_000, "cache_miss_tokens": 30_000},
    {"date": "2026-05-07", "computed_cost_usd": 0.05,
     "cache_hit_tokens": 60_000, "cache_miss_tokens": 40_000},
    {"date": "2026-05-08", "computed_cost_usd": 0.06,
     "cache_hit_tokens": 80_000, "cache_miss_tokens": 20_000},
])


def test_pre_cutover_rows_never_reach_an_aggregate():
    """The bug this page shipped with: cumsum ran across both pricing regimes
    while the tile above it said "post-cutover". A running total spanning two
    regimes describes neither."""
    s = cost_stats(_MIXED)
    assert s["runs"] == 3
    assert s["total"] == pytest.approx(0.15)          # not 1.25
    assert s["mean"] == pytest.approx(0.05)
    assert s["latest"] == pytest.approx(0.06)
    assert (s["series"]["date"] >= CUTOVER).all()


def test_post_cutover_is_inclusive_of_the_cutover_day():
    on_the_day = _frame([{"date": "2026-05-05", "computed_cost_usd": 0.03}])
    assert len(post_cutover(on_the_day)) == 1


def test_monthly_projection_is_the_seven_run_mean_times_cadence():
    """A cost per run is meaningless until projected — nobody reasons in
    fractions of a cent — so the projection has to be the figure people trust."""
    s = cost_stats(_MIXED)
    assert s["monthly"] == pytest.approx(s["avg7"] * 21.7)
    # The counterfactual is strictly worse than reality, or it isn't one.
    assert s["monthly_uncached"] > s["monthly"]


def test_cache_ratio_and_saving():
    c = cache_stats(_MIXED)
    assert c["latest"] == pytest.approx(0.80)          # 80k of 100k
    assert c["mean"] == pytest.approx(0.70)            # (.7 + .6 + .8) / 3
    # 210k cached tokens at $0.20/MTok saved.
    assert c["saved_total"] == pytest.approx(210_000 * 0.20 / 1_000_000)


def test_composition_sums_to_one_hundred_and_sorts_descending():
    df = _frame([{
        "date": "2026-05-06", "system_prompt_chars": 160_000,
        "watchlist_data_chars": 100_000, "tavily_chars": 36_000,
        "yfinance_chars": 34_000, "memory_chars": 18_000,
    }])
    blocks = prompt_composition(df)
    assert [b["name"] for b in blocks][0] == "System prompt"
    assert sum(b["share"] for b in blocks) == pytest.approx(100.0)
    assert all(a["chars"] >= b["chars"] for a, b in zip(blocks, blocks[1:]))


def test_thresholds_evaluate_both_directions():
    assert breached("cost", THRESHOLDS["cost"]["limit"] + 0.01)
    assert not breached("cost", THRESHOLDS["cost"]["limit"] - 0.01)
    assert breached("cache", 0.0)               # the real failure mode
    assert not breached("cache", 0.75)


def test_missing_telemetry_is_not_a_breach():
    """Absent telemetry is a gap in the record, not evidence of a problem —
    colouring it terracotta would cry wolf."""
    assert not breached("cost", None)
    assert not breached("cache", float("nan"))


def test_reliability_reports_real_warning_counts():
    """"1 validator warning" would be a fabrication: the JSON is a
    check-name -> count map and the counts are what the operator needs."""
    df = _frame([
        {"date": "2026-05-06", "validator_warnings_json": json.dumps({"a": 1})},
        {"date": "2026-05-07",
         "validator_warnings_json": json.dumps({"a": 11, "b": 25, "c": 5})},
    ])
    r = reliability(df)
    assert r["runs"] == 2
    assert r["warnings"] == 41 and r["checks"] == 3     # latest run, summed
    assert r["weekdays"] == 2 and r["missed"] == 0


def test_reliability_counts_weekdays_with_no_run():
    df = _frame([{"date": "2026-05-06"}, {"date": "2026-05-11"}])
    r = reliability(df)
    assert r["weekdays"] == 4          # Wed..Mon inclusive of weekdays only
    assert r["missed"] == 2            # Thu 07, Fri 08


def test_reliability_survives_unparseable_warning_json():
    df = _frame([{"date": "2026-05-06", "validator_warnings_json": "not json"}])
    assert reliability(df)["warnings"] == 0


def test_status_is_the_worst_cell():
    assert overall_status([{"breach": False, "near": False}])[0] == "Healthy"
    assert overall_status([{"breach": False, "near": True}])[0] == "Watch"
    assert overall_status(
        [{"breach": False, "near": True}, {"breach": True, "near": False}]
    )[0] == "Over budget"


@pytest.mark.parametrize("df", [
    pd.DataFrame(),
    _frame([{"date": "2026-04-01", "computed_cost_usd": 0.5}]),   # pre-cutover only
])
def test_empty_and_pre_cutover_only_frames_return_none_not_a_crash(df):
    assert cost_stats(df) is None
    assert cache_stats(df) is None
    assert prompt_composition(df) is None
