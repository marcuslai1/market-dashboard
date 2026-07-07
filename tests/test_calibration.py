"""Tests for the Briefing signal-calibration band (review P1-2)."""
from components.briefing.calibration import (
    _MIN_MATURED_N,
    _calibration_html,
    _is_low_confidence,
    _scorecard_rows,
    _scorecard_table_html,
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


# ── Thin/episodes adoption (spec 2026-07-05-paper-book-band-design) ──
def test_is_low_confidence_pipeline_thin_flag_wins_over_local_floor():
    # thin=False from the pipeline overrides the local n<30 floor…
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": 12, "thin": False}
    ) is False
    # …and thin=True flags even a large-n cell (episode floor not met).
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": 500, "thin": True}
    ) is True


def test_is_low_confidence_single_regime_still_gates_with_thin_false():
    # Regime coverage is orthogonal to the pipeline's sample-size gate: a
    # single-regime cell must never read "decision-grade" (it would
    # contradict the pipeline's own banner two lines below).
    assert _is_low_confidence(
        {"single_regime": True, "n_matured_10d": 500, "thin": False}
    ) is True


def test_scorecard_rows_carry_episode_fields():
    sp = {"CAUTION": {"n_matured_10d": 555, "win_rate_pct": 43.4,
                      "avg_return_10d": 1.83, "alpha_10d": -3.22,
                      "single_regime": False, "thin": False,
                      "n_episodes": 12, "alpha_episode_mean_10d": -2.9}}
    row = _scorecard_rows(sp, {})[0]
    assert row["n_episodes"] == 12
    assert row["ep_mean"] == -2.9
    assert row["low_conf"] is False


def test_table_shows_episode_column_only_when_fields_present():
    from components.briefing.calibration import _scorecard_table_html
    with_ep = _scorecard_table_html(_scorecard_rows(
        {"CAUTION": {"n_matured_10d": 555, "win_rate_pct": 43.4,
                     "avg_return_10d": 1.83, "alpha_10d": -3.22,
                     "single_regime": True, "thin": False,
                     "n_episodes": 12, "alpha_episode_mean_10d": -2.9}}, {}))
    assert " ep</td>" in with_ep       # sample cell: "555 · 12 ep"
    assert "α/ep" in with_ep           # new column header

    without = _scorecard_table_html(_scorecard_rows(_SP, {}))
    assert " ep</td>" not in without   # fallback sample cells unchanged
    assert "α/ep" not in without


def test_fallback_html_is_byte_identical_shape():
    # Golden guard: a field-absent corpus renders exactly the pre-adoption
    # markup (column count and headers), so visual baselines don't churn.
    html = _scorecard_table_html(_scorecard_rows(_SP, {"CAUTION": 23}))
    # Count closing header tags (</thead> is excluded — it ends with </thead>,
    # not </th>) so this reflects the 6 column headers exactly, no more.
    assert html.count("</th>") == 6    # Signal/Today/n/Win/Avg 10d/α — no more


def test_alpha_headers_exempt_from_uppercase_transform():
    # .ep-table th uppercases text, turning α into Α (reads as Latin "A").
    # The α glyphs must ship inside a .lc span the CSS exempts (UX 2026-07-07).
    html = _scorecard_table_html(_scorecard_rows(_SP, {}))
    assert '<span class="lc">α</span>' in html
    with_ep = _scorecard_table_html(_scorecard_rows(
        {"CAUTION": {"n_matured_10d": 5, "win_rate_pct": 40.0,
                     "avg_return_10d": 1.0, "alpha_10d": -1.0,
                     "single_regime": True,
                     "n_episodes": 2, "alpha_episode_mean_10d": -0.5}}, {}))
    assert '<span class="lc">α/ep</span>' in with_ep


# ── Decay/shrinkage adoption (upstream 2934f47, PIPELINE_FEATURES §37) ──
from components.briefing.calibration import (  # noqa: E402
    _decay_knobs_caption,
    _decayed_full_line,
)

_DECAYED_FULL = {
    # CAUTION deliberately listed first: the line must reorder to SIGNAL_ORDER.
    "CAUTION": {"alpha_decayed_10d": -4.6, "hit_rate_decayed_pct": 42.0,
                "alpha_shrunk_10d": -4.3, "hit_rate_shrunk_pct": 42.8,
                "n_episodes": 36, "shrinkage_s": 0.09},
    "BUY": {"alpha_decayed_10d": -0.8, "hit_rate_decayed_pct": 41.0,
            "alpha_shrunk_10d": -0.2, "hit_rate_shrunk_pct": 47.5,
            "n_episodes": 3, "shrinkage_s": 0.71},
}
_KNOBS = {"halflife_days": 90, "min_sample": 5, "strength": 0.3,
          "priors": {"alpha_10d": 0.0, "hit_rate_pct": 50.0}}


def test_decayed_full_line_orders_by_signal_and_shows_shrunk_alpha():
    line = _decayed_full_line(_DECAYED_FULL)
    assert line.startswith("Full corpus")
    # BUY precedes CAUTION per SIGNAL_ORDER despite the fixture's dict order
    assert line.index("BUY") < line.index("CAUTION")
    assert "-0.2%" in line             # the SHRUNK α (thin cell pulled toward 0)…
    assert "-0.8%" not in line         # …not the decayed-only value
    assert "(3 ep)" in line
    assert "(36 ep)" in line


def test_decayed_full_line_empty_when_absent():
    assert _decayed_full_line(None) == ""
    assert _decayed_full_line({}) == ""
    # signals outside SIGNAL_ORDER contribute nothing -> no line at all
    assert _decayed_full_line({"MYSTERY": {"alpha_shrunk_10d": 1.0}}) == ""


def test_decayed_full_line_none_safe():
    line = _decayed_full_line({"BUY": {"alpha_shrunk_10d": None, "n_episodes": None}})
    assert "—" in line                 # missing α renders as em-dash
    assert "ep" not in line            # missing episode count is omitted, not "None ep"


def test_decay_knobs_caption():
    txt = _decay_knobs_caption(_KNOBS)
    assert "half-life 90d" in txt
    assert "0.3" in txt
    assert "5 ep" in txt


def test_decay_knobs_caption_empty_and_partial():
    assert _decay_knobs_caption(None) == ""
    assert _decay_knobs_caption({}) == ""
    # strength without min_sample still renders, without the "(min … ep)" tail
    txt = _decay_knobs_caption({"strength": 0.3})
    assert "0.3" in txt
    assert "ep" not in txt


def test_calibration_html_shows_full_corpus_line_and_knobs_when_present():
    ci = {**_CI,
          "signal_performance_decayed_full": _DECAYED_FULL,
          "decay_shrinkage": _KNOBS}
    out = _calibration_html(ci, _WL)
    assert "cal-fullcorpus" in out
    assert "Full corpus" in out
    assert "half-life 90d" in out      # knobs land in the caveat paragraph
    assert "cal-caveat" in out


def test_calibration_html_field_absent_renders_pre_adoption_markup():
    # Golden guard (same intent as the </th> count above): a report without the
    # decay/shrinkage fields renders exactly the pre-adoption band — no new
    # line, no new caveat bit, same paragraph count.
    out = _calibration_html(_CI, _WL)
    assert "cal-fullcorpus" not in out
    assert "half-life" not in out
    assert out.count('<p class="') == 2   # cal-taxonomy + cal-caveat, no more
