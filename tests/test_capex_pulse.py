"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd

from components.briefing.capex_pulse import (
    _cluster_medians,
    _datasheet_html,
    _gap_chart_frame,
    _overdue_html,
)
from lib.capex import CURATION_OVERDUE_DAYS

_VERDICT = {"state": "digesting", "label": "DIGESTING", "tone": "watch",
            "gloss": "Spending is outrunning the revenue it produces."}


def _chip(key, measure, value, remark, tone="good"):
    return {"key": key, "measure": measure, "value": value, "remark": remark,
            "tone": tone, "label": measure, "sub": "", "detail": "", "arrow": "none"}


def test_datasheet_renders_verdict_and_one_row_per_chip():
    chips = [_chip("capex", "Capex growth", "+68.9%", "Up from +61.9%"),
             _chip("rev", "Customer sales", "+85.2%", "Unchanged since May")]
    html = _datasheet_html(_VERDICT, chips)
    assert "DIGESTING" in html
    assert html.count("<tr") == 3          # header row + two data rows
    assert "Capex growth" in html and "+68.9%" in html and "Up from +61.9%" in html
    assert "01" in html and "02" in html   # sequential numbering


def test_datasheet_numbers_rows_without_holes():
    chips = [_chip("a", "A", "1", "x"), _chip("b", "B", "2", "y"),
             _chip("c", "C", "3", "z")]
    html = _datasheet_html(_VERDICT, chips)
    for n in ("01", "02", "03"):
        assert f">{n}<" in html


def test_datasheet_escapes_html_metacharacters_per_field():
    """Stronger than the brief's example (see task-4-report.md): checks each of
    measure/value/remark independently, confirms the *exact* raw chip strings
    (which contain live '<script>' tags) never reach the output verbatim, and
    that the row/cell tag counts are unaffected by the injected markup — i.e.
    the metacharacters didn't get interpreted as structure.
    """
    raw_measure = "A & B <script>"
    raw_value = "<3 & >5"
    raw_remark = "P/E < 15 & rising >20% <script>alert(1)</script>"
    chips = [_chip("a", raw_measure, raw_value, raw_remark)]
    html = _datasheet_html(_VERDICT, chips)

    # Raw, unescaped chip content must never appear verbatim in the markup.
    assert raw_measure not in html
    assert raw_value not in html
    assert raw_remark not in html
    assert "<script>" not in html
    assert "</script>" not in html

    # The escaped forms prove the content still made it through.
    assert "A &amp; B &lt;script&gt;" in html
    assert "&lt;3 &amp; &gt;5" in html
    assert ("P/E &lt; 15 &amp; rising &gt;20% &lt;script&gt;alert(1)"
            "&lt;/script&gt;" in html)

    # Structural integrity: exactly header row + one data row, four cells —
    # the injected '<' '>' didn't spawn stray tags.
    assert html.count("<tr") == 2
    assert html.count("<td") == 4


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
