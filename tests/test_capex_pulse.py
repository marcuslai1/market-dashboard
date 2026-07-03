"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd

from components.briefing.capex_pulse import (_chips_html, _cluster_medians,
                                             _gap_chart_frame)
from lib.capex import CURATION_OVERDUE_DAYS


CHIPS = [
    {"key": "capex", "label": "Capex", "state": "accel",
     "detail": "core YoY +68.9% vs +53.5% prior — accelerating", "asof": "2026Q1"},
    {"key": "gap", "label": "Coverage gap", "state": "warn",
     "detail": "-10.0pp — capex outrunning revenue & <script>", "asof": "2026Q1"},
    {"key": "val", "label": "Valuation", "state": "na",
     "detail": "needs ≥5 reports", "asof": "—"},
]


def test_chips_html_renders_labels_states_and_asof():
    html = _chips_html(CHIPS, overdue_days=30)
    assert "Capex" in html and "2026Q1" in html
    assert "▲" in html and "⚠" in html and "—" in html
    assert "CURATION OVERDUE" not in html          # 30d is fresh


def test_chips_html_escapes_detail_text():
    html = _chips_html(CHIPS, overdue_days=None)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_chips_html_overdue_banner_past_threshold():
    html = _chips_html(CHIPS, overdue_days=CURATION_OVERDUE_DAYS + 1)
    assert "CURATION OVERDUE" in html and "capex_quarterly.json" in html


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
    assert "" not in piv.columns                    # unclustered rows excluded


def test_cluster_medians_empty_metric():
    piv = _cluster_medians(pd.DataFrame(columns=["date", "cluster", "forward_pe"]),
                           "forward_pe")
    assert piv.empty
