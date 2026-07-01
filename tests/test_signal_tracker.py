"""Tests for the credibility-critical Signal Tracker math.

Covers episode construction (trade-economics exits, ticker-format conversion,
AVOID handling) and forward-return accuracy. These are the numbers the
dashboard's track record rests on.
"""
import pandas as pd

from components.signal_tracker import (
    _classify_episode_verdict,
    build_signal_episodes,
    compute_signal_accuracy,
)


def _sig_df(rows):
    """rows = list of (date_str, ticker, signal, price)."""
    return pd.DataFrame(
        [
            {"date": pd.to_datetime(d), "ticker": tk, "signal": s, "price": p}
            for d, tk, s, p in rows
        ]
    )


def _prices_df(rows):
    """rows = list of (date_str, ticker, last_price)."""
    return pd.DataFrame(
        [
            {"date": pd.to_datetime(d), "ticker": tk, "last_price": lp}
            for d, tk, lp in rows
        ]
    )


# ── 2.1 ticker-format conversion for the active-episode latest price ──
def test_active_episode_uses_latest_db_price_for_foreign_ticker():
    """An active SGX episode must value its open position at the latest price
    from the price table (dot-form ticker), not the stale in-episode price."""
    sig = _sig_df([("2026-01-05", "D05_SI", "BUY", 30.0)])
    prices = _prices_df(
        [("2026-01-05", "D05.SI", 30.0), ("2026-02-01", "D05.SI", 33.0)]
    )
    eps = build_signal_episodes(sig, prices)
    row = eps[eps["ticker"] == "D05_SI"].iloc[0]
    assert row["is_active"]
    assert row["exit_price"] == 33.0
    assert round(row["return_pct"], 4) == 10.0


# ── 2.2 AVOID handling ──
def test_avoid_closes_a_buy_episode():
    """An AVOID that follows a BUY closes the BUY position (like CAUTION)."""
    sig = _sig_df(
        [("2026-01-05", "AMD", "BUY", 100.0), ("2026-01-06", "AMD", "AVOID", 90.0)]
    )
    eps = build_signal_episodes(sig, _prices_df([]))
    buy = eps[eps["signal"] == "BUY"].iloc[0]
    assert not buy["is_active"]
    assert buy["exit_price"] == 90.0
    assert round(buy["return_pct"], 4) == -10.0


def test_avoid_episode_is_scored():
    """A closed AVOID episode gets a directional verdict; a drop = avoided well."""
    sig = _sig_df(
        [("2026-01-05", "AMD", "AVOID", 100.0), ("2026-01-06", "AMD", "BUY", 90.0)]
    )
    eps = build_signal_episodes(sig, _prices_df([]))
    avoid = eps[eps["signal"] == "AVOID"].iloc[0]
    assert avoid["verdict"] == "✓ avoided"


def test_classify_verdict_avoid():
    assert _classify_episode_verdict("AVOID", -5.0, None, False) == "✓ avoided"
    assert _classify_episode_verdict("AVOID", 5.0, None, False) == "✗ wrong"


def test_compute_accuracy_includes_avoid():
    sig = _sig_df(
        [("2026-01-05", "AMD", "AVOID", 100.0)]
        + [(f"2026-01-{6 + i:02d}", "AMD", "HOLD", 100.0) for i in range(6)]
    )
    prices = _prices_df(
        [(f"2026-01-{5 + i:02d}", "AMD", 100.0 - i) for i in range(7)]
    )
    acc = compute_signal_accuracy(sig, prices)
    assert "AVOID" in set(acc["signal"])


# ── 2.3 SPY benchmark only for US tickers ──
def test_spy_benchmark_suppressed_for_foreign_ticker():
    sig = _sig_df([("2026-01-05", "IFX_DE", "BUY", 30.0)])
    prices = _prices_df(
        [(f"2026-01-{5 + i:02d}", "IFX.DE", 30.0 + i) for i in range(7)]
        + [(f"2026-01-{5 + i:02d}", "SPY", 500.0 + i) for i in range(7)]
    )
    acc = compute_signal_accuracy(sig, prices)
    row = acc.iloc[0]
    assert pd.isna(row["spy_5d"])


# ── edge cases (characterization) ──
def test_empty_inputs_return_empty_frames():
    empty = pd.DataFrame()
    assert build_signal_episodes(empty, empty).empty
    assert compute_signal_accuracy(empty, empty).empty


def test_none_entry_price_yields_no_return_not_crash():
    sig = _sig_df([("2026-01-05", "AMD", "BUY", None)])
    eps = build_signal_episodes(sig, _prices_df([]))
    row = eps.iloc[0]
    assert row["entry_price"] is None
    assert row["return_pct"] is None


def test_hold_is_non_directional():
    sig = _sig_df([("2026-01-05", "AMD", "HOLD", 100.0)])
    eps = build_signal_episodes(sig, _prices_df([]))
    assert eps.iloc[0]["verdict"] == "— non-directional"


def test_watch_missed_vs_quiet():
    # run_during >= 5% while WATCH => missed; else quiet.
    assert _classify_episode_verdict("WATCH", None, 7.0, False) == "⚠ missed"
    assert _classify_episode_verdict("WATCH", None, 1.0, False) == "— quiet"


def test_accuracy_skips_none_signal_price():
    sig = _sig_df([("2026-01-05", "AMD", "BUY", None)])
    prices = _prices_df([(f"2026-01-{5 + i:02d}", "AMD", 100.0 + i) for i in range(7)])
    assert compute_signal_accuracy(sig, prices).empty


def test_accuracy_insufficient_forward_rows_is_none():
    sig = _sig_df([("2026-01-05", "AMD", "BUY", 100.0)])
    prices = _prices_df([("2026-01-05", "AMD", 100.0), ("2026-01-06", "AMD", 101.0)])
    acc = compute_signal_accuracy(sig, prices)
    assert pd.isna(acc.iloc[0]["return_5d"])  # <5 forward rows
