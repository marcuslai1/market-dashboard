"""Paper-book band reducers + renderers (spec 2026-07-05-paper-book-band)."""
import pandas as pd

from components.paper_book import rebase_curves, select_policy, verdict_bits


def _nav_df(policy="v1_flat10"):
    return pd.DataFrame({
        "policy_id": [policy, policy],
        "date": ["2026-04-19", "2026-04-20"],
        "nav_units": [1_000_000, 1_004_500],
        "cash_units": [1_000_000, 900_000],
        "n_positions": [0, 1],
        "spy_close": [500.0, 510.0],
        "soxx_close": [200.0, 199.0],
    })


# ── select_policy ──
def test_select_policy_prefers_block_policy_id():
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("trim_on_caution")])
    out = select_policy(df, {"policy_id": "trim_on_caution"})
    assert set(out["policy_id"]) == {"trim_on_caution"}
    assert len(out) == 2


def test_select_policy_sole_id_without_block():
    out = select_policy(_nav_df(), {})
    assert len(out) == 2


def test_select_policy_multi_id_without_block_is_empty():
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("trim_on_caution")])
    assert select_policy(df, {}).empty     # never mix variants into one curve


def test_select_policy_empty_input():
    assert select_policy(pd.DataFrame(), {}).empty
    assert select_policy(None, {"policy_id": "v1_flat10"}).empty


# ── rebase_curves ──
def test_rebase_to_100_at_first_row():
    out = rebase_curves(select_policy(_nav_df(), {}))
    assert list(out.columns) == ["date", "Paper book", "SPY", "SOXX"]
    assert out["Paper book"].iloc[0] == 100.0
    assert round(out["Paper book"].iloc[1], 2) == 100.45
    assert round(out["SPY"].iloc[1], 1) == 102.0
    assert round(out["SOXX"].iloc[1], 1) == 99.5


def test_rebase_skips_series_with_no_valid_base():
    df = _nav_df()
    df["soxx_close"] = None
    out = rebase_curves(df)
    assert "SOXX" not in out.columns
    assert "Paper book" in out.columns


def test_rebase_empty_input():
    assert rebase_curves(pd.DataFrame()).empty
    assert rebase_curves(None).empty


# ── verdict_bits ──
def test_verdict_trailing():
    text, tone = verdict_bits({"nav_return_pct": 4.2, "spy_return_pct": 6.1,
                               "inception": "2026-04-19"})
    assert "+4.2%" in text and "+6.1%" in text and "2026-04-19" in text
    assert "trailing" in text
    assert tone == "neg"


def test_verdict_leading():
    text, tone = verdict_bits({"nav_return_pct": 8.0, "spy_return_pct": 6.1})
    assert "leading" in text
    assert tone == "pos"


def test_verdict_seeded_when_returns_none():
    text, tone = verdict_bits({"nav_return_pct": None, "spy_return_pct": None,
                               "inception": "2026-04-19"})
    assert "seeded" in text
    assert tone == ""
