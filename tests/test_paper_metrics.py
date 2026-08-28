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

