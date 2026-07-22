"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd
from streamlit.testing.v1 import AppTest

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


def test_datasheet_escapes_verdict_label_and_gloss():
    """Same guarantee as the per-chip escaping test above, but for the
    caption: the verdict's ``label`` and ``gloss`` are reader-facing text
    rendered with ``unsafe_allow_html=True`` (spec §6), so they must be
    escaped exactly like every chip field. This replaces the coverage lost
    when ``_verdict_html`` (and its test) was deleted in favor of the
    datasheet caption.
    """
    raw_label = "DIGESTING <b>now</b>"
    raw_gloss = "Spending & revenue: <script>alert(1)</script> outrunning >20%"
    verdict = {"state": "digesting", "tone": "watch",
               "label": raw_label, "gloss": raw_gloss}
    chips = [_chip("a", "A", "1", "x")]
    html = _datasheet_html(verdict, chips)

    assert raw_label not in html
    assert raw_gloss not in html
    assert "<script>" not in html
    assert "</script>" not in html

    assert "DIGESTING &lt;b&gt;now&lt;/b&gt;" in html
    assert ("Spending &amp; revenue: &lt;script&gt;alert(1)&lt;/script&gt; "
            "outrunning &gt;20%" in html)


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


def _capex_pulse_page_app():
    """Boot ONLY render_capex_pulse (see test_app_pages.py's _tracker_page_app
    for why non-default-page functions can't be driven through dashboard.py
    under AppTest: st.navigation resets to the default page on every rerun).

    AppTest.from_function extracts only this function's own source lines
    (inspect.getsourcelines) — module-level imports in capex_pulse.py are not
    carried along, so the import must live inside this wrapper's body. Keep
    this function's source ASCII-only: AppTest.from_function re-writes the
    extracted source to a temp script whose encoding round-trip breaks on
    non-ASCII characters on this host."""
    from components.briefing.capex_pulse import render_capex_pulse

    render_capex_pulse()


def test_capex_pulse_renders_the_plate_end_to_end():
    """Page-level integration guard: the datasheet plate actually reaches
    the rendered app, wired through real data, not just the pure HTML
    helper in isolation. ``AppTest.from_function`` is required — driving a
    non-default page through ``dashboard.py`` resets navigation to the
    default page.
    """
    at = AppTest.from_function(_capex_pulse_page_app).run(timeout=30)
    assert not at.exception
    html = "".join(m.value for m in at.markdown)
    assert "capex-sheet" in html
    assert "What it means" in html
    assert "Weakest borrower" in html
