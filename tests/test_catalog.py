"""Tests for the single-source signal ranking + catalog ticker coverage."""
import glob
import json

from lib.catalog import (
    CLUSTER_MAP,
    RETIRED_TICKERS,
    SIGNAL_BULLISHNESS,
    SIGNAL_ORDER,
    SIGNAL_SORT_RANK,
)
from live_prices import TICKER_TO_YAHOO


def _active_watchlist_tickers() -> set[str]:
    """Every non-retired ticker that appears in any report's watchlist."""
    seen: set[str] = set()
    for f in glob.glob("data/morning_report_*.json"):
        with open(f, encoding="utf-8") as fh:
            seen |= set((json.load(fh).get("watchlist") or {}).keys())
    return {t for t in seen if t not in RETIRED_TICKERS}


def test_every_active_ticker_has_cluster_and_yahoo():
    """A watchlist ticker missing from the catalog maps loses its sector label
    and its live-price overlay — guard against silent gaps (regression: SNDK)."""
    active = _active_watchlist_tickers()
    if not active:
        return  # no data checked out — nothing to assert
    missing_cluster = sorted(t for t in active if t not in CLUSTER_MAP)
    missing_yahoo = sorted(t for t in active if t not in TICKER_TO_YAHOO)
    assert not missing_cluster, f"missing from cluster map: {missing_cluster}"
    assert not missing_yahoo, f"missing from yahoo map: {missing_yahoo}"


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
