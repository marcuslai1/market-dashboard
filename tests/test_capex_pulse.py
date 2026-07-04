"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd

from components.briefing.capex_pulse import (
    _cluster_medians,
    _gap_chart_frame,
    _hero_gap_html,
    _overdue_html,
    _signals_html,
    _verdict_html,
)
from lib.capex import CURATION_OVERDUE_DAYS

GAP_CHIP = {"key": "gap", "label": "Coverage gap",
            "sub": "beneficiary revenue growth minus capex growth",
            "tone": "watch", "arrow": "none",
            "detail": "-18.6pp (rev +50.3% − capex +68.9%) — negative and widening & <script>",
            "asof": "2026Q1"}

SIGNALS = [
    {"key": "capex", "label": "Capex", "sub": "combined MSFT/GOOG capex",
     "tone": "neutral", "arrow": "up",
     "detail": "core YoY +68.9% vs +61.9% prior — accelerating", "asof": "2026Q1"},
    {"key": "rev", "label": "Beneficiary revenue", "sub": "median sales growth",
     "tone": "good", "arrow": "up", "detail": "median +85.2% — rising",
     "asof": "2026-07-03"},
]


def test_verdict_html_renders_label_and_gloss_and_escapes():
    html = _verdict_html({"state": "digesting", "label": "DIGESTING",
                          "tone": "watch", "gloss": "watch the gap <script>"})
    assert "DIGESTING" in html and "watch the gap" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_hero_gap_html_shows_asof_and_forward_note():
    note = {"now_pct": 85.2, "now_asof": "2026-07-03",
            "direction": "risen", "hint": "narrow"}
    html = _hero_gap_html(GAP_CHIP, note)
    assert "as of 2026Q1 earnings" in html
    assert "risen to +85.2%" in html and "may narrow" in html
    assert "<script>" not in html          # detail HTML-escaped


def test_hero_gap_html_omits_note_when_none():
    assert "↳" not in _hero_gap_html(GAP_CHIP, None)


def test_hero_gap_html_escapes_forward_note_fields():
    note = {"now_pct": 85.2, "now_asof": "2026-07-03<script>",
            "direction": "risen", "hint": "narrow"}
    html = _hero_gap_html(GAP_CHIP, note)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_signals_html_renders_arrows_labels_sublabels_and_key():
    html = _signals_html(SIGNALS)
    assert "Capex" in html and "▲" in html
    assert "median sales growth" in html          # sublabel present
    assert "healthy" in html and "direction only" in html   # key row


def test_overdue_html_only_past_threshold():
    assert _overdue_html(30) == ""
    assert "CURATION OVERDUE" in _overdue_html(CURATION_OVERDUE_DAYS + 1)


def test_gap_chart_frame_columns():
    df = _gap_chart_frame([{"cq": "2026Q1", "capex_yoy_pct": 68.9,
                            "rev_growth_pct": 58.9, "gap_pp": -10.0,
                            "rev_asof": "2026-05-02"}])
    assert list(df.columns) == ["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"]
    assert df.iloc[0]["quarter"] == "2026Q1"


def test_cluster_medians_pivots_by_cluster():
    fund = pd.DataFrame([
        {"date": "2026-06-01", "ticker": "NVDA", "cluster": "Semis",
         "revenue_growth_pct": 80.0},
        {"date": "2026-06-01", "ticker": "MU", "cluster": "Semis",
         "revenue_growth_pct": 40.0},
        {"date": "2026-06-01", "ticker": "D05_SI", "cluster": "SG Banks",
         "revenue_growth_pct": 5.0},
        {"date": "2026-06-01", "ticker": "X", "cluster": "",
         "revenue_growth_pct": 1.0},
    ])
    piv = _cluster_medians(fund, "revenue_growth_pct")
    assert piv.loc["2026-06-01", "Semis"] == 60.0
    assert piv.loc["2026-06-01", "SG Banks"] == 5.0
    assert "" not in piv.columns


def test_cluster_medians_empty_metric():
    piv = _cluster_medians(pd.DataFrame(columns=["date", "cluster", "forward_pe"]),
                           "forward_pe")
    assert piv.empty
