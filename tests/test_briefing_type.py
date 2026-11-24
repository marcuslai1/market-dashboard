"""The briefing card's text sizes, spacing and the colour of a price's move (owner 2026-11-24).

Owner: "its like a large dump of text ... looks very uniform"; "the colour tone makes it tough to
read. Maybe more spacing, or slightly larger font." An outside review of the published card named
tight spacing, long lines and small type, then one ink for every move. The rules are one block at
the end of assets/theme.css; the classes come from daily_briefing_v2._dir. A second outside review,
of the build, found the faults the later tests here pin.
"""
import re
from pathlib import Path

from components.briefing.daily_briefing import briefing_card_html
from components.briefing.daily_briefing_v2 import _PRICE_TILES, _dir, _signed
from tests.test_briefing_card import _v2, _with_tape

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "assets" / "theme.css").read_text(encoding="utf-8")
# The block, from the end of its own heading comment, with every later comment taken out.
BLOCK = re.sub(r"/\*.*?\*/", "", CSS.split("Briefing card: text sizes, spacing and the direction of a move", 1)[1]
               .split("*/", 1)[1], flags=re.S)
PHONE_OPEN = "@media (max-width: 719px) {"
PC, PHONE = BLOCK.split(PHONE_OPEN, 1)[0], BLOCK.split(PHONE_OPEN, 1)[1].split("\n}\n", 1)[0]
AFTER_PHONE = BLOCK.split(PHONE_OPEN, 1)[1].split("\n}\n", 1)[1]


def _rules(part: str) -> list:
    return [([s.strip() for s in " ".join(sels.split()).split(",")], body)
            for sels, body in re.findall(r"([^{}@]+)\{([^{}]*)\}", part)]


def _px(selector: str, part: str = PC, prop: str = "font-size"):
    """The size the LAST rule of ``part`` gives ``selector``, as the cascade would (rules of the
    block have the specificity of the ones they follow). None when the part does not set it."""
    found = None
    for names, body in _rules(part):
        m = re.search(rf"(?<![-\w]){prop}:\s*([\d.]+)px", body)
        if selector in names and m:
            found = float(m.group(1))
    return found


def _phone(selector: str) -> float:
    """What a phone gets: the phone rule's size, else the PC one."""
    v = _px(selector, PHONE)
    return v if v is not None else _px(selector)


def _tiles(tape: list) -> str:
    return briefing_card_html(_with_tape(tape), "2026-09-28").split('<div class="bf-tape">', 1)[1].split("</section>")[0]


def _row(name: str, chg, **over) -> dict:
    return {"name": name, "chg_pct": chg, "5d_pct": 1.0, "x_usual": 1.0, "level": None, "bp": None, **over}


# ── which figures take a direction ──────────────────────────────────────────

def test_dir_follows_the_sign_and_says_nothing_for_no_move():
    assert _dir(0.93) == " bf-up" and _dir(-10.55) == " bf-down"
    assert _dir(0) == "" and _dir(0.0) == "" and _dir(None) == "" and _dir("n/a") == "" and _dir(True) == ""


def test_a_move_that_prints_as_zero_or_is_not_a_number_takes_no_colour():
    # 0.004% printed "+0.00%" in green, and a NaN (which compares false both ways) came out red.
    assert _dir(0.004) == "" and _dir(-0.004) == "" and _dir(0.0049) == ""
    assert _dir(0.005) in ("", " bf-up") and _dir(0.006) == " bf-up" and _dir(-0.006) == " bf-down"
    assert _dir(float("nan")) == "" and _dir(float("inf")) == ""
    assert _signed(float("nan")) == "—"                                # and it prints as "no figure"
    assert '<span class="bf-v">+0.00%</span>' in _tiles([_row("SPY", 0.004)])


def test_only_the_price_rows_of_markets_are_coloured():
    assert {"SPY", "QQQ", "SOXX", "WTI", "Gold"} == _PRICE_TILES
    tiles = _tiles([_row("SOXX", -10.55), _row("WTI", 0.93), _row("Gold", -4.62), _row("SPY", 0)])
    assert '<span class="bf-v bf-down">−10.55%</span>' in tiles
    assert '<span class="bf-v bf-up">+0.93%</span>' in tiles
    assert '<span class="bf-v bf-down">−4.62%</span>' in tiles
    assert '<span class="bf-v">0.00%</span>' in tiles                  # no move, no colour


def test_the_dollar_index_and_a_row_nobody_listed_stay_ink():
    """Both dollar rows read alike (one coloured beside one white looked like a fault), and a
    rate or a gauge added to the row later is ink until someone lists it as a price."""
    tiles = _tiles([_row("DXY", -0.09), _row("US2Y", 1.4), _row("MOVE", 12.0)])
    assert '<span class="bf-v">−0.09%</span>' in tiles
    assert '<span class="bf-v">+1.40%</span>' in tiles and '<span class="bf-v">+12.00%</span>' in tiles
    assert "bf-up" not in tiles and "bf-down" not in tiles


def test_a_tile_that_leads_with_a_level_is_never_coloured():
    """A jump in the VIX must not be green, and a fall in a yield is not a loss."""
    tiles = _tiles([_row("VIX", 26.2, price=35.89), _row("USDSGD", -0.12, price=1.2902),
                    _row("US10Y", -2.77, level=4.91, bp=-14)])
    assert tiles.count('<span class="bf-v">') == 3
    assert "bf-up" not in tiles and "bf-down" not in tiles


def test_a_level_tile_with_no_level_on_file_shows_the_change_in_ink():
    # An older record has no `price`; a record can lack `level`. The tile falls back to the change,
    # and the change of a gauge or a rate still takes no colour.
    tiles = _tiles([_row("VIX", 26.2), _row("USDSGD", -0.12), _row("US10Y", -2.77)])
    assert '<span class="bf-v">+26.20%</span>' in tiles and '<span class="bf-v">−2.77%</span>' in tiles
    assert "bf-up" not in tiles and "bf-down" not in tiles


def test_names_that_moved_and_also_moved_are_coloured_by_direction():
    html = briefing_card_html(_v2(), "2026-09-28")
    assert '<td class="bf-mv bf-up">+3.66%<small>' in html            # Microsoft
    assert '<td class="bf-mv bf-down">−4.10%<small>' in html          # SK Hynix
    assert '<span class="bf-also-m bf-down">−4.49%</span>' in html    # WeRide, not looked up
    # the small line under a move (size, volume) is its own element and keeps its grey
    assert re.search(r"\.bf-mv small \{[^}]*color: var\(--ink-3\)", CSS)


def test_nothing_else_on_the_card_takes_a_direction_class():
    """The 5-day and 1-month figures, the chart facts and the sentences stay as they were, on a
    card that also holds the level tiles; and the site-wide `.up` / `.down` classes are not a way
    round the two rules."""
    tape = [_row("SPY", -3.64, mo_pct=-9.7), _row("VIX", 26.2, price=35.89, mo_pct=88.6),
            _row("USDSGD", -0.12, price=1.2902), _row("US10Y", -2.77, level=4.91, bp=-14), _row("DXY", -0.09)]
    html = briefing_card_html(_with_tape(tape), "2026-09-28")
    carriers = re.findall(r'class="([^"]*\bbf-(?:up|down)\b[^"]*)"', html)
    assert carriers and all(c.split()[0] in ("bf-v", "bf-mv", "bf-also-m") for c in carriers)
    assert not re.search(r'class="(?:[^"]* )?(?:up|down)(?: [^"]*)?"', html)


def test_the_direction_rules_name_the_three_elements_and_no_other():
    assert ".bf .bf-v.bf-up, .bf .bf-mv.bf-up, .bf .bf-also-m.bf-up { color: var(--up); }" in BLOCK
    assert ".bf .bf-v.bf-down, .bf .bf-mv.bf-down, .bf .bf-also-m.bf-down { color: var(--down); }" in BLOCK
    assert not re.search(r"\.bf \.bf-(?:up|down)\s*\{", CSS)            # no rule for the bare class
    # `bf-dn` is the data-notes row, an older class: the fall class must not reuse the name
    code = (ROOT / "components" / "briefing" / "daily_briefing_v2.py").read_text(encoding="utf-8")
    assert ".bf-dn { display: flex;" in CSS and '" bf-dn"' not in code


def test_the_tile_names_step_back_to_the_caption_grey():
    assert ".bf .bf-n, .bf .bf-vix b { color: var(--ink-3); }" in BLOCK


def test_each_figure_in_a_tiles_small_line_stays_with_its_label():
    # On a phone five of nine tiles broke "1mo" from its figure.
    html = briefing_card_html(_with_tape([_row("SPY", -3.64, x_usual=3.7, mo_pct=-9.71, price=689.81,
                                               **{"5d_pct": -8.56})]), "2026-09-28")
    assert ('<span class="bf-s"><span class="bf-nw">3.7× usual</span> · <span class="bf-nw">5d −8.6%</span> · '
            '<span class="bf-nw">1mo −9.7%</span></span>') in html
    assert ".bf-nw { white-space: nowrap; }" in BLOCK


# ── the order of sizes ──────────────────────────────────────────────────────

def test_sizes_step_down_in_one_order_on_a_pc():
    """Two trials and the first build each left a text larger than the thing above it."""
    section, head = _px(".bf .bf-sh h3"), _px(".bf .bf-head")
    lead, name, inner = _px(".bf .bf-box li b"), _px(".bf .bf-nm b"), _px(".bf .bf-also > b")
    sentence, row, note = _px(".bf .bf-det"), _px(".bf .bf-ev span"), _px(".bf .bf-dntext")
    assert section > head > lead >= name > inner >= sentence > row >= note > 12.5
    assert _px(".bf .bf-movers .bf-why") == sentence < name            # a reason is a sentence, under its name
    assert _px(".bf .bf-also li") == row < _px(".bf .bf-also > b")     # "Also moved" over its rows
    assert _px(".bf .bf-far li") == row < _px(".bf .bf-later-h b")     # "Later" over its rows
    assert _px(".bf .bf-cf + .bf-cap") == note                         # the note under the chart


def test_sizes_step_down_in_one_order_on_a_phone():
    section, head = _phone(".bf .bf-sh h3"), _phone(".bf .bf-head")
    lead, name, inner = _phone(".bf .bf-box li b"), _phone(".bf .bf-nm b"), _phone(".bf .bf-also > b")
    sentence, row, note = _phone(".bf .bf-det"), _phone(".bf .bf-ev span"), _phone(".bf .bf-dntext")
    assert section > head > lead >= name > inner >= sentence > row >= note > 13
    assert _phone(".bf .bf-also li") == row < _phone(".bf .bf-also > b")
    assert _phone(".bf .bf-far li") == row < _phone(".bf .bf-later-h b")
    assert _phone(".bf .bf-movers .bf-why") == sentence < name         # a phone-only rule must not lift a reason over its name
    assert _phone(".bf .bf-rchk li") == row <= _phone(".bf .bf-rchk summary")   # the drawer's line over its rows
    # the phone rules make no heading inside a block smaller (the first build shrank "Later" to 13px)
    assert "bf-later-h" not in PHONE and "bf-also > b" not in PHONE
    assert _phone(".bf .bf-key") == _phone(".bf .bf-prov") == 13       # the legend and the source note beside it


def test_sentences_are_fifteen_pixels_on_a_line_that_binds():
    names, body = next((n, b) for n, b in _rules(PC) if ".bf .bf-det" in n)
    assert "font-size: 15px" in body and "line-height: 1.62" in body and "max-width: 60ch" in body
    assert {".bf .bf-det", ".bf .bf-box li", ".bf .bf-cap", ".bf .bf-vix p", ".bf .bf-movers .bf-why",
            ".bf .bf-facts", ".bf .bf-out"} == set(names)
    # A list's items take the cap from their list; a rule for the items named a class that no list
    # has (`bf-facts` is a paragraph) and stayed capped where the list was not.
    assert "bf-pts > li { max-width" not in BLOCK and "bf-facts.bf-pts" not in BLOCK


def test_a_movers_reason_is_capped_on_the_block_inside_its_cell():
    """`max-width` does not bind on a table cell: at 768 to 1024px a reason ran 86 characters."""
    html = briefing_card_html(_v2(), "2026-09-28")
    assert '<td class="bf-why"><div class="bf-why-in">Copilot overhaul. ' in html
    assert '<td class="bf-why bf-none"><div class="bf-why-in">No reported cause found. ' in html
    assert html.count('<div class="bf-why-in">') == 3 and "</div></td>" in html
    assert ".bf .bf-why-in { max-width: 60ch; }" in PC and ".bf .bf-movers .bf-why { max-width: none; }" in PC
    assert ".bf .bf-why-in { max-width: none; }" in PHONE
    # The inner block takes its size from the cell. The order tests read the size on the cell's own
    # selector, so a size set on the inner block would pass them (an independent check, 2026-11-24).
    for names, body in _rules(re.sub(r"/\*.*?\*/", "", CSS, flags=re.S).replace("@", "\n@")):
        if any("bf-why-in" in n for n in names):
            assert "font-size" not in body and "line-height" not in body, names


def test_the_vix_box_runs_the_width_of_the_tiles():
    assert ".bf .bf-vix { max-width: none; }" in PC                    # its paragraph keeps the 60ch cap


# ── which widths get which rules ────────────────────────────────────────────

def test_phone_sizes_need_a_phone_window_and_a_narrow_card():
    """The window alone gave phone sizes to a 615-719px window whose card is in its wide layout;
    the card alone would give them to the right-hand column on a PC."""
    assert re.match(r"\s*@container \(max-width: 560px\) \{", PHONE)
    assert PHONE.rstrip().endswith("}") and PHONE.count("@container") == 1
    inner = PHONE.split("{", 1)[1]
    assert ".bf .bf-v { font-size: 22px; }" in inner and ".bf .bf-sec { padding: 24px 0; }" in inner
    assert "@media" not in PC and "@media" not in AFTER_PHONE          # one phone block, nothing loose after it


def test_the_wide_card_rules_apply_only_to_a_wide_card():
    """On a narrow card a movers row is a grid and its cells take no padding (an unscoped rule added
    352px to the phone's Names that moved in a trial); Week ahead sets a day at 200px or more (at
    112px a 1024px window drew seven columns two or three words wide)."""
    wide = re.search(r"@container \(min-width: 560\.01px\) \{([^@]*?)\n\}", PC).group(1)
    assert ".bf .bf-movers td { padding: 16px 14px 16px 0; }" in wide
    assert ".bf .bf-wk { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }" in wide
    outside = re.sub(r"@container[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", PC)
    assert ".bf .bf-movers td" not in outside and ".bf .bf-wk" not in outside


def test_the_cards_text_greys_are_the_warmer_ramp_on_the_card_only():
    # Owner 2026-11-24, shown the two side by side: "warmer whites are nice. Go with that."
    assert ".bf { --ink: #f5f4ee; --ink-2: #d8d7d0; --ink-3: #a6a59e; }" in AFTER_PHONE
    # the site's own three values are as they were, so the other pages do not change
    assert "--text-dark:#e9e8e2;" in CSS and "--text-2-dark:#d7d8db;" in CSS and "--text-3-dark:#a0a2a7;" in CSS
    assert CSS.count("#f5f4ee") == 2 and CSS.count("#d8d7d0") == 2 and CSS.count("#a6a59e") == 2   # the rule and its comment
