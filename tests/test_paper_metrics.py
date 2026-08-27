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
