"""Tests for the live-price overlay and the safe CSV reader."""
import pandas as pd

from lib.data_loader import _safe_read_csv
from live_prices import overlay_live


def _report():
    return {
        "benchmarks": {"SPY": {"price": 500.0, "chg_pct": 0.1, "rsi": 55}},
        "watchlist": {
            "AMD": {"price": 100.0, "chg_pct": 1.0, "currency": "USD", "rsi_14": 60},
            "D05_SI": {"price": 40.0, "chg_pct": 0.5, "currency": "SGD"},
        },
    }


def test_overlay_updates_price_and_chg_only():
    rpt = _report()
    live = {"SPY": {"price": 510.0, "chg_pct": 2.0},
            "AMD": {"price": 105.0, "chg_pct": 5.0}}
    out = overlay_live(rpt, live)
    assert out["benchmarks"]["SPY"]["price"] == 510.0
    assert out["benchmarks"]["SPY"]["rsi"] == 55          # frozen field untouched
    assert out["watchlist"]["AMD"]["price"] == 105.0
    assert out["watchlist"]["AMD"]["rsi_14"] == 60        # frozen field untouched


def test_overlay_partial_fill_leaves_unmatched_frozen():
    rpt = _report()
    out = overlay_live(rpt, {"AMD": {"price": 105.0, "chg_pct": 5.0}})
    assert out["watchlist"]["D05_SI"]["price"] == 40.0    # no live → frozen


def test_overlay_does_not_mutate_input():
    rpt = _report()
    overlay_live(rpt, {"AMD": {"price": 999.0, "chg_pct": 9.0}})
    assert rpt["watchlist"]["AMD"]["price"] == 100.0      # original untouched


def test_overlay_empty_live_returns_report():
    rpt = _report()
    assert overlay_live(rpt, {}) is rpt


def test_safe_read_csv_missing_file_returns_empty(tmp_path):
    assert _safe_read_csv(tmp_path / "nope.csv").empty


def test_safe_read_csv_malformed_returns_empty(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00\x00 not,a,valid\ncsv\x00file")
    out = _safe_read_csv(bad)
    assert isinstance(out, pd.DataFrame)  # never raises
