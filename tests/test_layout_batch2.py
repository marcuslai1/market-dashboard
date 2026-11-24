"""Layout review 2026-11-24, batch 2: the PC (an outside review of the layout), and the page's width.

Four changes, each pinned here so a later edit cannot undo it quietly:

Width. The page's content is at most 1,200px wide. The rule that used to say so named a class the
       current Streamlit page does not carry, so there was no cap (1,750px in a 1,920px window).
P3.    An opened Watchlist row stays pinned at the top of the window while its panel scrolls, and
       its panel covers the pinned column header. The review's third part, one row open at a
       time, was built, measured and left out: see ``test_rows_do_not_share_a_name``.
P5.    From 1220px the briefing card is two columns: today left, what is coming right.
P8.    The opened row's panel is one grid: on a PC the chart beside the levels, then technicals,
       valuation and news in a row of three.
"""
import re
from pathlib import Path

from components.briefing.daily_briefing import briefing_card_html
from components.watchlist.drilldown import render_drilldown_detail_html
from components.watchlist.row import render_ticker_details_html

_CSS = (Path(__file__).resolve().parent.parent / "assets" / "theme.css").read_text(encoding="utf-8")
_PAST = '[data-testid="stMain"]:has([data-testid="stElementContainer"] .wl-past)'


def _block(css: str, opener: str) -> str:
    """The body of the first ``opener { … }`` block, braces balanced."""
    start = css.index(opener)
    i = css.index("{", start)
    depth, j = 1, i + 1
    while depth:
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        j += 1
    return css[i + 1:j - 1]


def _outside_media(css: str) -> str:
    """``css`` with every ``@media`` / ``@container`` block removed: the rules that hold at every width."""
    out, i = [], 0
    for m in re.finditer(r"@(?:media|container)[^{]*\{", css):
        if m.start() < i:
            continue
        out.append(css[i:m.start()])
        depth, j = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        i = j
    out.append(css[i:])
    return "".join(out)


_BATCH2 = _CSS[_CSS.index("Layout review 2026-11-24, batch 2"):]


# ── the page's width ─────────────────────────────────────────────────────────
def test_page_content_is_capped_at_1200px():
    rule = _block(_CSS, '[data-testid="stMainBlockContainer"] {')
    # Streamlit counts its 5rem side padding inside the container's width.
    assert "max-width: calc(1200px + 10rem) !important" in rule
    assert "margin-left: auto" in rule and "margin-right: auto" in rule
    # The old rule named a class the page no longer has; nothing may bring it back as the cap.
    assert not re.search(r"(?m)^\.main \.block-container \{[^}]*max-width", _CSS)


# ── P3: an opened row ────────────────────────────────────────────────────────

def test_an_opened_row_is_pinned_and_its_panel_covers_the_column_header():
    always = _outside_media(_BATCH2)
    assert "details.tk-details[open] > summary { position: sticky; top: 0; z-index: 35; }" in always
    # Sticky needs the table's sideways scroller released, at every width.
    assert ".tk-scroll:has(> .tk-row.tk-head) { overflow-x: visible; }" in always
    # The header stays pinned (30); an opened panel paints over it (32) under the pinned row
    # (35) and the "Past report" strip (40). The first build unpinned the header whenever any
    # row was open, which left the rest of the table without column labels (review finding 3).
    assert ".tk-drilldown { position: relative; z-index: 32; }" in always
    assert "position: static" not in _BATCH2
    assert "z-index: 30" in _block(_CSS, ".tk-scroll > .tk-row.tk-head {")
    assert "z-index: 40" in _CSS[_CSS.index('[data-testid="stElementContainer"]:has(.wl-past) {'):][:120]



def test_a_pinned_row_sits_under_the_past_report_strip():
    """The offset is the strip's fixed height at that width, and it asks for the wrapper the
    strip's own pin is on."""
    always = _outside_media(_BATCH2)
    assert f"{_PAST} details.tk-details[open] > summary {{ top: 38px; }}" in always
    phone = _block(_BATCH2, "@media (max-width: 719px)")
    assert f"{_PAST} details.tk-details[open] > summary {{ top: 56px; }}" in phone
    strip = _CSS[_CSS.index("The strip has ONE known height at every width"):]
    assert "height: 38px" in _block(_outside_media(strip[:strip.index("On a PC the column header")]), ".wl-past {")
    assert "height: 56px" in _block(_block(strip, "@media (max-width: 719px)"), ".wl-past {")



def test_a_phone_pins_the_whole_row_and_names_its_group():
    """The first build pinned the first line only, which hid the next earnings date and, in a
    sales-growth order, the sales-growth sentence (review finding 5)."""
    phone = _block(_BATCH2, "@media (max-width: 719px)")
    assert "display: none" not in phone
    assert (".tk-scroll:has(> .tk-group) details.tk-details[open] > summary .tk-tick-cluster { display: block; }"
            in phone)
    # The group takes a line of its own under the ticker: beside it, "AI Power
    # Infrastructure" was cut to "AI POWER IN…" (the last outside review, finding 5).
    assert "flex-wrap: wrap" in _block(phone, "details.tk-details[open] > summary > .tk-tick {")
    assert "details.tk-details[open] > summary > .tk-tick .tk-tick-cluster { flex-basis: 100%; }" in phone


def test_rows_do_not_share_a_name():
    """A shared ``name`` on the rows' <details> keeps one open at a time without script. It
    was built for this batch and left out after measuring it: when the row that closes is
    above the one just tapped, the page loses that panel's height and the tapped row jumps
    (277px from the top to 0 in Chrome at 768 and 1440px). Putting it back needs a way to
    hold the page still first."""
    html = render_ticker_details_html("NVDA", {"price": 166.04, "chg_pct": 1.0})
    assert html.startswith('<details class="tk-details"><summary>')
    assert " name=" not in html.split("<summary>", 1)[0]


# ── P5: the briefing card in two columns ─────────────────────────────────────
def _card(**over) -> str:
    latest = {
        "schema": 2, "id": "20261123T111708Z", "ts_sgt": "2026-11-23T19:17:08+08:00", "data_date": "2026-11-23",
        "what_matters": [{"kind": "macro", "head": "A headline."}],
        "calendar": [{"sgt": "2026-11-25T21:30", "kind": "macro", "what": "US GDP", "impact": "high"}],
        "numbers": {"chart": {"NVDA": {"name": "Nvidia", "vs_sma50_pct": -39.4, "rsi": 15.0}}},
    }
    latest.update(over)
    return briefing_card_html({"schema": 1, "latest": latest, "recent": []}, "2026-11-23")


def test_today_and_coming_sections_sit_in_two_wrappers_in_reading_order():
    html = _card()
    today = html.split('<div class="bf-col bf-col-today">', 1)[1].split('<div class="bf-col bf-col-coming">', 1)[0]
    coming = html.split('<div class="bf-col bf-col-coming">', 1)[1].split("</section></div></div>", 1)[0]
    assert "<h3>What matters</h3>" in today and "<h3>Week ahead</h3>" not in today
    assert "<h3>Week ahead</h3>" in coming and "<h3>What matters</h3>" not in coming
    # Chart facts closes the right-hand column (2026-11-24: the left column ran about 550 to 590px
    # past the right, and the chart sat full width under both). It is still the block after the
    # coming dates, so the order on a phone is unchanged.
    assert "<h3>Chart facts</h3>" in coming and "<h3>Chart facts</h3>" not in today
    assert coming.index("<h3>Week ahead</h3>") < coming.index("<h3>Chart facts</h3>")
    assert "<h3>Data notes</h3>" not in coming
    # The masthead before the wrappers, the notes after them: full width.
    order = [html.index(x) for x in ('class="bf-date"', 'class="bf-cols"', "<h3>What matters</h3>",
                                     "<h3>Week ahead</h3>", "<h3>Chart facts</h3>", "</section></div></div>",
                                     "<h3>Data notes</h3>")]
    assert order == sorted(order)


def test_a_day_with_one_group_gets_no_wrappers():
    assert "bf-cols" not in _card(calendar=[])            # nothing coming
    assert "bf-cols" not in _card(what_matters=[])        # nothing for today
    assert "<h3>Week ahead</h3>" in _card(what_matters=[])
    # and Chart facts follows the one group, as it always did
    for html in (_card(calendar=[]), _card(what_matters=[])):
        assert html.index("<h3>Chart facts</h3>") < html.index("<h3>Data notes</h3>")
        assert html.count("<h3>Chart facts</h3>") == 1



def test_two_columns_from_1220px_and_no_box_below():
    assert ".bf-cols, .bf-col { display: contents; }" in _outside_media(_BATCH2)
    tail = _BATCH2[_BATCH2.index(".bf-cols, .bf-col { display: contents; }"):]
    # 1220, not 1100: below about 1200px the left column is under 560px and its sections fall
    # into their phone layouts (review finding 2).
    assert "@media (min-width: 1100px)" not in tail
    wide = _block(tail, "@media (min-width: 1220px)")
    cols = _block(wide, ".bf-cols {")
    assert "display: grid" in cols
    assert "grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr)" in cols
    # Each column is a box of its own and measures itself, so a section's narrow-card rules
    # apply inside it.
    col = _block(wide, ".bf-col {")
    assert "display: block" in col and "container-type: inline-size" in col
    assert "max-width: 720px" in _block(wide, ".bf-cfhead, .bf .bf-cf {")
    # Only the card's first section loses its top rule, not the first one in a column.
    assert ".bf > .bf-sec:first-child { border-top: 0; padding-top: 4px; }" in _CSS
    assert ".bf .bf-sec:first-child {" not in _CSS


def test_the_right_hand_column_is_not_set_like_a_phone():
    """At 381 to 560px a date keeps its place beside its text and Week ahead sets its days two
    abreast; both were phone layouts, and made the column about 1,100px taller than the one
    beside it (review finding 1)."""
    marker = _CSS.index("narrow card (phone, or a narrow column): stack")
    tail = _CSS[marker:]
    assert "bf-far li" not in _block(tail, "@container (max-width: 560px)")
    assert "bf-rchk li" not in _block(tail, "@container (max-width: 560px)")
    phone = _block(tail, "@container (max-width: 380px)")
    assert ".bf .bf-far li { grid-template-columns: 1fr; gap: 2px; }" in phone
    assert ".bf .bf-rchk li { grid-template-columns: 1fr; gap: 2px; }" in phone
    mid = _block(tail, "@container (min-width: 380.01px) and (max-width: 560px)")
    assert ".bf-wk { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in mid


def test_a_narrow_earnings_chart_takes_the_small_labels_whatever_the_window():
    """The chart's quarter labels shrank by window width only, so a narrow chart in the
    right-hand column of a wide window kept the large ones (review finding 2)."""
    marker = _CSS.index("The same for a narrow chart in a wide window")
    narrow = _block(_CSS[marker:], "@container (max-width: 440px)")
    assert "font-size: 11px" in _block(narrow, ".ec-x {") and "white-space: nowrap" in _block(narrow, ".ec-x {")
    assert ".ec-x small { font-size: 11px; }" in narrow
    assert "container-type: inline-size" in _block(_CSS, ".ec { position: relative;")


# ── P8: the opened row's panel ───────────────────────────────────────────────
_NVDA = {"price": 166.04, "chg_pct": 1.0, "currency": "USD", "sma50": 207.0, "sma200": 203.09,
         "rsi_14": 15.0, "vs_sma50_pct": -39.4, "valuation": {"forward_pe": 20.0},
         "recent_news": [{"title": "A headline", "publisher": "Reuters", "date": "2026-11-22"}]}
_HIST = [{"date": f"2026-11-{d:02d}", "price": 200.0 - d, "sma50": 207.0, "sma200": 203.0} for d in range(2, 24)]



def test_the_panel_is_one_grid_of_five_blocks_ahead_of_the_drawers():
    html = render_drilldown_detail_html(
        "NVDA", dict(_NVDA, next_earnings={"date": "2026-12-09", "days_until": 16, "status": "scheduled"}),
        price_hist=_HIST, report_date="2026-11-23", earnings_hist=None)
    assert '<details class="dd-drawer">' in html                # a drawer is there to come after
    grid, rest = html.split('<div class="dd-grid">', 1)[1].split('<details class="dd-drawer">', 1)
    order = [grid.index(x) for x in ('<div class="pc">', ">Levels<", ">Technicals<", ">Valuation<",
                                     '<div class="dd-news">')]
    assert order == sorted(order)
    assert grid.count('<div class="dd-col">') == 3
    assert "dd-news" not in rest and "dd-col" not in rest       # nothing of the grid after a drawer
    assert "dd-cols" not in html



def test_chart_beside_levels_on_a_pc_two_abreast_on_a_tablet_stacked_on_a_phone():
    grid = _block(_CSS, ".tk-drilldown .dd-grid {")
    assert "grid-template-columns: repeat(12, minmax(0, 1fr))" in grid
    assert "grid-column: span 4" in _block(_CSS, ".tk-drilldown .dd-grid > * {")
    chart = _block(_CSS, ".tk-drilldown .dd-grid > .pc {")
    assert "grid-column: span 8" in chart and "margin: 0" in chart       # 8 + 4, then 4 + 4 + 4
    tail = _CSS[_CSS.index(".tk-drilldown .dd-grid > .pc {"):]
    # Twelve tracks from 1220px: at 1100 a third of the panel was 268px (review finding 7).
    tablet = _block(tail, "@media (max-width: 1219.98px)")
    assert "repeat(2, minmax(0, 1fr))" in _block(tablet, ".tk-drilldown .dd-grid {")
    assert "grid-column: auto" in _block(tablet, ".tk-drilldown .dd-grid > * {")
    assert "grid-column: 1 / -1" in _block(tablet, ".tk-drilldown .dd-grid > .pc {")
    # No news: technicals and valuation halve the second row. No chart: news takes a row.
    # Both only on the twelve-track grid (they would add tracks to the two-column one).
    wide = _block(tail, "@media (min-width: 1220px)")
    assert ("grid-column: span 6" in _block(
        wide, ".tk-drilldown .dd-grid:has(> .pc):not(:has(> .dd-news)) > .dd-col:nth-child(n + 3) {"))
    assert "grid-column: 1 / -1" in _block(wide, ".tk-drilldown .dd-grid:not(:has(> .pc)) > .dd-news {")
    # No chart and no levels: two columns are the whole first row and take half each (a
    # third each left 386px of the row empty at 1440px; the last outside review, finding 3).
    assert "grid-column: span 6" in _block(
        wide, ".tk-drilldown .dd-grid:not(:has(> .pc)):not(:has(> .dd-col:nth-child(3))) > .dd-col {")
    assert "span 6" not in _outside_media(tail[:tail.index("The levels ladder")])
    marker = _CSS.index("Phone reflow — one-screen ledgers (owner request")
    phone = _block(_CSS[marker:], "@media (max-width: 719px)")
    assert "grid-template-columns: 1fr" in _block(phone, ".tk-drilldown .dd-grid {")
    # The phone panel gives its side padding back to the text.
    assert ".tk-drilldown { padding: 12px 8px; }" in phone
    assert "padding-left: 10px" in _block(phone, ".tk-drilldown .dd-card {")
    # The rules for the old three-column block went with it.
    assert ".dd-cols" not in _CSS and ".dd-head" not in _outside_media(_CSS).replace("(.dd-head)", "")
