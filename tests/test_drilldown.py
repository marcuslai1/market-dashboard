"""Tests for the watchlist drill-down detail builder — the P1-2 final slices.

Covers the three per-entry report fields surfaced 2026-07-02 (previously
produced-but-unconsumed): ``vs_cluster_chg_pct`` (Technicals cell),
``news_sentiment_skew`` (status chip), ``premarket.phrase`` (status chip).
Each slice must render when present, stay silent when absent, and keep the
escaping contract for pipeline-authored text.
"""
from components.watchlist.drilldown import render_drilldown_detail_html
from lib.charts import STATUS_NEG, STATUS_NEUTRAL, STATUS_POS, STATUS_WARN


# ── vs cluster (1d) — Technicals cell ──
def test_vs_cluster_renders_signed_value():
    html = render_drilldown_detail_html("NVDA", {"vs_cluster_chg_pct": 1.21})
    assert "vs cluster (1d)" in html
    assert "+1.21%" in html


def test_vs_cluster_negative_value():
    html = render_drilldown_detail_html("NVDA", {"vs_cluster_chg_pct": -14.55})
    assert "-14.55%" in html


def test_vs_cluster_absent_renders_no_cell():
    html = render_drilldown_detail_html("NVDA", {})
    assert "vs cluster" not in html


# ── news sentiment — status chip ──
def test_sentiment_chip_bullish_uses_pos_color():
    html = render_drilldown_detail_html("NVDA", {"news_sentiment_skew": "bullish"})
    assert "news · bullish" in html
    assert STATUS_POS in html


def test_sentiment_chip_bearish_uses_neg_color():
    html = render_drilldown_detail_html("NVDA", {"news_sentiment_skew": "bearish"})
    assert "news · bearish" in html
    assert STATUS_NEG in html


def test_sentiment_chip_mixed_and_neutral_colors():
    mixed = render_drilldown_detail_html("NVDA", {"news_sentiment_skew": "mixed"})
    assert "news · mixed" in mixed and STATUS_WARN in mixed
    neutral = render_drilldown_detail_html("NVDA", {"news_sentiment_skew": "neutral"})
    assert "news · neutral" in neutral and STATUS_NEUTRAL in neutral


def test_sentiment_absent_renders_no_chip():
    html = render_drilldown_detail_html("NVDA", {})
    assert "news ·" not in html


# ── premarket — status chip from the pipeline-authored phrase ──
def test_premarket_chip_renders_phrase_colored_by_sign():
    d = {"premarket": {"phrase": "premarket -0.9% vs prior close", "pm_chg_pct": -0.86}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "premarket -0.9% vs prior close" in html
    assert STATUS_NEG in html


# ── UX review 2026-07-07: plain-English chips, honest R:R stat ──
def test_momentum_chip_uses_plain_label_not_raw_identifier():
    d = {"momentum_warn": True, "momentum_warn_reasons": ["vol_ratio 0.67 (<0.7)"]}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Momentum warning" in html
    assert "momentum_warn" not in html          # raw field name no longer leaks
    # the pipeline-authored reason stays verbatim (escaped) — data, not chrome
    assert "vol_ratio 0.67 (&lt;0.7)" in html


def test_caution_chip_drops_redundant_raw_id_when_mapped():
    html = render_drilldown_detail_html("NVDA", {"caution_source": "hard_block"})
    assert "Mechanical hard block" in html
    assert "hard_block" not in html
    # unmapped ids still surface raw — the id is the only label available
    html2 = render_drilldown_detail_html("NVDA", {"caution_source": "mystery_gate"})
    assert "mystery_gate" in html2


def test_analyst_consensus_humanized():
    d = {"valuation": {"forward_pe": 15.3,
                       "analyst_consensus": {"recommendation": "strong_buy",
                                             "num_analysts": 58}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Strong buy · 58 analysts" in html
    assert "strong_buy" not in html


def test_analyst_consensus_none_renders_no_cell():
    # yfinance's literal "none" sentinel maps to "—", which the metrics grid
    # drops entirely — same treatment as any other absent metric.
    d = {"valuation": {"forward_pe": 15.3,
                       "analyst_consensus": {"recommendation": "none",
                                             "num_analysts": 4}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Analyst consensus" not in html
    assert "none" not in html


def test_headline_rr_flags_tight_stop_distortion():
    d = {"risk_reward": {"ratio": 22.5, "ratio_label": "22.5:1",
                         "rr_quality": "observed", "rr_distorted": True,
                         "invalidation": 194.74,
                         "sizing_rr": {"ratio": 3.9}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "tight-stop distorted" in html


def test_headline_rr_clean_when_not_distorted():
    d = {"risk_reward": {"ratio": 2.4, "ratio_label": "2.4:1",
                         "rr_quality": "observed", "invalidation": 100.0}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "distorted" not in html
    assert "2.4:1 (observed)" in html

    d_up = {"premarket": {"phrase": "premarket +0.5% vs prior close", "pm_chg_pct": 0.53}}
    html_up = render_drilldown_detail_html("NVDA", d_up)
    assert STATUS_POS in html_up


def test_premarket_without_phrase_renders_no_chip():
    html = render_drilldown_detail_html("NVDA", {"premarket": {"pm_chg_pct": -1.0}})
    assert "premarket" not in html


def test_premarket_phrase_is_escaped():
    d = {"premarket": {"phrase": '<script>alert(1)</script>', "pm_chg_pct": 1.0}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ── Wide-stop R:R falls back to sizing_rr (UX-BR-2 / WL-1 / TM-1) ──
# Tight-invalidation names carry the corrective deeper-stop ratio under
# `sizing_rr`, not `wide_stop_rr`; the "Wide-stop R:R" row must surface it
# rather than render "—" (Terminology promises both R:R numbers in the drilldown).
def test_wide_stop_rr_falls_back_to_sizing_rr():
    d = {"risk_reward": {
        "ratio_label": "46.5:1", "rr_quality": "observed", "rr_distorted": True,
        "structural_support": 190.82, "structural_support_pct": 2.1,
        "sizing_rr": {"ratio": 4.4, "ratio_label": "4.4:1"},
    }}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Wide-stop R:R" in html
    assert "4.4" in html            # sizing_rr.ratio surfaced (was "—")


def test_wide_stop_rr_prefers_explicit_field_over_sizing():
    d = {"risk_reward": {
        "ratio_label": "3.0:1", "wide_stop_rr": 2.5,
        "sizing_rr": {"ratio": 4.4},
        "structural_support": 100.0, "structural_support_pct": 5.0,
    }}
    html = render_drilldown_detail_html("NVDA", d)
    assert "2.5" in html
    assert "4.4" not in html        # explicit wide_stop_rr wins over the fallback


# ── Thesis highlights — news-matched guardrail bullets (surfacing gap closed 2026-07-04) ──
# The pipeline emits thesis_highlights on ~5/29 names/day (thesis guardrails that fired
# on the day's news, e.g. MSFT's OpenAI-RPO caveat); previously rendered nowhere. Surface
# them as an amber-bordered list above the Technicals section when present.
def test_thesis_highlights_render_each_bullet():
    d = {"thesis_highlights": [
        "SK Hynix dominates HBM3E with >50% share",
        "ADR/China delisting risk is a standing consideration",
    ]}
    html = render_drilldown_detail_html("000660_KS", d)
    assert "Thesis highlights" in html
    assert "SK Hynix dominates HBM3E with &gt;50% share" in html   # > HTML-escaped
    assert "ADR/China delisting risk is a standing consideration" in html


def test_thesis_highlights_absent_renders_no_section():
    html = render_drilldown_detail_html("NVDA", {})
    assert "Thesis highlights" not in html


def test_thesis_highlights_empty_or_blank_items_stay_silent():
    html = render_drilldown_detail_html("NVDA", {"thesis_highlights": ["", "  "]})
    assert "Thesis highlights" not in html


def test_thesis_highlights_escapes_dollars_and_markup():
    d = {"thesis_highlights": ["~45% of MSFT $625B RPO is OpenAI-linked <risk>"]}
    html = render_drilldown_detail_html("MSFT", d)
    assert "&#36;625B" in html        # $ neutralized so Streamlit won't render LaTeX math
    assert "<risk>" not in html        # raw markup escaped, not injected
    assert "&lt;risk&gt;" in html


# ── Earnings history — quarter-on-quarter expected vs actual (2026-07-24) ──

def _eh_rows():
    """Newest-first records like the CSV export; NaN mimics empty CSV cells."""
    nan = float("nan")
    return [
        {"fiscal_label": "2026-Q3", "quarter_end": "2026-07-31",
         "eps_estimate": 2.08, "eps_actual": nan, "eps_surprise_pct": nan,
         "revenue_estimate": 91.82e9, "revenue_actual": nan,
         "revenue_yoy_pct": nan, "gross_margin_pct": nan, "operating_margin_pct": nan},
        {"fiscal_label": "2026-Q2", "quarter_end": "2026-04-30",
         "eps_estimate": 1.77, "eps_actual": 1.87, "eps_surprise_pct": 5.6,
         "revenue_estimate": nan, "revenue_actual": 81.615e9,
         "revenue_yoy_pct": 85.2, "gross_margin_pct": 74.9, "operating_margin_pct": 65.6},
        {"fiscal_label": "2026-Q1", "quarter_end": "2026-01-31",
         "eps_estimate": 1.54, "eps_actual": 1.62, "eps_surprise_pct": -3.1,
         "revenue_estimate": nan, "revenue_actual": 68.127e9,
         "revenue_yoy_pct": nan, "gross_margin_pct": nan, "operating_margin_pct": nan},
    ]


def test_earnings_history_renders_section_and_table():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert "Earnings history" in html
    assert "2026-Q2" in html and "1.87" in html
    assert "81.61B" in html                       # revenue T/B/M formatting


def test_earnings_history_absent_is_silent():
    assert "Earnings history" not in render_drilldown_detail_html("NVDA", {})
    assert "Earnings history" not in render_drilldown_detail_html(
        "NVDA", {}, earnings_hist=[])


def test_earnings_history_beat_and_miss_encoding():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert 'class="eps-beat">▲ +5.6%' in html     # beat: up arrow + green class
    assert 'class="eps-miss">▼ -3.1%' in html      # miss: down arrow + red class


def test_earnings_history_coming_quarter_snapshot():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert "upcoming" in html                      # coming-quarter pill
    assert "91.82B" in html and ">est<" in html    # forward revenue estimate marked


def test_earnings_history_missing_margins_render_dash():
    # 2026-Q1 has null margins → cells must be em-dash, not crash.
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert "74.9%" in html                          # a present margin still shows
