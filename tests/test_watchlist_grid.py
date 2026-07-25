"""The Watchlist grid builders (spec 2026-07-25 §4-§6, §10).

The filter chips double as the page's distribution readout, so they are built
from the data and never hardcoded: the design account's mockup shows a 3/6/6
spread that does not exist anywhere in the corpus.
"""
from components.watchlist.grid import (
    FILTER_ALL,
    FILTER_CHANGED,
    build_filter_options,
    build_grid_html,
    column_header_html,
    filter_items,
    footer_html,
    group_header_html,
    group_items,
    method_note_html,
)

ITEMS = [
    ("NVDA", {"signal": "WATCH", "1mo_pct": 4.0}),
    ("MSFT", {"signal": "HOLD", "1mo_pct": 2.0}),
    ("INTC", {"signal": "HOLD", "1mo_pct": 1.0}),
    ("MU", {"signal": "CAUTION", "1mo_pct": 9.0}),
]


# ── chips ──
def test_all_chip_counts_every_shown_name():
    keys, labels = build_filter_options(ITEMS, {"MU"})
    assert keys[0] == FILTER_ALL
    assert labels[FILTER_ALL] == "All · 4"


def test_changed_chip_carries_the_row_marker_glyph():
    _, labels = build_filter_options(ITEMS, {"MU", "INTC"})
    assert labels[FILTER_CHANGED] == "● Changed · 2"


def test_no_changed_chip_when_nothing_changed():
    # A dead "· 0" chip would be worse than no chip: the bar is a readout.
    keys, labels = build_filter_options(ITEMS, set())
    assert FILTER_CHANGED not in keys
    assert FILTER_CHANGED not in labels


def test_changed_tickers_outside_the_book_do_not_inflate_the_count():
    # A retired name whose signal moved is filtered out of `items` upstream; it
    # must not be counted by a chip that can never show it.
    _, labels = build_filter_options(ITEMS, {"MU", "RETIRED_THING"})
    assert labels[FILTER_CHANGED] == "● Changed · 1"


def test_only_signals_present_get_a_chip_in_rank_order():
    keys, _ = build_filter_options(ITEMS, {"MU"})
    assert keys == [FILTER_ALL, FILTER_CHANGED, "WATCH", "HOLD", "CAUTION"]
    assert "BUY" not in keys      # absent from the data → absent from the bar


def test_signal_chips_are_title_case_with_counts():
    _, labels = build_filter_options(ITEMS, set())
    assert labels["HOLD"] == "Hold · 2"


def test_every_key_has_a_label():
    keys, labels = build_filter_options(ITEMS, {"MU"})
    assert set(keys) == set(labels)


# ── filtering ──
def test_all_returns_every_item():
    assert filter_items(ITEMS, {"MU"}, FILTER_ALL) == ITEMS


def test_changed_returns_only_changed_rows():
    got = filter_items(ITEMS, {"MU", "INTC"}, FILTER_CHANGED)
    assert [tk for tk, _ in got] == ["INTC", "MU"]


def test_signal_filter_returns_only_that_group():
    got = filter_items(ITEMS, set(), "HOLD")
    assert [tk for tk, _ in got] == ["MSFT", "INTC"]


def test_unknown_or_none_selection_falls_back_to_all():
    # st.pills lets a user click the active chip off, returning None; an empty
    # book is never the right answer.
    assert filter_items(ITEMS, set(), None) == ITEMS


def test_a_signal_absent_from_todays_book_falls_back_to_all():
    # The selection survives in session state. A reader who filtered to BUY on a
    # day that had BUY names must not land on a blank page the next morning.
    assert filter_items(ITEMS, set(), "BUY") == ITEMS


# ── groups ──
def test_groups_come_out_in_signal_rank_order_preserving_row_order():
    groups = group_items(ITEMS)
    assert [sig for sig, _ in groups] == ["WATCH", "HOLD", "CAUTION"]
    assert [tk for tk, _ in groups[1][1]] == ["MSFT", "INTC"]


def test_group_header_carries_signal_colour_count_and_a_filling_rule():
    from lib.catalog import SIGNAL_COLORS
    html = group_header_html("CAUTION", 21)
    assert SIGNAL_COLORS["CAUTION"] in html    # the group IS a signal
    assert ">21<" in html
    assert "tk-group-rule" in html             # the labelled-divider hairline


# ── the blob ──
def test_grid_is_one_element_containing_header_groups_and_rows():
    html = build_grid_html(ITEMS, {"MU"}, {}, lambda tk, d, **kw: f"<row-{tk}>")
    assert html.startswith('<div class="tk-scroll"')
    assert html.rstrip().endswith("</div>")
    for tk in ("NVDA", "MSFT", "INTC", "MU"):
        assert f"<row-{tk}>" in html
    # Column header first, then the first group header, then its row.
    assert html.index("tk-head") < html.index("tk-group") < html.index("<row-NVDA>")


def test_grid_passes_the_changed_flag_and_earnings_through():
    seen = {}

    def _row(tk, d, signal_changed=False, earnings_hist=None):
        seen[tk] = (signal_changed, earnings_hist)
        return ""

    build_grid_html(ITEMS, {"MU"}, {"MU": [{"q": 1}]}, _row)
    assert seen["MU"] == (True, [{"q": 1}])
    assert seen["NVDA"] == (False, None)


def test_filtered_grid_emits_only_the_surviving_group_header():
    # Filtering is Python-side, not CSS-hidden, so a filtered view never leaves
    # an empty group header behind and every count is honest for that filter.
    shown = filter_items(ITEMS, set(), "HOLD")
    html = build_grid_html(shown, set(), {}, lambda tk, d, **kw: "")
    assert html.count('class="tk-group"') == 1
    assert "CAUTION" not in html
    assert ">2<" in html          # the HOLD group's own count


def test_empty_book_still_renders_a_column_header():
    html = build_grid_html([], set(), {}, lambda tk, d, **kw: "")
    assert "tk-head" in html
    assert "tk-group" not in html


def test_column_header_has_seven_cells_and_no_cluster_column():
    head = column_header_html()
    assert head.count("columnheader") == 7
    assert "Cluster" not in head          # demoted into the ticker cell
    assert "vs 50-day" in head


def test_signal_is_the_second_column():
    # The row's verdict: you should never read four numbers before learning
    # what the call is.
    head = column_header_html()
    assert head.index("Ticker") < head.index("Signal") < head.index("Last")


# ── copy ──
def test_method_note_bolds_exactly_the_three_inferable_encodings():
    note = method_note_html()
    assert note.count("<b>") == 3
    assert "±10%" in note
    assert "tight-stop" in note
    assert "70" in note and "30" in note


def test_footer_states_the_count_and_the_dot_legend():
    foot = footer_html(4, 32)
    assert "4 of 32" in foot
    assert "changed" in foot.lower()
