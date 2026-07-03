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
