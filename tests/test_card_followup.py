"""Three follow-ups on the briefing card (owner 2026-11-24, on the outside review of the card's filler).

The review's findings 8 and 9 named what the card still showed every day without being asked. The
owner took four; three are this page's (the fourth, which recheck rows reach the card, is decided
by MarketReport's ``publish``):

1. Below 1220px the chart follows names that moved. It was under the dated blocks, about nine
   screens down a phone. (The markup's order: tests/test_layout_batch2.py, tests/test_briefing_card.py.)
2. The five-row source note under Upcoming events is a closed drawer, "About these dates".
3. "Also moved, not looked up" is a closed drawer when it lists more than six names.
"""
import re
from pathlib import Path

from components.briefing.daily_briefing import briefing_card_html
from components.briefing.daily_briefing_v2 import _ALSO_OPEN, _sec
from tests.test_briefing_card import _v2
from tests.test_briefing_type import PHONE, _phone, _px
from tests.test_look_batch2 import _block

CSS = (Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(encoding="utf-8")


def _card_with_also(n: int) -> str:
    payload = _v2()
    payload["latest"]["numbers"]["also_moved"] = [
        {"key": f"T{i}", "name": f"Name {i}", "chg_pct": 2.0 + i, "x_usual": 2.1, "vol_ratio": 1.2} for i in range(n)]
    return briefing_card_html(payload, "2026-09-28")


# ── the source note under Upcoming events ───────────────────────────────────

def test_the_upcoming_events_note_is_a_closed_drawer_under_the_dates():
    html = briefing_card_html(_v2(), "2026-09-28")
    far = html[html.index("<h3>Upcoming events</h3>"):].split("</section>", 1)[0]
    assert far.count("<details") == 1
    dates, drawer = far.split('<details class="bf-about">', 1)
    # Closed: the browser opens a <details> only when it carries `open`.
    assert drawer.startswith('<summary>About these dates</summary><ul class="bf-prov bf-prov-list"><li><b>Earnings dates</b> ')
    assert drawer.endswith("</ul></details>") and drawer.count("<li>") == 5
    # Every date stays on the page without a click, the second month too (owner 2026-09-29).
    assert '<ul class="bf-far">' in dates and '<div class="bf-later">' in dates
    assert "bf-prov" not in dates


def test_upcoming_events_says_in_view_that_its_dates_are_not_singapore_time():
    """The closed note says a macro date is New York's and an earnings date the exchange's. Week
    ahead and Earnings above are in Singapore time, so the heading's aside says these are not."""
    html = briefing_card_html(_v2(), "2026-09-28")
    head = html[html.index("<h3>Upcoming events</h3>"):].split("</div>", 1)[0]
    assert head.endswith('<span class="bf-aside">to two months · dates only, not converted to SGT</span>')


def test_a_one_sentence_source_note_is_never_a_drawer():
    html = briefing_card_html(_v2(), "2026-09-28")
    assert html.count('class="bf-about"') == 1
    assert '<p class="bf-prov">Calendar: morning report · Rechecks: catalysts.json</p>' in html
    # A drawer's name on a one-sentence note changes nothing, and a note of no rows is no note.
    one = _sec("T", "<p>x</p>", prov="One line.", prov_title="About")
    assert one.endswith('<p>x</p><p class="bf-prov">One line.</p></section>') and "<details" not in one
    assert _sec("T", "<p>x</p>", prov=[], prov_title="About").endswith("<p>x</p></section>")


# ── also moved ──────────────────────────────────────────────────────────────

def test_a_short_also_moved_list_shows_as_before():
    html = _card_with_also(_ALSO_OPEN)
    assert _ALSO_OPEN == 6
    block = html.split('<div class="bf-also">', 1)[1].split("</div>", 1)[0]
    assert block.startswith("<b>Also moved, not looked up:</b><ul>") and block.count("<li>") == 6
    assert '<details class="bf-also">' not in html


def test_a_long_also_moved_list_is_a_closed_drawer_that_gives_the_count():
    html = _card_with_also(_ALSO_OPEN + 1)
    assert '<div class="bf-also">' not in html
    drawer = html.split('<details class="bf-also">', 1)[1].split("</details>", 1)[0]
    assert drawer.startswith("<summary><b>Also moved, not looked up:</b> 7 names</summary><ul>")
    # Every name is still there, with its move and its direction.
    assert drawer.count("<li>") == 7
    assert '<span class="bf-also-n">Name 6</span><span class="bf-also-m bf-up">+8.00%</span>' in drawer
    # The section's footnote stays outside the drawer: it explains the table above as well.
    after = html.split('<details class="bf-also">', 1)[1].split("</details>", 1)[1].split("</section>", 1)[0]
    assert after.startswith('<p class="bf-prov">') and "are listed without a reason" in after


# ── the drawers' lines ──────────────────────────────────────────────────────

def test_the_drawer_lines_are_headings_inside_a_block():
    """One size for the card's three drawer lines, over the rows they open, on a PC and a phone."""
    for line in (".bf .bf-also > summary", ".bf .bf-about > summary"):
        assert _px(line) == _px(".bf .bf-rchk summary") == _px(".bf .bf-also > b") == 15, line
        assert _phone(line) == 15 and _phone(line) > _phone(".bf .bf-also li"), line
    assert "bf-also > summary" not in PHONE and "bf-about" not in PHONE   # no phone rule resizes them
    # The note inside "About these dates" is still the caption it was.
    assert ".bf .bf-prov { font-size: 12.5px;" in CSS and _px(".bf .bf-prov") is None   # set once, outside the sizes block
    assert _phone(".bf .bf-about > summary") > _phone(".bf .bf-prov") == 13


def test_a_phone_gives_the_new_drawer_lines_a_44px_target():
    """The same way as the rechecks line: 12px of padding above and below, and 12px less margin."""
    body = _block(CSS[CSS.index("9: phone tap targets"):], "@media (max-width: 719px)")
    assert "padding: 12px 0" in _block(body, ".bf-about > summary {")
    assert "padding: 12px 0" in _block(body, ".bf-also > summary {")
    assert "margin-top: 2px" in _block(body, ".bf details.bf-about, .bf details.bf-also {")
    # At every width they are set like the rechecks line: a pointer, the sentence grey, the marker kept.
    rule = _block(CSS, ".bf .bf-also > summary, .bf .bf-about > summary {")
    assert "cursor: pointer" in rule and "color: var(--ink-2)" in rule
    # The count line's lead is in the ink of the rechecks line's lead.
    assert "color: var(--ink)" in _block(CSS, ".bf .bf-also > summary b {")
    assert "color: var(--ink)" in _block(CSS, ".bf-rchk summary b {")
    # No rule takes the marker away: none hides it, re-lays the line out, or names the marker.
    for line in re.findall(r"[^{}]*summary[^{}]*\{[^{}]*\}", CSS):
        if "bf-also" in line or "bf-about" in line:
            selector, rules = line.rsplit("{", 1)
            assert "list-style" not in rules and "display:" not in rules, line
            assert "marker" not in rules and "::marker" not in selector, line


def test_a_phone_takes_the_drawer_lines_padding_off_what_follows():
    """The 12px under a line would add to the gap after it: 20px above an opened list, 26 and
    36px under a closed line (outside review of the build, 2026-11-25)."""
    body = _block(CSS[CSS.index("9: phone tap targets"):], "@media (max-width: 719px)")
    assert "margin-top: 0" in _block(body, ".bf details.bf-also[open] > ul, .bf details.bf-about[open] > .bf-prov {")
    assert "margin-top: 2px" in _block(body, ".bf details.bf-also:not([open]) + .bf-prov {")
    assert "margin-bottom: -12px" in _block(body, ".bf details.bf-about:not([open]) {")
