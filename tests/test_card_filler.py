"""The briefing card's filler (owner 2026-11-24).

Owner, on the Chart facts block: "it doesnt really tell me much of anything. Like doesnt quite
add value to my understanding", then asked where else the card says little. Read over twelve
report dates, the chart had shown nearly the same names with nearly the same note. Two changes
to this page, each pinned here:

1. "The watchlist through time" replaces Chart facts: in every stored report, the count of
   names above their 50-day average and the middle name's distance from its own.
2. Names that moved for one reported reason carry one sentence, printed once.
3. A Markets tile whose headline is the day's change states its level (dollar index, oil, gold).

The other changes are to what the briefing writes (MarketReport, the briefing skill). An outside
review of the first build (2026-11-24) is behind several of these tests; each says so.
"""
import re
from pathlib import Path

import pytest

from components.briefing.daily_briefing import briefing_card_html
from components.briefing.daily_briefing_v2 import _BREADTH_MIN, _SUB_LEVEL, _shared, _why_key
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

def _plots(sec: str) -> list:
    """The two panels' plots, each from its opening tag to the end of its box."""
    return ['<div class="bf-br-plot"' + p.split("</i></div>", 1)[0] for p in sec.split('<div class="bf-br-plot"')[1:]]


def test_the_chart_states_the_latest_figure_over_each_panel():
    sec = _chart(_series([15, 14, 12, 9, 6, 4], mid=[4.0, 2.0, 1.0, -3.0, -8.0, -12.34]))
    assert '<p class="bf-br-h"><b>Above their 50-day average</b><span>4 of 20 · 28 Sep</span></p>' in sec
    assert '<p class="bf-br-h"><b>Middle name, from its 50-day average</b><span>−12.3% · 28 Sep</span></p>' in sec
    assert sec.count('<div class="bf-br-plot"') == 2 and sec.count("<svg") == 2 and sec.count("<polyline") == 2
    assert sec.count('class="bf-br-dot"') == 2                                       # the latest point of each line
    assert "each report since 21 Sep" in sec
    assert "<rect" not in sec and "RSI" not in sec                                   # the first build's lower panel


def test_the_upper_panel_is_the_share_of_the_list():
    """All of the list sits at the top line and none at the bottom one; a report takes one band of
    the width, so a weekend takes none."""
    top = _plots(_chart(_series([20, 10, 0, 0, 20])))[0]
    assert top.count('y1="2.0" y2="2.0"') == 1 and top.count('y1="50.0" y2="50.0"') == 1 and 'y1="98.0"' in top
    assert top.split('points="', 1)[1].split('"', 1)[0].split() == [
        "100.0,2.0", "300.0,50.0", "500.0,98.0", "700.0,98.0", "900.0,2.0"]
    assert re.findall(r'<span class="bf-br-y" style="top:([\d.]+)%">(\w+)</span>', top) == [
        ("2.0", "all"), ("50.0", "half"), ("98.0", "none")]
    assert 'style="left:90.00%;top:2.0%"' in top                                     # the dot on the last point


def test_the_lower_panel_has_its_own_scale_in_whole_tens_and_marks_the_average():
    """A percentage, not a share: its scale runs to the whole tens that hold every figure and zero,
    and the one marked line is the average itself. The first build drew a second count on the upper
    panel's scale in a box half its height and said the two heights compared (outside review)."""
    low = _plots(_chart(_series([15, 14, 12, 9, 6], mid=[12.0, 4.0, 0.0, -8.0, -26.6])))[1]
    labels = re.findall(r'<span class="bf-br-y" style="top:([\d.]+)%">([^<]+)</span>', low)
    assert labels == [("2.0", "+20%"), ("40.4", "0"), ("98.0", "−30%")]              # +20 to −30: zero two-fifths down
    assert low.count("bf-br-zero") == 1 and '<line class="bf-br-grid bf-br-zero" x1="0" x2="1000" y1="40.4"' in low
    pts = low.split('points="', 1)[1].split('"', 1)[0].split()
    assert pts[2] == "500.0,40.4" and pts[0] == "100.0,17.4"                         # 0% on the line, +12% above it
    # every figure below the average: zero is the top of the scale, and is still the marked line
    under = _plots(_chart(_series([3, 2, 1, 1, 0], mid=[-11.0, -14.0, -19.0, -22.0, -26.6])))[1]
    assert re.findall(r'style="top:[\d.]+%">([^<]+)</span>', under) == ["0", "−30%"]
    assert '<line class="bf-br-grid bf-br-zero" x1="0" x2="1000" y1="2.0"' in under
    # a flat line at the average still gets a scale
    flat = _plots(_chart(_series([10, 10, 10, 10, 10], mid=0.0)))[1]
    assert re.findall(r'style="top:[\d.]+%">([^<]+)</span>', flat) == ["+10%", "0", "−10%"]
    assert ".bf-br-top" not in CSS and ".bf-br-low" not in CSS                       # one height for both plots


def test_the_facts_under_the_chart_start_with_what_changed():
    """The report before comes first. The first build led with three sentences that had not changed
    in twelve reports, which is what the owner disliked in the old chart (outside review)."""
    rows = _series([15, 14, 12, 9, 6, 4], mid=[4.0, 2.0, 1.0, -3.0, -8.0, -12.34])
    assert _facts(rows) == [
        "The report before (25 Sep): 6 of 20 above, the middle name −8.0%.",
        "Highest share above in these reports: 15 of 20, on 21 Sep. Lowest: 4 of 20, on 28 Sep.",
        "The middle name ran from −12.3% (28 Sep) to +4.0% (21 Sep)."]
    # five reports or more on one side of half the list, counting today: named with the day it began
    assert "Fewer than half above in every report since 22 Sep." in _facts(_series([15, 14, 9, 8, 6, 4, 3]))
    assert "More than half above in every report since 22 Sep." in _facts(_series([3, 4, 11, 12, 14, 16, 17]))
    # a shorter run, and a day on which exactly half are above, say nothing
    assert not any("than half" in f for f in _facts(rows))
    assert not any("than half" in f for f in _facts(_series([3, 3, 3, 3, 3, 10])))
    # every report on one side: there is no day it began
    assert "Fewer than half above in every report in this chart." in _facts(_series([3, 4, 3, 2, 1, 0]))


def test_the_highest_is_the_highest_share_and_says_so():
    """"Most above: 27 of 27 on 4 Jun" stood under a chart in which 30 of 33 were above on 23 Sep, and
    in which five reports had the whole list above (outside review). The sentence names the share,
    and a figure reached more than once is dated by its last report."""
    rows = _series([27, 27, 20, 30, 12, 0, 1, 0])
    for r, n in zip(rows, (27, 27, 30, 33, 33, 34, 34, 34), strict=True):
        r["n"] = n
    assert _facts(rows)[-2] == ("Highest share above in these reports: 27 of 27, last on 18 Sep. "
                                "Lowest: 0 of 34, last on 28 Sep.")
    assert not any(f.startswith("Most") for f in _facts(rows))


def test_a_report_with_no_middle_figure_breaks_the_line_and_never_invents_one():
    rows = _series([15, 14, 12, 9, 6, 4], mid=[4.0, 2.0, None, -3.0, -8.0, None])
    sec = _chart(rows)
    low = _plots(sec + "</i></div>")[1]
    assert low.count("<polyline") == 2 and "bf-br-dot" not in low                    # two runs, no dot for today
    assert "<b>Middle name, from its 50-day average</b><span>no figure · 28 Sep</span>" in sec
    assert _facts(rows)[0] == "The report before (25 Sep): 6 of 20 above, the middle name −8.0%."
    # none at all: the upper panel stands alone and no sentence speaks of a middle name
    none = _chart(_series([15, 14, 12, 9, 6, 4], mid=[None] * 6))
    assert none.count('<div class="bf-br-plot"') == 1 and "Middle name" not in none
    assert _facts(_series([15, 14, 12, 9, 6, 4], mid=[None] * 6)) == [
        "The report before (25 Sep): 6 of 20 above.",
        "Highest share above in these reports: 15 of 20, on 21 Sep. Lowest: 4 of 20, on 28 Sep."]
    # a figure that is not a finite number is no figure
    nan = _series([15, 14, 12, 9, 6, 4], mid=[4.0, 2.0, float("nan"), -3.0, -8.0, float("inf")])
    assert _chart(nan).count("<polyline") == 3 and "nan" not in _chart(nan) and "inf" not in _chart(nan)


def test_rows_that_are_not_counts_are_left_out():
    good = _series([15, 14, 12, 9, 6, 4])
    bad = [None, "x", {"date": "not a date", "n": 20, "above": 3}, {"date": "2026-09-01", "n": 0, "above": 0},
           {"date": "2026-09-02", "n": 20, "above": 21}, {"date": "2026-09-03", "n": float("nan"), "above": 3},
           {"date": "2026-09-04", "n": 20, "above": None}]
    assert _facts(bad + good) == _facts(good)
    assert "each report since 21 Sep" in _chart(bad + good)


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
    for gone in ("bf-cf", "bf-cfhead", "bf-near", "bf-beside", "bf-val", "bf-nm2", "bf-rsi", "bf-zero\""):
        assert gone not in CSS and gone not in CODE, gone


def _months(sec: str) -> list:
    axis = sec.split('<div class="bf-br-x" aria-hidden="true">', 1)[1].split("</div>", 1)[0]
    return re.findall(r'<span( class="bf-br-alt")? style="left:([\d.]+)%">([^<]+)</span>', axis)


def test_month_starts_run_along_the_bottom():
    found = _months(_chart(_series(list(range(60)), n=60, end="2026-11-24")))
    assert [m for _, _, m in found] == ["Sep", "Oct", "Nov"] and not any(alt for alt, _, _ in found)
    lefts = [float(x) for _, x, _ in found]
    assert lefts == sorted(lefts) and max(lefts) <= 93                               # none runs off the right edge
    # A chart from 31 Aug to 1 Oct is September's: one day of August gives its place to
    # September, and October, one report from the right edge, gets no label.
    assert [m for _, _, m in _months(_chart(_series(list(range(24)), n=60, end="2026-10-01")))] == ["Sep"]


def test_a_year_of_reports_keeps_every_month_and_a_narrow_card_shows_every_second():
    """The chart holds up to 260 reports. Then no month is 9% of the width, and a rule that
    dropped a label within 9% of the last dropped every second month on a PC with room for all
    twelve; on a 320px phone two labels 9% apart touch (outside review)."""
    found = _months(_chart(_series([5] * 260, n=34, end="2027-03-12")))
    labels = [m for _, _, m in found]
    # (the reports run 16 Mar 2026 to 12 Mar 2027: the first March is a short stub and the second
    # starts at the right edge, so neither is named)
    assert labels == ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "2027", "Feb"]
    # every second one from the right is marked, so the last month named always shows
    assert [bool(alt) for alt, _, _ in found] == [False, True] * 5 + [False]
    block = CSS.split("A year of reports puts a month start every 8% of the plot", 1)[1]
    assert re.match(r"[^{]*\*/\s*@container \(max-width: 440px\) \{\s*\.bf-br-x \.bf-br-alt \{ display: none; \}", block)
    # nine months of reports have room at any width: nothing is marked
    assert not any(alt for alt, _, _ in _months(_chart(_series([5] * 185, n=34, end="2026-11-24"))))


def test_a_chart_that_crosses_a_new_year_says_which_year():
    rows = _series([20, 18, 15] + [5] * 57, n=34, mid=[9.0, 8.0] + [-5.0] * 58, end="2027-01-29")
    sec = _chart(rows)
    assert "each report since 9 Nov 2026" in sec                                     # the subtitle
    assert [m for _, _, m in _months(sec)] == ["Nov", "Dec", "2027"]
    facts = _facts(rows)
    assert "Highest share above in these reports: 20 of 34, on 9 Nov 2026." in facts[-2]
    assert facts[-1] == "The middle name ran from −5.0% (11 Nov 2026) to +9.0% (9 Nov 2026)."
    assert facts[0].startswith("The report before (28 Jan): ")                       # this year needs no number
    # within one year no date carries one
    assert "2026" not in _chart(_series([15, 14, 12, 9, 6, 4]))


def test_the_note_says_when_the_list_changed_size():
    rows = _series([9, 9, 9, 9, 9, 4])
    for r in rows[:3]:
        r["n"] = 17
    assert ("The list had between 17 and 20 names with a 50-day average over these reports, so the upper plot "
            "shows the share of the list.") in _chart(rows)
    # a list that grew and shrank back is still a list that changed (the first build compared the ends only)
    back = _series([9, 9, 9, 9, 9, 4])
    back[2]["n"] = 24
    assert "between 20 and 24 names" in _chart(back)
    assert "The list had" not in _chart(_series([9, 9, 9, 9, 9, 4]))
    assert "the one in the middle, so half the list is further below" in _chart(rows)


def test_each_plot_is_described_and_its_heading_stays_text():
    """A screen reader skips what is inside an image. The first build wrapped both headings in one
    and its description left out the lower panel's figure (outside review)."""
    sec = _chart(_series([15, 14, 9, 8, 6, 4, 3], mid=[4.0, 2.5, -1.0, -3.0, -8.0, -12.5, -9.25]))
    assert '<div class="bf-br">' in sec and sec.count('role="img"') == 2
    labels = re.findall(r'<div class="bf-br-plot" role="img" aria-label="([^"]*)">', sec)
    assert labels[0].startswith("Line chart, 7 reports from 18 Sep to 28 Sep: the share of the list")
    assert "Latest: 3 of 20." in labels[0] and "Highest share above in these reports: 15 of 20, on 18 Sep." in labels[0]
    assert "Latest: −9.2%." in labels[1] and "The middle name ran from −12.5% (25 Sep) to +4.0% (18 Sep)." in labels[1]
    for plot in _plots(sec):
        assert "bf-br-h" not in plot                                                 # no heading inside an image
    assert sec.count('aria-hidden="true"') == 3                                      # two drawings and the month row


def test_the_chart_states_figures_and_reads_nothing_into_them():
    """Colour is a claim: one ink for both panels, the hue of price data from the report, and no
    word or line that says what a figure means."""
    sec = _chart(_series([15, 14, 9, 8, 6, 4, 3], mid=-22.0)).lower()
    for word in ("oversold", "overbought", "washed", "bounce", "capitulat", "fear", "bullish", "bearish", "signal",
                 "cheap", "stretched"):
        assert word not in sec, word
    assert "bf-up" not in sec and "bf-down" not in sec
    rules = "\n".join(re.findall(r"^[^{}\n]*\.bf-br[^{]*\{[^}]*\}", CSS, flags=re.M))
    for token in ("--up", "--down", "--stress", "--good", "--bad", "--accent"):
        assert token not in rules, token
    assert rules.count("var(--metric-input)") == 2                                   # the line and the dot


# ── a level on the tiles that lead with a change ────────────────────────────

def test_the_dollar_oil_and_gold_tiles_state_their_level():
    """The markets note used to carry these ("the dollar index rose 0.5% to 104.32"). With the note
    no longer repeating a tile, a tile marked "Lowest since the 10 Aug report" showed no level at
    all (outside review)."""
    assert _SUB_LEVEL == {"DXY": ("", 2), "WTI": ("$", 2), "Gold": ("$", 0)}
    tape = [{"name": "DXY", "chg_pct": 0.49, "5d_pct": 0.74, "x_usual": 1.4, "price": 104.32, "mo_pct": 2.42},
            {"name": "WTI", "chg_pct": -3.95, "5d_pct": -6.47, "x_usual": 1.3, "price": 80.17, "mo_pct": -22.89},
            {"name": "Gold", "chg_pct": 3.87, "5d_pct": -5.23, "x_usual": 2.3, "price": 3651.4, "mo_pct": -9.3},
            {"name": "SPY", "chg_pct": 4.71, "5d_pct": -2.39, "x_usual": 4.3, "price": 722.29, "mo_pct": -4.96},
            {"name": "WTI", "chg_pct": 1.0, "5d_pct": 1.0, "x_usual": 1.0, "price": None}]
    payload = _v2()
    payload["latest"]["numbers"]["tape"] = tape
    tiles = briefing_card_html(payload, "2026-09-28").split('<div class="bf-tape">', 1)[1].split("</section>")[0]
    assert '<span class="bf-s"><span class="bf-nw">at 104.32</span> · <span class="bf-nw">1.4× usual</span>' in tiles
    assert '<span class="bf-nw">at $80.17</span>' in tiles and '<span class="bf-nw">at $3,651</span>' in tiles
    assert tiles.count(">at ") == 3 and "722" not in tiles                           # no fund price; none with no figure
    # the headline of each is still its change, coloured only where the row is a price
    assert '<span class="bf-v">+0.49%</span>' in tiles and '<span class="bf-v bf-down">−3.95%</span>' in tiles


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
    # the kind of quote mark, a closing full stop and spacing do not part two copies of one sentence
    curly = "AP says chip stocks rallied after Wall Street\u2019s  rebound"
    assert _why_key(curly) == _why_key(one) == "AP says chip stocks rallied after Wall Street's rebound"
    assert len(_shared([_row("AAA", one), _row("BBB", curly)])) == 1
    assert len(_shared([_row("AAA", one), _row("BBB", one.replace("rallied", "rose"))])) == 2


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


def test_names_with_no_reported_cause_are_never_set_together():
    """"No reported cause found." under a name that rose and one that fell would set the two together
    as if they had moved together, and pull the second out of its place (outside review)."""
    none = "No reported cause found."
    table = _movers([_row("AAA", none, state="none_found", src=()), _row("BBB", "Its own news."),
                     _row("CCC", none, state="none_found", src=())])
    assert "rowspan" not in table and "bf-sh-" not in table
    assert table.count('<td class="bf-why bf-none"><div class="bf-why-in">No reported cause found. ') == 2
    assert table.index("<b>Aaa</b>") < table.index("<b>Bbb</b>") < table.index("<b>Ccc</b>")


def test_a_name_the_card_shows_twice_carries_its_ticker_in_also_moved():
    """SK Hynix's Korean listing was written up and its US listing sat under "Also moved" as a second
    "SK Hynix" with nothing to tell them apart (outside review)."""
    payload = _v2()
    payload["latest"]["numbers"]["also_moved"] = [
        {"key": "SKHY", "name": "SK Hynix", "chg_pct": 20.0, "x_usual": 3.9, "vol_ratio": 1.62},
        {"key": "WRD", "name": "WeRide", "chg_pct": -4.49, "x_usual": 1.4, "vol_ratio": 1.27},
        {"key": "NOK", "name": "NOK", "chg_pct": 9.7}]
    html = briefing_card_html(payload, "2026-09-28")
    assert '<span class="bf-also-n">SK Hynix <small>SKHY</small></span>' in html      # the fixture's movers hold 000660_KS
    assert '<span class="bf-also-n">WeRide</span>' in html and '<span class="bf-also-n">NOK</span>' in html
    assert "always looked up" not in html and "are listed without a reason" in html


def test_the_stylesheet_shows_one_form_of_a_shared_reason_at_a_time():
    assert ".bf-movers tr.bf-sh-why { display: none; }" in CSS
    marker = CSS.index("narrow card (phone, or a narrow column): stack")
    narrow = CSS[marker:].split("@container (max-width: 560px) {", 1)[1].split("\n}\n", 1)[0]
    assert ".bf .bf-movers td.bf-why-span { display: none; }" in narrow
    # on a narrow card every row but a group header is a grid, which brings the reason's row back
    assert ".bf .bf-movers tr:not(.bf-grp) { display: grid;" in narrow
    assert ".bf .bf-movers tbody tr.bf-sh-row { border-bottom: 0; padding-bottom: 0; }" in narrow
    # One rule down the left ties the names to their reason at both widths, and on a narrow card the
    # names sit closer to each other than the reason does to the last of them (outside review: the
    # only sign had been a faint line that was not there, and a 10px gap inside against 8px after).
    assert "border-left: 2px solid var(--rule-strong); padding-left: 12px; }" in narrow
    assert ".bf .bf-movers tbody tr.bf-sh-row:not(.bf-sh-first) { padding-top: 6px; }" in narrow
    assert ".bf .bf-movers tbody tr.bf-sh-why { padding-top: 10px; }" in narrow
    assert (".bf .bf-movers td.bf-why-span { border-left: 2px solid var(--rule-strong); padding-left: 14px; "
            "vertical-align: middle; }") in CSS
    # no rule between the names of one group on a wide card
    assert ".bf .bf-movers tbody tr.bf-sh-row:not(.bf-sh-last) td:not(.bf-why) { border-bottom: 0; }" in CSS
    # Streamlit rules every table row along its top: seen in a browser as a line between two names of a group
    assert (".bf .bf-movers tbody tr.bf-sh-row:not(.bf-sh-first), .bf .bf-movers tbody tr.bf-sh-why "
            "{ border-top: 0; }") in CSS
