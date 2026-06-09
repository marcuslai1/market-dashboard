"""Tests for components.scenario_log.extract_scenario_history."""
from components.scenario_log import extract_scenario_history


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
