"""The briefing card's filler (owner 2026-11-24).

Owner, on the Chart facts block: "it doesnt really tell me much of anything. Like doesnt quite
add value to my understanding", then asked where else the card says little. Read over twelve
report dates, the chart had shown nearly the same names with nearly the same note. Two changes
to this page, each pinned here:

1. "The watchlist through time" replaces Chart facts: the count of names above their 50-day
   average, and of names with an RSI under 30, in every stored report.
2. Names that moved for one reported reason carry one sentence, printed once.

The other changes are to what the briefing writes (MarketReport, the briefing skill).
"""
import re
from pathlib import Path

import pytest

from components.briefing.daily_briefing import briefing_card_html
from components.briefing.daily_briefing_v2 import _BREADTH_MIN, _shared
from tests.test_briefing_card import _series, _v2

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "assets" / "theme.css").read_text(encoding="utf-8")
CODE = (ROOT / "components" / "briefing" / "daily_briefing_v2.py").read_text(encoding="utf-8")
TITLE = "<h3>The watchlist through time</h3>"


def _chart(rows) -> str:
    """The chart's section, or "" when the card draws none."""
    payload = _v2()
    payload["latest"]["numbers"]["breadth"] = rows
    html = briefing_card_html(payload, "2026-09-28")
    if TITLE not in html:
        return ""
    return html[html.index(TITLE):].split("</section>", 1)[0]


def _facts(rows) -> list:
    return re.findall(r"<li>(.*?)</li>", _chart(rows).split('<ul class="bf-br-facts">', 1)[1].split("</ul>", 1)[0])


# ── the watchlist through time ──────────────────────────────────────────────

def test_the_chart_states_the_latest_count_over_each_panel():
    sec = _chart(_series([15, 14, 12, 9, 6, 4], low=2))
    assert '<p class="bf-br-h"><b>Above their 50-day average</b><span>4 of 20 · 28 Sep</span></p>' in sec
    assert '<p class="bf-br-h"><b>RSI under 30</b><span>2 of 20 · 28 Sep</span></p>' in sec
    assert sec.count('<div class="bf-br-plot') == 2 and sec.count("<svg") == 2
    assert sec.count("<polyline") == 1 and sec.count('class="bf-br-bar"') == 6      # a line above, bars below
    assert sec.count('class="bf-br-dot"') == 1                                       # the latest point, on the line
    assert "names counted in each report since 21 Sep" in sec


def test_both_panels_use_one_scale_the_share_of_the_list():
    """All of the list sits at the top gridline and none at the bottom one, in both panels, so
    the two heights compare; a report takes one band of the width, so a weekend takes none."""
    rows = _series([20, 10, 0, 0, 20], low=10)
    sec = _chart(rows)
    assert sec.count('y1="2" y2="2"') == 2 and sec.count('y1="50" y2="50"') == 2 and sec.count('y1="98" y2="98"') == 2
    pts = sec.split('<polyline class="bf-br-line" points="', 1)[1].split('"', 1)[0].split()
    assert pts == ["100.0,2.0", "300.0,50.0", "500.0,98.0", "700.0,98.0", "900.0,2.0"]
    bars = re.findall(r'<rect class="bf-br-bar" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"/>', sec)
    assert bars[0] == ("0.0", "50.0", "200.00", "48.0") and len(bars) == 5           # half the list, half the height
    for word in ("all", "half", "none"):
        assert sec.count(f">{word}</span>") == 2
    assert 'style="left:90.00%;top:2.0%"' in sec                                     # the dot on the last point


def test_the_facts_under_the_chart_say_what_the_plot_shows():
    assert _facts(_series([15, 14, 12, 9, 6, 4])) == [
        "Most above: 15 of 20 on 21 Sep.", "No name had an RSI under 30 in any of these reports."]
    # five reports or more on one side of half the list, counting today: named with the day it began
    rows = _series([15, 14, 9, 8, 6, 4, 3])
    assert "Fewer than half above in every report since 22 Sep." in _facts(rows)
    assert "More than half above in every report since 22 Sep." in _facts(_series([3, 4, 11, 12, 14, 16, 17]))
    # a shorter run, and a day on which exactly half are above, say nothing
    assert not any("than half" in f for f in _facts(_series([15, 14, 12, 9, 6, 4])))
    assert not any("than half" in f for f in _facts(_series([3, 3, 3, 3, 3, 10])))
    # every report on one side: there is no day it began
    assert "Fewer than half above in every report in this chart." in _facts(_series([3, 4, 3, 2, 1, 0]))
    # a tie for the most goes to the later report
    assert _facts(_series([15, 9, 15, 9, 6, 4]))[0] == "Most above: 15 of 20 on 23 Sep."


def test_the_rsi_count_has_its_own_base():
    """A new listing has an RSI before it has a 50-day average, so the two counts are not always
    of the same number of names."""
    rows = _series([15, 14, 12, 9, 6, 4])
    rows[2].update(rsi_n=21, rsi_low=7)
    rows[-1].update(rsi_n=21, rsi_low=3)
    sec = _chart(rows)
    assert "<span>3 of 21 · 28 Sep</span>" in sec and "<span>4 of 20 · 28 Sep</span>" in sec
    assert _facts(rows)[-1] == "Most with an RSI under 30: 7 of 21 on 23 Sep."
    assert sec.count('class="bf-br-bar"') == 2                                       # no bar for a count of none


def test_a_report_with_no_rsi_draws_no_bar_and_says_so_when_it_is_the_last():
    rows = _series([15, 14, 12, 9, 6, 4], low=2)
    rows[-1].update(rsi_n=0, rsi_low=None)
    sec = _chart(rows)
    assert "<b>RSI under 30</b><span>no figure · 28 Sep</span>" in sec
    assert sec.count('class="bf-br-bar"') == 5
    # a count larger than its base is not a figure
    rows[0].update(rsi_n=3, rsi_low=9)
    assert _chart(rows).count('class="bf-br-bar"') == 4


def test_rows_that_are_not_counts_are_left_out():
    good = _series([15, 14, 12, 9, 6, 4])
    bad = [None, "x", {"date": "not a date", "n": 20, "above": 3}, {"date": "2026-09-01", "n": 0, "above": 0},
           {"date": "2026-09-02", "n": 20, "above": 21}, {"date": "2026-09-03", "n": float("nan"), "above": 3},
           {"date": "2026-09-04", "n": 20, "above": None}]
    assert _facts(bad + good) == _facts(good)
    assert "names counted in each report since 21 Sep" in _chart(bad + good)


@pytest.mark.parametrize("rows", [None, [], "x", _series([15, 14, 12, 9])])
def test_too_few_reports_draw_no_chart(rows):
    assert _BREADTH_MIN == 5
    assert _chart(rows) == ""


def test_a_record_from_before_the_change_draws_no_chart_at_all():
    """A briefing published before 2026-11-25 carries the five picked names and no series. The
    old bars are not drawn for it: the block is gone, not kept for old records."""
    payload = _v2(chart_facts={"names": ["BE"], "note": "Bloom is far above its average."})
    nums = payload["latest"]["numbers"]
    del nums["breadth"]
    nums["chart"] = {"BE": {"name": "Bloom Energy", "vs_sma50_pct": 25.7, "rsi": 62.8}}
    html = briefing_card_html(payload, "2026-09-28")
    assert TITLE not in html and "Chart facts" not in html and "Bloom is far above" not in html
    assert "<h3>Data notes</h3>" in html
    for gone in ("bf-cf", "bf-cfhead", "bf-near", "bf-beside", "bf-val", "bf-nm2", "bf-rsi", "bf-zero"):
        assert gone not in CSS and gone not in CODE, gone


def test_month_starts_run_along_the_bottom_without_touching():
    sec = _chart(_series(list(range(60)), n=60, end="2026-11-24"))
    axis = sec.split('<div class="bf-br-x" aria-hidden="true">', 1)[1].split("</div>", 1)[0]
    assert re.findall(r">(\w+)</span>", axis) == ["Sep", "Oct", "Nov"]
    lefts = [float(x) for x in re.findall(r'left:([\d.]+)%', axis)]
    assert lefts == sorted(lefts) and all(b - a >= 9 for a, b in zip(lefts, lefts[1:], strict=False))
    assert max(lefts) <= 93                                                          # none runs off the right edge
    # A chart from 31 Aug to 1 Oct is September's: one day of August gives its place to
    # September, and October, one report from the right edge, gets no label.
    short = _chart(_series(list(range(24)), n=60, end="2026-10-01"))
    assert re.findall(r">(\w+)</span>", short.split('class="bf-br-x"', 1)[1].split("</div>", 1)[0]) == ["Sep"]


def test_the_note_says_when_the_list_grew():
    rows = _series([9, 9, 9, 9, 9, 4])
    for r in rows[:3]:
        r.update(n=17, rsi_n=17)
    sec = _chart(rows)
    assert ("The list had 17 names with a 50-day average in the first of these reports and 20 in the last, so "
            "the plots show the share of the list.") in sec
    assert "The list had" not in _chart(_series([9, 9, 9, 9, 9, 4]))
    assert "Counted from each morning report" in sec and "14-day relative strength index" in sec


def test_the_chart_is_described_for_a_reader_who_cannot_see_it():
    sec = _chart(_series([15, 14, 9, 8, 6, 4, 3], low=1))
    label = sec.split('<div class="bf-br" role="img" aria-label="', 1)[1].split('"', 1)[0]
    assert label.startswith("Two charts of 7 reports from 18 Sep 2026 to 28 Sep 2026.")
    assert "Names above their 50-day average: 3 of 20 on the last report." in label
    assert "Most above: 15 of 20 on 18 Sep." in label and "Fewer than half above in every report since 22 Sep." in label
    assert sec.count('aria-hidden="true"') == 3                                      # two plots and the month row


def test_the_chart_states_counts_and_reads_nothing_into_them():
    """Colour is a claim: one ink for both panels, the hue of price data from the report, and no
    word or line that says what a count means."""
    sec = _chart(_series([15, 14, 9, 8, 6, 4, 3], low=12)).lower()
    for word in ("oversold", "overbought", "washed", "bounce", "capitulat", "fear", "bullish", "bearish", "signal"):
        assert word not in sec, word
    assert "bf-up" not in sec and "bf-down" not in sec
    rules = "\n".join(re.findall(r"^[^{}\n]*\.bf-br[^{]*\{[^}]*\}", CSS, flags=re.M))
    for token in ("--up", "--down", "--stress", "--good", "--bad"):
        assert token not in rules, token
    assert rules.count("var(--metric-input)") == 4                                   # line, area, bars, dot


# ── names that moved for one reason ─────────────────────────────────────────

def _movers(rows: list) -> str:
    payload = _v2(movers=rows)
    nums = payload["latest"]["numbers"]
    nums["movers"] = {r["key"]: {"name": r["key"].title(), "market": r.get("market", "US"), "chg_pct": 5.0 + i,
                                 "x_usual": 2.0, "vol_ratio": 1.2} for i, r in enumerate(rows)}
    payload["latest"]["sources"] += [{"title": "Rally (AP)", "url": "https://apnews.com/x", "date": "2026-09-28"}]
    html = briefing_card_html(payload, "2026-09-28")
    return html.split('<table class="bf-movers">', 1)[1].split("</table>", 1)[0]


def _row(key: str, why: str, state: str = "found", src=(1,), **over) -> dict:
    return {"key": key, "why": why, "why_state": state, "src": list(src), **over}


def test_names_with_the_same_sentence_are_set_together():
    one = "AP says chip stocks rallied after Wall Street's rebound."
    groups = _shared([_row("AAA", one), _row("BBB", "Its own news."), _row("CCC", one), _row("DDD", one + " ")])
    assert [[it["key"] for it in g] for g in groups] == [["AAA", "CCC", "DDD"], ["BBB"]]
    # a different state is a different thing to say, and a row with no text stands alone
    groups = _shared([_row("AAA", one), _row("BBB", one, state="none_found"), _row("CCC", ""), _row("DDD", "")])
    assert [[it["key"] for it in g] for g in groups] == [["AAA"], ["BBB"], ["CCC"], ["DDD"]]


def test_a_shared_reason_is_one_cell_beside_its_names_and_one_row_under_them():
    one = "AP says chip stocks rallied after the rebound in New York."
    table = _movers([_row("AAA", one), _row("BBB", "Its own news."), _row("CCC", one, src=(2,)), _row("DDD", one)])
    text = one
    # the wide card: the reason once, in a cell that spans the three names' rows
    assert table.count('<td class="bf-why bf-why-span" rowspan="3">') == 1
    # the narrow card: a row of its own after the last of them
    assert table.count('<tr class="bf-sh-why"><td class="bf-why" colspan="3">') == 1
    assert table.count(text) == 2                                                    # those two, and no per-name copy
    order = [table.index(x) for x in ('<tr class="bf-sh-row bf-sh-first">', "<b>Aaa</b>", "rowspan=",
                                      '<tr class="bf-sh-row">', "<b>Ccc</b>", '<tr class="bf-sh-row bf-sh-last">',
                                      "<b>Ddd</b>", '<tr class="bf-sh-why">', "<b>Bbb</b>")]
    assert order == sorted(order)
    # each name keeps its own move, and the reason carries every source its rows named, once each
    assert table.count('<td class="bf-mv bf-up">') == 4
    span = table.split("bf-why-span", 1)[1].split("</td>", 1)[0]
    assert span.count('class="bf-src"') == 2 and "cnbc" in span.lower() and ">AP " in span
    # a name with its own reason is a plain row, as before
    assert '<td class="bf-why"><div class="bf-why-in">Its own news. ' in table


def test_names_in_different_markets_do_not_share_a_cell():
    one = "AP says chip stocks rallied after Wall Street's rebound."
    table = _movers([_row("AAA", one), _row("BBB", one, market="KRX"), _row("CCC", one, market="KRX")])
    assert table.count("rowspan=") == 1 and 'rowspan="2"' in table                    # the two Korean names
    assert table.count('<tr class="bf-sh-why">') == 1
    assert table.index("<b>Aaa</b>") < table.index("rowspan=")                       # the US name is a plain row


def test_no_reported_cause_shared_by_two_names_keeps_its_look():
    table = _movers([_row("AAA", "No reported cause found.", state="none_found", src=()),
                     _row("BBB", "No reported cause found.", state="none_found", src=())])
    assert '<td class="bf-why bf-none bf-why-span" rowspan="2">' in table
    assert '<tr class="bf-sh-why"><td class="bf-why bf-none" colspan="3">' in table


def test_the_stylesheet_shows_one_form_of_a_shared_reason_at_a_time():
    assert ".bf-movers tr.bf-sh-why { display: none; }" in CSS
    marker = CSS.index("narrow card (phone, or a narrow column): stack")
    narrow = CSS[marker:].split("@container (max-width: 560px) {", 1)[1].split("\n}\n", 1)[0]
    assert ".bf .bf-movers td.bf-why-span { display: none; }" in narrow
    # on a narrow card every row but a group header is a grid, which brings the reason's row back
    assert ".bf .bf-movers tr:not(.bf-grp) { display: grid;" in narrow
    assert ".bf .bf-movers tbody tr.bf-sh-row { border-bottom: 0; padding-bottom: 0; }" in narrow
    # no rule between the names of one group on a wide card
    assert ".bf .bf-movers tbody tr.bf-sh-row:not(.bf-sh-last) td:not(.bf-why) { border-bottom: 0; }" in CSS
    # Streamlit rules every table row along its top: seen in a browser as a line between two names of a group
    assert (".bf .bf-movers tbody tr.bf-sh-row:not(.bf-sh-first), .bf .bf-movers tbody tr.bf-sh-why "
            "{ border-top: 0; }") in CSS
