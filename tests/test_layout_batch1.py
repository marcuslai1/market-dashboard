"""Layout review 2026-11-24, batch 1: a phone's first screen (an outside review of the layout).

Measured on a 390 x 844 phone before the change: the Watchlist's first company sat 936px down
and the Briefing's "What matters" 1,235px down, both past the first screen. Four changes, each
pinned here so a later edit cannot undo it quietly:

P1.  The Watchlist opens with one toolbar row (Report date and Order, two selects) and the table.
     The "The Watchlist" heading and the quote strip (the Briefing's own) left the page.
P2.  A phone row is two lines, not a three-line card.
P4.  On a phone the masthead is two lines and the briefing card's "as of" boxes fold to a short
     block that still carries every entry's label and time.
P11. On a narrow card a Week ahead day is its header over full-width events, and a Chart facts
     end label that would print on top of "0" is dropped.
"""
import glob
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import live_prices
from components.briefing.daily_briefing import briefing_card_html
from components.watchlist.row import earnings_cell_html

_CSS = (Path(__file__).resolve().parent.parent / "assets" / "theme.css").read_text(encoding="utf-8")


def _block(css: str, opener: str) -> str:
    """The body of the first ``opener { … }`` block, braces balanced."""
    start = css.index(opener)
    i = css.index("{", start)
    depth, j = 1, i + 1
    while depth:
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        j += 1
    return css[i + 1:j - 1]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(live_prices, "fetch_live_quotes", lambda: {})


def _page(name: str) -> tuple[AppTest, str]:
    at = AppTest.from_file("dashboard.py", default_timeout=60)
    at.run()
    if name != "Briefing":
        at.radio(key="page_nav").set_value(name).run()
    assert not at.exception, [e.value for e in at.exception]
    # The page's own blocks, without the stylesheet the app injects as markdown.
    return at, " ".join(str(m.value) for m in at.markdown if not str(m.value).startswith("<style>"))


# ── P1: the Watchlist's toolbar ──────────────────────────────────────────────
def test_watchlist_opens_with_two_selects_and_no_heading_or_quote_strip():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at, page = _page("Watchlist")
    assert at.selectbox(key="watchlist_date").label == "Report date"
    if glob.glob("data/growth.json"):
        assert at.selectbox(key="wl_order").label == "Order"
    assert [r.key for r in at.radio] == ["page_nav"]      # Order is no longer a radio
    assert 'class="pulse-grid"' not in page                 # the quote strip is the Briefing's
    assert "The Watchlist" not in page and "section-head" not in page
    # What the heading's subtitle used to say now rides on the sort line.
    assert "click a row for the detail" in page
    assert "LIVE" in page                                   # the live line stays


def test_briefing_keeps_the_quote_strip():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    _, page = _page("Briefing")
    assert 'class="pulse-grid"' in page


def test_toolbar_is_one_row_and_44px_on_a_phone():
    marker = _CSS.index("Layout review 2026-11-24, batch 1")
    tail = _CSS[marker:]
    row = _block(tail, ".st-key-wl_toolbar {")
    assert "flex-direction: row !important" in row and "flex-wrap: nowrap !important" in row
    # Each select has a width of its own on a PC, so the date is not a page-wide bar.
    assert "width: 180px !important" in _block(tail, ".st-key-wl_toolbar > .st-key-watchlist_date {")
    phone = _block(tail, "@media (max-width: 719px)")
    assert "min-height: 44px" in _block(phone, '.st-key-wl_toolbar [data-baseweb="select"] > div {')
    # The radio's rules went with the radio.
    assert '.st-key-wl_order [role="radiogroup"]' not in _CSS


# ── P2: two-line phone rows ──────────────────────────────────────────────────
def _phone_rows() -> str:
    marker = _CSS.index("Phone reflow — one-screen ledgers (owner request")
    return _block(_CSS[marker:], "@media (max-width: 719px)")


def test_phone_row_is_two_lines_on_four_fixed_tracks():
    body = _phone_rows()
    summary = _block(body, "details.tk-details > summary {")
    tracks = re.findall(r"minmax\([^)]*\)|[^\s(]+",
                        re.search(r"grid-template-columns:\s*([^;]+);", summary).group(1))
    assert len(tracks) == 4, tracks
    # Line 1: ticker and price. Line 2: 5 d, 1 mo, RSI, earnings. The gauge cell is gone.
    assert "grid-area: 1 / 1 / 2 / 3" in _block(body, "details.tk-details > summary > div:nth-child(1) {")
    assert "grid-area: 1 / 3 / 2 / 5" in _block(body, "details.tk-details > summary > div:nth-child(2) {")
    for n, area in ((3, "2 / 1"), (4, "2 / 2"), (6, "2 / 3"), (7, "2 / 4")):
        assert f"grid-area: {area}" in _block(body, f"details.tk-details > summary > div:nth-child({n}) {{"), n
    assert "display: none" in _block(body, "details.tk-details > summary > div:nth-child(5) {")
    # Every figure left on line 2 still names itself.
    for n, label in ((3, "5 d"), (4, "1 mo"), (6, "RSI"), (7, "Earnings")):
        assert f'content: "{label}"' in _block(
            body, f"details.tk-details > summary > div:nth-child({n})::before {{"), label


def test_phone_row_drops_the_cluster_only_under_cluster_headers():
    """A growth-sorted table has no cluster headers, so its rows keep the cluster."""
    body = _phone_rows()
    assert "display: none" in _block(body, ".tk-scroll:has(> .tk-group) .tk-tick-cluster {")
    assert not re.search(r"(?m)^\s*\.tk-tick-cluster\s*\{[^}]*display:\s*none", body)


def test_an_earnings_cell_with_no_date_is_marked_and_left_out_on_a_phone():
    none = earnings_cell_html({}, "2026-11-23")
    assert 'class="tk-earn" data-none="1"' in none and "—" in none
    dated = earnings_cell_html({"next_earnings": {"date": "2026-12-09", "days_until": 16,
                                                  "status": "scheduled"}}, "2026-11-23")
    assert "data-none" not in dated and "9 Dec" in dated
    body = _phone_rows()
    hide = "details.tk-details > summary > div.tk-earn[data-none] { display: none; }"
    assert hide in body
    # Same weight as the rule that lays the cell out, so it has to come after it.
    assert body.index(hide) > body.index("details.tk-details > summary > div:nth-child(7) {")


# ── P4: the Briefing's first phone screen ────────────────────────────────────
def test_phone_masthead_is_two_lines():
    marker = _CSS.index("P4: the Briefing's first phone screen")
    body = _block(_CSS[marker:], "@media (max-width: 719px)")
    assert "display: none" in _block(body, ".masthead .kicker {")
    assert "flex-direction: row" in _block(body, ".masthead .right {")


def _card(**over) -> str:
    latest = {
        "schema": 2, "id": "20261123T111708Z", "ts_sgt": "2026-11-23T19:17:08+08:00", "data_date": "2026-11-23",
        "as_of": [{"label": "US prices", "when": "Fri 20 Nov close (New York)", "note": "last US session"},
                  {"label": "SGX · KRX prices", "when": "Mon 23 Nov, 12:05 SGT", "note": "part-day"}],
        "what_matters": [{"kind": "macro", "head": "A headline."}],
        "numbers": {},
    }
    latest.update(over)
    return briefing_card_html({"schema": 1, "latest": latest, "recent": []}, "2026-11-23")



def test_as_of_lines_fold_with_every_label_and_time_kept():
    html = _card()
    fold = html.split('<details class="bf-asof-fold">', 1)[1].split("</details>", 1)[0]
    summary = fold.split("</summary>", 1)[0]
    # The folded line: each entry's label and its time as written, brackets included (a first
    # version dropped a closing bracket, which would have dropped "(preliminary)" as well).
    assert "<b>US prices</b> Fri 20 Nov close (New York)</span>" in summary
    assert "<b>SGX · KRX prices</b> Mon 23 Nov, 12:05 SGT</span>" in summary
    assert "last US session" not in summary                 # the note stays behind the tap
    # Behind the tap, and in the wide form, the boxes are whole.
    for boxes in (fold.split("</summary>", 1)[1], html.split('<dl class="bf-asof bf-asof-wide">', 1)[1]):
        assert "Fri 20 Nov close (New York)<small>last US session</small>" in boxes
    # The chip beside the date still says when the briefing was written.
    assert '<span class="bf-chip">Written 19:17 SGT</span>' in html
    # An entry with no time shows a dash, not a bare label.
    empty = _card(as_of=[{"label": "Europe prices", "when": ""}])
    assert "<b>Europe prices</b> —</span>" in empty


def test_no_as_of_entries_means_no_fold():
    html = _card(as_of=[])
    assert "bf-asof" not in html


def test_one_form_of_the_as_of_lines_shows_at_a_time():
    marker = _CSS.index("P4: the Briefing's first phone screen")
    tail = _CSS[marker:]
    assert ".bf-asof-fold { display: none; }" in tail          # a PC keeps the boxes
    phone = _block(tail[tail.index(".bf-asof-fold { display: none; }"):], "@media (max-width: 719px)")
    assert ".bf-asof-wide { display: none; }" in phone
    assert ".bf-asof-fold { display: block; }" in phone
    assert "min-height: 44px" in _block(phone, ".bf-asof-fold > summary {")


# "Next" on a narrow card: one line an item (the block was 201px on a 390px phone).
_CAL = [
    {"sgt": "2026-11-23T13:00", "kind": "macro", "what": "Singapore October inflation, released"},
    {"sgt": "2026-11-24T17:00", "kind": "event",
     "what": "Micron Taoyuan union: member vote on the company's proposal ends, time not announced"},
    {"sgt": "2026-11-25T05:30", "kind": "earnings",
     "what": "Dell Technologies results, not held (read-across for Nvidia, CoreWeave): call at 3:30 p.m. Central"},
    {"sgt": "2026-11-25T21:30", "kind": "macro", "what": "US GDP second estimate (Q3) + PCE inflation (October)"},
    {"sgt": "2026-11-26T16:30", "kind": "event", "what": "Micron Taoyuan union: second mediation session"},
]


def _next_items(html: str) -> list:
    block = html.split('<div class="bf-next-list">', 1)[1].split("</div>", 1)[0]
    return re.findall(r"<span data-kind=\"\w+\"( data-notime)?><strong>(.*?)</strong> "
                      r"<time datetime=\"[^\"]+\">(\w{3}) <span class=\"bf-next-hm\">(\d\d:\d\d)</span></time></span>", block)


def test_next_holds_the_three_coming_rows_whole_and_marks_a_stand_in_time():
    html = _card(calendar=_CAL)
    items = _next_items(html)
    # The three rows after the time of writing (19:17 on 23 Nov), text uncut in the markup:
    # the one-line form is the stylesheet's doing, so a wide card still prints every word.
    assert [(day, hm) for _, _, day, hm in items] == [("Tue", "17:00"), ("Wed", "05:30"), ("Wed", "21:30")]
    assert [text for _, text, _, _ in items] == [c["what"] for c in _CAL[1:4]]
    # Only the row whose text says its time is not announced is marked.
    assert [bool(mark) for mark, _, _, _ in items] == [True, False, False]
    # However the writer cases it or brackets it, and in the two other wordings found in
    # the logged briefings, the row is marked.
    # Then wordings no briefing has used yet, the short forms at the very end of the text
    # among them (the first pattern ended in a stray control character and missed those;
    # outside review, 2026-11-24).
    for what in ("Samsung preliminary results (by the Seoul open; Time not announced)",
                 "Wolfspeed's answer is due in the Delaware court on 23 Oct (US date); time not set",
                 "US Philadelphia Fed business index (November); usual release time, not confirmed",
                 "Samsung preliminary results, time TBA", "Samsung preliminary results (time TBC)",
                 "Samsung preliminary results, time TBD", "Samsung preliminary results; time: not announced",
                 "Samsung preliminary results, time not yet announced"):
        odd = _card(calendar=[{"sgt": "2026-11-24T08:00", "kind": "earnings", "what": what}])
        assert _next_items(odd)[0][0] == " data-notime", what
    # A row that names a real time is not, nor one where "time" is the tail of another word.
    for what in ("US CPI (October), 08:30 New York time", "ECB rate decision (14:15 Frankfurt time, its usual time)",
                 "A ruling is due sometime, not known to the court's clerk"):
        real = _card(calendar=[{"sgt": "2026-11-24T21:30", "kind": "macro", "what": what}])
        assert _next_items(real)[0][0] == "", what
    # No control character hides in the pattern.
    from components.briefing.daily_briefing_v2 import _NO_TIME
    assert all(ch.isprintable() for ch in _NO_TIME.pattern)


def test_every_next_row_is_in_week_ahead_in_full():
    # What makes the cut harmless: the same rows, whole, further down the card.
    html = _card(calendar=_CAL)
    week = html.split('<div class="bf-wk">', 1)[1]
    for row in _CAL[1:4]:
        assert f'<span>{row["what"]}</span>' in week, row["what"]


def test_next_is_one_line_an_item_on_a_narrow_card_only():
    marker = _CSS.index('"Next" on a narrow card')
    body = _block(_CSS[marker:], "@container (max-width: 560px)")
    assert "order: -1" in _block(body, ".bf-next-list time {")                  # the time leads
    text = _block(body, ".bf-next-list strong {")
    assert "text-overflow: ellipsis" in text and "white-space: nowrap" in text and "min-width: 0" in text
    # The time's column is as wide as the widest time, so the three texts start on one line:
    # one grid for the list, and each item takes its two tracks (`subgrid`). A browser
    # without `subgrid` keeps the item's own two tracks, declared on the line before.
    tracks = "grid-template-columns: minmax(58px, max-content) minmax(0, 1fr);"
    assert tracks in _block(body, ".bf-next-list {")
    item = _block(body, ".bf-next-list > span[data-kind] {")
    assert "grid-column: 1 / -1" in item
    assert tracks in item and item.index(tracks) < item.index("grid-template-columns: subgrid;")
    # The block's own second column may shrink, so a long text is cut, not pushed sideways.
    assert ".bf-next { grid-template-columns: auto minmax(0, 1fr); }" in body
    # A stand-in clock is hidden here and nowhere else: a wide card prints the text whole,
    # with the words that say the time is not announced. A dash in the switched-off grey
    # holds the clock's place.
    hide = ".bf-next-list > span[data-notime] .bf-next-hm { display: none; }"
    assert hide in body and _CSS.count(".bf-next-hm { display: none") == 1
    assert "var(--ink-4)" in _block(body, ".bf-next-list > span[data-notime] time::after {")
    # The clock's own span keeps the time's typeface (a site-wide rule gives spans the body face).
    assert ".bf-next-list time .bf-next-hm { font-family: inherit; }" in _CSS


# ── P11: Week ahead headers, Chart facts axis ────────────────────────────────
def _narrow_card() -> str:
    marker = _CSS.index("narrow card (phone, or a narrow column): stack")
    return _block(_CSS[marker:], "@container (max-width: 560px)")


def test_a_day_is_its_header_over_full_width_events_on_a_narrow_card():
    body = _narrow_card()
    assert ".bf-day { grid-template-columns: 1fr; }" in body
    assert "grid-column: 2" not in body        # the events no longer sit in a second column
    assert "display: flex" in _block(body, ".bf-dh {")
    assert "display: inline" in _block(body, ".bf-dh b {")


def _ticks(chart: dict) -> dict:
    html = _card(numbers={"chart": {k: {"name": k, "vs_sma50_pct": v, "rsi": 50.0} for k, v in chart.items()}})
    axis = html.split('<div class="bf-ax">', 1)[1].split("</div>", 1)[0]
    return {text: cls for cls, text in re.findall(r'<span(?: class="([\w-]+)")?[^>]*>([^<]+)</span>', axis)}



def test_an_end_label_next_to_zero_is_marked_and_dropped_on_a_narrow_card():
    # Every bar below zero, as on 23 Nov 2026: the axis runs -60 to +10 and "+10%" sat on "0".
    low = _ticks({"NVDA": -39.36, "NBIS": -55.15, "DBS": -10.68})
    assert low["+10%"] == "bf-near" and low["0"] == "" and low["−60%"] == ""
    # Every bar far above zero: the "-10%" end is the one next to "0".
    high = _ticks({"BE": 45.0, "MU": 12.0})
    assert high["−10%"] == "bf-near" and high["+50%"] == ""
    # The line is a quarter of the axis. At exactly a fifth (-40 to +10) the two labels still
    # touched on a 360px phone, so that end is marked; at exactly a quarter (-10 to +30) it is not.
    assert _ticks({"NVDA": -39.0, "MU": -12.0})["+10%"] == "bf-near"
    assert "bf-near" not in _ticks({"BE": 25.7, "AVGO": -6.2}).values()
    # Dropped where the minor ticks are (a card up to 440px), not on every card up to 560px.
    marker = _CSS.index("what matters keeps its tag column")
    assert ".bf-ax .bf-near { display: none; }" in _block(_CSS[marker:], "@container (max-width: 440px)")
    assert ".bf-ax .bf-near" not in _narrow_card()


def _bar_labels(chart: dict) -> dict:
    html = _card(numbers={"chart": {k: {"name": k, "vs_sma50_pct": v, "rsi": 50.0} for k, v in chart.items()}})
    rows = html.split('<ul class="bf-cf"', 1)[1].split("</ul>", 1)[0]
    found = re.findall(r'<span class="bf-nm2">(\w+)</span>.*?<span class="(bf-val[\w -]*)" style="left:([\d.]+)%">', rows)
    return {name: (cls, float(left)) for name, cls, left in found}


def test_a_bar_below_zero_keeps_its_figure_clear_of_the_rsi_column():
    # 23 Nov 2026: every bar below zero, the zero line at 85.71% of the axis. The figures
    # sat right of the line, where a 320px phone has 17px, and ran into the RSI figure.
    low = _bar_labels({"DBS": -10.68, "UOB": -13.6, "NVDA": -39.36, "NBIS": -55.15})
    # A long bar holds its figure inside, at the zero end; a short one has it on its left.
    assert low["NVDA"] == ("bf-val bf-in", 85.71) and low["NBIS"] == ("bf-val bf-in", 85.71)
    assert low["DBS"][0] == "bf-val bf-beside" and low["UOB"][0] == "bf-val bf-beside"
    assert low["DBS"][1] == pytest.approx(85.71 - 10.68 / 70 * 100, abs=0.02)       # the bar's far end
    for selector in (".bf-val.bf-in {", ".bf-val.bf-beside {"):
        assert "transform: translateX(-100%)" in _block(_CSS, selector)
    assert "color" not in _block(_CSS, ".bf-val.bf-beside {")           # ink, as beside the bar
    # Not "bf-out": that class is the results list's and would move the figure off its row.
    assert ".bf .bf-out {" in _CSS and not any("bf-out" in cls for cls, _ in low.values())
    # With a quarter of the axis or more right of zero, the figure stays where it was.
    mixed = _bar_labels({"BE": 25.7, "AVGO": -6.2})
    assert mixed["AVGO"] == ("bf-val", 26.5)                        # the zero line at 25%, plus 1.5
    assert mixed["BE"][0] == "bf-val bf-in"


# ── after the outside review of this batch (2026-11-24) ──────────────────────
def test_an_older_date_keeps_its_quote_strip():
    """The Briefing only shows the latest report's quotes, so on an older date the Watchlist
    is the one place that day's index levels can be read (review finding 2)."""
    files = sorted(glob.glob("data/morning_report_*.json"))
    if len(files) < 2:
        pytest.skip("needs two report dates checked out")
    older = re.search(r"(\d{4}-\d{2}-\d{2})", files[0]).group(1)
    at = AppTest.from_file("dashboard.py", default_timeout=60)
    at.session_state["watchlist_date"] = older
    at.run()
    at.radio(key="page_nav").set_value("Watchlist").run()
    assert not at.exception, [e.value for e in at.exception]
    page = " ".join(str(m.value) for m in at.markdown if not str(m.value).startswith("<style>"))
    assert 'class="wl-past"' in page and 'class="pulse-grid"' in page
    assert page.index('class="wl-past"') < page.index('class="pulse-grid"') < page.index('class="tk-scroll"')


def test_the_click_hint_is_on_the_sort_line_of_every_order():
    from components.watchlist.growth import sortline_html
    for field in ("avg2y", "latest_q"):
        assert sortline_html(field, "2026-11-22").rstrip("</div>").endswith("click a row for the detail"), field


def test_the_two_selects_are_built_inside_the_toolbar_container():
    """The row and the 44px height hang on the container's key (review finding 12)."""
    import inspect

    from components.watchlist.watchlist import render_watchlist_toolbar
    src = inspect.getsource(render_watchlist_toolbar)
    box = src.index('with st.container(key="wl_toolbar"):')
    assert box < src.index('key="watchlist_date"') < src.index('key="wl_order"')
    indent = [ln for ln in src[box:].splitlines() if 'key="watchlist_date"' in ln or 'key="wl_order"' in ln]
    assert all(ln.startswith("        ") for ln in indent)        # inside the with-block


def test_a_long_earnings_cell_cannot_run_over_the_rsi_cell():
    """On 23 Nov 2026 "EARNINGS 14 Jan est. · in 52 d" (143px) printed over the RSI figure:
    the first tracks left the cell 106px (review finding 1)."""
    body = _phone_rows()
    summary = _block(body, "details.tk-details > summary {")
    tracks = [int(px) for px in re.findall(r"(\d+)px", re.search(r"grid-template-columns:\s*([^;]+);", summary).group(1))]
    gap = int(re.search(r"gap:\s*\d+px (\d+)px", summary).group(1))
    # A 390px phone: 358px of table, 4px of padding each side.
    assert 358 - 8 - sum(tracks) - 3 * gap >= 143
    cell = _block(body, "details.tk-details > summary > div:nth-child(7) {")
    for decl in ("min-width: 0", "max-width: 100%", "flex-wrap: wrap"):
        assert decl in cell, decl


def test_a_name_whose_calendar_could_not_be_read_still_says_so_on_a_phone():
    """"No calendar" is a fact about the data, not an empty cell: it is not marked for hiding."""
    from lib import next_earnings as ne_mod
    cell = earnings_cell_html({"next_earnings": {"status": "unavailable"}}, "2026-11-23")
    assert ne_mod.next_earnings({"next_earnings": {"status": "unavailable"}}, "2026-11-23").when is None
    assert "no calendar" in cell and "data-none" not in cell


def test_phone_masthead_rule_leaves_the_terminology_heading_alone():
    marker = _CSS.index("P4: the Briefing's first phone screen")
    body = _block(_CSS[marker:], "@media (max-width: 719px)")
    assert ".masthead:not(.section-head) {" in body
    assert not re.search(r"(?m)^\s*\.masthead \{", body)


def test_the_fold_has_no_animation_and_the_toolbar_takes_the_accent_when_focused():
    marker = _CSS.index("Layout review 2026-11-24, batch 1")
    end = _CSS.index("Layout review 2026-11-24, batch 2")
    block = _CSS[marker:end]
    assert "transition" not in block                        # house rule: no animation
    focused = '.st-key-wl_toolbar [data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; }'
    assert focused in block
    # Streamlit keeps its own focus colour (the theme's amber) on a select after the
    # browser's focus has left it, so the border is held clear in every other state.
    resting = '.st-key-wl_toolbar [data-baseweb="select"] > div { border-color: transparent !important; }'
    assert resting in block and block.index(resting) < block.index(focused)
