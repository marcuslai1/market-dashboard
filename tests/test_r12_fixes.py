"""Pins for the 2026-09-15 external-review (R12a + R12b-semantic) fix batch.

Each test names the finding it closes. The review's own probe file lives in
the pipeline repo's audit folder (codex-reviews/2026-09-15) and is opt-in;
these are the permanent, collected pins.
"""
from __future__ import annotations

import inspect
from datetime import date

import pandas as pd
import pytest

import components.pipeline_stats as ps_page
from components import retrospective as review
from components import signal_tracker as tracker
from lib.calls import first_of_run
from lib.capex import pulse_verdict
from lib.data_loader import _load_sqlite_prices_cached
from lib.formatters import currency_for_key, rr_display
from lib.levels import rr_level
from lib.paper_metrics import lane_trade_stats
from lib.pipeline_metrics import (
    FLASH,
    RATE_HIT_FLASH,
    RATE_HIT_NEW,
    RATE_MISS_FLASH,
    RATE_MISS_NEW,
    REPRICE,
    cache_saving_per_run,
    card_for,
    prompt_composition,
)
from lib.symbols import RETIRED_ANY_SPELLING, provider_symbol


def _frame(rows):
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ── F01 — cache saving priced on the card in force, incl. the Flash era ──
def test_f01_card_for_has_three_eras():
    assert card_for(pd.Timestamp("2026-08-16")) == (0.07, 0.27)
    assert card_for(REPRICE) == (RATE_HIT_NEW, RATE_MISS_NEW)
    assert card_for(FLASH) == (RATE_HIT_FLASH, RATE_MISS_FLASH)
    assert card_for(None) == (RATE_HIT_FLASH, RATE_MISS_FLASH)
    # Flash card = CNY 1.00 miss / 0.02 hit at 7.15
    assert pytest.approx(1.00 / 7.15) == RATE_MISS_FLASH
    assert pytest.approx(0.02 / 7.15) == RATE_HIT_FLASH


def test_f01_saving_per_run_uses_flash_rate_on_flash_rows():
    df = _frame([
        {"date": "2026-08-16", "cache_hit_tokens": 1_000_000},
        {"date": "2026-08-20", "cache_hit_tokens": 1_000_000},
        {"date": "2026-09-11", "cache_hit_tokens": 1_000_000},
    ])
    expected = (0.20 + (0.66 - 0.022) + (1.00 - 0.02) / 7.15) / 3
    assert cache_saving_per_run(df) == pytest.approx(expected)


# ── F02 — prompt shares divide by the whole prompt ──
def test_f02_composition_uses_total_prompt_chars_with_other_slice():
    df = _frame([{
        "date": "2026-09-15", "system_prompt_chars": 160_000,
        "watchlist_data_chars": 80_000, "tavily_chars": 30_000,
        "yfinance_chars": 20_000, "memory_chars": 10_000,
        "total_prompt_chars": 500_000,
    }])
    blocks = prompt_composition(df)
    by = {b["name"]: b for b in blocks}
    assert by["Other (not itemised)"]["chars"] == 200_000
    assert by["System prompt"]["share"] == pytest.approx(32.0)
    assert sum(b["share"] for b in blocks) == pytest.approx(100.0)


def test_f02_composition_without_total_column_still_normalises_itemised():
    df = _frame([{"date": "2026-09-15", "system_prompt_chars": 60,
                  "watchlist_data_chars": 40}])
    blocks = prompt_composition(df)
    assert {b["name"] for b in blocks} & {"Other (not itemised)"} == set()
    assert sum(b["share"] for b in blocks) == pytest.approx(100.0)


# ── F03 / F04 — popover names its corpus + basis; pipeline outcomes preferred ──
def _acc():
    return pd.DataFrame({"signal": ["CAUTION", "CAUTION", "BUY"],
                         "return_5d": [-1.0, 2.0, 3.0],
                         "return_20d": [-4.0, -1.0, 5.0]})


def test_f03_raw_direction_note_names_scope_not_all_history():
    note = tracker._raw_direction_note(_acc(), "CAUTION", "avoid", "calls dated X → Y")
    assert note.startswith("Raw price direction, calls dated X → Y:")
    assert "all history" not in note
    default = tracker._raw_direction_note(_acc(), "CAUTION", "avoid")
    assert "pipeline runs" in default and "all history" not in default


def test_f04_raw_direction_frame_reads_exported_outcomes_in_range():
    log = _frame([
        {"date": "2026-08-01", "ticker": "AMD", "signal": "CAUTION",
         "return_5d": -1.0, "return_20d": -3.0},
        {"date": "2026-08-02", "ticker": "AMD", "signal": "CAUTION",
         "return_5d": -2.0, "return_20d": -4.0},        # same run: not a call
        {"date": "2026-09-01", "ticker": "AMD", "signal": "CAUTION",
         "return_5d": 1.0, "return_20d": 2.0},          # second run, out of range
        {"date": "2026-08-03", "ticker": "NVDA", "signal": "HOLD",
         "return_5d": 1.0, "return_20d": 2.0},          # non-directional
    ])
    out = tracker.raw_direction_frame(log, date(2026, 8, 1), date(2026, 8, 31))
    assert len(out) == 1
    assert out.iloc[0]["return_20d"] == -3.0
    assert set(out.columns) >= {"signal", "return_5d", "return_20d"}
    assert tracker.raw_direction_frame(pd.DataFrame()).empty


def test_f04_accuracy_docstring_states_run_count_basis():
    doc = tracker.compute_signal_accuracy.__doc__
    assert "PIPELINE RUNS" in doc and "not" in doc


# ── F05 — one call-dedupe rule on both pages (HOLD splits a run) ──
def test_f05_first_of_run_splits_on_hold_and_watch():
    df = _frame([
        {"date": "2026-06-01", "ticker": "AMD", "signal": "CAUTION"},
        {"date": "2026-06-02", "ticker": "AMD", "signal": "HOLD"},
        {"date": "2026-06-03", "ticker": "AMD", "signal": "CAUTION"},
        {"date": "2026-06-04", "ticker": "AMD", "signal": "CAUTION"},
    ])
    calls = first_of_run(df)
    assert list(calls["date"].dt.day) == [1, 2, 3]
    assert len(review.dedupe_calls(df)) == 2
    prices = _frame([{"date": f"2026-06-{d:02d}", "ticker": "AMD", "last_price": 100.0 + d}
                     for d in range(1, 30)])
    sig = df.assign(price=100.0)
    acc = tracker.compute_signal_accuracy(sig, prices)
    assert len(acc) == 2                       # used to be 1 (HOLD filtered first)


# ── F06 — the producer's thin flag (episode floor) mutes the tile ──
def _ci_cell(**kw):
    cell = {"alpha_10d": 2.0, "n_alpha_10d": 30, "single_regime": False,
            "regimes_present": ["chop", "trend_up"]}
    cell.update(kw)
    return {"signal_performance": {"ACCUMULATE": cell}}


def test_f06_tile_and_readiness_honour_thin_flag():
    ci = _ci_cell(thin=True)
    html = tracker._alpha_scorecard_html(ci["signal_performance"],
                                         {"ACCUMULATE": {"n_episodes": 2}}, pd.DataFrame())
    assert "only 2 independent episodes" in html
    assert 'calib-cell thin' in html
    assert "holding up" not in html
    ok = tracker._alpha_scorecard_html(_ci_cell(thin=False)["signal_performance"], {}, pd.DataFrame())
    assert "holding up" in ok
    assert "cross-regime evidence" not in tracker._readiness_html(ci)


# ── F07 — help text names the producer's benchmark families ──
def test_f07_help_names_qqq_and_sti():
    tip = tracker._alpha_tip_text("ACCUMULATE", 1.2, "")
    assert "QQQ" in tip and "STI" in tip
    method = tracker._method_html(_ci_cell())
    assert "QQQ" in method and "SOXX for semiconductor names, SPY otherwise" not in method


# ── F08 — Review method note states the hit-flag-first rule ──
def test_f08_method_note_states_target_stop_rule():
    assert "touched its target" in review._METHOD_NOTE
    assert "touched its stop" in review._METHOD_NOTE
    assert "mirrors the Signal" not in (review.classify_call.__doc__ or "")


# ── F09 — native currency on Review price levels ──
def test_f09_currency_for_key_and_item_html():
    assert currency_for_key("D05_SI") == "SGD"
    assert currency_for_key("000660_KS") == "KRW"
    assert currency_for_key("IFX_DE") == "EUR"
    assert currency_for_key("NVDA") == "USD"
    assert currency_for_key("D05_SI", {"D05_SI": {"currency": "XYZ"}}) == "XYZ"
    row = pd.Series({"ticker": "D05_SI", "signal": "BUY", "entry_price": 41.2,
                     "upside_target": 45.0, "invalidation": 39.0,
                     "date": pd.Timestamp("2026-09-01")})
    html = review.call_item_html(row, "worked", "up +3.0%", "SGD")
    assert "@ S&#36;41.20" in html and "target S&#36;45.00" in html
    assert "@ &#36;" not in html


# ── F10 — distorted R:R without a fallback prints no ratio ──
def test_f10_distorted_without_sizing_is_na():
    rr = {"ratio": 6.0, "ratio_label": "6.0:1", "rr_distorted": True, "sizing_rr": None,
          "rr_quality": "observed"}
    assert rr_display(rr) == ("n/a", 0.0, False)
    cell = rr_level(rr)
    assert cell.value == "n/a" and "not meaningful" in cell.sub
    # with a sizing fallback the adjusted ratio still shows
    rr["sizing_rr"] = {"ratio": 3.8, "ratio_label": "3.8:1"}
    assert rr_display(rr) == ("3.8:1", 3.8, True)


# ── F11 — retired filter matches provider (dotted) symbols ──
def test_f11_retired_filter_drops_dotted_symbols(tmp_path):
    assert provider_symbol("2308_TW") == "2308.TW" and provider_symbol("COHR") == "COHR"
    assert {"2308_TW", "2308.TW", "COHR"} <= RETIRED_ANY_SPELLING
    csv = tmp_path / "market_data.csv"
    rows = ["date,ticker,last_price", "2026-09-01,2308.TW,1.0",
            "2026-09-01,COHR,2.0", "2026-09-01,NVDA,3.0"]
    csv.write_text(chr(10).join(rows) + chr(10), encoding="utf-8")
    out = _load_sqlite_prices_cached(str(csv), 1.0)
    assert list(out["ticker"]) == ["NVDA"]


# ── F12 — an empty selected range clips to nothing and says so ──
def test_f12_empty_range_warns_instead_of_showing_all_history(monkeypatch):
    telemetry = _frame([{"date": "2026-09-01", "computed_cost_usd": 0.05,
                         "cache_hit_tokens": 1, "cache_miss_tokens": 1}])
    monkeypatch.setattr(ps_page, "load_pipeline_stats", lambda: telemetry)
    monkeypatch.setattr(ps_page, "load_token_usage", lambda: pd.DataFrame())
    monkeypatch.setattr(ps_page, "render_section_head", lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(ps_page.st, "warning", lambda msg, *a, **k: seen.append(str(msg)))
    monkeypatch.setattr(ps_page.st, "markdown", lambda *a, **k: None)
    ps_page.render_pipeline_stats_page({}, date(2020, 1, 1), date(2020, 1, 2))
    assert seen and "No pipeline data" in seen[0]


# ── F13 — run-rate tile names its seven-run basis ──
def test_f13_run_rate_tile_names_seven_run_basis():
    src = inspect.getsource(ps_page)
    assert "7-run average × 21.7 runs/mo" in src
    assert "from {cost[\"runs\"]} runs in range</div>" not in src


# ── F14 — Held runs to the economic exit ──
def test_f14_held_duration_spans_entry_to_exit():
    sig = _frame([
        {"date": "2026-06-01", "ticker": "AMD", "signal": "BUY", "price": 100.0},
        {"date": "2026-06-02", "ticker": "AMD", "signal": "HOLD", "price": 101.0},
        {"date": "2026-06-11", "ticker": "AMD", "signal": "CAUTION", "price": 105.0},
    ])
    eps = tracker.build_signal_episodes(sig, pd.DataFrame())
    buy = eps[eps["signal"] == "BUY"].iloc[0]
    assert buy["exit_date"] == pd.Timestamp("2026-06-11")
    assert int(buy["duration_days"]) == 11         # was 1 (streak length)


# ── F15 — capex CRACKING gloss claims only what the rule tests ──
def test_f15_cracking_gloss_has_no_unmeasured_widening_claim():
    v = pulse_verdict(True, -5.0, True, False)
    assert v["state"] == "cracking" and "gap is opening" not in v["gloss"]


# ── F16 — tombstoned calls are 'no outcome recorded', not 'too early' ──
def test_f16_tombstone_is_no_outcome_not_too_early():
    row = pd.Series({"signal": "CAUTION", "return_20d": float("nan"),
                     "maturation_status": "non_trading_day",
                     "hit_upside_target": float("nan"), "hit_invalidation": float("nan")})
    bucket, outcome = review.classify_call(row)
    assert bucket == "pending" and outcome.startswith("no outcome recorded")
    calls = _frame([{"date": "2026-06-13", "ticker": "BE", "signal": "CAUTION",
                     "return_20d": float("nan"), "maturation_status": "non_trading_day"},
                    {"date": "2026-06-20", "ticker": "AMD", "signal": "BUY",
                     "return_20d": float("nan"), "maturation_status": None}])
    digest = review.build_month_digest(calls, "2026-06")
    board = review.month_scoreboard_html(digest, None)
    assert "1 still inside their 20-session windows" in board
    assert "1 with no outcome recorded" in board
    assert "all 2 calls are still inside" not in board
    # a plain NULL without a status keeps the old wording
    plain = pd.Series({"signal": "CAUTION", "return_20d": float("nan"),
                       "maturation_status": None})
    assert review.classify_call(plain) == ("pending", "too early to judge")


# ── F17 — exit-reason buckets cover every lane's own rule ──
def test_f17_time_and_trail_exits_land_in_the_right_bucket():
    pid = "x"
    trades = pd.DataFrame([
        {"policy_id": pid, "exit_reason": "caution_exit", "avg_entry_price": 100,
         "entry_stop": 90, "exit_price": 120, "pnl_pct": 20, "pnl_units": 20000},
        {"policy_id": pid, "exit_reason": "time_stop", "avg_entry_price": 100,
         "entry_stop": 90, "exit_price": 101, "pnl_pct": 1, "pnl_units": 1000},
        {"policy_id": pid, "exit_reason": "trail_stop", "avg_entry_price": 100,
         "entry_stop": 90, "exit_price": 110, "pnl_pct": 10, "pnl_units": 10000},
        {"policy_id": pid, "exit_reason": "stop", "avg_entry_price": 100,
         "entry_stop": 90, "exit_price": 90, "pnl_pct": -10, "pnl_units": -10000},
        {"policy_id": pid, "exit_reason": "delist_exit", "avg_entry_price": 100,
         "entry_stop": 90, "exit_price": 100, "pnl_pct": 0, "pnl_units": 0},
    ])
    by = lane_trade_stats(trades, pid)["by_reason"]
    assert by["exit_rule"]["n"] == 2 and by["exit_rule"]["mean_r"] == pytest.approx(1.05)
    assert by["stop"]["n"] == 2 and by["other"]["n"] == 1
