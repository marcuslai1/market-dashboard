"""Tests for the single-source signal ranking derived from catalog order."""
from lib.catalog import SIGNAL_BULLISHNESS, SIGNAL_ORDER, SIGNAL_SORT_RANK


def test_avoid_is_a_first_class_signal():
    assert "AVOID" in SIGNAL_ORDER


def test_sort_rank_orders_best_to_worst():
    # Lower = more bullish (used for watchlist sort: BUY on top).
    assert SIGNAL_SORT_RANK["BUY"] < SIGNAL_SORT_RANK["WATCH"]
    assert SIGNAL_SORT_RANK["WATCH"] < SIGNAL_SORT_RANK["CAUTION"]
    assert SIGNAL_SORT_RANK["CAUTION"] < SIGNAL_SORT_RANK["AVOID"]


def test_bullishness_orders_worst_to_best():
    # Higher = more bullish (used for upgrade/downgrade direction).
    assert SIGNAL_BULLISHNESS["BUY"] > SIGNAL_BULLISHNESS["CAUTION"]
    assert SIGNAL_BULLISHNESS["CAUTION"] > SIGNAL_BULLISHNESS["AVOID"]


def test_ranks_cover_every_ordered_signal():
    for sig in SIGNAL_ORDER:
        assert sig in SIGNAL_SORT_RANK
        assert sig in SIGNAL_BULLISHNESS
