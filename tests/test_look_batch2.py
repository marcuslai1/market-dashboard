"""Look review 2026-11-23, second batch (an outside review of the live site).

Three things, each pinned here so a later stylesheet edit cannot undo it quietly:

1. The Watchlist's seven columns fit a tablet-width table (the Earnings column
   used to fall off the right edge between 720 and 970px of window width).
2. Phone tap targets are at least 44px tall.
3. An older report date on the Watchlist says so in a pinned strip (the masthead
   always carries the latest report's date).

A second outside review of the build (same day) changed the strip's sentence, the
phone layout of the Terminology jump list and the tablet rule's upper bound, and
named three gaps in these tests; each is marked "second review" below.
"""
import glob
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import live_prices
from components.watchlist.grid import past_report_notice_html

_CSS = (Path(__file__).resolve().parent.parent / "assets" / "theme.css").read_text(encoding="utf-8")

#: The narrowest table the tablet rule has to serve: a 720px window less a 10px
#: scrollbar and Streamlit's 16px page padding on each side (measured 2026-11-23).
NARROWEST_TABLET_TABLE_PX = 678


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


#: The upper bound was 991.98px until the layout review of 2026-11-24 released the table's sideways
#: scroller at every width: at 992px the wide tracks had 3px to spare.
_TABLET = "@media (min-width: 719.01px) and (max-width: 1099.98px)"


# ── 1. tablet columns ────────────────────────────────────────────────────────
def test_tablet_tracks_fit_the_narrowest_tablet_table():
    body = _block(_CSS, _TABLET)
    rule = _block(body, ".tk-row, .tk-row.tk-head, details.tk-details > summary")
    minimums = [int(px) for px in re.findall(r"minmax\((\d+)px,", rule)]
    assert len(minimums) == 7, "the Watchlist row is seven tracks"
    gap = int(re.search(r"gap:\s*(\d+)px", rule).group(1))
    pad = int(re.search(r"padding-left:\s*(\d+)px", rule).group(1))
    assert int(re.search(r"padding-right:\s*(\d+)px", rule).group(1)) == pad
    assert sum(minimums) + 6 * gap + 2 * pad <= NARROWEST_TABLET_TABLE_PX
    # The group header's side padding keeps step with the rows under it.
    group = _block(body, ".tk-group {")
    assert f"padding-left: {pad}px" in group and f"padding-right: {pad}px" in group


def test_tablet_rule_starts_where_the_phone_cards_stop():
    """The phone reflow is ``max-width: 719px``; a 719.3px window (a zoomed or
    scaled one) must not fall between the two rules and clip again. The upper
    bound is past 980px so a wide scrollbar cannot squeeze the last column's
    padding (second review, finding 7). Decimals, not the ``(width > 719px)``
    range form, which older Safari drops whole."""
    assert _TABLET in _CSS
    assert "@media (min-width: 720px) and" not in _CSS
    assert "@media (width >" not in _CSS


# ── 2. phone tap targets ─────────────────────────────────────────────────────
def test_phone_tap_targets_take_a_44px_minimum():
    marker = _CSS.index("9: phone tap targets")
    tail = _CSS[marker:]
    # The tabs take it at every width: the strip's own 11px moves inside the tab.
    before_media = tail[:tail.index("@media (max-width: 719px)")]
    tab = _block(before_media, '.st-key-page_nav [role="radiogroup"] > label {')
    assert "min-height: 44px" in tab
    assert "padding-top: 11px !important" in tab   # or the tab's words jump up 11px
    assert "padding-top: 0 !important" in _block(before_media, '.st-key-page_nav [role="radiogroup"] {')
    body = _block(tail, "@media (max-width: 719px)")
    # The Order options were on this list until Order became a select in the page's
    # toolbar (layout review 2026-11-24; tests/test_layout_batch1.py pins its 44px).
    for selector in (
        ".term-index-item",
        ".term-door > summary",
    ):
        assert "min-height: 44px" in _block(body, selector + " {"), selector
    # The drill-down drawers share the Terminology drawers' rule.
    assert ".tk-drilldown details.dd-drawer > summary,\n  .term-door > summary" in body.replace("\r\n", "\n")


def test_phone_recheck_line_grows_by_padding():
    """The briefing's one disclosure line (second review, finding 6a)."""
    marker = _CSS.index("9: phone tap targets")
    body = _block(_CSS[marker:], "@media (max-width: 719px)")
    assert "padding: 12px 0" in _block(body, ".bf-rchk summary {")


def test_phone_jump_list_runs_in_two_columns():
    """Eleven 44px links in one column were 484px tall (second review, finding 4)."""
    marker = _CSS.index("9: phone tap targets")
    body = _block(_CSS[marker:], "@media (max-width: 719px)")
    assert "column-count: 2" in _block(body, ".term-index {")
    assert "column-span: all" in _block(body, ".term-index-head {")
    assert "break-inside: avoid" in _block(body, ".term-index-item {")


# ── 3. an older report date ──────────────────────────────────────────────────
def test_past_report_strip_is_silent_on_the_latest_date():
    assert past_report_notice_html("2026-11-23", "2026-11-23") == ""
    assert past_report_notice_html("", "2026-11-23") == ""


def test_past_report_strip_names_both_dates():
    html = past_report_notice_html("2026-10-23", "2026-11-23")
    assert 'class="wl-past"' in html
    assert "Past report" in html
    assert "Fri 23 Oct 2026" in html          # the date on screen
    assert "Mon 23 Nov 2026" in html          # the latest, which the masthead shows
    # It claims the prices only (second review, finding 1): the sales-growth lines,
    # the company profile and the earnings history are the current files, and none
    # of them is a price.
    assert "Prices are from this report, not the latest one" in html
    for too_wide in ("rows", "everything", "all figures"):
        assert too_wide not in html.lower(), too_wide
    # The latest date is its own span, which the stylesheet drops on a phone.
    assert '<span class="wl-past-latest"> (Mon 23 Nov 2026)</span>' in html


def test_past_report_strip_escapes_an_unexpected_date_string():
    html = past_report_notice_html("<b>x</b>", "2026-11-23")
    assert "<b>x</b>" not in html and "&lt;b&gt;" in html


def test_past_report_strip_is_pinned_without_a_tone_colour():
    assert ('[data-testid="stElementContainer"]:has(.wl-past) { position: sticky; top: 0; z-index: 40; }'
            in _CSS)   # 40 puts it above the pinned column header (30)
    rules = " ".join(re.findall(r"\.wl-past[^{]*\{[^}]*\}", _CSS))
    assert rules.count("{") >= 5, "the strip's own rules were not found"
    # The verdict and fault colours as theme.css names them (second review, 6b).
    for tone in ("--stress", "--tone-", "--up", "--down"):
        assert tone not in rules, tone



def test_strip_has_one_fixed_height_at_every_width():
    """Two things pin directly under the strip (the column header on a PC, an opened
    row's summary at every width since the layout review of 2026-11-24), so the strip
    cannot grow by wrapping: 38px on one line, 56px on a phone, the sentence cut with an
    ellipsis (second review, findings 3 and 6b). The one-line form is the base and a
    phone overrides it, so no window width falls between two rules."""
    marker = _CSS.index("The strip has ONE known height at every width")
    tail = _CSS[marker:]
    base = tail[:tail.index("@media")]
    strip = _block(base, ".wl-past {")
    assert "height: 38px" in strip and "flex-wrap: nowrap" in strip and "overflow: hidden" in strip
    assert "white-space: nowrap" in _block(base, ".wl-past-tag, .wl-past-date {")
    note = _block(base, ".wl-past-note {")
    for decl in ("min-width: 0", "white-space: nowrap", "overflow: hidden", "text-overflow: ellipsis"):
        assert decl in note, decl
    phone = _block(tail, "@media (max-width: 719px)")
    assert "height: 56px" in _block(phone, ".wl-past {") and "flex-wrap: wrap" in _block(phone, ".wl-past {")
    assert "@media (min-width: 719.01px) {" not in tail[:tail.index("On a PC the column header")]


def test_pinned_column_header_sits_under_the_strip_on_a_pc():
    """Both are pinned from 1100px; the header's offset must equal the strip's
    fixed height or one covers the other."""
    marker = _CSS.index("On a PC the column header is pinned too")
    body = _block(_CSS[marker:], "@media (min-width: 1100px)")
    # The offset asks for the same wrapper the pin is on, so a renamed wrapper
    # undoes both together (second review, finding 3). No :has() inside a :has().
    head = _block(body, '[data-testid="stMain"]:has([data-testid="stElementContainer"] .wl-past)'
                        ' .tk-scroll > .tk-row.tk-head {')
    assert "top: 38px" in head
    assert ":has(.wl-past) .tk-scroll" not in _CSS
    assert not re.search(r":has\([^()]*:has\(", _CSS)


def test_phone_strip_drops_the_latest_date():
    marker = _CSS.index("The strip has ONE known height at every width")
    body = _block(_CSS[marker:], "@media (max-width: 719px)")
    assert "display: none" in _block(body, ".wl-past-latest {")


def test_watchlist_page_shows_the_strip_only_on_an_older_date():
    files = sorted(glob.glob("data/morning_report_*.json"))
    if len(files) < 2:
        pytest.skip("needs two report dates checked out")
    older = re.search(r"(\d{4}-\d{2}-\d{2})", files[0]).group(1)
    at = AppTest.from_file("dashboard.py", default_timeout=60)
    at.run()
    at.radio(key="page_nav").set_value("Watchlist").run()
    assert not at.exception, [e.value for e in at.exception]
    page = " ".join(str(m.value) for m in at.markdown)
    assert 'class="wl-past"' not in page
    assert "LIVE" in page                     # the latest date keeps its live line (6c)

    # A widget on a non-default page cannot be driven through dashboard.py under
    # AppTest (st.navigation resets to the default page on every rerun, see
    # test_app_pages), so the older date is seeded before the page is opened.
    at = AppTest.from_file("dashboard.py", default_timeout=60)
    at.session_state["watchlist_date"] = older
    at.run()
    at.radio(key="page_nav").set_value("Watchlist").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="watchlist_date").value == older
    page = " ".join(str(m.value) for m in at.markdown)
    assert 'class="wl-past"' in page
    assert "Snapshot · report-date values" not in page   # the strip says it instead
    assert "viewing" not in page.lower()      # the subtitle no longer repeats the date
