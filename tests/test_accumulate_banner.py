"""Briefing ACCUMULATE banner: a cleared Gate reads per regime in the neutral
tone, never "✅ … Live-eligible" in green (MarketReport clean-sheet review
§12.10 step 1 follow-up, owner go 2026-09-24)."""
from components.briefing.accumulate_status import accumulate_banner_html, accumulate_banner_text

_CLEARED = {"graduated": True, "alpha_10d": 3.31, "n_matured": 42,
            "line": "ACCUMULATE — gate cleared: 42 matured, +3.3% alpha across "
                    "2 regimes. Live-eligible.",
            "by_regime_alpha": {"trend_up": -0.56, "chop": 5.59}}


def test_cleared_gate_names_each_regime_and_a_negative_one():
    text, tone = accumulate_banner_text(_CLEARED)
    assert text == ("ACCUMULATE: Gate floors met, pooled +3.3% over 42 rows; by regime "
                    "chop +5.6% / trend_up -0.6%. Not shown in every regime.")
    assert tone == "test"


def test_cleared_gate_never_renders_live_eligible_green_or_a_check_mark():
    out = accumulate_banner_html(_CLEARED)
    assert "Live-eligible" not in out
    assert "✅" not in out
    assert 'data-tone="ok"' not in out
    assert 'data-tone="test"' in out


def test_cleared_gate_all_regimes_non_negative_still_says_not_proof():
    aps = dict(_CLEARED, by_regime_alpha={"chop": 1.2, "trend_up": 0.4})
    assert accumulate_banner_text(aps)[0].endswith(
        "Non-negative in every regime so far, not proof of edge.")


def test_cleared_gate_without_regime_split_says_not_proof():
    aps = {k: v for k, v in _CLEARED.items() if k != "by_regime_alpha"}
    assert accumulate_banner_text(aps)[0] == (
        "ACCUMULATE: Gate floors met, pooled +3.3% over 42 rows. Not proof of edge.")


def test_paper_phase_line_renders_as_before():
    aps = {"graduated": False, "line": "ACCUMULATE — paper phase: 9 matured, +1.0% alpha. "
                                      "Blocking: need 10 events. Size as paper."}
    text, tone = accumulate_banner_text(aps)
    assert text == "🧪 " + aps["line"] and tone == "test"


def test_absent_block_renders_nothing():
    assert accumulate_banner_html(None) == ""
    assert accumulate_banner_html({"graduated": True}) == ""
