"""Tests for the Retrospective page.

Data rules: spec 2026-07-20-reader-retrospective-design.
Layout: spec 2026-07-25-review-retrospective-redesign-design.
"""
import pandas as pd

from components.retrospective import (
    banner_text,
    build_month_digest,
    call_item_html,
    classify_call,
    dedupe_calls,
    digest_html,
    hit_rate,
    month_label,
    month_label_short,
    month_scoreboard_html,
)


def _log(rows):
    """Minimal signal_log-shaped frame. rows = list of (date, ticker, signal)."""
    df = pd.DataFrame(rows, columns=["date", "ticker", "signal"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_dedupe_collapses_consecutive_same_signal_run_to_first_row():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "ACCUMULATE"),
        ("2026-06-02", "AMD", "ACCUMULATE"),
        ("2026-06-03", "AMD", "ACCUMULATE"),
    ]))
    assert len(calls) == 1
    assert calls.iloc[0]["date"] == pd.Timestamp("2026-06-01")


def test_dedupe_hold_gap_splits_runs_into_two_calls():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "ACCUMULATE"),
        ("2026-06-02", "AMD", "HOLD"),
        ("2026-06-03", "AMD", "ACCUMULATE"),
    ]))
    assert len(calls) == 2
    assert list(calls["date"]) == [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-03")]


def test_dedupe_filters_non_directional_signals():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "HOLD"),
        ("2026-06-02", "NVDA", "WATCH"),
        ("2026-06-03", "TSM", "CAUTION"),
    ]))
    assert list(calls["signal"]) == ["CAUTION"]


def test_dedupe_is_per_ticker():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "CAUTION"),
        ("2026-06-01", "NVDA", "CAUTION"),
    ]))
    assert len(calls) == 2


def test_dedupe_empty_frame_returns_empty():
    assert dedupe_calls(pd.DataFrame()).empty


def _call(signal, ret20=None, hit_up=None, hit_stop=None):
    return pd.Series({
        "signal": signal,
        "return_20d": float("nan") if ret20 is None else ret20,
        "hit_upside_target": float("nan") if hit_up is None else hit_up,
        "hit_invalidation": float("nan") if hit_stop is None else hit_stop,
    })


def test_long_target_hit_is_worked():
    bucket, outcome = classify_call(_call("ACCUMULATE", ret20=16.4, hit_up=1.0, hit_stop=0.0))
    assert bucket == "worked"
    assert "hit its target" in outcome
    assert "+16.4%" in outcome


def test_long_stop_hit_is_failed():
    bucket, outcome = classify_call(_call("BUY", ret20=-5.6, hit_up=0.0, hit_stop=1.0))
    assert bucket == "failed"
    assert "stopped out" in outcome


def test_long_both_levels_hit_scores_by_20d_return_sign():
    bucket, outcome = classify_call(_call("BUY", ret20=3.0, hit_up=1.0, hit_stop=1.0))
    assert bucket == "worked"
    assert "both" in outcome
    bucket, _ = classify_call(_call("BUY", ret20=-3.0, hit_up=1.0, hit_stop=1.0))
    assert bucket == "failed"


def test_long_no_levels_hit_scores_by_return_sign():
    assert classify_call(_call("ACCUMULATE", ret20=2.0, hit_up=0.0, hit_stop=0.0))[0] == "worked"
    assert classify_call(_call("ACCUMULATE", ret20=-2.0, hit_up=0.0, hit_stop=0.0))[0] == "failed"


def test_long_flat_return_is_failed():
    # Mirrors the Signal Tracker scorecard: long calls are right only when price ROSE.
    assert classify_call(_call("BUY", ret20=0.0, hit_up=0.0, hit_stop=0.0))[0] == "failed"


def test_long_immature_is_pending():
    bucket, outcome = classify_call(_call("ACCUMULATE"))
    assert bucket == "pending"
    assert "too early" in outcome


def test_caution_drop_is_worked_rally_is_failed():
    bucket, outcome = classify_call(_call("CAUTION", ret20=-9.2))
    assert bucket == "worked"
    assert "staying out was right" in outcome
    assert "9.2%" in outcome
    bucket, outcome = classify_call(_call("AVOID", ret20=4.1))
    assert bucket == "failed"
    assert "rallied" in outcome


def test_caution_flat_counts_as_worked():
    # Scorecard scores avoid-mode with (return <= 0) as right; keep identical.
    assert classify_call(_call("CAUTION", ret20=0.0))[0] == "worked"


def test_caution_immature_is_pending():
    assert classify_call(_call("AVOID"))[0] == "pending"


def test_hit_flag_without_return_still_resolves():
    bucket, outcome = classify_call(_call("BUY", hit_up=1.0, hit_stop=0.0))
    assert bucket == "worked"
    assert "%" not in outcome  # no return available -> no percentage claimed


def test_month_label():
    assert month_label("2026-07") == "July 2026"


def _calls_frame():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-05", "2026-06-20", "2026-07-02"]),
        "ticker": ["AMD", "NVDA", "TSM"],
        "signal": ["ACCUMULATE", "CAUTION", "BUY"],
        "return_20d": [12.0, 3.0, float("nan")],
        "hit_upside_target": [1.0, float("nan"), float("nan")],
        "hit_invalidation": [0.0, float("nan"), float("nan")],
    })
    return df


def test_build_month_digest_filters_to_month_and_counts():
    d = build_month_digest(_calls_frame(), "2026-06")
    assert d["month"] == "2026-06"
    assert d["n_calls"] == 2
    assert d["n_resolved"] == 2          # AMD worked, NVDA failed
    assert d["n_worked"] == 1
    assert [r["ticker"] for r, _ in d["groups"]["worked"]] == ["AMD"]
    assert [r["ticker"] for r, _ in d["groups"]["failed"]] == ["NVDA"]
    assert d["groups"]["pending"] == []


def test_build_month_digest_pending_only_month():
    d = build_month_digest(_calls_frame(), "2026-07")
    assert d["n_calls"] == 1
    assert d["n_resolved"] == 0
    assert [r["ticker"] for r, _ in d["groups"]["pending"]] == ["TSM"]


def test_banner_text_prefers_report_banner():
    assert banner_text({"confidence_banner": "NOT yet decision-grade."}) == "NOT yet decision-grade."


def test_banner_text_falls_back_when_absent():
    fallback = banner_text(None)
    assert "single market regime" in fallback
    assert banner_text({"confidence_banner": "  "}) == fallback


def _row(signal="ACCUMULATE", ticker="AMD"):
    return pd.Series({
        "date": pd.Timestamp("2026-06-05"),
        "ticker": ticker,
        "signal": signal,
        "entry_price": 203.43,
        "invalidation": 195.96,
        "upside_target": 218.84,
    })


def test_call_item_html_shows_call_and_levels_with_entity_dollars():
    out = call_item_html(_row(), "worked", "hit its target inside 20 sessions (+16.4%)")
    assert "AMD" in out
    assert "&#36;203.43" in out
    assert "target &#36;218.84" in out
    assert "stop &#36;195.96" in out
    assert "$" not in out            # raw dollars would trip Streamlit LaTeX
    assert 'data-bucket="worked"' in out


def test_call_item_html_levels_sit_on_their_own_line_after_the_outcome():
    """Levels used to interrupt the outcome sentence in parentheses; they now
    follow it in a separate element so the sentence reads uninterrupted."""
    out = call_item_html(_row(), "worked", "hit its target inside 20 sessions")
    assert '<div class="retro-levels">' in out
    assert out.index("hit its target") < out.index("retro-levels")


def test_call_item_html_pairs_signal_pill_with_outcome_bucket():
    """The row's whole point: the pill states the rating, the bucket states the
    outcome. A CAUTION call that worked must carry both, un-merged."""
    out = call_item_html(_row(signal="CAUTION"), "worked", "fell 12.4% — staying out was right")
    assert 'data-bucket="worked"' in out      # rail + glyph = outcome
    assert "CAUTION" in out and "sig-pill" in out   # pill = rating
    assert "✓" in out


def test_call_item_html_caution_shows_entry_but_no_target_stop():
    out = call_item_html(_row(signal="CAUTION"), "failed", "rallied +4.0% instead")
    assert "&#36;203.43" in out
    assert "target" not in out
    assert "stop" not in out


def test_month_label_short_is_the_segment_label():
    assert month_label_short("2026-07") == "Jul 2026"


def test_hit_rate_divides_by_resolved_not_by_all_calls():
    d = build_month_digest(_calls_frame(), "2026-06")   # 2 resolved, 1 worked
    assert hit_rate(d) == 50.0


def test_hit_rate_is_none_when_nothing_resolved():
    d = build_month_digest(_calls_frame(), "2026-07")   # 1 call, still open
    assert hit_rate(d) is None


def test_scoreboard_leads_with_the_percentage_and_shows_its_arithmetic():
    d = build_month_digest(_calls_frame(), "2026-06")
    out = month_scoreboard_html(d)
    assert "50%" in out
    assert "data-empty" not in out                       # a real reading, in brass
    assert "1 of 2 resolved calls went our way" in out   # never a bare percentage
    assert "June 2026 · hit rate" in out                 # which month, what measure


def test_scoreboard_bar_and_counts_carry_the_unresolved_slice():
    """The hit rate excludes open calls by design, so the bar and counts are what
    stop a partial month reading as a complete one."""
    calls = _calls_frame()
    d = build_month_digest(calls, "2026-06")
    out = month_scoreboard_html(d)
    assert 'data-seg="worked" style="width:50.0%;"' in out
    assert 'data-seg="failed" style="width:50.0%;"' in out
    assert 'data-seg="open"' not in out            # June has none open
    assert "Still open" in out and "New calls" in out and "Resolved" in out
    assert 'aria-label="1 worked, 1 failed, 0 still open of 2 calls"' in out


def test_scoreboard_pending_only_month_states_it_instead_of_dividing():
    d = build_month_digest(_calls_frame(), "2026-07")
    out = month_scoreboard_html(d)
    # No 0%, no ZeroDivisionError, and no bare dash sitting in the figure slot
    # where it reads as a rule. data-empty steps it out of the brass treatment.
    assert '<div class="rb-hit" data-empty="1">No verdict yet</div>' in out
    assert "its 20-session window hasn't closed yet" in out
    assert 'data-seg="open" style="width:100.0%;"' in out


def test_scoreboard_empty_verdict_names_the_open_count_when_plural():
    calls = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-03", "2026-08-04"]),
        "ticker": ["AMD", "TSM"],
        "signal": ["BUY", "CAUTION"],
        "return_20d": [float("nan")] * 2,
        "hit_upside_target": [float("nan")] * 2,
        "hit_invalidation": [float("nan")] * 2,
    })
    out = month_scoreboard_html(build_month_digest(calls, "2026-08"))
    assert "all 2 calls are still inside their 20-session windows" in out


def test_digest_html_scoreboard_then_groups_empty_groups_omitted():
    d = build_month_digest(_calls_frame(), "2026-06")
    out = digest_html(d)
    assert "50%" in out
    assert out.index("retro-board") < out.index("What worked")   # verdict first
    assert "What didn&#x27;t" in out or "What didn't" in out
    assert "Too early to judge" not in out   # empty groups are omitted


def test_digest_html_pending_month_renders_board_and_pending_group():
    d = build_month_digest(_calls_frame(), "2026-07")
    out = digest_html(d)
    assert "retro-board" in out
    assert "No verdict yet" in out   # R12 F16: head renamed (tombstones share it)
    assert "What worked" not in out


def test_digest_html_month_with_no_calls_omits_the_scoreboard():
    d = build_month_digest(_calls_frame(), "2026-05")
    out = digest_html(d)
    assert "retro-board" not in out          # nothing to score
    assert "No calls this month." in out


def test_page_renders_and_month_picker_switches_months():
    from streamlit.testing.v1 import AppTest

    def app():
        # ASCII-only + self-contained: AppTest.from_function round-trips this
        # source through a locale-encoded temp file on Windows.
        import pandas as pd

        from components.retrospective import render_retrospective_page

        log = pd.DataFrame({
            "date": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-07-01"]),
            "ticker": ["AMD", "AMD", "NVDA"],
            "signal": ["ACCUMULATE", "ACCUMULATE", "CAUTION"],
            "entry_price": [100.0, 100.0, 50.0],
            "invalidation": [95.0, 95.0, 47.0],
            "upside_target": [110.0, 110.0, 55.0],
            "hit_invalidation": [0.0, 0.0, None],
            "hit_upside_target": [1.0, 1.0, None],
            "return_20d": [12.0, 12.5, None],
        })
        report = {"calibration_insights": {"confidence_banner": "Single-regime test banner."}}
        render_retrospective_page(report, log)

    at = AppTest.from_function(app, default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    body = " ".join(str(m.value) for m in at.markdown)
    # The caveat is rendered before any figure, so no number is read unqualified.
    assert body.index("Single-regime test banner.") < body.index("hit rate")
    assert "NVDA" in body                           # default month = latest (2026-07)
    assert "too early" in body.lower()
    assert "still in progress" in body.lower()      # newest month only
    # Archive: switch to June, the resolved AMD call appears with its verdict
    at.radio(key="retro_month").set_value("2026-06").run()
    assert not at.exception
    body = " ".join(str(m.value) for m in at.markdown)
    assert "AMD" in body
    assert "hit its target" in body
    assert "100%" in body                           # 1 of 1 resolved call worked
    assert "1 of 1 resolved call went our way" in body
    assert "Paper book" not in body                 # panel removed 2026-10-01 (books frozen)
    assert "still in progress" not in body.lower()  # June is closed


def test_page_empty_log_renders_honest_empty_state():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.retrospective import render_retrospective_page
        render_retrospective_page({}, pd.DataFrame())

    at = AppTest.from_function(app, default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    texts = " ".join(str(c.value) for c in at.caption) + " ".join(
        str(m.value) for m in at.markdown)
    assert "No calls logged yet" in texts
