"""Caution-trim experiment band reducers (MarketReport spec 2026-07-09)."""
import pandas as pd

from components.trim_experiment import _build_table, _curve_fig, _parse_pid


def _nav(policy, navs, spys=(500.0, 510.0)):
    return pd.DataFrame({
        "policy_id": [policy] * len(navs),
        "date": ["2026-04-19", "2026-04-20"][: len(navs)],
        "nav_units": navs,
        "cash_units": [1_000_000] * len(navs),
        "n_positions": [0] * len(navs),
        "spy_close": list(spys)[: len(navs)],
        "soxx_close": [200.0] * len(navs),
    })


def _grid_df():
    return pd.concat([
        _nav("v1_flat10", [1_000_000, 1_020_000]),           # +2.0%
        _nav("v1_tc_ext_50s", [1_000_000, 1_035_000]),       # +3.5%
        _nav("v1_tc_rsi_100", [1_000_000, 990_000]),         # -1.0%
    ])


# ── _parse_pid ──
def test_parse_pid_variants():
    assert _parse_pid("v1_tc_ext_50r") == ("Over-extended", "50%", "re-add")
    assert _parse_pid("v1_tc_any_33s") == ("Any CAUTION", "33%", "sticky")
    assert _parse_pid("v1_tc_thesis_100") == ("Thesis deterioration",
                                              "100% (exit)", "—")


# ── _build_table ──
def test_build_table_deltas_and_sort():
    tbl, base_ret, spy_ret = _build_table(_grid_df())
    assert round(base_ret, 1) == 2.0
    assert round(spy_ret, 1) == 2.0                     # 500 -> 510
    assert list(tbl["_pid"]) == ["v1_tc_ext_50s", "v1_tc_rsi_100"]  # Δ desc
    top = tbl.iloc[0]
    assert round(top["Δ vs base"], 1) == 1.5            # 3.5 - 2.0
    assert round(top["Δ vs SPY"], 1) == 1.5
    bottom = tbl.iloc[-1]
    assert round(bottom["Δ vs base"], 1) == -3.0


def test_build_table_ignores_non_trim_policies():
    tbl, _, _ = _build_table(pd.concat([
        _nav("v1_flat10", [1_000_000, 1_020_000]),
        _nav("v1_trail10", [1_000_000, 1_010_000]),      # stop book: excluded
    ]))
    assert tbl.empty


# ── _curve_fig ──
def test_curve_fig_always_carries_spy_and_baseline():
    fig = _curve_fig(_grid_df(), ["v1_tc_ext_50s"])
    names = [t.name for t in fig.data]
    assert names[0] == "SPY" and names[1] == "Baseline"
    assert any("Over-extended" in n for n in names)
    # every trace rebased to 100 at the first point
    for t in fig.data:
        assert round(t.y[0], 6) == 100.0


def test_curve_fig_empty_selection_still_plots_reference():
    fig = _curve_fig(_grid_df(), [])
    assert [t.name for t in fig.data] == ["SPY", "Baseline"]
