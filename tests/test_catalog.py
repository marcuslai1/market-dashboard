"""Catalog ticker coverage (the signal ranking left with the labels, 2026-10-01)."""
import glob
import json

from lib.catalog import CLUSTER_MAP, RETIRED_TICKERS
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
