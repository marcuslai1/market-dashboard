"""Long text on the briefing card is set as lists (owner 2026-11-24: "text dumps with no structuring").

Four blocks were one paragraph each: the markets note, "Also moved, not looked up", the data
notes and the source note under Upcoming events (14, 14, 14 and 12 lines on a phone on
23 Nov 2026). The words are the same; each block now breaks where its parts end. Pinned here:

1. a writer's note of three sentences or more becomes a list, one sentence a line, with no word
   lost, moved or changed; a shorter one stays a paragraph;
2. "Also moved" is one row a name;
3. the Upcoming events source note is one row for each kind of date, in its own words.
"""
import re
from pathlib import Path

from components.briefing.daily_briefing import briefing_card_html
from components.briefing.daily_briefing_v2 import _points, _sentences

_CSS = (Path(__file__).resolve().parent.parent / "assets" / "theme.css").read_text(encoding="utf-8")

_NOTES = ("The 20 Nov briefing gave gold's fall as 5.1% for Thursday 19 Nov. That price was not final: "
          "Thursday's final move was −1.5%, and most of the fall belongs to Friday. Outlets give smaller "
          "falls for gold on Friday (Reuters: spot −2.8%; Investing.com: futures −4%). The run's calendar "
          "lists Dell's results on 25 Nov; Dell's own notice says Tuesday 24 Nov.")


def _block(css: str, opener: str) -> str:
    """The body of the first ``opener { … }`` block, braces balanced."""
    start = css.index(opener)
    i = css.index("{", start)
    depth, j = 1, i + 1
    while depth:
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        j += 1
    return css[i + 1:j - 1]


def _card(**over) -> str:
    latest = {
        "schema": 2, "id": "20261123T111708Z", "ts_sgt": "2026-11-23T19:17:08+08:00", "data_date": "2026-11-23",
        "what_matters": [{"kind": "macro", "head": "A headline."}],
        "numbers": {"health": {"fetched": 35, "expected": 35}},
    }
    latest.update(over)
    return briefing_card_html({"schema": 1, "latest": latest, "recent": []}, "2026-11-23")


# ── 1. a note's sentences ────────────────────────────────────────────────────
def test_sentences_break_at_sentence_ends_only():
    parts = _sentences(_NOTES)
    assert len(parts) == 4
    assert parts[0] == "The 20 Nov briefing gave gold's fall as 5.1% for Thursday 19 Nov."
    # A decimal point, "Investing.com:" and a semicolon are not sentence ends.
    assert parts[2] == ("Outlets give smaller falls for gold on Friday (Reuters: spot −2.8%; "
                        "Investing.com: futures −4%).")
    # Nothing lost, moved or changed.
    assert " ".join(parts) == _NOTES


def test_an_abbreviation_does_not_end_a_sentence():
    text = "Dell's call is at 3:30 p.m. Central on Tuesday. Results come before the call. Korea is shut."
    assert _sentences(text) == ["Dell's call is at 3:30 p.m. Central on Tuesday.",
                                "Results come before the call.", "Korea is shut."]
    assert _sentences("Nvidia vs. AMD this week. No. 1 by sales.") == ["Nvidia vs. AMD this week.",
                                                                       "No. 1 by sales."]


def test_a_sentence_can_start_with_a_figure_or_a_quote():
    assert _sentences("Gold fell. 14 names have an RSI under 30. “Risk-off,” said Reuters.") == [
        "Gold fell.", "14 names have an RSI under 30.", "“Risk-off,” said Reuters."]
    assert _sentences("") == [] and _sentences(None) == []



def test_a_note_of_two_sentences_is_a_paragraph_and_one_of_three_is_a_list():
    assert _points("Clean day.", "bf-dntext") == '<p class="bf-dntext">Clean day.</p>'
    assert _points("One. Two.", "bf-cap") == '<p class="bf-cap">One. Two.</p>'
    assert _points("One. Two. Three.", "bf-cap") == '<ul class="bf-cap bf-pts"><li>One.</li><li>Two.</li><li>Three.</li></ul>'
    assert _points("", "bf-cap") == "" and _points(None, "bf-cap") == ""
    html = _points(_NOTES, "bf-dntext")
    assert html.startswith('<ul class="bf-dntext bf-pts"><li>') and html.count("<li>") == 4
    # The list holds the note's own words in the note's own order.
    assert " ".join(re.findall(r"<li>(.*?)</li>", html)) == _NOTES



def test_list_items_are_escaped():
    html = _points("A <b>bold</b> claim. Second point. Third point.", "bf-cap")
    assert html.startswith('<ul class="bf-cap bf-pts">')
    assert "<b>" not in html and "&lt;b&gt;bold&lt;/b&gt;" in html


def test_card_sets_long_data_notes_and_markets_note_as_lists():
    html = _card(data_notes=_NOTES, tape_note=_NOTES,
                 numbers={"health": {"fetched": 35, "expected": 35},
                          "tape": [{"name": "SPY", "chg_pct": -3.64, "5d_pct": -8.6}]})
    assert html.count('<ul class="bf-dntext bf-pts">') == 1
    assert html.count('<ul class="bf-cap bf-pts">') == 1
    short = _card(data_notes="Clean day.")
    assert '<p class="bf-dntext">Clean day.</p>' in short and "bf-pts" not in short


# ── 2. also moved ────────────────────────────────────────────────────────────
def test_also_moved_is_one_row_a_name():
    html = _card(
        movers=[{"key": "MSFT", "why": "Copilot overhaul.", "why_state": "found"}],
        numbers={"movers": {"MSFT": {"name": "Microsoft", "market": "US", "chg_pct": 3.66, "x_usual": 2.1}},
                 "also_moved": [{"key": "TSM", "name": "TSMC", "chg_pct": -9.48, "x_usual": 3.4, "vol_ratio": 2.08},
                                {"key": "U11_SI", "name": "UOB", "chg_pct": 2.14, "x_usual": 2.0,
                                 "vol_ratio": 0.72, "vol_basis": "same_time_of_day"},
                                {"key": "WRD", "name": "WeRide", "chg_pct": -4.49, "x_usual": 1.4}]})
    block = html.split('<div class="bf-also">', 1)[1].split("</div>", 1)[0]
    assert block.startswith("<b>Also moved, not looked up:</b><ul>")
    assert block.count("<li>") == 3
    assert ('<li><span class="bf-also-n">TSMC</span><span class="bf-also-m bf-down">−9.48%</span>'
            '<span class="bf-also-x">3.4× usual · vol 2.08×</span></li>') in block
    # A market still open when the report ran: volume against the usual by that time of day.
    assert "2.0× usual · vol 0.72× usual so far" in block
    # No volume on file: the row says nothing about it.
    assert '<span class="bf-also-x">1.4× usual</span>' in block


# ── 3. the Upcoming events source note ───────────────────────────────────────

def test_upcoming_events_source_note_is_one_row_for_each_kind_of_date():
    html = _card(numbers={"health": {"fetched": 35, "expected": 35},
                          "further_out": [{"date": "2026-12-09", "kind": "macro", "what": "FOMC Rate Decision",
                                           "later": False}]})
    note = html.split('<ul class="bf-prov bf-prov-list">', 1)[1].split("</ul>", 1)[0]
    rows = re.findall(r"<li>(.*?)</li>", note)
    assert len(rows) == 5
    # Each row leads with its own first words in bold, and only those (outside review, finding 9).
    leads = [re.match(r"<b>(.*?)</b> ", r).group(1) for r in rows]
    assert leads == ["Earnings dates", "Macro:", "Policy dates", "Conferences:", "Not held:"]
    # The rows read on as the one paragraph did: not a word added, dropped or moved.
    assert re.sub(r"</?b>", "", " ".join(rows)) == (
        "Earnings dates past 14 days are the exchange's local date. Most come from Yahoo Finance's calendar: "
        "“estimated date” marks one Yahoo itself calls an estimate, and an unmarked one can still move. “date "
        "confirmed” marks a date the project took from the company's own announcement. Macro: high-impact "
        "releases only, dated in New York time, so a Singapore-morning release (MAS) shows the day before. "
        "Policy dates (a tariff taking effect, a deadline) and company releases the calendar feed does not "
        "carry: entered by hand from the official notice, in that authority's own date. Conferences: the "
        "pipeline's tech-events list. Not held: results from a company off the watchlist that move names on "
        "it (looked up 21 days ahead).")


def test_other_sections_keep_a_one_line_source_note():
    html = _card(numbers={"health": {"fetched": 35, "expected": 35},
                          "tape": [{"name": "SPY", "chg_pct": -3.64, "5d_pct": -8.6}]})
    assert '<p class="bf-prov">Numbers: morning report</p>' in html


# ── the styles ───────────────────────────────────────────────────────────────

def test_list_styles_are_ink_and_hairlines_only():
    # The list block ends where the next dated block starts (text sizes and the direction of a
    # move, 2026-11-24), which names --up / --down for two classes of its own.
    block = _CSS[_CSS.index("Long text set as lists"):_CSS.index("Briefing card: text sizes, spacing")]
    for selector in (".bf ul.bf-pts {", ".bf ul.bf-pts > li {", ".bf ul.bf-prov-list {",
                     ".bf .bf-also ul {", ".bf .bf-also li {"):
        assert selector in block, selector
    # Colour is a claim: a caveat or an unexplained move takes no tone or kind colour.
    for tone in ("--stress", "--tone-", "--up", "--down", "--metric-", "--brass", "--calendar", "--accent"):
        assert tone not in block, tone
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", block)
    # The old paragraph rule for "Also moved" still sets the block's type and spacing.
    assert ".bf .bf-also {" in _CSS
    # A name keeps room beside the move and the detail (214px of the row): at 250px columns it had 36px.
    # A card narrower than that (a 320px phone) takes its own width, not 300px and a sideways scroll.
    assert "minmax(min(300px, 100%), 1fr)" in _block(block, ".bf .bf-also ul {")
    # A long name wraps inside its cell and cannot push the row wider.
    name = _block(block, ".bf-also-n {")
    assert "min-width: 0" in name and "overflow-wrap: anywhere" in name
    # On a card up to 300px the detail drops under the name and the move: in three columns
    # a name had 53px and broke inside a word.
    tiny = _block(block, "@container (max-width: 300px)")
    assert "grid-template-columns: minmax(0, 1fr) auto" in _block(tiny, ".bf .bf-also li {")
    assert ".bf-also-x { grid-column: 1 / -1; }" in tiny


# ── 4. the writer's own lines, text under a headline, recheck questions ───────
def test_a_note_written_one_point_a_line_keeps_the_writers_points():
    """From 2026-11-24 the briefing puts each point of a markets note or a data note on its
    own line; a point may be several sentences and is not cut again."""
    note = "Gold: the 20 Nov figure was not final. Thursday's final move was −1.5%.\nDell reports Tuesday 24 Nov."
    html = _points(note, "bf-dntext")
    assert html == ('<ul class="bf-dntext bf-pts">'
                    "<li>Gold: the 20 Nov figure was not final. Thursday's final move was −1.5%.</li>"
                    "<li>Dell reports Tuesday 24 Nov.</li></ul>")
    # One line is not a list of one.
    assert _points("Clean day.\n", "bf-dntext") == '<p class="bf-dntext">Clean day.</p>'


def test_no_line_break_from_a_note_reaches_the_page():
    """A blank line inside a paragraph of the card splits it, and the half after it is set
    as a plain <p> that has lost the paragraph's class (one test page, 2026-11-24, Streamlit
    1.58; one line break displayed the same as none, and the sections after the split were
    unchanged in that test). Whatever line breaks a text carries, none is printed."""
    for text in ("Clean day.\n\n", "One.\n\nTwo.", "A point.\n\nA second point.\n\n\nA third.",
                 "One sentence\nbroken over lines. Second. Third. Fourth."):
        assert "\n" not in _points(text, "bf-dntext"), text
    html = _card(what_matters=[{"kind": "macro", "head": "A headline.", "detail": "One.\n\nTwo."}],
                 data_notes="Coverage is full.\n\nNo latch.", tape_note="Quiet.\n\n",
                 vix_note={"text": "The VIX closed at 20.\n\nNo cause found."},
                 after_data=[{"lead": "Oil", "text": "Brent rose.\n\nWTI too."}],
                 numbers={"health": {"fetched": 35, "expected": 35},
                          "tape": [{"name": "SPY", "chg_pct": -3.64, "5d_pct": -8.6}]})
    assert "\n" not in html
    # Two blank-line-separated points are the writer's two lines.
    assert '<ul class="bf-dntext bf-pts"><li>Coverage is full.</li><li>No latch.</li></ul>' in html


_LONG = "Reuters says the debut failed to catch fire. The index fell for a seventh session. The Nasdaq fell 5.3%. CNBC lists five forces."
_SRC = [{"title": "Story (CNBC)", "url": "https://www.cnbc.com/x", "date": "2026-11-20"}]



def test_text_under_a_headline_stays_a_paragraph_however_long():
    """A What-matters detail, an After-the-data item, the VIX note and a result are one topic
    under their own headline. They were set as lists from four sentences for a few hours on
    2026-11-24; an outside review found that worse than the paragraph (a second rule beside
    the item's own, source links read as the last sentence's, 510px more on a phone)."""
    html = _card(what_matters=[{"kind": "move", "head": "All 35 names fell.", "detail": _LONG, "src": [0]}],
                 after_data=[{"lead": "US futures on Monday", "text": _LONG, "src": [0]}],
                 vix_note={"text": _LONG, "src": [0]},
                 earnings={"out": [{"key": "WRD", "text": _LONG, "src": [0]}]},
                 numbers={"health": {"fetched": 35, "expected": 35}, "names": {"WRD": "WeRide"},
                          "tape": [{"name": "SPY", "chg_pct": -3.64, "5d_pct": -8.6}]},
                 sources=_SRC)
    assert "bf-pts" not in html
    assert f'<span class="bf-det">{_LONG} <a class="bf-src"' in html      # the links follow the paragraph
    assert f"<li><b>US futures on Monday</b> {_LONG} <a class=" in html
    assert f'<div class="bf-vix"><b>The VIX</b><p>{_LONG} <a class=' in html
    assert f"<li><b>WeRide</b> {_LONG} <a class=" in html



def test_recheck_questions_are_one_a_line():
    html = _card(calendar=[{"sgt": "2026-11-25T21:30", "kind": "macro", "what": "US GDP", "impact": "high"}],
                 rechecks=[{"date": "2026-11-25", "items": [{"name": "Nvidia", "q": "Is the 10-Q out?"},
                                                            {"name": "Navitas", "q": "Did it file its reply?"}]}])
    assert ('<span><span class="bf-rq"><b>Nvidia</b> Is the 10-Q out?</span>'
            '<span class="bf-rq"><b>Navitas</b> Did it file its reply?</span></span>') in html
    assert " · <b>" not in html
    assert ".bf-rchk li .bf-rq { display: block; }" in _CSS


# ── after the outside review of this change (2026-11-24) ─────────────────────
def test_initials_titles_and_a_month_before_a_day_number_do_not_end_a_sentence():
    assert _sentences("J.P. Morgan cut its target. Shares fell.") == ["J.P. Morgan cut its target.", "Shares fell."]
    assert _sentences("Talks in Washington, D.C. 2026 budget next. Then a vote.") == [
        "Talks in Washington, D.C. 2026 budget next.", "Then a vote."]
    assert _sentences("Sec. 232 tariffs start. Chips are exempt.") == ["Sec. 232 tariffs start.", "Chips are exempt."]
    assert _sentences("Due Dec. 9 in court. Then appeal.") == ["Due Dec. 9 in court.", "Then appeal."]
    # A month at the end of a sentence still ends it (the usual form in these notes).
    assert _sentences("Korea is shut Friday 9 Oct. Intel has not posted.") == [
        "Korea is shut Friday 9 Oct.", "Intel has not posted."]
    # A sentence may close on a quote or a bracket after its full stop.
    assert _sentences('He said "no." Then he left.') == ['He said "no."', "Then he left."]
    assert _sentences("A note (see the filing.) Next point.") == ["A note (see the filing.)", "Next point."]


def test_the_chart_facts_note_is_a_list_from_three_sentences():
    note = "Every name is below its average. Nvidia's RSI is the lowest. Nebius is the furthest below."
    html = _card(chart_facts={"names": ["NVDA"], "note": note},
                 numbers={"health": {"fetched": 35, "expected": 35},
                          "chart": {"NVDA": {"name": "Nvidia", "vs_sma50_pct": -39.4, "rsi": 15.0}}})
    assert '<ul class="bf-cap bf-pts"><li>Every name is below its average.</li>' in html
    short = _card(chart_facts={"names": ["NVDA"], "note": "Plain note."},
                  numbers={"health": {"fetched": 35, "expected": 35},
                           "chart": {"NVDA": {"name": "Nvidia", "vs_sma50_pct": -39.4, "rsi": 15.0}}})
    assert '<p class="bf-cap">Plain note.</p>' in short


def test_a_line_break_in_the_middle_of_a_sentence_is_not_a_point():
    """The writer's lines are points only when every line ends a sentence; a stray break
    leaves the note to be cut by sentence (outside review, finding 7)."""
    stray = "Gold fell\non Friday. Oil rose. The dollar was flat."
    assert _points(stray, "bf-cap") == ('<ul class="bf-cap bf-pts"><li>Gold fell on Friday.</li>'
                                        "<li>Oil rose.</li><li>The dollar was flat.</li></ul>")
    assert _points("Gold fell\non Friday.", "bf-cap") == '<p class="bf-cap">Gold fell on Friday.</p>'


def test_no_text_on_the_card_carries_a_line_break_into_the_page():
    """Every writer's text goes through ``_txt``, which turns any run of spaces or line breaks
    into one space (outside review, finding 8)."""
    from components.briefing.sections import _txt
    assert _txt("One.\n\nTwo.\r\n  Three.") == "One. Two. Three."
    html = _card(what_matters=[{"kind": "macro", "head": "A\n\nheadline.", "detail": "One.\n\nTwo."}],
                 tonight="No release\n\ntonight.",
                 calendar=[{"sgt": "2026-11-25T21:30", "kind": "macro", "what": "US\n\nGDP", "impact": "high"}],
                 movers=[{"key": "MSFT", "why": "Copilot\n\noverhaul.", "why_state": "found"}],
                 numbers={"health": {"fetched": 35, "expected": 35},
                          "movers": {"MSFT": {"name": "Microsoft", "market": "US", "chg_pct": 3.66, "x_usual": 2.1}}})
    assert "\n" not in html
