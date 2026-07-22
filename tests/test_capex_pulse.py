"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd
from streamlit.testing.v1 import AppTest

from components.briefing.capex_pulse import (
    _breakdown_html,
    _cluster_medians,
    _datasheet_html,
    _gap_chart_frame,
    _overdue_html,
    _sheet_rows,
)
from lib.capex import CURATION_OVERDUE_DAYS

_VERDICT = {"state": "digesting", "label": "DIGESTING", "tone": "watch",
            "gloss": "Spending is outrunning the revenue it produces."}


def _chip(key, measure, value, remark, tone="good", detail="", sub="",
          asof="2026Q1"):
    return {"key": key, "measure": measure, "value": value, "remark": remark,
            "tone": tone, "label": measure, "sub": sub, "detail": detail,
            "arrow": "none", "asof": asof}


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


def test_sheet_rows_orders_the_plate_and_survives_a_missing_chip():
    """Spec §4: a missing chip omits its row and the numbering closes up.
    Indexing by_key[k] raised KeyError and took the whole Briefing down."""
    chips = [_chip("fragile", "Weakest borrower", "CRWV", "z"),
             _chip("capex", "Capex growth", "+68.9%", "x"),
             _chip("rev", "Customer sales", "+85.2%", "y")]   # no gap, no val
    rows = _sheet_rows(chips)
    assert [c["key"] for c in rows] == ["capex", "rev", "fragile"]
    html = _datasheet_html(_VERDICT, rows)
    for n in ("01", "02", "03"):
        assert f">{n}<" in html
    assert ">04<" not in html


def test_sheet_rows_empty_when_no_chips():
    assert _sheet_rows([]) == []


def test_breakdown_carries_the_detail_the_plate_leaves_out():
    """The changelog promises the jargon 'moved into the History panel' — so
    every chip's measure, as-of, detail and sub must actually render there."""
    chips = [_chip("val", "Chip valuations", "25.4x", "Inside its own range",
                   detail="Semis median fwd PE 25.4 (80th pct 29.5) · PEG 0.63",
                   sub="Semis forward P/E vs its own recent range",
                   asof="2026-07-22"),
             _chip("fragile", "Weakest borrower", "CRWV", "Borrows to fund",
                   detail="CRWV 2026Q1 capex $6.8B · amber — FY26 guide $31-35B",
                   sub="the debt-funded name most likely to crack first",
                   asof="2026Q1")]
    html = _breakdown_html(chips)
    assert "Chip valuations" in html and "Weakest borrower" in html
    assert "80th pct 29.5" in html and "PEG 0.63" in html      # the jargon lands
    assert "as of 2026-07-22" in html and "as of 2026Q1" in html
    assert "Semis forward P/E vs its own recent range" in html  # sub survives
    assert "amber" in html                                     # curator's note
    assert html.count('class="cd-row"') == 2
    # Dollar amounts must not reach Streamlit's LaTeX parser.
    assert "$6.8B" not in html and "&#36;6.8B" in html


def test_breakdown_escapes_html_metacharacters():
    chips = [_chip("val", "A & B <script>", "1", "x",
                   detail="P/E < 15 & rising >20% <script>alert(1)</script>",
                   sub="rev & capex <b>", asof="<i>now</i>")]
    html = _breakdown_html(chips)
    assert "<script>" not in html and "</script>" not in html
    assert "<b>" not in html and "<i>" not in html
    assert "A &amp; B &lt;script&gt;" in html
    assert "P/E &lt; 15 &amp; rising &gt;20%" in html


def test_breakdown_tolerates_missing_optional_fields():
    """A chip whose detail/sub/asof are absent must still render its row."""
    chip = {"key": "capex", "measure": "Capex growth", "value": "—",
            "remark": "x", "tone": "na"}
    html = _breakdown_html([chip])
    assert "Capex growth" in html and html.count('class="cd-row"') == 1


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
    (inspect.getsourcelines) - module-level imports in capex_pulse.py are not
    carried along, so the import must live inside this wrapper's body.

    NOTE: keep this function's source ASCII-only. AppTest.from_function
    re-writes the extracted source to a temp script with the LOCALE encoding
    on older Streamlit (cp1252 on Windows) and reads it back as UTF-8, so any
    non-ASCII char here breaks script compilation on Windows. The pinned 1.58
    round-trips UTF-8 correctly, but requirements.txt floats
    streamlit>=1.39.0,<1.59 - the convention holds for the whole range."""
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
    # The History panel's per-row breakdown ships with it - the changelog says
    # the jargon moved there, so it has to actually be rendered.
    assert "capex-detail" in html
    assert "Figures behind each row" in html
