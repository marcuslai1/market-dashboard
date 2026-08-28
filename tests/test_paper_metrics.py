"""Strategy scorecard math (lib/paper_metrics.py, 2026-08-27).

Failure names: a Sharpe that drifts from the pipeline's convention, an
R-multiple with the wrong denominator, a stop drag that counts exits it
should not, sleeve cash that is not "cash not in positions", or a lane
without nav rows leaking into the scorecard — each is one test.
"""
import math

import pandas as pd
import pytest

from lib import paper_metrics as pm


def _nav(pid, navs, spy=None, cash=None, sleeve=None):
    n = len(navs)
    return pd.DataFrame({
        "policy_id": [pid] * n,
        "date": [f"2026-05-{i + 1:02d}" for i in range(n)],
        "nav_units": navs,
        "cash_units": cash if cash is not None else [0] * n,
        "n_positions": [1] * n,
        "spy_close": spy if spy is not None else [500.0] * n,
        "soxx_close": [200.0] * n,
        "sleeve_units": sleeve if sleeve is not None else [None] * n,
    })


def test_series_stats_match_pipeline_convention():
    navs = [1_000_000, 1_010_000, 1_005_000, 1_020_000]
    out = pm.lane_nav_stats(_nav("x", navs), "x")
    assert out["ret_pct"] == pytest.approx(2.0)
    rets = [0.01, 1_005_000 / 1_010_000 - 1, 1_020_000 / 1_005_000 - 1]
    mu = sum(rets) / 3
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / 2)
    assert out["sharpe"] == pytest.approx(mu / sd * math.sqrt(252))
    assert out["max_dd_pct"] == pytest.approx((1_005_000 / 1_010_000 - 1) * 100)
    assert out["spy"]["ret_pct"] == pytest.approx(0.0)


def test_cash_idle_counts_the_sleeve_as_not_in_positions():
    df = _nav("x", [1_000_000] * 3, cash=[0, 0, 0],
              sleeve=[500_000, 500_000, 500_000])
    assert pm.lane_nav_stats(df, "x")["avg_cash_pct"] == pytest.approx(50.0)
    df = _nav("y", [1_000_000] * 3, cash=[250_000] * 3)
    assert pm.lane_nav_stats(df, "y")["avg_cash_pct"] == pytest.approx(25.0)


def _trades(pid):
    return pd.DataFrame({
        "policy_id": [pid] * 3,
        "ticker": ["NVDA", "AMD", "MU"],
        "entry_date": ["2026-05-01"] * 3,
        "avg_entry_price": [100.0, 100.0, 100.0],
        "tranches": [1, 1, 1],
        "exit_date": ["2026-05-10"] * 3,
        "exit_price": [120.0, 92.0, 108.0],
        "exit_reason": ["caution_exit", "stop", "caution_exit"],
        "pnl_pct": [20.0, -8.0, 8.0],
        "pnl_units": [20_000, -8_000, 8_000],
        "entry_stop": [92.0, 92.0, None],
        "fees_units": [None, None, None],
    })


def test_r_multiples_use_first_tranche_stop_and_skip_missing():
    out = pm.lane_trade_stats(_trades("x"), "x")
    # NVDA: (120-100)/(100-92) = +2.5R ; AMD: (92-100)/8 = -1R ; MU: no stop
    assert out["n_r"] == 2
    assert out["expectancy_r"] == pytest.approx((2.5 - 1.0) / 2)
    assert out["by_reason"]["exit_rule"]["mean_r"] == pytest.approx(2.5)
    assert out["by_reason"]["stop"]["mean_r"] == pytest.approx(-1.0)
    assert out["win_rate_pct"] == pytest.approx(200 / 3)
    assert out["fees_pct"] is None


def test_stop_drag_is_only_the_stop_exits():
    out = pm.lane_trade_stats(_trades("x"), "x")
    assert out["stop_drag_pct"] == pytest.approx(-0.8)          # -8_000 / 1e6
    assert out["by_reason"]["exit_rule"]["net_nav_pct"] == pytest.approx(2.8)


def test_scorecard_skips_lanes_without_nav_rows():
    nav = _nav("a", [1_000_000, 1_010_000, 1_020_000])
    rows = pm.scorecard(nav, _trades("a"), None, ["a", "ghost"])
    assert [r["policy_id"] for r in rows] == ["a"]
    assert rows[0]["n_trades"] == 3 and rows[0]["n_positions"] is None


def test_soxx_beta_reads_half_the_index_move_and_invested_beta_scales_by_exposure():
    """Failure: a lane that captures exactly half of every SOXX move while
    50% invested reads a portfolio beta other than 0.5, or an invested-only
    beta other than 1.0."""
    import numpy as np
    rng = np.random.default_rng(1)
    soxx = [100.0]
    for _ in range(40):
        soxx.append(soxx[-1] * (1 + rng.normal(0, 0.02)))
    navs = [1_000_000]
    for a, b in zip(soxx, soxx[1:]):
        navs.append(round(navs[-1] * (1 + 0.5 * (b / a - 1))))
    nav_df = _nav("x", navs, cash=[n // 2 for n in navs])
    nav_df["soxx_close"] = soxx
    out = pm.lane_nav_stats(nav_df, "x")
    assert out["beta_soxx"] == pytest.approx(0.5, abs=0.02)
    assert out["beta_soxx_invested"] == pytest.approx(1.0, abs=0.05)
    assert out["soxx"]["ret_pct"] == pytest.approx((soxx[-1] / soxx[0] - 1) * 100)


def test_worst_open_position_drawdown_is_the_deepest_held_name():
    nav_df = _nav("x", [1_000_000] * 5)
    pos = pd.DataFrame({"policy_id": ["x", "x", "y"], "ticker": ["A", "B", "C"],
                        "max_dd_pct": [3.2, 26.6, 40.0]})
    out = pm.lane_scorecard(nav_df, None, pos, "x")
    assert out["n_positions"] == 2 and out["worst_open_dd_pct"] == pytest.approx(-26.6)


# ── selection haircut (deflated Sharpe) ──

def _walk(pid, n, drift, seed):
    import random
    rnd = random.Random(seed)
    nav, v = [], 1_000_000.0
    for _ in range(n):
        v *= 1 + drift + rnd.gauss(0, 0.01)
        nav.append(round(v))
    return _nav(pid, nav)


def test_selection_haircut_reports_luck_benchmark_and_probability():
    df = pd.concat([_walk(f"t{i}", 90, 0.0, i) for i in range(20)]
                   + [_walk("edge", 90, 0.004, 99)], ignore_index=True)
    h = pm.selection_haircut(df, "edge")
    assert h["n_trials"] == 21 and h["n_sessions"] == 89
    assert 0.0 <= h["dsr"] <= 1.0
    assert h["lucky_best_sharpe_ann"] > 0            # best-of-21 by luck is positive
    assert h["sharpe_ann"] > h["lucky_best_sharpe_ann"]   # a real edge clears it
    assert h["dsr"] > 0.5


def test_selection_haircut_silent_when_short_or_alone():
    assert pm.selection_haircut(_walk("a", 10, 0.0, 1), "a") == {}
    assert pm.selection_haircut(_walk("a", 90, 0.0, 1), "a") == {}     # one trial
    assert pm.selection_haircut(None, "a") == {}



# ── two-factor residual (pipeline §66, 2026-08-29) ────────────────────────
def _factor_book(pid, n=90, b_spy=0.5, b_soxx=0.3, alpha=0.0005, seed=7):
    """NAV that is a known SPY/SOXX load plus alpha; SPY and SOXX walk."""
    import random
    rng = random.Random(seed)
    spy, soxx, nav = [500.0], [200.0], [1_000_000.0]
    for _ in range(n - 1):
        rs = rng.gauss(0.0004, 0.01)
        rx = 0.8 * rs + rng.gauss(0.0, 0.012)
        spy.append(spy[-1] * (1 + rs))
        soxx.append(soxx[-1] * (1 + rx))
        nav.append(nav[-1] * (1 + alpha + b_spy * rs + b_soxx * rx))
    return pd.DataFrame({"policy_id": [pid] * n,
                         "date": [f"2026-{5 + i // 28:02d}-{i % 28 + 1:02d}" for i in range(n)],
                         "nav_units": nav, "cash_units": [0] * n, "n_positions": [1] * n,
                         "spy_close": spy, "soxx_close": soxx, "sleeve_units": [None] * n})


def test_factor_residual_recovers_the_load_and_strips_it():
    out = pm.lane_nav_stats(_factor_book("f"), "f")
    assert out["beta_spy"] == pytest.approx(0.5, abs=0.02)
    assert out["beta_soxx_2f"] == pytest.approx(0.3, abs=0.02)
    assert out["r2_2f"] > 0.99
    # residual keeps the alpha: ~0.05%/day over 89 days ≈ +4.5%
    assert out["resid_ret_pct"] == pytest.approx(4.5, abs=0.5)
    assert out["resid_sharpe"] > out["sharpe"]          # the noise was the factor
    assert out["resid_max_dd_pct"] == pytest.approx(0.0, abs=0.01)


def test_factor_residual_is_zero_for_a_pure_index_tracker():
    out = pm.lane_nav_stats(_factor_book("t", b_spy=0.0, b_soxx=1.0, alpha=0.0), "t")
    assert out["beta_soxx_2f"] == pytest.approx(1.0, abs=1e-6)
    assert out["resid_ret_pct"] == pytest.approx(0.0, abs=1e-6)
    assert out["resid_vol_pct"] < 1e-6            # residual is float noise only


def test_factor_residual_silent_on_flat_benchmarks_or_short_series():
    out = pm.lane_nav_stats(_nav("x", [1_000_000 + i for i in range(30)]), "x")
    assert "resid_sharpe" not in out          # flat SPY/SOXX → singular design
    out = pm.lane_nav_stats(_factor_book("s", n=10), "s")
    assert "resid_sharpe" not in out


def test_selection_haircut_residual_mode_uses_the_stripped_series():
    df = pd.concat([_factor_book(f"t{i}", alpha=0.0, seed=i) for i in range(12)]
                   + [_factor_book("edge", alpha=0.002, seed=99)], ignore_index=True)
    raw = pm.selection_haircut(df, "edge")
    res = pm.selection_haircut(df, "edge", residual=True)
    assert raw["n_trials"] == res["n_trials"] == 13
    assert res["sharpe_ann"] != raw["sharpe_ann"]
    assert res["dsr"] > 0.5                    # a real residual edge survives the haircut
    # a factor-only book has no residual edge
    df2 = pd.concat([_factor_book(f"t{i}", alpha=0.0, seed=i) for i in range(12)]
                    + [_factor_book("tide", b_soxx=1.2, alpha=0.0, seed=5)], ignore_index=True)
    assert pm.selection_haircut(df2, "tide", residual=True)["dsr"] < 0.5


def test_rolling_sharpes_track_a_fading_residual_edge():
    # alpha in the first half only → residual rolling Sharpe falls toward 0
    n = 120
    a = _factor_book("f", n=n, alpha=0.003, seed=4)
    b = _factor_book("f", n=n, alpha=0.0, seed=4)
    df = pd.concat([a.iloc[: n // 2], b.iloc[n // 2:]], ignore_index=True)
    df["date"] = [f"2026-{5 + i // 28:02d}-{i % 28 + 1:02d}" for i in range(n)]
    roll = pm.rolling_sharpes(df, "f", window=30)
    assert list(roll.columns) == ["date", "resid_sharpe", "raw_sharpe"]
    assert len(roll) == n - 1 - 30 + 1
    assert roll["resid_sharpe"].iloc[0] > roll["resid_sharpe"].iloc[-1]


def test_rolling_sharpes_empty_when_short_or_flat():
    assert pm.rolling_sharpes(_factor_book("s", n=25), "s", window=30).empty
    assert pm.rolling_sharpes(_nav("x", [1_000_000 + i for i in range(60)]), "x").empty
    assert pm.rolling_sharpes(None, "x").empty


def test_stress_read_scales_the_shock_by_whole_pot_beta():
    assert pm.stress_read({}) == {}
    s = pm.stress_read({"beta_soxx": 0.4})
    assert s["book_move_pct"] == pytest.approx(-4.0)
