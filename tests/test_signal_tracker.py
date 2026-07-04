"""Tests for the credibility-critical Signal Tracker math.

Covers episode construction (trade-economics exits, ticker-format conversion,
AVOID handling) and forward-return accuracy. These are the numbers the
dashboard's track record rests on.
"""
import pandas as pd

from components.signal_tracker import (
    _changelog_strip_html,
    _classify_episode_verdict,
    _readiness_html,
    _ret_num_cell,
    _scorecard_html,
    build_signal_episodes,
    compute_signal_accuracy,
)
from lib.charts import STATUS_NEG, STATUS_POS


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


# ── Ledger return colouring is neutral, not sign-based (UX-ST-1) ──
def test_ledger_returns_are_not_sign_coloured():
    # A correct CAUTION call (price fell) must NOT render red, and a gain must
    # NOT render green — the direction-aware "Trades won" winbar carries
    # performance, mirroring the calibration cards. The +/- sign still shows
    # direction; only the misleading valence colour is removed.
    neg = _ret_num_cell(-34.8)
    pos = _ret_num_cell(12.5)
    assert "-34.8%" in neg and STATUS_NEG not in neg
    assert "+12.5%" in pos and STATUS_POS not in pos


def test_ledger_missing_return_renders_dash():
    assert "—" in _ret_num_cell(None)


# ── Scorecard: plain-language, honest small-sample flags (redesign) ──

def _acc_df(signal, returns_5d):
    return pd.DataFrame([{"signal": signal, "return_5d": r} for r in returns_5d])


def test_scorecard_shows_avoid_rate_and_flags_thin_for_caution():
    """CAUTION is scored on the AVOID direction (a drop = right), and a cell
    resting on fewer than the decision-grade floor is flagged thin."""
    # 4 CAUTION: 3 fell (right), 1 rose (wrong) -> avoid rate 75%, n=4 -> thin
    html = _scorecard_html(_acc_df("CAUTION", [-3.0, -1.0, -2.0, 4.0]))
    assert "CAUTION" in html
    assert "75%" in html
    assert "thin" in html.lower()


def test_scorecard_win_rate_for_buy_and_not_thin_at_floor():
    """BUY scored on the WIN direction (a rise = right); 10 samples clears the
    thin floor, so no thin flag anywhere."""
    html = _scorecard_html(_acc_df("BUY", [1.0] * 10))
    assert "100%" in html
    assert "thin" not in html.lower()


def test_scorecard_pending_below_min_samples():
    html = _scorecard_html(_acc_df("BUY", [1.0, 2.0]))  # n=2 < 3 -> Pending
    assert "Pending" in html


def test_scorecard_empty_frame_does_not_crash():
    html = _scorecard_html(pd.DataFrame())
    assert "BUY" in html and "CAUTION" in html  # all cells render, all Pending


# ── What-we've-changed strip ──

def test_changelog_strip_renders_entries():
    html = _changelog_strip_html(
        [{"date": "2026-07-04", "title": "Honest flags", "note": "small-sample"}]
    )
    assert "2026-07-04" in html
    assert "Honest flags" in html


def test_changelog_strip_empty_is_blank():
    assert _changelog_strip_html([]) == ""


# ── Readiness ("trust") meter — how close to decision-grade ──

def test_readiness_single_regime_is_not_decision_grade():
    """One regime + every signal single-regime -> 0 decision-grade, and the
    verdict tells the reader to treat it as directional."""
    ci = {"signal_performance": {
        "CAUTION": {"n_matured_10d": 96, "n_alpha_10d": 96,
                    "single_regime": True, "regimes_present": ["trend_up"]},
        "BUY": {"n_matured_10d": 10, "n_alpha_10d": 10,
                "single_regime": True, "regimes_present": ["trend_up"]},
    }}
    html = _readiness_html(ci)
    assert "1 of 3" in html            # regimes seen
    assert "106" in html               # total matured calls
    assert "0 of 2" in html            # decision-grade / scored
    low = html.lower()
    assert "directional" in low and "not proven" in low


def test_readiness_multiregime_signal_counts_decision_grade():
    """A signal with >=10 matured across 2 regimes counts as decision-grade."""
    ci = {"signal_performance": {
        "CAUTION": {"n_matured_10d": 40, "n_alpha_10d": 40, "single_regime": False,
                    "regimes_present": ["trend_up", "trend_down"]},
    }}
    html = _readiness_html(ci)
    assert "2 of 3" in html
    assert "1 of 1" in html            # CAUTION is decision-grade


def test_readiness_empty_is_blank():
    assert _readiness_html({}) == ""
    assert _readiness_html(None) == ""
