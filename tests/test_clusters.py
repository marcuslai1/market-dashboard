"""Tests for the Briefing cluster band (review P1-2)."""
from components.briefing.clusters import (
    _extension_breadth,
    _norm,
    _signal_mix,
)


def test_norm_dot_to_underscore():
    assert _norm("D05.SI") == "D05_SI"
    assert _norm("000660.KS") == "000660_KS"


def test_signal_mix_orders_best_to_worst():
    wl = {"A": {"signal": "AVOID"}, "B": {"signal": "WATCH"}, "C": {"signal": "WATCH"}}
    # WATCH ranks above AVOID in SIGNAL_ORDER, so it comes first.
    assert _signal_mix(["A", "B", "C"], wl) == [("WATCH", 2), ("AVOID", 1)]


def test_signal_mix_buckets_null_and_missing_last():
    wl = {"A": {"signal": "HOLD"}, "B": {"signal": None}}
    # "C" is absent from the watchlist -> also counts toward the "—" bucket.
    assert _signal_mix(["A", "B", "C"], wl) == [("HOLD", 1), ("—", 2)]


def test_extension_breadth_counts_blocked_normalized():
    er = {"blocked_tickers": ["D05_SI", "000660_KS"]}
    assert _extension_breadth(["D05.SI", "O39.SI", "000660.KS"], er) == (2, 3)


def test_extension_breadth_none_without_regime():
    assert _extension_breadth(["D05.SI"], None) is None
    assert _extension_breadth(["D05.SI"], {}) is None
