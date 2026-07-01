"""Tests for the Briefing signal-calibration band (review P1-2)."""
from components.briefing.calibration import (
    _MIN_MATURED_N,
    _is_low_confidence,
    _scorecard_rows,
    _taxonomy_line,
    _today_signal_counts,
)


def test_today_signal_counts_skips_null_and_absent():
    wl = {
        "A": {"signal": "CAUTION"},
        "B": {"signal": "CAUTION"},
        "C": {"signal": None},
        "D": {},
    }
    counts = _today_signal_counts(wl)
    assert counts["CAUTION"] == 2
    assert sum(counts.values()) == 2  # null + absent contribute nothing


def test_is_low_confidence_single_regime_true_regardless_of_n():
    assert _is_low_confidence({"single_regime": True, "n_matured_10d": 500}) is True


def test_is_low_confidence_thin_n():
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": _MIN_MATURED_N - 1}
    ) is True


def test_is_low_confidence_decision_grade():
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": _MIN_MATURED_N}
    ) is False


def test_scorecard_rows_ordered_and_annotated():
    sp = {
        "CAUTION": {"n_matured_10d": 526, "win_rate_pct": 47.1, "avg_return_10d": 2.71,
                    "alpha_10d": -3.05, "single_regime": True},
        "BUY": {"n_matured_10d": 3, "win_rate_pct": 33.3, "avg_return_10d": -0.54,
                "alpha_10d": -0.46, "single_regime": True},
    }
    rows = _scorecard_rows(sp, {"CAUTION": 23})
    # BUY precedes CAUTION per SIGNAL_ORDER even with zero current exposure
    assert [r["signal"] for r in rows] == ["BUY", "CAUTION"]
    assert rows[0]["today"] == 0
    assert rows[1]["today"] == 23
    assert rows[0]["low_conf"] is True


def test_taxonomy_line_from_full_corpus():
    tax = {"full_corpus": {"observed_ordering_str": "HOLD -0.1 > CAUTION -2.6",
                           "monotonic": "PARTIAL"}}
    line = _taxonomy_line(tax)
    assert "HOLD -0.1 > CAUTION -2.6" in line
    assert "partially monotonic" in line


def test_taxonomy_line_empty_when_no_ordering():
    assert _taxonomy_line({}) == ""
    assert _taxonomy_line({"full_corpus": {"observed_ordering_str": ""}}) == ""
