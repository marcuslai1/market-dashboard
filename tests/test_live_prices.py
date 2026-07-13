"""Tests for the live-price overlay and the safe CSV reader."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from lib.data_loader import _safe_read_csv
from live_prices import overlay_live

_ET = ZoneInfo("America/New_York")


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


# ── Extended-hours (PRE/POST) quotes ───────────────────────────────────

def test_us_session_now_windows():
    from live_prices import _us_session_now
    mon = 13  # 2026-07-13 is a Monday
    assert _us_session_now(datetime(2026, 7, mon, 4, 0, tzinfo=_ET)) == "PRE"
    assert _us_session_now(datetime(2026, 7, mon, 9, 29, tzinfo=_ET)) == "PRE"
    assert _us_session_now(datetime(2026, 7, mon, 9, 30, tzinfo=_ET)) is None
    assert _us_session_now(datetime(2026, 7, mon, 15, 59, tzinfo=_ET)) is None
    assert _us_session_now(datetime(2026, 7, mon, 16, 0, tzinfo=_ET)) == "POST"
    assert _us_session_now(datetime(2026, 7, mon, 19, 59, tzinfo=_ET)) == "POST"
    assert _us_session_now(datetime(2026, 7, mon, 20, 0, tzinfo=_ET)) is None
    assert _us_session_now(datetime(2026, 7, mon, 3, 59, tzinfo=_ET)) is None
    # Sunday: never an extended session
    assert _us_session_now(datetime(2026, 7, 12, 5, 0, tzinfo=_ET)) is None


def test_us_symbols_excludes_foreign_futures_indices():
    from live_prices import _us_symbols
    mapping = {
        "NVDA": "NVDA", "SPY": "SPY",
        "D05_SI": "D05.SI", "IFX_DE": "IFX.DE",   # foreign listings
        "WTI": "CL=F", "VIX": "^VIX",              # futures / index
        "DXY": "DX-Y.NYB",                          # dash + dot
    }
    assert _us_symbols(mapping) == {"NVDA": "NVDA", "SPY": "SPY"}


def _bars(index, data):
    """Synthetic yf.download-shaped frame: (field, ticker) MultiIndex columns."""
    cols = pd.MultiIndex.from_product([["Close"], list(data)])
    return pd.DataFrame(
        {("Close", sym): vals for sym, vals in data.items()},
        index=pd.DatetimeIndex(index),
    )[cols]


def test_ext_quotes_from_bars_picks_in_window_only():
    from live_prices import _ext_quotes_from_bars
    now = datetime(2026, 7, 13, 5, 30, tzinfo=_ET)  # Monday, PRE session
    idx = [
        datetime(2026, 7, 10, 15, 59, tzinfo=_ET),  # Friday regular (stale)
        datetime(2026, 7, 13, 4, 30, tzinfo=_ET),   # Monday pre-market
        datetime(2026, 7, 13, 5, 0, tzinfo=_ET),    # Monday pre-market (later)
    ]
    bars = _bars(idx, {
        "NVDA": [210.9, 209.0, 208.0],
        "AMD": [557.9, None, None],       # no in-window trade → absent
        "MU": [979.3, 930.0, None],       # NaN tail → earlier in-window bar
    })
    out = _ext_quotes_from_bars(bars, "PRE", now, {"NVDA": "NVDA", "AMD": "AMD", "MU": "MU"})
    assert out == {"NVDA": 208.0, "MU": 930.0}


def test_ext_quotes_from_bars_all_stale_returns_empty():
    from live_prices import _ext_quotes_from_bars
    now = datetime(2026, 7, 13, 5, 30, tzinfo=_ET)
    idx = [datetime(2026, 7, 10, 15, 59, tzinfo=_ET)]
    bars = _bars(idx, {"NVDA": [210.9]})
    assert _ext_quotes_from_bars(bars, "PRE", now, {"NVDA": "NVDA"}) == {}


def test_fetch_one_missing_prev_close_falls_back_to_price_only(monkeypatch):
    """A days-old listing (SKHYV) has last_price but no previous_close yet:
    show the live price with an unknown Δ instead of dropping the quote."""
    import sys
    import types

    import live_prices

    class _FI:
        last_price = 168.01
        previous_close = None

    class _Ticker:
        def __init__(self, sym):
            self.fast_info = _FI()

    stub = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", stub)
    assert live_prices._fetch_one("SKHYV") == {"price": 168.01, "chg_pct": None}


def test_fetch_live_quotes_merges_ext_quotes(monkeypatch):
    import live_prices as lp

    monkeypatch.setattr(lp, "_us_session_now", lambda now=None: "PRE")
    monkeypatch.setattr(lp, "_fetch_one", lambda sym: {"price": 100.0, "chg_pct": 1.0})
    monkeypatch.setattr(lp, "_fetch_ext_bars", lambda syms: object())
    monkeypatch.setattr(
        lp, "_ext_quotes_from_bars",
        lambda bars, session, now, sym_to_key: {"NVDA": 98.0},
    )
    lp.fetch_live_quotes.clear()
    out = lp.fetch_live_quotes()
    lp.fetch_live_quotes.clear()
    assert out["NVDA"]["ext_price"] == 98.0
    assert out["NVDA"]["ext_session"] == "PRE"
    assert abs(out["NVDA"]["ext_chg_pct"] - (-2.0)) < 1e-9
    assert out["__meta__"]["session"] == "PRE"
    # non-US names got no ext fields
    assert "ext_price" not in out.get("D05_SI", {})


def test_fetch_live_quotes_no_session_skips_ext(monkeypatch):
    import live_prices as lp

    called = []
    monkeypatch.setattr(lp, "_us_session_now", lambda now=None: None)
    monkeypatch.setattr(lp, "_fetch_one", lambda sym: {"price": 100.0, "chg_pct": 1.0})
    monkeypatch.setattr(lp, "_fetch_ext_bars", lambda syms: called.append(syms))
    lp.fetch_live_quotes.clear()
    out = lp.fetch_live_quotes()
    lp.fetch_live_quotes.clear()
    assert called == []
    assert out["__meta__"]["session"] is None


def test_overlay_ext_fields_win_and_tag_session():
    rpt = _report()
    live = {"AMD": {"price": 105.0, "chg_pct": 5.0,
                    "ext_price": 103.0, "ext_chg_pct": 3.0, "ext_session": "PRE"},
            "SPY": {"price": 510.0, "chg_pct": 2.0}}
    out = overlay_live(rpt, live)
    assert out["watchlist"]["AMD"]["price"] == 103.0
    assert out["watchlist"]["AMD"]["chg_pct"] == 3.0
    assert out["watchlist"]["AMD"]["live_session"] == "PRE"
    assert out["watchlist"]["AMD"]["rsi_14"] == 60          # frozen field untouched
    assert "live_session" not in out["benchmarks"]["SPY"]   # no ext → no tag
    assert rpt["watchlist"]["AMD"]["price"] == 100.0        # input not mutated


def test_overlay_none_chg_pct_is_carried():
    """SKHYV-style quote: live price, unknown Δ."""
    rpt = _report()
    out = overlay_live(rpt, {"AMD": {"price": 105.0, "chg_pct": None}})
    assert out["watchlist"]["AMD"]["price"] == 105.0
    assert out["watchlist"]["AMD"]["chg_pct"] is None


def test_safe_read_csv_missing_file_returns_empty(tmp_path):
    assert _safe_read_csv(tmp_path / "nope.csv").empty


def test_safe_read_csv_malformed_returns_empty(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00\x00 not,a,valid\ncsv\x00file")
    out = _safe_read_csv(bad)
    assert isinstance(out, pd.DataFrame)  # never raises
