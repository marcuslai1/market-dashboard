"""Tests for the Retrospective page (spec 2026-07-20-reader-retrospective-design)."""
import pandas as pd

from components.retrospective import build_month_digest, classify_call, dedupe_calls, month_label


def _log(rows):
    """Minimal signal_log-shaped frame. rows = list of (date, ticker, signal)."""
    df = pd.DataFrame(rows, columns=["date", "ticker", "signal"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_dedupe_collapses_consecutive_same_signal_run_to_first_row():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "ACCUMULATE"),
        ("2026-06-02", "AMD", "ACCUMULATE"),
        ("2026-06-03", "AMD", "ACCUMULATE"),
    ]))
    assert len(calls) == 1
    assert calls.iloc[0]["date"] == pd.Timestamp("2026-06-01")


def test_dedupe_hold_gap_splits_runs_into_two_calls():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "ACCUMULATE"),
        ("2026-06-02", "AMD", "HOLD"),
        ("2026-06-03", "AMD", "ACCUMULATE"),
    ]))
    assert len(calls) == 2
    assert list(calls["date"]) == [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-03")]


def test_dedupe_filters_non_directional_signals():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "HOLD"),
        ("2026-06-02", "NVDA", "WATCH"),
        ("2026-06-03", "TSM", "CAUTION"),
    ]))
    assert list(calls["signal"]) == ["CAUTION"]


def test_dedupe_is_per_ticker():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "CAUTION"),
        ("2026-06-01", "NVDA", "CAUTION"),
    ]))
    assert len(calls) == 2


def test_dedupe_empty_frame_returns_empty():
    assert dedupe_calls(pd.DataFrame()).empty


def _call(signal, ret20=None, hit_up=None, hit_stop=None):
    return pd.Series({
        "signal": signal,
        "return_20d": float("nan") if ret20 is None else ret20,
        "hit_upside_target": float("nan") if hit_up is None else hit_up,
        "hit_invalidation": float("nan") if hit_stop is None else hit_stop,
    })


def test_long_target_hit_is_worked():
    bucket, outcome = classify_call(_call("ACCUMULATE", ret20=16.4, hit_up=1.0, hit_stop=0.0))
    assert bucket == "worked"
    assert "hit its target" in outcome
    assert "+16.4%" in outcome


def test_long_stop_hit_is_failed():
    bucket, outcome = classify_call(_call("BUY", ret20=-5.6, hit_up=0.0, hit_stop=1.0))
    assert bucket == "failed"
    assert "stopped out" in outcome


def test_long_both_levels_hit_scores_by_20d_return_sign():
    bucket, outcome = classify_call(_call("BUY", ret20=3.0, hit_up=1.0, hit_stop=1.0))
    assert bucket == "worked"
    assert "both" in outcome
    bucket, _ = classify_call(_call("BUY", ret20=-3.0, hit_up=1.0, hit_stop=1.0))
    assert bucket == "failed"


def test_long_no_levels_hit_scores_by_return_sign():
    assert classify_call(_call("ACCUMULATE", ret20=2.0, hit_up=0.0, hit_stop=0.0))[0] == "worked"
    assert classify_call(_call("ACCUMULATE", ret20=-2.0, hit_up=0.0, hit_stop=0.0))[0] == "failed"


def test_long_flat_return_is_failed():
    # Mirrors the Signal Tracker scorecard: long calls are right only when price ROSE.
    assert classify_call(_call("BUY", ret20=0.0, hit_up=0.0, hit_stop=0.0))[0] == "failed"


def test_long_immature_is_pending():
    bucket, outcome = classify_call(_call("ACCUMULATE"))
    assert bucket == "pending"
    assert "too early" in outcome


def test_caution_drop_is_worked_rally_is_failed():
    bucket, outcome = classify_call(_call("CAUTION", ret20=-9.2))
    assert bucket == "worked"
    assert "staying out was right" in outcome
    assert "9.2%" in outcome
    bucket, outcome = classify_call(_call("AVOID", ret20=4.1))
    assert bucket == "failed"
    assert "rallied" in outcome


def test_caution_flat_counts_as_worked():
    # Scorecard scores avoid-mode with (return <= 0) as right; keep identical.
    assert classify_call(_call("CAUTION", ret20=0.0))[0] == "worked"


def test_caution_immature_is_pending():
    assert classify_call(_call("AVOID"))[0] == "pending"


def test_hit_flag_without_return_still_resolves():
    bucket, outcome = classify_call(_call("BUY", hit_up=1.0, hit_stop=0.0))
    assert bucket == "worked"
    assert "%" not in outcome  # no return available -> no percentage claimed


def test_month_label():
    assert month_label("2026-07") == "July 2026"


def _calls_frame():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-05", "2026-06-20", "2026-07-02"]),
        "ticker": ["AMD", "NVDA", "TSM"],
        "signal": ["ACCUMULATE", "CAUTION", "BUY"],
        "return_20d": [12.0, 3.0, float("nan")],
        "hit_upside_target": [1.0, float("nan"), float("nan")],
        "hit_invalidation": [0.0, float("nan"), float("nan")],
    })
    return df


def test_build_month_digest_filters_to_month_and_counts():
    d = build_month_digest(_calls_frame(), "2026-06")
    assert d["month"] == "2026-06"
    assert d["n_calls"] == 2
    assert d["n_resolved"] == 2          # AMD worked, NVDA failed
    assert d["n_worked"] == 1
    assert [r["ticker"] for r, _ in d["groups"]["worked"]] == ["AMD"]
    assert [r["ticker"] for r, _ in d["groups"]["failed"]] == ["NVDA"]
    assert d["groups"]["pending"] == []


def test_build_month_digest_pending_only_month():
    d = build_month_digest(_calls_frame(), "2026-07")
    assert d["n_calls"] == 1
    assert d["n_resolved"] == 0
    assert [r["ticker"] for r, _ in d["groups"]["pending"]] == ["TSM"]
