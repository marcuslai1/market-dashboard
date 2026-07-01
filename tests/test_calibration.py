"""Tests for the Briefing signal-calibration band (review P1-2)."""
from components.briefing.calibration import (
    _MIN_MATURED_N,
    _calibration_html,
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


_SP = {
    "CAUTION": {"n_matured_10d": 526, "win_rate_pct": 47.1, "avg_return_10d": 2.71,
                "alpha_10d": -3.05, "single_regime": True},
    "HOLD": {"n_matured_10d": 67, "win_rate_pct": 35.8, "avg_return_10d": -2.58,
             "alpha_10d": -6.34, "single_regime": True},
}
_CI = {
    "signal_performance": _SP,
    "taxonomy_discrimination": {
        "full_corpus": {"observed_ordering_str": "HOLD -0.1 > CAUTION -2.6",
                        "monotonic": "PARTIAL"},
    },
    "confidence_banner": "NOT yet decision-grade — single-regime.",
    "data_window": {"from": "2026-05-02", "to": "2026-07-01", "lookback_days": 60},
}
_WL = {"A": {"signal": "CAUTION"}, "B": {"signal": "CAUTION"}, "C": {"signal": "HOLD"}}


def test_calibration_html_has_scorecard_and_anchored_headline():
    out = _calibration_html(_CI, _WL)
    assert "cal-scorecard" in out
    # dominant today = CAUTION (2 names); headline names it with its 10d alpha
    assert "most common today (2&nbsp;names)" in out
    assert "-3.0% α" in out


def test_calibration_html_taxonomy_line_present_and_escaped():
    out = _calibration_html(_CI, _WL)
    assert "Signal ordering (full corpus):" in out
    assert "partially monotonic" in out
    assert "HOLD -0.1" in out
    assert "&gt;" in out  # the '>' in the ordering string is HTML-escaped


def test_calibration_html_caveat_and_window():
    out = _calibration_html(_CI, _WL)
    assert "NOT yet decision-grade" in out
    assert "60-day window" in out
    assert "2026-05-02" in out


def test_low_confidence_rows_muted():
    out = _calibration_html(_CI, _WL)
    # both buckets are single_regime -> every data row carries the flag
    assert 'data-lowconf="1"' in out


def test_empty_calibration_placeholder():
    assert "No calibration data" in _calibration_html({}, _WL)
    assert "No calibration data" in _calibration_html({"signal_performance": {}}, _WL)


def test_missing_taxonomy_and_window_tolerated():
    out = _calibration_html({"signal_performance": _SP}, _WL)
    assert "cal-scorecard" in out          # scorecard still renders
    assert "Signal ordering" not in out    # taxonomy line omitted
    assert "cal-caveat" not in out         # no caveat paragraph


def test_dominant_signal_without_bucket_falls_back():
    # today's dominant signal (WATCH) has no scorecard bucket -> generic headline
    ci = {"signal_performance": {"HOLD": _SP["HOLD"]}}
    wl = {"A": {"signal": "WATCH"}, "B": {"signal": "WATCH"}, "C": {"signal": "HOLD"}}
    out = _calibration_html(ci, wl)
    assert "Signal calibration · 60-day window" in out


def test_banner_and_ordering_escaped():
    ci = {
        "signal_performance": _SP,
        "taxonomy_discrimination": {"full_corpus": {
            "observed_ordering_str": "<img src=x onerror=alert(1)>", "monotonic": "NO"}},
        "confidence_banner": "<script>alert(1)</script>",
    }
    out = _calibration_html(ci, _WL)
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
