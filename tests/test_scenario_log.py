"""Tests for components.scenario_log.extract_scenario_history + _get_probs."""
from components.scenario_log import _get_probs, extract_scenario_history


# ── _get_probs ──
def test_get_probs_new_format_returns_pct_and_midpoint():
    out = _get_probs({"geopolitical": {"probabilities": {"base": 55, "optimistic": 20}}})
    assert out["Base"] == ("55%", 55.0)
    assert out["Optimistic"] == ("20%", 20.0)


def test_get_probs_legacy_range_midpoint():
    out = _get_probs(
        {"geopolitical": {"scenarios": {"base_case": {"probability": "50-55%"}}}}
    )
    disp, mid = out["Base"]
    assert disp == "50-55%"
    assert mid == 52.5


def test_get_probs_new_format_nonnumeric_is_safe():
    """A malformed probability must not crash the drift/compare pages."""
    out = _get_probs({"geopolitical": {"probabilities": {"base": "n/a"}}})
    assert out["Base"][1] is None


def test_description_pulled_from_scenarios_when_probabilities_present():
    """New-format reports carry an integer `probabilities` dict AND per-case
    `scenarios[name].description` (writeups restored 2026-06-08). The extractor
    must surface the description. Regression: the probabilities branch hardcoded
    `description=""`, so the restored writeups never reached the Scenario Log."""
    reports = {
        "2026-06-09": {
            "geopolitical": {
                "probabilities": {"base": 55, "optimistic": 20,
                                  "pessimistic": 20, "wildcard": 5},
                "scenarios": {
                    "base": {"description": "Hormuz stalemate holds at ~$90 WTI."},
                    "optimistic": {"description": "Ceasefire; WTI back to $75."},
                },
            }
        }
    }
    df = extract_scenario_history(reports)
    base_row = df[df["scenario"] == "Base"].iloc[0]
    assert base_row["description"] == "Hormuz stalemate holds at ~$90 WTI."
    opt_row = df[df["scenario"] == "Optimistic"].iloc[0]
    assert opt_row["description"] == "Ceasefire; WTI back to $75."


def test_extract_history_legacy_scenarios_only():
    """Legacy reports (5 in data) carry only `scenarios` with range strings —
    parse the midpoint and description without a `probabilities` block."""
    reports = {
        "2026-03-01": {
            "geopolitical": {
                "scenarios": {
                    "base_case": {"probability": "50-55%", "description": "Base."},
                    "pessimistic_case": {"probability": "20%", "description": "Bear."},
                }
            }
        }
    }
    df = extract_scenario_history(reports)
    base = df[df["scenario"] == "Base"].iloc[0]
    assert base["probability_mid"] == 52.5
    assert base["description"] == "Base."
    pess = df[df["scenario"] == "Pessimistic"].iloc[0]
    assert pess["probability_mid"] == 20.0


def test_probabilities_without_scenarios_descriptions_is_safe():
    """A new-format report with no `scenarios` block must not raise and yields
    empty descriptions."""
    reports = {
        "2026-06-08": {
            "geopolitical": {"probabilities": {"base": 60, "optimistic": 40}}
        }
    }
    df = extract_scenario_history(reports)
    assert (df["description"] == "").all()
    assert set(df["scenario"]) == {"Base", "Optimistic"}
