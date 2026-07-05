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


def test_fetch_live_quotes_disabled_by_env(monkeypatch):
    """LIVE_QUOTES_DISABLED=1 must skip every fetch attempt entirely.

    The visual harness relies on this: a dead proxy makes each fetch FAIL fast,
    but yfinance's per-ticker fallback chain keeps the worker threads hot-looping
    retries, starving the script thread and stalling first render past the
    harness's settle timeout."""
    import live_prices

    calls = []
    monkeypatch.setattr(live_prices, "_fetch_one", lambda sym: calls.append(sym))
    monkeypatch.setenv("LIVE_QUOTES_DISABLED", "1")
    live_prices.fetch_live_quotes.clear()  # st.cache_data — don't serve a stale entry
    out = live_prices.fetch_live_quotes()
    live_prices.fetch_live_quotes.clear()  # don't poison later tests' cache
    assert calls == [], "a fetch was attempted despite LIVE_QUOTES_DISABLED"
    assert out["__meta__"]["n_ok"] == 0
    assert {k: v for k, v in out.items() if k != "__meta__"} == {}


def test_safe_read_csv_missing_file_returns_empty(tmp_path):
    assert _safe_read_csv(tmp_path / "nope.csv").empty


def test_safe_read_csv_malformed_returns_empty(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00\x00 not,a,valid\ncsv\x00file")
    out = _safe_read_csv(bad)
    assert isinstance(out, pd.DataFrame)  # never raises
