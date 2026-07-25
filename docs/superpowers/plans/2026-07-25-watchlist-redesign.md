# Watchlist Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Watchlist page as a triageable dense grid — explicit signal groups, a persistent "changed today" filter, and a centred extension gauge — and restructure its 15-block drill-down into a verdict-first card with three drawers.

**Architecture:** The page stays one `st.markdown` blob for the whole grid (a `<div>` opened in one markdown does not wrap sibling Streamlit blocks). Pure HTML builders move into two new modules (`grid.py`, `gauge.py`) so every geometry and copy decision is unit-testable without a Streamlit run; `watchlist.py` keeps the only Streamlit calls (the `st.pills` filter + the one markdown emit). The drill-down splits into an orchestrator (`drilldown.py`) and the drawer bodies (`drilldown_drawers.py`).

**Tech Stack:** Python 3.10 / Streamlit 1.58 (floors at 1.42) / pandas / plain CSS in `assets/theme.css` / pytest + `streamlit.testing.v1.AppTest` / Playwright visual baselines via the Docker harness.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-25-watchlist-redesign-design.md`. Where this plan and the spec disagree, the spec wins.
- **Worktree:** all work in `.claude/worktrees/watchlist-redesign` on branch `watchlist-redesign`. Never `git checkout` in the main tree — two other terminals hold it.
- **`EXT_MAX = 20.0`**, `EXT_THRESHOLD = 10.0` — the gauge's fixed clamp and its brass/terracotta switch. Shared across every row, never per-row.
- **Grid columns, exactly:** `132px 108px 112px 74px 168px 52px 96px`, `gap: 12px`.
- **Colour roles are one-to-one** (spec §2): signal palette = rating only; `--up`/`--down` = price movement only; `--brass` = measurement; `--stress` = threshold crossed / gate / falsifier; `--accent`/`--eyebrow` = structure and navigation. A violation is a bug even if it looks fine.
- **No new upstream fields and no new arithmetic.** Presentation layer only.
- **Absence tiers hold.** The corpus is 102 reports back to 2026-03-12; no block may start hard-failing on an old report. A missing value renders a bare `—`, never `—%`.
- **`drilldown.py` and `drilldown_drawers.py` stay Streamlit-free** — pure HTML strings. `earnings_history.csv` is threaded in by the caller.
- **Escaping stays at its current boundary:** report-authored text goes through `_escape_dollars`, attribute values through `_escape_attr`, URLs through `_safe_href`. `tests/test_rendering_security.py` must pass unchanged.
- **Commit style:** `git commit -F <file>` with a heredoc, never `-m "…"` — PowerShell 5.1 word-splits embedded quotes in args to native exes. Every commit message ends with the two trailer lines used by the repo.
- **Do not touch** `data/changelog.json` until Task 10, and put it in its own commit.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `components/watchlist/gauge.py` | **new.** The extension gauge: `EXT_MAX`, `EXT_THRESHOLD`, `extension_gauge_html`. The page's one visual, with real geometry worth testing in isolation. |
| `components/watchlist/grid.py` | **new.** Pure grid builders: filter-chip options, filter application, column header, group headers, the full `.tk-scroll` blob, the method note, the footer. |
| `components/watchlist/watchlist.py` | The only Streamlit-touching watchlist module: the `st.pills` chip row and the single `st.markdown` emit. |
| `components/watchlist/row.py` | One row's `<summary>` (seven cells) + the `<details>` wrapper. No longer builds the writeup — that moves into the drill-down card. |
| `components/watchlist/drilldown.py` | The drill-down card: header, status chips, entry-block box, verdict, what-changed, what-to-do, levels plate, two columns. Delegates drawers. |
| `components/watchlist/drilldown_drawers.py` | **new.** The three drawer bodies: Earnings, Risk & reward detail, Pipeline detail. |
| `lib/cards.py` | `render_section_head` gains `masthead: bool = False` (verbatim replica of the Tracker branch's shape). |
| `dashboard.py` | `_page_watchlist`: masthead head + new descriptor copy. |
| `assets/theme.css` | New/edited blocks: `.section-head.masthead`, the seven-column grid, `.tk-group*`, row cells, `.tk-ext*`, `.st-key-wl_filter` chips, `.dd-*` card, drawers, the seven-cell phone reflow. |
| `tests/test_watchlist_grid.py` | **new.** Chip options, filtering, group headers, blob structure, footer, method note. |
| `tests/test_watchlist_row.py` | Extended: two-line cells, steel dot, RSI zones, gauge presence. |
| `tests/test_watchlist_gauge.py` | **new.** Gauge geometry, clamping, tone switch, absence. |
| `tests/test_drilldown.py` | Extended: card order, levels plate, drawers, relocated blocks. |

---

## Task 1: Masthead page head

**Files:**
- Modify: `lib/cards.py:12-18`
- Modify: `assets/theme.css` (append a rule pair near `.section-head`)
- Modify: `dashboard.py:374-377`
- Test: `tests/test_cards.py` (create if absent)

**Interfaces:**
- Produces: `lib.cards._section_head_html(title: str, sub: str = "", masthead: bool = False) -> str` and `render_section_head(title, sub="", masthead=False) -> None`.

This is a **verbatim replica** of what the `signal-tracker-redesign` branch already wrote, so the eventual merge sees identical hunks and auto-resolves. Do not improve on it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cards.py
from lib.cards import _section_head_html


def test_section_head_default_has_no_masthead_class():
    assert _section_head_html("The Watchlist", "sub") == (
        '<div class="section-head"><h2>The Watchlist</h2>'
        '<span class="sub">sub</span></div>'
    )


def test_masthead_flag_adds_the_class():
    html = _section_head_html("The Watchlist", "sub", masthead=True)
    assert 'class="section-head masthead"' in html
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `python -m pytest tests/test_cards.py -v`
Expected: FAIL — `ImportError: cannot import name '_section_head_html'`.

- [ ] **Step 3: Implement**

```python
# lib/cards.py — replace the current render_section_head
def _section_head_html(title: str, sub: str = "", masthead: bool = False) -> str:
    """Editorial section header markup: serif <h2> left, mono sub right.

    ``masthead=True`` gives the four top-level document pages the heavier 2px
    full-strength rule (spec 2026-07-25 §3) without moving every other section
    head on the site. Pure so it can be tested without a Streamlit run.
    """
    cls = "section-head masthead" if masthead else "section-head"
    return (f'<div class="{cls}"><h2>{title}</h2>'
            f'<span class="sub">{sub}</span></div>')


def render_section_head(title: str, sub: str = "", masthead: bool = False) -> None:
    """Editorial section header: serif <h2> on the left, mono sub on the right."""
    st.markdown(_section_head_html(title, sub, masthead), unsafe_allow_html=True)
```

- [ ] **Step 4: Run the test — expect PASS**

- [ ] **Step 5: Add the CSS**

Immediately after the `.section-head .sub { … }` block in `assets/theme.css`:

```css
/* Masthead-weight section head — the site's marker for "top-level document
   surface". Four pages use it (Watchlist, Tracker, Review, Briefing head);
   .section-head stays 1px everywhere else, so this must not change globally. */
.section-head.masthead { border-bottom: 2px solid var(--color-text); padding-bottom: 10px; }
.section-head.masthead h2 { font-size: 1.875rem !important; font-weight: 600; }
```

- [ ] **Step 6: Swap the page head copy**

In `dashboard.py::_page_watchlist._render_watchlist_body`, replace the `sub_label` block:

```python
        sub_label = "The whole book · click any row for the full read"
        if not _is_latest:
            sub_label += f" · viewing {selected_date}"
        render_section_head("The Watchlist", sub_label, masthead=True)
```

The name count moves out of the descriptor — the filter chips carry it now (spec §4.1), and the footer restates it.

- [ ] **Step 7: Run the full suite, then commit**

Run: `python -m pytest tests/ -q -x --ignore=tests/visual`

```bash
git add lib/cards.py assets/theme.css dashboard.py tests/test_cards.py
git commit -F .git/COMMIT_BODY   # see Global Constraints for the heredoc form
```

Message: `feat(watchlist): masthead-weight page head; render_section_head(masthead=)`

---

## Task 2: The extension gauge

**Files:**
- Create: `components/watchlist/gauge.py`
- Test: `tests/test_watchlist_gauge.py`

**Interfaces:**
- Produces: `EXT_MAX: float = 20.0`, `EXT_THRESHOLD: float = 10.0`, `extension_gauge_html(vs50: float | None) -> str`.
- Consumed by: Task 4 (`row.py`).

The gauge is the only column that encodes a **rule** rather than an input to judgment, which is why it gets a visual at all. Fixed scale, clamped, centred on zero.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_watchlist_gauge.py
"""The extension gauge — the Watchlist's one visual (spec 2026-07-25 §8).

The scale is FIXED at ±EXT_MAX for every row: a shared scale is what makes the
bars comparable down the page. Clamping past the threshold is deliberate —
past the block, how far past stops changing the decision.
"""
from components.watchlist.gauge import (
    EXT_MAX,
    EXT_THRESHOLD,
    extension_gauge_html,
)


def test_missing_value_renders_bare_dash_and_no_track():
    html = extension_gauge_html(None)
    assert "—" in html
    assert "—%" not in html
    assert "tk-ext-track" not in html


def test_positive_grows_right_from_centre():
    html = extension_gauge_html(10.0)
    assert "left:50%" in html
    assert "right:50%" not in html


def test_negative_grows_left_from_centre():
    html = extension_gauge_html(-10.0)
    assert "right:50%" in html
    assert "left:50%" not in html


def test_full_scale_fills_exactly_half_the_track():
    # ±EXT_MAX is the widest a bar may be: half the track, from the centre out.
    assert "width:50.00%" in extension_gauge_html(EXT_MAX)


def test_half_scale_fills_a_quarter():
    assert "width:25.00%" in extension_gauge_html(EXT_MAX / 2)


def test_value_past_the_scale_is_clamped_not_overflowed():
    clamped = extension_gauge_html(-40.0)
    assert "width:50.00%" in clamped
    # …and still prints its true value, so clamping never hides the number.
    assert "-40.0%" in clamped


def test_under_threshold_is_brass():
    assert 'data-tone="under"' in extension_gauge_html(EXT_THRESHOLD - 0.1)


def test_at_threshold_is_terracotta():
    # "at or past" — the block fires at the threshold, so the colour must too.
    assert 'data-tone="over"' in extension_gauge_html(EXT_THRESHOLD)
    assert 'data-tone="over"' in extension_gauge_html(-EXT_THRESHOLD)


def test_zero_renders_a_track_with_no_fill_width():
    html = extension_gauge_html(0.0)
    assert "tk-ext-track" in html
    assert "width:0.00%" in html


def test_number_carries_the_price_delta_class():
    # The bar reads the threshold; the number reads the direction. Redundant
    # encoding, same principle as the Tracker's tiles.
    assert "delta-up" in extension_gauge_html(4.0)
    assert "delta-down" in extension_gauge_html(-4.0)
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_watchlist_gauge.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Check the delta-class names before implementing**

Run: `python -c "from lib.formatters import _delta_class; print(_delta_class(1), _delta_class(-1), _delta_class(0), _delta_class(None))"`

If the up/down class names are not `delta-up` / `delta-down`, fix the two assertions in `test_number_carries_the_price_delta_class` to the real names — the point of the test is that the number uses the **price-delta** system, not which string encodes it.

- [ ] **Step 4: Implement**

```python
# components/watchlist/gauge.py
"""The Watchlist extension gauge — the page's one visual.

``vs 50-day`` is the mechanical block criterion: the pipeline refuses entries on
names too far extended above the average. Every other column on the grid is an
input to judgment; this one is a rule. A signed number makes the reader compare
+14.3% against a threshold they have to remember; a centred bar makes "too far
right" a shape.

Design decisions worth not re-litigating (spec 2026-07-25 §8):

* **Centred, not left-anchored.** The quantity is signed and zero is meaningful
  — the 50-day *is* the reference. A left-anchored bar would imply a magnitude
  scale where "small" is the left end, which is wrong: below the average is the
  interesting other direction.
* **One fixed scale for every row.** A per-row scale would make the bars
  incomparable, which is the only reason to draw them.
* **Clamping is accepted.** −17.5% and a hypothetical −40% look identical. Past
  the threshold, how far past stops changing the decision — and the exact value
  is printed beneath regardless.
* **Brass then terracotta, never green/red.** A green/red gauge would read as
  "good/bad", wrong in both directions: −17.5% is not "bad", it is "not
  extended, but broken". Brass is the data axis; terracotta marks the crossing.
"""
from __future__ import annotations

from lib.formatters import _delta_class, _fmt_num, _sign

#: Full-scale extension, in percent. Bars clamp here.
EXT_MAX = 20.0
#: Where the pipeline's entry block bites — the brass → terracotta switch.
EXT_THRESHOLD = 10.0


def extension_gauge_html(vs50: float | None) -> str:
    """One row's extension gauge: track, zero line, fill, signed number.

    ``None`` renders a bare em-dash with no track — never "—%" (the absent-value
    bug guarded by tests/test_watchlist_row.py).
    """
    if vs50 is None:
        return '<div class="tk-ext tk-ext-empty">—</div>'
    frac = min(abs(vs50), EXT_MAX) / EXT_MAX
    # Half the track is one side of zero, so full scale is a 50% fill.
    width = frac * 50.0
    side = "left" if vs50 > 0 else "right"
    tone = "over" if abs(vs50) >= EXT_THRESHOLD else "under"
    return (
        '<div class="tk-ext">'
        '<div class="tk-ext-track">'
        '<div class="tk-ext-zero"></div>'
        f'<div class="tk-ext-fill" data-tone="{tone}" '
        f'style="{side}:50%;width:{width:.2f}%;"></div>'
        '</div>'
        f'<div class="tk-ext-num {_delta_class(vs50)}">'
        f'{_sign(vs50)}{_fmt_num(vs50, 1)}%</div>'
        '</div>'
    )
```

- [ ] **Step 5: Run the tests — expect PASS**

- [ ] **Step 6: Commit**

Message: `feat(watchlist): extension gauge — fixed ±20% scale, centred on the 50-day`

---

## Task 3: The grid builders

**Files:**
- Create: `components/watchlist/grid.py`
- Test: `tests/test_watchlist_grid.py`

**Interfaces:**
- Produces:
  - `FILTER_ALL = "all"`, `FILTER_CHANGED = "changed"`
  - `build_filter_options(items, changed_tickers) -> tuple[list[str], dict[str, str]]` — `(keys, labels)`
  - `filter_items(items, changed_tickers, selected) -> list[tuple[str, dict]]`
  - `group_items(items) -> list[tuple[str, list[tuple[str, dict]]]]`
  - `column_header_html() -> str`
  - `group_header_html(signal: str, count: int) -> str`
  - `build_grid_html(items, changed_tickers, earnings_map, row_builder) -> str`
  - `method_note_html() -> str`, `footer_html(n_shown: int, n_total: int) -> str`
- `items` is always the already-sorted `list[tuple[str, dict]]` the page builds.
- Consumed by: Task 5 (`watchlist.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_watchlist_grid.py
"""The Watchlist grid builders (spec 2026-07-25 §4-§6, §10).

The filter chips double as the page's distribution readout, so they are built
from the data and never hardcoded: the account's mockup shows a 3/6/6 spread
that does not exist in the corpus.
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
    keys, labels = build_filter_options(ITEMS, set())
    assert FILTER_CHANGED not in keys
    assert FILTER_CHANGED not in labels


def test_only_signals_present_get_a_chip_in_rank_order():
    keys, _ = build_filter_options(ITEMS, {"MU"})
    assert keys == [FILTER_ALL, FILTER_CHANGED, "WATCH", "HOLD", "CAUTION"]
    assert "BUY" not in keys      # absent from the data → absent from the bar


def test_signal_chips_are_title_case_with_counts():
    _, labels = build_filter_options(ITEMS, set())
    assert labels["HOLD"] == "Hold · 2"


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


def test_column_header_has_seven_cells_and_no_cluster_column():
    head = column_header_html()
    assert head.count("columnheader") == 7
    assert "Cluster" not in head          # demoted into the ticker cell
    assert "vs 50-day" in head


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
```

- [ ] **Step 2: Run and confirm failure** (`ImportError`).

- [ ] **Step 3: Implement**

```python
# components/watchlist/grid.py
"""Watchlist grid builders — pure HTML, no Streamlit.

Everything the dense grid needs except the row itself: the filter chips' option
set, the filter and grouping logic, the column header, the group headers, the
single wrapper blob, and the two pieces of footnote copy.

Two constructions here are load-bearing and easy to break:

1. **One blob.** The column header, every group header and every row are emitted
   in ONE string, because a ``<div>`` opened in one ``st.markdown`` and closed in
   another does not wrap sibling Streamlit blocks — the browser auto-closes it,
   and ``.tk-scroll`` stops containing the rows.
2. **Python-side filtering.** Rows are filtered before rendering rather than
   hidden with CSS, so a filtered view never leaves an empty group header behind
   and every header's count is the honest count *within that filter*.
"""
from __future__ import annotations

from typing import Callable

from lib.catalog import SIGNAL_COLORS, SIGNAL_SORT_RANK

FILTER_ALL = "all"
FILTER_CHANGED = "changed"

#: label, and whether the cell's content is right-aligned. Order is the grid's.
#: Signal sits second because it is the row's verdict — you should never read
#: four numbers before learning what the call is. The gauge column centres,
#: because its bar is centred on zero.
_COLUMNS: list[tuple[str, str]] = [
    ("Ticker", "left"),
    ("Signal", "left"),
    ("Last · Δ", "right"),
    ("1 mo", "right"),
    ("vs 50-day", "center"),
    ("RSI", "right"),
    ("R:R", "right"),
]

_RANK_LAST = len(SIGNAL_SORT_RANK)


def _signals_present(items) -> list[str]:
    """Signals actually in this book, in rank order."""
    seen = {d.get("signal", "HOLD") for _, d in items}
    return sorted(seen, key=lambda s: SIGNAL_SORT_RANK.get(s, _RANK_LAST))


def build_filter_options(items, changed_tickers) -> tuple[list[str], dict[str, str]]:
    """``(keys, labels)`` for the Show chips.

    The counts are themselves information — the bar doubles as the "shape of the
    book" readout — so they are derived from the data every run. A day with only
    CAUTION names shows two chips; a day with nothing changed shows no Changed
    chip at all rather than a dead ``· 0``.
    """
    changed = {tk for tk, _ in items if tk in (changed_tickers or set())}
    keys: list[str] = [FILTER_ALL]
    labels: dict[str, str] = {FILTER_ALL: f"All · {len(items)}"}
    if changed:
        keys.append(FILTER_CHANGED)
        # The leading ● mirrors the row marker, so the connection needs no legend.
        labels[FILTER_CHANGED] = f"● Changed · {len(changed)}"
    for sig in _signals_present(items):
        n = sum(1 for _, d in items if d.get("signal", "HOLD") == sig)
        keys.append(sig)
        labels[sig] = f"{sig.title()} · {n}"
    return keys, labels


def filter_items(items, changed_tickers, selected):
    """Apply one chip. Anything unrecognised — including ``None`` from a chip
    clicked off — falls back to the whole book."""
    if selected == FILTER_CHANGED:
        changed = changed_tickers or set()
        return [(tk, d) for tk, d in items if tk in changed]
    if selected in SIGNAL_SORT_RANK:
        return [(tk, d) for tk, d in items if d.get("signal", "HOLD") == selected]
    return list(items)


def group_items(items):
    """``[(signal, rows), …]`` in rank order, preserving each group's row order.

    A sort is only legible if you already know the rank order. Explicit groups
    with counts make the ordering self-documenting, let a reader skip 21 CAUTION
    names outright, and give the eye rest points in a long scroll.
    """
    out: list[tuple[str, list]] = []
    for sig in _signals_present(items):
        rows = [(tk, d) for tk, d in items if d.get("signal", "HOLD") == sig]
        if rows:
            out.append((sig, rows))
    return out


def column_header_html() -> str:
    cells = "".join(
        f'<div role="columnheader" class="tk-h-{align}">{label}</div>'
        for label, align in _COLUMNS
    )
    return f'<div class="tk-row tk-head" role="row">{cells}</div>'


def group_header_html(signal: str, count: int) -> str:
    """Dot + name + count + a hairline that fills the rest of the width.

    11px uppercase, not a real heading size: these are dividers inside ONE table,
    not sections of a document — sizing them up would fragment the page into
    three tables. The dot and name take the signal palette because the group *is*
    a signal; this is the only coloured text at heading scale on the page.
    """
    color = SIGNAL_COLORS.get(signal, "#9F988B")
    return (
        f'<div class="tk-group" style="--sig:{color};" role="row">'
        f'<span class="tk-group-dot"></span>'
        f'<span class="tk-group-name">{signal}</span>'
        f'<span class="tk-group-count">{count}</span>'
        f'<span class="tk-group-rule"></span>'
        f'</div>'
    )


def build_grid_html(
    items,
    changed_tickers,
    earnings_map: dict,
    row_builder: Callable[..., str],
) -> str:
    """The whole table as one string: wrapper, column header, groups, rows."""
    changed = changed_tickers or set()
    parts = [column_header_html()]
    for sig, rows in group_items(items):
        parts.append(group_header_html(sig, len(rows)))
        parts.extend(
            row_builder(
                tk,
                d,
                signal_changed=(tk in changed),
                earnings_hist=earnings_map.get(tk),
            )
            for tk, d in rows
        )
    return (
        '<div class="tk-scroll" role="table" '
        'aria-label="Watchlist — click a row to expand">'
        f'{"".join(parts)}</div>'
    )


def method_note_html() -> str:
    """The three pieces of encoding a reader cannot infer from looking.

    Bolding is by what breaks comprehension if missed, never by keyword
    importance — which is why the bold count is exactly three.
    """
    return (
        '<div class="tk-method">'
        'Extension is measured against the 50-day average, and the pipeline '
        'blocks entries past <b>±10%</b> — the point where the gauge turns '
        'terracotta. <b>R:R is the tight-stop-corrected ratio</b>, the same '
        'figure the writeup cites, not the raw headline. RSI turns terracotta '
        'past <b>70 and 30</b>, the overbought and oversold thresholds.'
        '</div>'
    )


def footer_html(n_shown: int, n_total: int) -> str:
    return (
        '<div class="tk-foot">'
        f'Showing {n_shown} of {n_total} names · '
        '<span class="tk-changed tk-changed-legend"></span> '
        'a steel dot marks a signal that changed since the prior report.'
        '</div>'
    )
```

- [ ] **Step 4: Run the tests — expect PASS**

- [ ] **Step 5: Commit**

Message: `feat(watchlist): grid builders — data-driven chips, signal groups, one blob`

---

## Task 4: Rebuild the row

**Files:**
- Modify: `components/watchlist/row.py` (whole `render_ticker_details_html` summary; the writeup block moves out in Task 6)
- Modify: `tests/test_watchlist_row.py` (extend; all 7 existing tests must still pass)

**Interfaces:**
- Consumes: `components.watchlist.gauge.extension_gauge_html`.
- Produces: `render_ticker_details_html(tk, d, signal_changed=False, earnings_hist=None) -> str` — signature unchanged.

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_watchlist_row.py`:

```python
# ── redesign 2026-07-25: seven cells, two-line ticker, visible R:R qualifier ──
def test_ticker_cell_carries_the_cluster_as_a_sub_line():
    # Cluster stopped being a column: it is context you want while looking at a
    # name, not an axis you scan, and it was eating 100px of a fixed grid.
    html = render_ticker_details_html("NVDA", {"signal": "WATCH", "price": 210.0})
    assert "tk-tick-cluster" in html


def test_changed_row_gets_the_steel_dot():
    html = render_ticker_details_html(
        "MU", {"signal": "CAUTION", "price": 990.0}, signal_changed=True
    )
    assert "tk-changed" in html
    assert 'data-signal-changed="true"' in html   # the first-mount flash survives


def test_unchanged_row_has_no_dot():
    html = render_ticker_details_html("MU", {"signal": "CAUTION", "price": 990.0})
    assert "tk-changed" not in html


def test_row_carries_the_extension_gauge():
    html = render_ticker_details_html(
        "MU", {"signal": "CAUTION", "price": 990.0, "vs_sma50_pct": 11.0}
    )
    assert "tk-ext-track" in html
    assert 'data-tone="over"' in html


def test_rsi_is_flagged_hot_at_seventy_and_cold_at_thirty():
    hot = render_ticker_details_html("D05.SI", {"signal": "CAUTION", "rsi_14": 77})
    cold = render_ticker_details_html("CRWV", {"signal": "CAUTION", "rsi_14": 28})
    mid = render_ticker_details_html("NVDA", {"signal": "WATCH", "rsi_14": 55})
    assert 'data-zone="hot"' in hot
    assert 'data-zone="cold"' in cold
    assert 'data-zone=""' in mid


def test_adjusted_rr_qualifier_is_visible_text_not_only_a_title():
    # Shipped code hid this in a title attribute — invisible on touch, and it is
    # the difference between a 1.5:1 that clears the gate and one that doesn't.
    d = {
        "signal": "CAUTION",
        "risk_reward": {
            "ratio": 22.5, "ratio_label": "22.5:1", "rr_distorted": True,
            "sizing_rr": {"ratio": 1.49, "ratio_label": "1.49:1"},
        },
    }
    html = render_ticker_details_html("MU", d)
    assert "tight-stop adj." in html
    assert "1.49:1" in html
    assert "22.5:1" in html      # raw headline survives on the title


def test_unadjusted_rr_has_no_qualifier_line():
    d = {"signal": "WATCH", "risk_reward": {"ratio": 2.6, "ratio_label": "2.6:1"}}
    assert "tight-stop adj." not in render_ticker_details_html("NVDA", d)
```

- [ ] **Step 2: Run and confirm the seven new tests fail, the seven old ones pass**

Run: `python -m pytest tests/test_watchlist_row.py -v`

- [ ] **Step 3: Rewrite the summary**

Replace the `summary = (…)` expression in `components/watchlist/row.py`:

```python
    cluster = CLUSTER_MAP.get(tk, "")
    changed_dot = (
        '<span class="tk-changed" '
        'title="Signal changed since the prior report"></span>'
        if signal_changed else ""
    )
    # The threshold is what matters, not the value, so the colour interprets for
    # the reader. Terracotta, not red: an overbought reading is a data
    # condition, not a CAUTION rating.
    rsi_zone = "hot" if (rsi or 0) >= 70 else "cold" if rsi is not None and rsi <= 30 else ""
    rr_sub = (
        '<div class="tk-rr-sub">tight-stop adj.</div>' if rr_adjusted else ""
    )

    summary = (
        '<summary>'
        f'<div class="tk-tick">'
        f'<div class="tk-tick-id"><span class="tk-tick-tk">{display_tk}</span>'
        f'{changed_dot}</div>'
        f'<div class="tk-tick-cluster">{cluster}</div></div>'
        f'<div>{_signal_pill_html(sig)}</div>'
        f'<div class="tk-last">'
        f'<div class="tk-last-px">'
        f'{f"{pfx}{_fmt_num(price, dec)}" if price is not None else "—"}</div>'
        f'<div class="tk-last-chg {_delta_class(chg)}">'
        f'{_pct_cell(chg, 2)}{ext_tag}</div></div>'
        f'<div class="tk-1mo {_delta_class(m1)}">{_pct_cell(m1, 1)}</div>'
        f'{extension_gauge_html(vs50)}'
        f'<div class="tk-rsi" data-zone="{rsi_zone}">{_fmt_num(rsi, 0)}</div>'
        f'<div class="tk-rr"{rr_title}>'
        f'<div class="tk-rr-val">{rr_label or "—"}</div>{rr_sub}</div>'
        '</summary>'
    )
```

Add `from components.watchlist.gauge import extension_gauge_html` to the imports. Keep `rr_title` exactly as it is — the raw headline still rides the `title` for grep-ability, the sub-line is the *visible* half.

- [ ] **Step 4: Run the tests — expect all 14 to pass**

- [ ] **Step 5: Commit**

Message: `feat(watchlist): two-line row cells, steel changed-dot, visible R:R qualifier`

---

## Task 5: Wire the filter chips

**Files:**
- Modify: `components/watchlist/watchlist.py` (rewrite `render_watchlist`)
- Test: `tests/test_app_pages.py` (add one `AppTest.from_function` case)

**Interfaces:**
- Consumes: everything from Task 3, plus `render_ticker_details_html`.
- Produces: `render_watchlist(watchlist: dict, changed_tickers: set[str] | None = None) -> None` — signature unchanged.

- [ ] **Step 1: Write the failing page test**

Append to `tests/test_app_pages.py`:

```python
def test_watchlist_page_renders_chips_groups_and_the_gauge():
    """Drive the page function directly.

    AppTest through dashboard.py resets nav to the default page, so widgets on
    any other page are unreachable — from_function is the only way in.
    """
    from streamlit.testing.v1 import AppTest

    import dashboard

    at = AppTest.from_function(dashboard._page_watchlist).run(timeout=60)
    assert not at.exception
    blob = " ".join(m.value for m in at.markdown)
    assert "tk-group" in blob          # explicit signal groups
    assert "tk-ext-track" in blob      # the gauge
    assert "tk-foot" in blob           # the legend footer
    # The chips are a real widget, so the filter survives the 60s live-price
    # fragment rerun instead of resetting to All once a minute.
    assert any(p.label == "Show" for p in at.get("pills"))
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `python -m pytest tests/test_app_pages.py -k watchlist_page_renders -v`

If `at.get("pills")` is not the right accessor in this Streamlit version, run
`python -c "from streamlit.testing.v1 import AppTest; print([a for a in dir(AppTest) if not a.startswith('_')])"`
and use whatever the version exposes; assert on the widget's presence and its label either way.

- [ ] **Step 3: Rewrite `render_watchlist`**

```python
"""Watchlist grid renderer — the only Streamlit-touching watchlist module.

``render_watchlist`` emits the Show chips, then the whole table (column header,
group headers, one ``<details>`` per ticker) in a single ``st.markdown``, then
the method note and the legend footer.
"""
from __future__ import annotations

import streamlit as st

from components.watchlist.grid import (
    FILTER_ALL,
    build_filter_options,
    build_grid_html,
    filter_items,
    footer_html,
    method_note_html,
)
from components.watchlist.row import render_ticker_details_html
from lib.catalog import RETIRED_TICKERS, SIGNAL_SORT_RANK
from lib.data_loader import load_earnings_history


def render_watchlist(
    watchlist: dict, changed_tickers: set[str] | None = None
) -> None:
    """The whole book: filter chips, the dense grid, the footnotes.

    ``changed_tickers`` is the set of tickers whose signal differs from the prior
    report. They drive both the persistent ● Changed chip and the steel dot on
    the row — in the shipped version this information lived only in a first-mount
    CSS flash, so it expired seconds after you landed.
    """
    changed_set = changed_tickers or set()
    _rank_last = len(SIGNAL_SORT_RANK)
    items = sorted(
        [(tk, d) for tk, d in watchlist.items() if tk not in RETIRED_TICKERS],
        key=lambda x: (
            SIGNAL_SORT_RANK.get(x[1].get("signal", "HOLD"), _rank_last),
            -(x[1].get("1mo_pct") or 0),
        ),
    )

    keys, labels = build_filter_options(items, changed_set)
    selected = st.pills(
        "Show",
        keys,
        selection_mode="single",
        default=FILTER_ALL,
        format_func=lambda k: labels[k],
        key="wl_filter",
    )
    # A chip clicked off returns None; the whole book is the right fallback.
    shown = filter_items(items, changed_set, selected or FILTER_ALL)

    st.markdown(
        '<div class="tk-sortline">Grouped by signal · then by one-month return '
        '· retired names excluded</div>',
        unsafe_allow_html=True,
    )

    # Quarter-on-quarter earnings history (separate CSV export) → per-ticker
    # records, newest quarter first (as exported). groupby(sort=False) preserves
    # that order; missing file → empty map → the drawer stays silent.
    eh_df = load_earnings_history()
    eh_map: dict[str, list] = {}
    if not eh_df.empty and "ticker" in eh_df.columns:
        for tkey, grp in eh_df.groupby("ticker", sort=False):
            eh_map[tkey] = grp.to_dict("records")

    st.markdown(
        build_grid_html(shown, changed_set, eh_map, render_ticker_details_html),
        unsafe_allow_html=True,
    )
    st.markdown(method_note_html(), unsafe_allow_html=True)
    st.markdown(footer_html(len(shown), len(items)), unsafe_allow_html=True)
```

- [ ] **Step 4: Run the page test and the whole non-visual suite**

Run: `python -m pytest tests/ -q --ignore=tests/visual`

- [ ] **Step 5: Commit**

Message: `feat(watchlist): persistent Show filter — chips carry the book's distribution`

---

## Task 6: The drill-down card — top half

**Files:**
- Modify: `components/watchlist/row.py` (drop the writeup block; body becomes one call)
- Modify: `components/watchlist/drilldown.py` (card wrapper, header, chips, entry-block, verdict, what-changed, what-to-do, levels plate, two columns)
- Modify: `components/briefing/action_card.py` (`_entry_target_invalidation_html` gains a fourth-cell variant)
- Modify: `tests/test_drilldown.py`

**Interfaces:**
- Produces: `render_drilldown_detail_html(tk, d, earnings_hist=None) -> str` — signature unchanged, but it now owns the **whole** body including the writeup.
- Produces: `components.briefing.action_card.levels_plate_html(d: dict, ccy: str, *, with_rr: bool = False) -> str`.

- [ ] **Step 1: Read the existing tests before changing anything**

Run: `python -m pytest tests/test_drilldown.py -v` and skim the file. Note any test asserting a block's **absence** — moving the writeup into this function could newly satisfy it. Fix such a test by narrowing its assertion to the block it means, never by keeping the old structure.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_drilldown.py`:

```python
# ── redesign 2026-07-25: verdict-first card, levels plate, three drawers ──
_MU = {
    "signal": "CAUTION",
    "price": 990.0,
    "currency": "USD",
    "entry_block": "BLOCKED: 5-day change +16.1% (>10% momentum chase block).",
    "entry_block_reader": "Entry blocked: up 16.1% in five sessions.",
    "reentry_zone": {"level": "$952.20"},
    "risk_reward": {
        "invalidation": 952.2, "upside_target": 1089.12,
        "ratio": 2.6, "ratio_label": "2.6:1",
        "upside_pct": 10.0, "downside_pct": 3.8,
    },
    "writeup": {
        "headline": "An 11.3% surge reclaims the 50-day.",
        "prior_period_delta_narrative": "Rating held from yesterday.",
        "what_to_do": "Wait for the move to settle.",
        "thesis_break_condition": "A close back below the 50-day.",
    },
    "support_legs": ["HBM sold out", "Pricing power", "Capex discipline"],
}


def test_card_carries_the_rows_signal_rail():
    html = render_drilldown_detail_html("MU", _MU)
    assert 'class="dd-card"' in html
    assert 'data-signal="CAUTION"' in html


def test_entry_block_precedes_the_verdict_headline():
    # The trade is blocked: the most consequential fact goes before the analysis,
    # not mid-list.
    html = render_drilldown_detail_html("MU", _MU)
    assert html.index("dd-entry-block") < html.index("dd-verdict")


def test_verdict_precedes_what_changed_which_precedes_what_to_do():
    html = render_drilldown_detail_html("MU", _MU)
    assert html.index("dd-verdict") < html.index("dd-delta") < html.index("dd-whatdo")


def test_levels_plate_has_four_cells_in_role_colours():
    html = render_drilldown_detail_html("MU", _MU)
    assert html.count("dd-lv-val") == 4
    assert "952.20" in html                      # trigger
    assert "var(--up)" in html                   # target: a price you hope for
    assert "var(--down)" in html                 # invalidation: one you fear
    assert "var(--brass)" in html                # R:R: a measurement, not a price


def test_pillars_are_numbered_and_the_falsifier_is_last():
    html = render_drilldown_detail_html("MU", _MU)
    assert ">01<" in html and ">03<" in html
    assert html.index("dd-pillar") < html.index("dd-break")


def test_technicals_and_valuation_share_the_left_column():
    html = render_drilldown_detail_html("MU", _MU)
    assert "dd-col-left" in html and "dd-col-right" in html
```

- [ ] **Step 3: Run and confirm failure**

- [ ] **Step 4: Add the four-cell levels plate to `action_card.py`**

Refactor `_entry_target_invalidation_html` so the cell builder is shared, then add:

```python
def levels_plate_html(d: dict, ccy: str, *, with_rr: bool = False) -> str:
    """Trigger / target / invalidation, plus R:R when ``with_rr``.

    Four colours, each by role: the two prices you are hoping for and fearing
    take market-direction colours, and the ratio is a measurement, so it takes
    brass. Promoted out of a section stack into a grid because price levels are
    what you act on — they should be findable without reading.

    ``with_rr=False`` reproduces the action card's three-cell triplet byte for
    byte; only the Watchlist drill-down passes ``True``.
    """
```

The existing three-cell call site must be left byte-identical — assert that by running the action-card tests before committing.

- [ ] **Step 5: Restructure `drilldown.py`**

`render_drilldown_detail_html` becomes:

```python
def render_drilldown_detail_html(tk, d, earnings_hist=None) -> str:
    ...
    return (
        f'<div class="dd-card" data-signal="{_escape_attr(sig)}">'
        f'{_header_html(tk, d, pfx, dec)}'
        f'{_status_chips_html(d)}'
        f'{_entry_block_html(d)}'
        f'{_verdict_html(d)}'          # dd-verdict / dd-delta / dd-whatdo
        f'{levels_plate_html(d, ccy, with_rr=True)}'
        f'<div class="dd-cols">'
        f'<div class="dd-col-left">{_technicals_pairs_html(d)}'
        f'{_valuation_pairs_html(tk, d)}</div>'
        f'<div class="dd-col-right">{_thesis_html(d)}</div>'
        f'</div>'
        f'{render_drawers_html(tk, d, earnings_hist)}'
        f'</div>'
    )
```

Shapes to emit:

```html
<div class="dd-head">
  <div class="dd-head-id"><div class="dd-head-tk">MU</div>
    <div class="dd-head-sub">Memory</div></div>
  <div class="dd-head-right"><div class="dd-head-px">$990.00</div>{pill}</div>
</div>

<div class="dd-pair"><span class="dd-pair-lbl">vs 50-day</span>
  <span class="dd-pair-val">+3.9%</span></div>

<div class="dd-pillar"><span class="dd-pillar-n">01</span>
  <span class="dd-pillar-t">HBM sold out</span></div>

<div class="dd-break">A close back below the 50-day.</div>
```

Label/value pairs reuse the field sets already in `_drilldown_metrics_html`'s
`tech_metrics` and `val_metrics` lists — same data, new container. Drop the
`Cluster` row from valuation (it is in the card header and the ticker cell now).
`_drilldown_metrics_html` and `_drilldown_section_html` stay, because the drawer
bodies in Task 7 still use them.

Re-base the status chips' colours: the data-quality chips (`momentum_warn`,
`data_anomaly`, and the `caution_source` ids currently mapped to `STATUS_WARN`)
move to `var(--stress)` — amber is WATCH's hue and a data-quality warning is not
a signal. The news-skew and premarket chips keep up/down: that *is* market
direction.

- [ ] **Step 6: Strip the writeup out of `row.py`**

The body collapses to one call, since the drill-down now owns the whole card:

```python
    body = (
        '<div class="tk-drilldown">'
        f'{render_drilldown_detail_html(tk, d, earnings_hist=earnings_hist)}'
        '</div>'
    )
```

Delete the now-unused `_writeup_for_render` import and the four `body_parts`
blocks from `row.py`.

- [ ] **Step 7: Run the drill-down, row, and security suites**

Run: `python -m pytest tests/test_drilldown.py tests/test_watchlist_row.py tests/test_rendering_security.py tests/test_briefing.py -v`

- [ ] **Step 8: Commit**

Message: `feat(watchlist): verdict-first drill-down card with a four-cell levels plate`

---

## Task 7: The three drawers

**Files:**
- Create: `components/watchlist/drilldown_drawers.py`
- Modify: `components/watchlist/drilldown.py` (move the relocated blocks out)
- Modify: `tests/test_drilldown.py`

**Interfaces:**
- Produces: `render_drawers_html(tk: str, d: dict, earnings_hist=None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_three_drawers_are_collapsed_details_not_st_expanders():
    # They live inside a markdown-injected <details>, where st.expander cannot.
    html = render_drilldown_detail_html("MU", dict(_MU, pre_earnings_band={
        "earnings_date": "2026-08-01", "days_until": 7,
    }, accumulate_gates={"g1_signal_eligible": True}))
    assert html.count('<details class="dd-drawer"') == 3
    assert "open" not in html.split("dd-drawer")[1][:40]   # collapsed by default


def test_a_drawer_with_no_populated_block_does_not_render():
    html = render_drilldown_detail_html("MU", _MU)   # no band, no gates, no RCP
    assert "Pipeline detail" not in html


def test_every_relocated_block_still_renders_somewhere():
    d = dict(
        _MU,
        pre_earnings_band={"earnings_date": "2026-08-01", "days_until": 7,
                           "setup_archetype": "neutral"},
        accumulate_gates={"g1_signal_eligible": True, "all_mechanical_pass": False},
        rcp_state={"current_phase": "cooling_off", "sessions_since_gap": 3},
        support_zones=[900.0], resistance_zones=[1100.0],
        avoid_source={"publication": "Reuters", "headline_fragment": "x"},
        earnings_results_in_news={"headline": "beat"},
    )
    html = render_drilldown_detail_html("MU", d)
    for needle in ("Earnings", "Risk &amp; reward detail", "Pipeline detail",
                   "Signal eligible", "Regime Change Pending", "Support",
                   "Reuters", "beat"):
        assert needle in html, needle
```

- [ ] **Step 2: Run and confirm failure**

- [ ] **Step 3: Implement `drilldown_drawers.py`**

Move, unchanged in content and only re-wrapped, from `drilldown.py`:

| Drawer summary | Blocks moved |
| --- | --- |
| `Earnings` | `pre_earnings_band` (archetype, bull/bear, six metrics) + `_earnings_history_html` |
| `Risk &amp; reward detail` | the upside/invalidation prose lines, the headline/wide-stop/structural metrics, `support_zones` / `resistance_zones` |
| `Pipeline detail` | `accumulate_gates`, `rcp_state`, `catalyst`, `avoid_source`, `earnings_results_in_news` |

```python
def _drawer(summary: str, body: str) -> str:
    """One collapsed drawer, or "" when nothing in it populated."""
    if not body:
        return ""
    return (
        f'<details class="dd-drawer"><summary>{summary}</summary>'
        f'<div class="dd-drawer-body">{body}</div></details>'
    )
```

Keep every `_escape_dollars` / `_escape_attr` / `_safe_href` call exactly where it
is. `thesis_highlights` does **not** come here — it goes in the right column
(Task 6's `_thesis_html`), between the pillars and the break condition.

- [ ] **Step 4: Run the tests, plus security**

Run: `python -m pytest tests/test_drilldown.py tests/test_rendering_security.py -v`

- [ ] **Step 5: Commit**

Message: `feat(watchlist): fold the audit-only blocks into three collapsed drawers`

---

## Task 8: The CSS

**Files:**
- Modify: `assets/theme.css` — replace `.tk-row` / `details.tk-details > summary` column tracks, add the new blocks, rewrite the phone reflow.

No unit test drives CSS; the visual baselines in Task 10 do. Work through the list, then look at a real render.

- [ ] **Step 1: Replace both grid track declarations**

`.tk-row` (line ~965) and `details.tk-details > summary` (line ~1013) both carry
`grid-template-columns: 80px 1fr 110px 110px 80px 100px 60px 70px`. Both become:

```css
  grid-template-columns: 132px 108px 112px 74px 168px 52px 96px;
```

Row padding goes to `12px`. Keep the `.tk-scroll` / sticky-header `:has()` rules
untouched — the 814px total still fits the ≥1100px viewport where that rule
releases `overflow-x`.

- [ ] **Step 2: Column header rules**

```css
/* Two weights, on purpose: the strong top rule opens the data zone (the same
   "shelf" logic as the Briefing's pulse tape); the faint bottom rule only
   separates labels from rows. Reading downward: a firm start, a soft handoff. */
.tk-row.tk-head {
  border-top: 1px solid var(--color-text);
  border-bottom: 1px solid var(--color-divider);
  font-size: 9.5px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--color-text-3); padding: 8px 12px;
}
.tk-h-right { text-align: right; }
.tk-h-center { text-align: center; }
```

- [ ] **Step 3: Group headers**

```css
.tk-group { display: flex; align-items: center; gap: 8px; padding: 20px 12px 6px; }
.tk-group-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--sig); }
.tk-group-name {
  font-family: var(--font-display); font-size: 11px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--sig);
}
.tk-group-count { font-size: 11px; color: var(--color-text-4); font-variant-numeric: tabular-nums; }
/* Labelled divider: the trailing hairline binds the label to the rows beneath
   it and gives each group a clean top edge without a second border weight. */
.tk-group-rule { flex: 1; height: 1px; background: var(--color-divider); }
```

- [ ] **Step 4: Row cells**

```css
.tk-tick-id { display: flex; align-items: center; gap: 6px; }
.tk-tick-tk { font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tk-tick-cluster {
  font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-3); opacity: 0.45; margin-top: 2px;
}
/* Steel, not a signal colour: "something changed today" is a structural fact
   about the row, not a rating — and it must not compete with the pill 100px to
   its right. Same steel as the ● Changed chip. */
.tk-changed { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex: 0 0 auto; }
.tk-last { text-align: right; }
.tk-last-px { font-size: 13.5px; font-variant-numeric: tabular-nums; }
.tk-last-chg { font-size: 11px; }
.tk-1mo { text-align: right; font-variant-numeric: tabular-nums; }
.tk-rsi { text-align: right; font-variant-numeric: tabular-nums; }
/* An overbought reading is a data condition, not a CAUTION rating: 77 on a
   name that happens to carry CAUTION is still terracotta, never red. */
.tk-rsi[data-zone="hot"], .tk-rsi[data-zone="cold"] { color: var(--stress); }
.tk-rr { text-align: right; }
.tk-rr-val { font-size: 13px; font-variant-numeric: tabular-nums; }
.tk-rr-sub { font-size: 8.5px; opacity: 0.42; letter-spacing: 0.04em; }
```

- [ ] **Step 5: The gauge**

```css
.tk-ext { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.tk-ext-track { position: relative; width: 100%; height: 9px; border: 1px solid var(--color-divider); }
/* Steel and over-tall so it stays visible where a bar crosses it — a structural
   reference mark, not data. */
.tk-ext-zero { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background: var(--accent); }
.tk-ext-fill { position: absolute; top: 0; bottom: 0; }
/* Brass is the data axis; terracotta marks the threshold crossing. Never
   green/red — that would read as "good/bad", wrong in both directions. */
.tk-ext-fill[data-tone="under"] { background: var(--brass); }
.tk-ext-fill[data-tone="over"] { background: var(--stress); }
.tk-ext-num { font-size: 10.5px; font-variant-numeric: tabular-nums; }
.tk-ext-empty { text-align: center; }
```

- [ ] **Step 6: Filter chips, sort line, method note, footer**

```css
/* Steel, because filtering is navigation, never a rating. The 14% wash is the
   one background on the page: a selected chip among adjacent chips reads too
   weakly on a border change alone. Scoped by the key class rather than a
   data-testid chain — testids on button internals have moved between the local
   1.50 / CI 1.58 / cloud-latest versions, the key class has not. */
.st-key-wl_filter [data-baseweb="button"],
.st-key-wl_filter button {
  border: 1px solid var(--color-divider) !important;
  border-radius: 3px !important; background: transparent !important;
  color: var(--color-text-3) !important;
  font-family: var(--font-display) !important; font-size: 10.5px !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
  padding: 4px 10px !important;
}
.st-key-wl_filter button[aria-pressed="true"],
.st-key-wl_filter button[aria-checked="true"] {
  border-color: var(--accent) !important;
  background: color-mix(in srgb, var(--accent) 14%, transparent) !important;
  color: var(--color-text) !important;
}
.st-key-wl_filter [role="group"] { gap: 8px !important; }

/* The page's only statement of its own ordering AND its survivorship-bias
   exclusion. Small, but without it a reader cannot tell whether row order
   means anything. */
.tk-sortline { font-size: 9.5px; opacity: 0.45; letter-spacing: 0.04em; margin: 2px 0 10px; }

.tk-method {
  font-size: 12.5px; opacity: 0.60; line-height: 1.6;
  max-width: 96ch; margin: 18px 0 0; border-top: 1px solid var(--color-divider); padding-top: 12px;
}
.tk-method b { color: var(--color-text); font-weight: 600; }
.tk-foot {
  font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-3); margin: 10px 0 0;
}
.tk-changed-legend { display: inline-block; vertical-align: 1px; }
```

Verify the active-state selector against a real render (Step 9) — Streamlit's
pills use `aria-pressed` in some versions and `aria-checked` in others, which is
why both are listed.

- [ ] **Step 7: The drill-down card**

```css
.dd-card { border-left: 3px solid var(--color-divider); padding-left: 18px; }
.dd-card[data-signal="BUY"] { border-left-color: var(--buy); }
.dd-card[data-signal="ACCUMULATE"] { border-left-color: var(--accumulate); }
.dd-card[data-signal="WATCH"] { border-left-color: var(--watch); }
.dd-card[data-signal="HOLD"] { border-left-color: var(--ink-3); }
.dd-card[data-signal="CAUTION"] { border-left-color: var(--caution); }
.dd-card[data-signal="AVOID"] { border-left-color: var(--avoid); }

.dd-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 12px; }
.dd-head-tk { font-family: var(--font-display); font-size: 22px; font-weight: 700; }
.dd-head-sub { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-3); }
.dd-head-right { text-align: right; }
.dd-head-px { font-size: 16px; font-variant-numeric: tabular-nums; margin-bottom: 5px; }

/* Terracotta because it is a gate condition, not a rating — and first, because
   "the trade is blocked" outranks every piece of analysis below it. */
.dd-entry-block {
  border: 1px solid var(--color-divider); border-left: 3px solid var(--stress);
  padding: 10px 14px; margin: 0 0 16px; font-size: 12.5px; line-height: 1.5;
}
.dd-verdict { font-family: var(--font-display); font-size: 21px; line-height: 1.25; margin: 0 0 8px; }
/* The only italic in the block, so it reads as a parenthetical update rather
   than part of the thesis. */
.dd-delta { font-style: italic; opacity: 0.78; font-size: 13px; margin: 0 0 10px; max-width: 72ch; }
/* Larger and darker than any other prose here, because it is the actionable
   instruction. Everything below it is evidence. */
.dd-whatdo { font-size: 14px; line-height: 1.6; max-width: 66ch; color: var(--color-text); margin: 0 0 18px; }

.dd-levels { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--color-divider);
             border: 1px solid var(--color-divider); margin: 0 0 20px; }
.dd-levels > * { background: var(--color-bg); padding: 12px 14px; min-width: 0; }
.dd-lv-lbl { font-size: 9.5px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-3); }
.dd-lv-val { font-family: var(--font-display); font-size: 20px; font-variant-numeric: tabular-nums; margin-top: 4px; }
.dd-lv-sub { font-size: 10px; color: var(--color-text-4); margin-top: 2px; }

.dd-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
/* Dashed, not solid, to distinguish "reference rows inside a card" from the
   solid row dividers of the table. */
.dd-pair { display: flex; justify-content: space-between; gap: 12px;
           border-bottom: 1px dashed var(--color-divider); padding: 6px 0; font-size: 12.5px; }
.dd-pair-lbl { color: var(--color-text-3); }
.dd-pair-val { font-variant-numeric: tabular-nums; }
/* Numbering makes the pillars a finite argument rather than a bullet dump. */
.dd-pillar { display: flex; gap: 10px; align-items: baseline; margin-bottom: 8px; font-size: 13px; line-height: 1.5; }
.dd-pillar-n { font-variant-numeric: tabular-nums; color: var(--color-text-4); font-size: 11px; flex: 0 0 auto; }
/* Deliberately last and terracotta: it is the falsifier. */
.dd-break { border-left: 2px solid var(--stress); padding-left: 10px; margin-top: 14px;
            font-size: 12.5px; line-height: 1.5; color: var(--color-text-2); }

details.dd-drawer { border: 1px solid var(--color-divider); margin-top: 10px; }
details.dd-drawer > summary {
  cursor: pointer; list-style: none; padding: 9px 12px;
  font-family: var(--font-display); font-size: 10.5px; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--eyebrow);
}
details.dd-drawer > summary::-webkit-details-marker { display: none; }
details.dd-drawer > summary::marker { content: ""; }
details.dd-drawer > summary::after { content: "+"; float: right; }
details.dd-drawer[open] > summary::after { content: "−"; }
.dd-drawer-body { padding: 0 12px 14px; }
```

- [ ] **Step 8: Rewrite the phone reflow**

In the `Phone reflow — one-screen ledgers` block, the `nth-child(1)…(8)` label
set becomes seven cells:

```css
  details.tk-details > summary > div:nth-child(1) { grid-area: 1 / 1 / 2 / 3; }
  details.tk-details > summary > div:nth-child(2) { grid-area: 1 / 3 / 2 / 4; justify-self: end; }
  details.tk-details > summary > div:nth-child(n + 3) { text-align: left !important; }
  details.tk-details > summary > div:nth-child(3)::before { content: "Last · Δ"; }
  details.tk-details > summary > div:nth-child(4)::before { content: "1 mo"; }
  details.tk-details > summary > div:nth-child(5)::before { content: "vs 50-day"; }
  details.tk-details > summary > div:nth-child(6)::before { content: "RSI"; }
  details.tk-details > summary > div:nth-child(7)::before { content: "R:R"; }
  /* A 168px bar cannot survive a stacked card; the number is the same
     information, so the track drops and the figure stays. */
  .tk-ext-track { display: none; }
  .tk-ext { align-items: flex-start; }
  .dd-cols { grid-template-columns: 1fr; gap: 20px; }
  .dd-levels { grid-template-columns: repeat(2, 1fr); }
```

The old `div.name` rule and the `nth-child(8)` label are deleted — the cluster is
no longer its own cell.

- [ ] **Step 9: Look at a real render**

The Playwright MCP browser is single-instance and another terminal may hold it.
Use the Docker harness from **PowerShell**, scoped to this page:

```
make visual-compare PYTEST_ARGS="-k watchlist"
```

It writes `tests/visual/_diffs/watchlist.actual.png`. Crop it with PIL before
reading it — a 3000px page burns context. Check specifically: chip active state
(is it `aria-pressed` or `aria-checked`?), the gauge's zero line visible through
a crossing bar, and that no column is clipped.

- [ ] **Step 10: Commit**

Message: `style(watchlist): seven-column grid, group rules, gauge and card CSS`

---

## Task 9: Verify against the whole corpus

**Files:** none — this is a check, and any failure it finds is fixed in the task that owns the code.

- [ ] **Step 1: Render every report date through the pure builders**

```python
# throwaway script, run from the worktree root
import glob, json
from components.watchlist.grid import build_grid_html, build_filter_options
from components.watchlist.row import render_ticker_details_html

for f in sorted(glob.glob("data/morning_report_*.json")):
    wl = json.load(open(f)).get("watchlist", {})
    items = sorted(wl.items(), key=lambda x: x[0])
    build_filter_options(items, set())
    html = build_grid_html(items, set(), {}, render_ticker_details_html)
    assert "—%" not in html, f
    assert "None" not in html, f
print("102 reports OK")
```

Expected: no exception on any of the 102 reports, and neither `—%` nor a leaked
`None` anywhere. A pre-adoption report missing `writeup`, `reentry_zone` or
`risk_reward` must render, not raise.

- [ ] **Step 2: Full non-visual suite**

Run: `python -m pytest tests/ -q --ignore=tests/visual`
Expected: all green. Report the actual count.

- [ ] **Step 3: Lint**

Run: `python -m ruff check components lib dashboard.py tests`
Expected: clean. Ruff has failed CI on import ordering in this repo before — fix
any `I001` rather than ignoring it.

- [ ] **Step 4: Commit any fixes**

---

## Task 10: Close-out

- [ ] **Step 1: Changelog entry, in its own commit**

Append to `data/changelog.json` (the strip shows the 10 newest). One entry
covering: signal groups with counts, the persistent Changed filter, the
extension gauge, the visible R:R qualifier, and the drill-down's verdict-first
order with three drawers.

Own commit, nothing else in it: an entry here moves the two Signal-Tracker
visual baselines, and whichever of the three branches lands second regenerates.

- [ ] **Step 2: Regenerate the visual baselines**

From PowerShell (not Git Bash), via the Docker harness. Regen skips unchanged
PNGs. Expect `watchlist` and `watchlist-nvda-drilldown` to move; if a Briefing
or Tracker baseline moves, something leaked out of scope — find it before
accepting the PNG.

- [ ] **Step 3: Full suite including visual**

- [ ] **Step 4: Commit the baselines**

Message: `test(visual): regenerate the Watchlist baselines for the redesign`

- [ ] **Step 5: Report**

State what shipped, what the test counts are, and which baselines moved. Do not
merge — three branches are open and the owner sequences the merges.

---

## Self-Review

**Spec coverage:**

| Spec § | Task |
| --- | --- |
| §3 page head | 1 |
| §4 filter bar (chips, Changed, st.pills, key-class styling, sort line) | 3, 5, 8 |
| §5 columns + width budget | 3, 8 |
| §5.2 phone reflow | 8 |
| §6 group headers + one-blob constraint | 3 |
| §7 the row | 4 |
| §8 the gauge | 2 |
| §9.1 reading order | 6 |
| §9.2 levels plate | 6 |
| §9.3 two columns, numbered pillars, highlights, falsifier last | 6 |
| §9.4 three drawers | 7 |
| §10 method note + footer | 3, 8 |
| §11 furniture kept | 1 (only the head changes) |
| §12 data plumbing + absence tiers | 9 |
| §13 shared couplings | 1 (verbatim replica), 10 (changelog alone) |
| §14 testing | 2, 3, 4, 5, 6, 7, 9, 10 |
| §15 sequencing | task order |

No gaps.

**Placeholder scan:** every code step carries real code; the two places that
say "verify against a real render" (Task 8 Step 9, chip `aria-*` state) and
"check the accessor" (Task 2 Step 3, Task 5 Step 2) are deliberate — they are
facts about a third-party library's rendered output that must be observed, not
guessed, and each names the exact command to observe it with.

**Type consistency:** `extension_gauge_html(vs50)` is defined in Task 2 and
consumed in Task 4 under that name. `build_grid_html(items, changed_tickers,
earnings_map, row_builder)` is defined in Task 3 and called in Task 5 with
`render_ticker_details_html` as `row_builder`, whose signature
`(tk, d, signal_changed=False, earnings_hist=None)` matches the keyword
arguments Task 3 passes. `levels_plate_html(d, ccy, *, with_rr=False)` is
defined in Task 6 and called there. `render_drawers_html(tk, d, earnings_hist)`
is defined in Task 7 and called in Task 6's orchestrator — Task 6 must therefore
land a stub returning `""` for its own tests to pass, replaced in Task 7.
