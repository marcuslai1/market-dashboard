"""Tests for components.briefing.macro.macro_prints_html — FRED Core-5 strip."""
import re

from components.briefing.macro import (
    _SPARK_H,
    _SPARK_PAD,
    _spark_points,
    macro_prints_html,
    risks_card_html,
)


def _ind():
    return {
        "CPI (YoY)": {"value": 3.9, "prior": 3.3, "chg": 0.6, "units": "% YoY",
                      "asof": "2026-04-01", "age_days": 68, "is_stale": True},
        "Unemployment": {"value": 4.3, "prior": 4.3, "chg": 0.0, "units": "%",
                         "asof": "2026-05-01", "age_days": 38, "is_stale": False},
        "Nonfarm payrolls": {"value": 172.0, "prior": 179.0, "chg": -7.0,
                             "units": "k jobs (MoM)", "asof": "2026-05-01",
                             "age_days": 38, "is_stale": False},
    }


def test_renders_payroll_and_pct():
    html = macro_prints_html(_ind())
    assert "+172k" in html          # payroll formatting
    assert "3.9%" in html           # pct formatting
    assert "4.3%" in html


def test_stale_flag_shown():
    html = macro_prints_html(_ind())
    assert "STALE" in html          # CPI is_stale


def test_delta_arrows():
    html = macro_prints_html(_ind())
    assert "▼7k" in html            # payroll chg -7.0
    assert "▲0.6" in html           # CPI chg +0.6


def test_gap_row_renders_na():
    html = macro_prints_html({"CPI (YoY)": {"status": "gap", "series_id": "CPIAUCSL"}})
    assert "n/a" in html.lower()


def test_empty_returns_blank():
    assert macro_prints_html({}) == ""
    assert macro_prints_html(None) == ""


# --- Sparkline + cell chrome (prints-grid redesign 2026-07-25) ---------------
# The trend line is reconstructed from the report archive (lib.data_loader
# .load_macro_history) because macro_indicators carry no series history. These
# pin the rules that keep it honest: no line invented from too few points, no
# crash on a flat series, and a constant cell height either way.

def test_sparkline_renders_a_polyline_from_history():
    html = macro_prints_html(_ind(), {"CPI (YoY)": [3.1, 3.4, 3.3, 3.9]})
    assert "<polyline" in html
    assert "var(--brass)" in html            # data axis, never a signal hue
    assert 'vector-effect="non-scaling-stroke"' in html


def test_shipped_history_wins_over_the_archive():
    """Once the pipeline ships `history`, it is the better source: same FRED
    fetch as `value`, so revision-current and already ending on it. No splice."""
    d = {"value": 3.5, "prior": 4.2, "history": [3.1, 3.3, 3.6, 4.2, 3.5]}
    assert _spark_points(d, [9.9, 9.9, 9.9]) == [3.1, 3.3, 3.6, 4.2, 3.5]


def test_one_point_history_falls_back_rather_than_drawing_nothing():
    d = {"value": 3.5, "prior": 4.2, "history": [3.5]}
    assert _spark_points(d, [3.1, 3.3, 4.3, 3.5]) == [3.1, 3.3, 4.2, 3.5]


def test_sparkline_tail_is_reseated_on_the_report_not_the_archive():
    """FRED revises. May payrolls entered the corpus at 172k and were revised to
    129k; the report's own prior/value are authoritative, so the line cannot end
    somewhere the delta beneath it disagrees with."""
    d = {"value": 57.0, "prior": 129.0, "chg": -72.0, "asof": "2026-06-01",
         "series_id": "PAYEMS", "age_days": 53}
    pts = _spark_points(d, [115.0, 172.0])       # archive's stale 172k tail
    assert pts == [129.0, 57.0]


def test_sparkline_keeps_archive_points_older_than_the_reported_pair():
    d = {"value": 3.5, "prior": 4.2}
    assert _spark_points(d, [3.1, 3.3, 4.3, 3.5]) == [3.1, 3.3, 4.2, 3.5]


def test_report_alone_still_yields_a_line():
    """Prior and value are two real observations — every cell gets a silhouette
    even before the archive is deep enough to add older points."""
    assert _spark_points({"value": 3.5, "prior": 4.2}, None) == [4.2, 3.5]
    assert "<polyline" in macro_prints_html(_ind())


def test_gap_row_draws_no_line():
    """No value and no prior is not a trend — reserve the box, draw nothing."""
    assert _spark_points({"status": "gap"}, None) == []
    html = macro_prints_html({"CPI (YoY)": {"status": "gap", "series_id": "CPIAUCSL"}})
    assert "<polyline" not in html


def test_line_less_cell_keeps_the_spark_box_for_baseline_alignment():
    """A line-less cell must still reserve the box, or its delta/date row rides
    up and the row loses its common baseline."""
    ind = _ind()
    ind["Core PCE (YoY)"] = {"status": "gap", "series_id": "PCEPILFE"}
    html = macro_prints_html(ind)
    assert html.count('class="fp-spark"') == 4   # 4 rows, one of them line-less
    assert '<div class="fp-spark"></div>' in html


def test_flat_series_does_not_divide_by_zero():
    ind = _row("Fed funds (eff.)", "DFF", 2, False, asof="2026-06-30", value=3.63)
    ind["Fed funds (eff.)"]["prior"] = 3.63
    html = macro_prints_html(ind, {"Fed funds (eff.)": [3.63, 3.63, 3.63]})
    assert "<polyline" in html
    assert "nan" not in html.lower()
    # A rate that never moved is drawn on the centre line, not autoscaled.
    centre = _SPARK_PAD + (_SPARK_H - 2 * _SPARK_PAD) / 2
    assert re.search(rf'points="[\d.]+,{centre:.1f} [\d.]+,{centre:.1f}', html)


def test_sub_basis_point_noise_is_drawn_as_near_flat():
    """The effective rate held 3.62-3.63 all quarter. Autoscaling that 1bp
    spread to the cell height drew a violent zigzag on the print the FOMC
    decision turns on; the flat band keeps it inside a fifth of the height."""
    ind = _row("Fed funds (eff.)", "DFF", 2, False, asof="2026-07-22", value=3.63)
    ind["Fed funds (eff.)"]["prior"] = 3.63
    html = macro_prints_html(ind, {"Fed funds (eff.)": [3.62, 3.63, 3.62, 3.63]})
    ys = [float(y) for _x, y in
          (p.split(",") for p in re.search(r'points="([^"]+)"', html).group(1).split())]
    assert max(ys) - min(ys) < 0.2 * _SPARK_H


def test_a_real_move_still_uses_the_full_height():
    """The band must damp noise only — a 0.1pp move in unemployment is real."""
    ind = _row("Unemployment", "UNRATE", 20, False, asof="2026-06-01", value=4.2)
    ind["Unemployment"]["prior"] = 4.3
    html = macro_prints_html(ind, {"Unemployment": [4.3, 4.2]})
    ys = [float(y) for _x, y in
          (p.split(",") for p in re.search(r'points="([^"]+)"', html).group(1).split())]
    assert max(ys) - min(ys) == _SPARK_H - 2 * _SPARK_PAD


def test_endpoint_marker_is_not_a_circle():
    """preserveAspectRatio="none" scales x and y differently, so a <circle>
    would render as an ellipse. The marker is a zero-length round-capped path,
    drawn in stroke space and therefore immune to the stretch."""
    html = macro_prints_html(_ind(), {"CPI (YoY)": [3.3, 3.9, 4.3, 3.5]})
    assert "<circle" not in html
    assert 'stroke-linecap="round"' in html


def test_fomc_relevant_prints_are_flagged():
    ind = _ind()
    ind["Fed funds (eff.)"] = {"value": 3.63, "chg": 0.0, "asof": "2026-07-22",
                              "age_days": 2, "series_id": "DFF"}
    html = macro_prints_html(ind)
    # CPI + Fed funds carry the accent rail; unemployment and payrolls do not.
    assert html.count('data-key="1"') == 2
    assert '<div class="fp-cell" data-key="1"><div class="fp-label">CPI' in html
    assert '<div class="fp-cell"><div class="fp-label">Unemployment' in html


# --- Release-aware freshness (known series_id) -------------------------------
# Upstream computes age_days from the FRED *observation* date (1st of the
# observation month), so a monthly print is ~40d "old" the day it is released.
# The dashboard must not parrot that as STALE: a known monthly series is stale
# only once the *next* release should already exist.

def _row(label, series_id, age_days, is_stale, asof="2026-05-01", value=4.3):
    return {label: {"value": value, "prior": value, "chg": 0.1, "units": "%",
                    "asof": asof, "age_days": age_days,
                    "series_id": series_id, "is_stale": is_stale}}


def test_monthly_fresh_print_not_stale_despite_upstream_flag():
    # May CPI viewed on Jul 2: 62d from obs date but released Jun 10 — the
    # freshest print that exists. Upstream flags it stale; dashboard must not.
    html = macro_prints_html(_row("CPI (YoY)", "CPIAUCSL", 62, True))
    assert "STALE" not in html


def test_monthly_hides_observation_age_day_count():
    html = macro_prints_html(_row("CPI (YoY)", "CPIAUCSL", 62, True))
    assert "May" in html
    assert "62d" not in html


def test_monthly_superseded_is_stale_even_if_upstream_says_fresh():
    # 80d past a May observation: the June CPI (released ~Jul 14) exists and
    # the report missed it — genuinely stale.
    html = macro_prints_html(_row("CPI (YoY)", "CPIAUCSL", 80, False))
    assert "STALE" in html


def test_pce_longer_release_lag_not_stale_at_85d():
    # PCE releases ~90d after the observation date (May print lands Jun 25;
    # June print not until Jul 30) — 85d-old May data is still the latest.
    html = macro_prints_html(_row("Core PCE (YoY)", "PCEPILFE", 85, True))
    assert "STALE" not in html


def test_daily_series_keeps_day_count():
    html = macro_prints_html(
        _row("Fed funds (eff.)", "DFF", 2, False, asof="2026-06-30", value=3.63))
    assert "2d" in html
    assert "STALE" not in html


def test_daily_series_stale_when_feed_quiet():
    html = macro_prints_html(
        _row("Fed funds (eff.)", "DFF", 12, False, asof="2026-06-20", value=3.63))
    assert "STALE" in html


def test_unknown_series_falls_back_to_upstream_flag_and_age():
    html = macro_prints_html(_row("CPI (YoY)", "NEW_SERIES_XYZ", 40, True))
    assert "STALE" in html
    assert "40d" in html


# --- Active-risks tag heuristic (UX-BR-1) -----------------------------------
# The tag slot shows a short "Category:" prefix when one exists, else the
# severity badge. A plain sentence that merely contains a colon must NOT be
# sliced into a truncated fragment (the old `[:24]` bug produced tags like
# "US-China tech tensions p").

def test_risk_label_is_never_truncated_mid_word():
    """The invariant the original guard existed for: no "[:24]" fragments.

    Revised 2026-07-22. This case previously asserted a fall back to the
    severity badge, on the theory that a clause ending in a verb is prose. The
    corpus disagrees — "U.S. tariff uncertainty persists: …" is a real risk
    NAME, structurally identical — and the old guard rejected 117 of 206
    colon-bearing risks, so most rows lost their name. What must never happen
    is a truncated fragment, which is what this now pins.
    """
    geo = {"active_risks": [
        "US-China tech tensions persist: Pentagon blacklist aims at China's AI."
    ]}
    html = risks_card_html(geo)
    assert '<div class="tag">US-China tech tensions p</div>' not in html
    assert '<div class="tag">US-China tech tensions persist</div>' in html


def test_risk_short_category_prefix_becomes_tag():
    geo = {"active_risks": ["Iran-Hormuz: WTI spikes back above 90 on failed talks."]}
    html = risks_card_html(geo)
    assert '<div class="tag">Iran-Hormuz</div>' in html


def test_risk_label_is_stripped_from_the_body():
    """The label is the tag; printing it again in the body is duplication."""
    geo = {"active_risks": ["Iran-Hormuz: WTI spikes back above 90 on failed talks."]}
    html = risks_card_html(geo)
    assert '<div class="text">WTI spikes back above 90 on failed talks.</div>' in html
    assert "Iran-Hormuz: WTI" not in html


def test_risk_multiword_label_survives_the_old_space_limit():
    """The row that exposed this: 25 chars and 3 spaces, one over each old cap."""
    geo = {"active_risks": [
        "US-China AI tech tensions: Bessent threatened sanctions on Chinese AI labs."
    ]}
    html = risks_card_html(geo)
    assert '<div class="tag">US-China AI tech tensions</div>' in html
    assert '<div class="tag">LOW</div>' not in html


def test_risk_paragraph_with_a_colon_still_falls_back_to_severity():
    """The one genuine prose case in the corpus — a 181-char paragraph."""
    geo = {"active_risks": [
        "Fed hawkish hold reinforced — May PCE hit a 3-year high at 4.1% headline; "
        "BofA's rate-hike call persists. Next catalyst: the July FOMC decision."
    ]}
    html = risks_card_html(geo)
    assert '<div class="tag">LOW</div>' in html


def test_risk_without_a_colon_keeps_its_full_text():
    geo = {"active_risks": ["Broad risk-off with no obvious catalyst"]}
    html = risks_card_html(geo)
    assert '<div class="tag">LOW</div>' in html
    assert "Broad risk-off with no obvious catalyst" in html
