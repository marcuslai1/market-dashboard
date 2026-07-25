# Signal Tracker Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Signal Tracker page's construction and colour discipline to match the owner's design account, without changing what information the page carries.

**Architecture:** Five shared CSS devices are extracted first (hairline cell grid, steel stat tick, drawer grammar, terracotta warning, date spine), then each of the page's four sections is re-expressed in terms of them. Python changes are confined to the HTML-building helpers in `components/signal_tracker.py`, `components/paper_book.py` and `components/briefing/calibration.py`; no data, math or upstream field changes. Plotly is kept for the NAV plot and given HTML chrome around it.

**Tech Stack:** Python 3.10, Streamlit (>=1.42,<1.59), pandas, Plotly, pytest, Playwright visual-regression harness in Docker.

**Spec:** `docs/superpowers/specs/2026-07-25-signal-tracker-redesign-design.md`

## Global Constraints

- **Colour roles never overlap.** Signal palette = signal ratings only. `--brass` = measurements. `--stress` (terracotta) = trust limitations. `--accent`/`--eyebrow` (steel) = structure and flagging. `--up`/`--down` = market direction. Everything else neutral (`--color-text-2/3/4`).
- **Amber (`#f59e0b`, `STATUS_WARN`) is WATCH.** It must not appear in any data-quality or sample-adequacy context on this page.
- **No block is cut, moved between pages, or reordered.** This is a presentation-layer change only — no new signals, metrics or upstream fields.
- **Absence tiers are preserved.** Every block already skips itself when its data is missing; pre-adoption corpora must keep rendering. No section may start hard-failing on an older report.
- New/edited CSS uses the `--color-*` / `--font-display` token layer, not the legacy `--ink` / `--serif` / `--rule` aliases. Blocks not touched by this work are left alone.
- Local commits use `git commit -F <file>` (PowerShell 5.1 word-splits embedded quotes in `-m`).
- Run tests with `python -m pytest` (module form) so repo-root imports resolve.
- Visual baselines are regenerated **once, in Task 9**, inside the pinned `mcr.microsoft.com/playwright/python:v1.60.0-jammy` image. Never commit a baseline rendered on the Windows host.

---

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `assets/theme.css` | all styling; shared devices + per-section blocks | 1–8 |
| `lib/cards.py` | `_section_head_html` / `render_section_head` (+ masthead variant) | 1 |
| `components/briefing/calibration.py` | §1 row + body markup | 2 |
| `components/signal_tracker.py` | trust meter, methodology copy, tiles, HOLD footnote, changelog spine, page marker | 3, 4, 8 |
| `components/paper_book.py` | headline sentence, stats grid, chart chrome, stop-rule lanes | 5, 6, 7 |
| `tests/test_design_tokens.py` | device + colour-discipline guards | 1, 4 |
| `tests/test_cards.py` (new) | section-head HTML | 1 |
| `tests/test_calibration.py` | §1 assertions | 2 |
| `tests/test_signal_tracker.py` | trust meter, tiles, changelog | 3, 4, 8 |
| `tests/test_paper_book.py` | headline, stats, chart chrome, lanes | 5, 6, 7 |
| `tests/test_app_pages.py` | page-level smoke assertions | 4 |
| `data/changelog.json` | reader-facing methodology entry | 9 |
| `tests/visual/baselines/*.png` | regenerated baselines | 9 |

---

## Task 1: Foundation — shared devices

**Files:**
- Modify: `assets/theme.css:1202-1216` (`.fp-grid` / `.fp-cell` → selector lists), end of file (new device block)
- Modify: `lib/cards.py:11-18`
- Test: `tests/test_cards.py` (create), `tests/test_design_tokens.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - CSS classes `.hair-grid` (grid container), `.hair-grid > *` (cell), `.hair-grid > [data-flag]` (steel top rail), `.stat-tick` (with `<b>` value + `<span>` label children), `.warn-thin`, `.spine`, `.section-head.masthead`.
  - `lib.cards._section_head_html(title: str, sub: str = "", masthead: bool = False) -> str`
  - `lib.cards.render_section_head(title: str, sub: str = "", masthead: bool = False) -> None`
  - Page marker convention: the Signal Tracker page emits `<span class="tracker-page"></span>`; drawer CSS is scoped with `.stApp:has(.tracker-page)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cards.py`:

```python
"""Section-head primitive — the masthead variant must stay opt-in.

The Signal Tracker's four peer sections take a 2px full-strength rule (spec
2026-07-25 §3.5). Every other section head on the site keeps the 1px hairline,
so the variant is a flag, never the default.
"""
from lib.cards import _section_head_html


def test_section_head_default_is_not_masthead():
    html = _section_head_html("Paper book", "no real money")
    assert 'class="section-head"' in html
    assert "masthead" not in html
    assert "Paper book" in html and "no real money" in html


def test_section_head_masthead_variant_adds_the_class():
    html = _section_head_html("Signal tracker", "track record", masthead=True)
    assert 'class="section-head masthead"' in html


def test_section_head_without_sub_still_renders():
    assert "<h2>Terminology</h2>" in _section_head_html("Terminology")
```

Append to `tests/test_design_tokens.py`:

```python
# ── Signal Tracker redesign (spec 2026-07-25): shared devices ──

def test_hairline_grid_device_is_single_sourced():
    """The FRED prints grid and the tracker's grids must be the same device, so
    'a grid of cells' always means 'peer measurements, compare across'."""
    assert ".hair-grid, .fp-grid" in _THEME_CSS
    assert ".hair-grid > *, .fp-cell" in _THEME_CSS


def test_stat_tick_is_two_px_steel_not_a_signal_rail():
    """2px --accent, deliberately not the 3px rail signal rows use: the tick
    says 'this is one discrete figure', never 'this is a rating'."""
    block = _THEME_CSS.split(".stat-tick {", 1)[1].split("}", 1)[0]
    assert "border-left: 2px solid var(--accent)" in block


def test_thin_sample_warning_is_terracotta_never_watch_amber():
    """Amber is WATCH. A data-quality warning is not a signal, so it takes the
    data palette's stress colour."""
    block = _THEME_CSS.split(".warn-thin {", 1)[1].split("}", 1)[0]
    assert "var(--stress)" in block
    assert "#f59e0b" not in block


def test_masthead_section_head_is_the_two_px_rule():
    block = _THEME_CSS.split(".section-head.masthead {", 1)[1].split("}", 1)[0]
    assert "border-bottom: 2px solid var(--color-text)" in block
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_cards.py tests/test_design_tokens.py -q`
Expected: FAIL — `ImportError: cannot import name '_section_head_html'` plus four assertion failures on the missing CSS.

- [ ] **Step 3: Re-base the FRED grid onto the shared device**

In `assets/theme.css`, replace the `.fp-grid` and `.fp-cell` rules (currently at 1202–1216) with selector lists. Output for the Briefing is byte-identical — same declarations, now shared:

```css
/* The 1px-gap-over-a-divider-ground trick draws hairlines between every cell
   without per-cell borders. Shared with the Signal Tracker's tiles, paper-book
   stats and stop-rule lanes (spec 2026-07-25 §3.1): a grid of cells always
   means "peer measurements, compare across". */
.hair-grid, .fp-grid {
  display: grid; gap: 1px;
  background: var(--color-divider); border: 1px solid var(--color-divider);
}
.fp-grid { grid-template-columns: repeat(5, 1fr); }
/* The rail is declared transparent rather than omitted so flagged and unflagged
   cells keep identical internal height — no 2px jog along the row. */
.hair-grid > *, .fp-cell {
  background: var(--color-bg); min-width: 0;
  border-top: 2px solid transparent;
}
.fp-cell { padding: 0 11px 10px; }
/* Structural flag, not a rating: steel, because a signal hue here would read as
   a verdict on the number. */
.hair-grid > [data-flag], .fp-cell[data-key] { border-top-color: var(--accent); }
```

- [ ] **Step 4: Append the remaining devices at the end of `assets/theme.css`**

```css
/* ══════════════════════════════════════════════════════════════════════
   SIGNAL TRACKER REDESIGN (spec 2026-07-25) — shared devices
   The page teaches a grammar by repetition. Each device is declared once here
   and consumed by several sections; the colour roles never overlap.
   ══════════════════════════════════════════════════════════════════════ */

/* A discrete figure: value over label (the site-wide order), with a 2px steel
   tick. Deliberately 2px — the 3px rail is signal language on watchlist rows
   and clusters, and must not be confused with "this is a number". */
.stat-tick { border-left: 2px solid var(--accent); padding-left: 12px; }
.stat-tick b {
  display: block; font-family: var(--font-display); font-size: 26px;
  font-weight: 600; line-height: 1.1; color: var(--color-text);
  font-variant-numeric: tabular-nums;
}
.stat-tick span {
  display: block; font-family: var(--font-display); font-size: 9.5px;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--color-text-3); margin-top: 4px;
}

/* Trust limitation, never a rating. Terracotta because amber is WATCH: a
   data-quality warning is not a signal, so it takes the data palette's stress
   colour. This keeps the rule intact even where a warning "wants" to be amber. */
.warn-thin { color: var(--stress); }

/* Date-spine ledger (consumed by "What we've changed"). The fixed date column
   makes a continuous vertical spine: you scan chronology first, then read
   across. Tick is --color-divider, not accent — every entry is a peer. */
.spine { border-top: 1px solid var(--color-divider); }
.spine > * {
  display: grid; grid-template-columns: 112px 1fr; gap: 0 20px;
  padding: 16px 0; border-bottom: 1px solid var(--color-divider);
}

/* Four peer documents stacked: the masthead-weight rule, used only by the
   Signal Tracker's section heads. Every other head on the site keeps the 1px
   hairline, so this stays opt-in. */
.section-head.masthead { border-bottom: 2px solid var(--color-text); padding-bottom: 10px; }
.section-head.masthead h2 { font-size: 1.875rem !important; font-weight: 600; }

/* Page-level drill-downs: hairline-bordered, square, steel uppercase summary.
   Bordered — unlike the inline Week Ahead expander — because these are
   page-level sections rather than a detail inside a row. Streamlit renders
   st.expander as a real <details>, so this is CSS only and every widget inside
   keeps working. Scoped to the page marker so no other page's expanders move.
   (The chevron already rotates on open — that animation is Streamlit's own.) */
.stApp:has(.tracker-page) details[data-testid="stExpander"] {
  border: 1px solid var(--color-divider); border-radius: 0;
  background: transparent; margin: 10px 0;
}
.stApp:has(.tracker-page) details[data-testid="stExpander"] summary {
  font-family: var(--font-display); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--eyebrow);
}
```

- [ ] **Step 5: Split `render_section_head` into a pure builder plus the renderer**

Replace `lib/cards.py:11-18` with:

```python
def _section_head_html(title: str, sub: str = "", masthead: bool = False) -> str:
    """Editorial section header markup: serif <h2> left, mono sub right.

    ``masthead=True`` gives the Signal Tracker's four peer sections the heavier
    2px full-strength rule (spec 2026-07-25 §3.5) without moving every other
    section head on the site. Pure so it can be tested without a Streamlit run.
    """
    cls = "section-head masthead" if masthead else "section-head"
    return (f'<div class="{cls}"><h2>{title}</h2>'
            f'<span class="sub">{sub}</span></div>')


def render_section_head(title: str, sub: str = "", masthead: bool = False) -> None:
    """Editorial section header: serif <h2> on the left, mono sub on the right."""
    st.markdown(_section_head_html(title, sub, masthead), unsafe_allow_html=True)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_cards.py tests/test_design_tokens.py -q`
Expected: PASS.

- [ ] **Step 7: Confirm nothing else moved**

Run: `python -m pytest tests/ -q --ignore=tests/visual`
Expected: PASS — the `.fp-grid` re-base is declaration-identical, so the Briefing tests are unaffected.

- [ ] **Step 8: Commit**

```bash
git add assets/theme.css lib/cards.py tests/test_cards.py tests/test_design_tokens.py
git commit -F <message-file>
```

Message: `feat(tracker): extract the shared devices the redesign repeats` — body explains that the hairline grid, stat tick, terracotta warning, date spine and masthead head are declared once so the page can teach one grammar.

---

## Task 2: §1 Signal calibration — the row and its body

**Files:**
- Modify: `components/briefing/calibration.py:200-221` (`_scorecard_table_html`), `:224-257` (`_headline_html`)
- Modify: `assets/theme.css:2073-2082` (`.cal-*` block)
- Test: `tests/test_calibration.py`

**Interfaces:**
- Consumes: `.warn-thin` and the token layer from Task 1.
- Produces: markup classes `.cal-count`, `.cal-alpha`, `.cal-conf` (steel outline chip), and `td.alpha` inside `.cal-scorecard`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calibration.py`:

```python
# ── Redesign (spec 2026-07-25 §4): colour roles on the calibration row ──
from components.briefing.calibration import _headline_html, _scorecard_rows

_PERF = {"CAUTION": {"n_matured_10d": 96, "n_alpha_10d": 96, "win_rate_pct": 48.0,
                     "avg_return_10d": -1.2, "alpha_10d": -2.8, "n_episodes": 21,
                     "alpha_episode_mean_10d": -2.1, "single_regime": False}}


def test_headline_alpha_is_brass_not_a_second_verdict():
    """Alpha measures the signal's performance — it is data, not a rating. In a
    signal hue it would read as a second CAUTION verdict."""
    rows = _scorecard_rows(_PERF, {"CAUTION": 21})
    html = _headline_html(rows, {"CAUTION": 21})
    assert 'class="cal-alpha"' in html
    assert "-2.8% α / 10d" in html


def test_headline_count_recedes_without_its_own_line():
    rows = _scorecard_rows(_PERF, {"CAUTION": 21})
    html = _headline_html(rows, {"CAUTION": 21})
    assert 'class="cal-count"' in html
    assert "21" in html and "names" in html


def test_confidence_is_a_structural_chip_not_red_text():
    """Confidence is a structural qualifier — how much to trust the number — so
    it takes the structural colour, outlined rather than filled."""
    block = _THEME_CSS.split(".cal-conf {", 1)[1].split("}", 1)[0]
    assert "var(--accent)" in block
    assert "var(--caution)" not in block


def test_alpha_columns_in_the_body_are_flagged_for_brass():
    rows = _scorecard_rows(_PERF, {"CAUTION": 21})
    html = _scorecard_table_html(rows)
    assert 'class="num alpha"' in html


def test_calibration_caveat_is_not_italic():
    """The paper book's single-regime disclaimer is the only italic on the
    page — that is why it is noticeable."""
    block = _THEME_CSS.split(".cal-caveat {", 1)[1].split("}", 1)[0]
    assert "italic" not in block
```

Add at the top of `tests/test_calibration.py` (after the existing imports) if not already present:

```python
from pathlib import Path

from components.briefing.calibration import _scorecard_table_html

_THEME_CSS = (Path(__file__).resolve().parent.parent / "assets" / "theme.css").read_text(
    encoding="utf-8"
)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_calibration.py -q`
Expected: FAIL — `cal-alpha` / `cal-count` / `num alpha` absent, `.cal-conf` still `var(--caution)`, `.cal-caveat` still italic.

- [ ] **Step 3: Rebuild the headline row**

In `components/briefing/calibration.py::_headline_html`, replace the return block inside `if row is not None:` (currently lines 249–256) with:

```python
            n = counts[dominant]
            names = "name" if n == 1 else "names"
            return (
                '<span class="cal-headline">'
                f"{_signal_pill_html(dominant, small=True)}"
                f'<span class="cal-head-txt">most common today '
                f'<span class="cal-count">({n}&nbsp;{names})</span> · '
                # Brass: alpha is a measurement of the signal's performance, not
                # a second verdict on it. Red here would read as another CAUTION.
                f'<b class="cal-alpha">{_pct(row["alpha"])} α / 10d</b> · '
                f'<span class="cal-conf" title="{conf_tip}">{conf}</span>'
                "</span></span>"
            )
```

- [ ] **Step 4: Flag the body's α columns**

In `_scorecard_table_html`, change the two α cells so CSS can colour them:

```python
        ep_td = (f'<td class="num alpha" data-l="alpha/ep">{_pct(r["ep_mean"])}</td>'
                 if has_ep else "")
```

and

```python
            f'<td class="num alpha" data-l="alpha">{_pct(r["alpha"])}</td>{ep_td}</tr>'
```

- [ ] **Step 5: Restyle the `.cal-*` block**

In `assets/theme.css`, replace `.cal-conf`, `.cal-scorecard tr[data-lowconf="1"]` and `.cal-caveat` (currently 2075, 2078, 2081) with:

```css
/* Parenthetical detail — recedes without needing a line of its own. */
.cal-count { color: var(--color-text-4); }
/* Measurement, not a rating: the loudest thing on the row after the pill,
   because it is the actual content. */
.cal-alpha { color: var(--brass); font-weight: 600; font-variant-numeric: tabular-nums; }
/* Structural qualifier — how much to trust the number — so it takes the
   structural colour. Outlined rather than filled keeps it quiet: it qualifies
   the figure, it isn't the headline. */
.cal-conf {
  display: inline-block; border: 1px solid var(--accent); color: var(--accent);
  background: transparent; border-radius: var(--radius-pill);
  font-family: var(--font-display); font-size: 9.5px; letter-spacing: 0.1em;
  text-transform: uppercase; padding: 1px 6px;
}
.cal-scorecard td.alpha { color: var(--brass); font-weight: 600; }
/* Opacity, not tint: the brass α cells must recede with the row, and a colour
   swap alone would leave them at full strength. */
.cal-scorecard tr[data-lowconf="1"] { opacity: 0.62; }
.cal-caveat { color: var(--color-text-3); font-size: 11.5px; line-height: 1.5; margin: 4px 0 0; }
```

- [ ] **Step 6: Give §1's section head the masthead rule**

In `components/briefing/calibration.py::render_calibration` (line 311), add the flag so all four of the page's heads share the masthead weight:

```python
    render_section_head("Signal calibration",
                        "How today's signals have actually performed",
                        masthead=True)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_calibration.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add components/briefing/calibration.py assets/theme.css tests/test_calibration.py
git commit -F <message-file>
```

Message: `feat(tracker): the calibration row reads as an instrument, not a verdict`

---

## Task 3: §2 Trust meter and the methodology paragraph

**Files:**
- Modify: `components/signal_tracker.py:442-484` (`_readiness_html`), `:674-706` (page head, marker, caption)
- Modify: `assets/theme.css:2252-2270` (`.rd-*` block)
- Test: `tests/test_signal_tracker.py`, `tests/test_app_pages.py`

**Interfaces:**
- Consumes: `card_container` from `lib.cards`, `.stat-tick` from Task 1.
- Produces: `_readiness_html` returns a `card_container(...)` string; `_method_html() -> str`; the page emits `<span class="tracker-page"></span>` (the scope hook Task 1's drawer CSS depends on).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_signal_tracker.py`:

```python
# ── Redesign (spec 2026-07-25 §5): trust meter + methodology paragraph ──
from components.signal_tracker import _method_html

_CI_SINGLE = {"signal_performance": {
    "CAUTION": {"n_matured_10d": 96, "n_alpha_10d": 96,
                "single_regime": True, "regimes_present": ["trend_up"]},
}}


def test_trust_meter_is_one_blueprint_card():
    """The caveat must be impossible to read separately from the numbers it
    limits, so it lives in the same frame — not a second card, not a footnote."""
    html = _readiness_html(_CI_SINGLE)
    assert "blueprint" in html
    assert html.count("blueprint") == 1
    assert "directional" in html.lower()


def test_trust_meter_stats_use_the_shared_tick():
    html = _readiness_html(_CI_SINGLE)
    assert html.count('class="stat-tick"') == 3


def test_trust_meter_does_not_borrow_watch_amber():
    """The warn state changes the sentence; it must not borrow WATCH's hue."""
    assert "#f59e0b" not in _readiness_html(_CI_SINGLE)


def test_method_bolds_only_the_three_load_bearing_phrases():
    """Bolding is by what breaks comprehension if missed, not by keyword
    importance: what counts as right for each family, and that this is not the
    alpha view."""
    html = _method_html()
    assert html.count("<b>") == 3
    assert "<b>rise</b>" in html and "<b>drop</b>" in html
    assert "<b>raw price direction</b>" in html


def test_method_points_at_this_page_not_the_briefing():
    """The calibration band moved onto this page in the 2026-07 overhaul — the
    old pointer sent readers to a band that is no longer there."""
    html = _method_html()
    assert "Briefing" not in html
```

Append to `tests/test_app_pages.py` (the drawer grammar is keyed on this marker, so without it the CSS silently no-ops):

```python
def test_tracker_page_emits_the_scope_marker():
    """The page's drawer grammar is scoped with .stApp:has(.tracker-page); if
    the marker stops rendering, every drawer quietly reverts."""
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_function(_tracker_page_app, default_timeout=30)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    assert 'class="tracker-page"' in " ".join(str(m.value) for m in at.markdown)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_signal_tracker.py -q`
Expected: FAIL — `ImportError: cannot import name '_method_html'`.

- [ ] **Step 3: Rebuild `_readiness_html` as a blueprint card**

In `components/signal_tracker.py`, add `from lib.cards import card_container, render_section_head` to the imports, then replace the body of `_readiness_html` from `n_regimes = len(regimes)` to the end with:

```python
    n_regimes = len(regimes)
    if decision_grade > 0 and n_regimes >= 2:
        verdict = ("Some signals now have cross-regime evidence — still read the "
                   "per-signal sample sizes below before leaning on any one.")
    else:
        verdict = ("Read the scorecard as directional, not proven. A second market "
                   "regime — a downturn or a choppy stretch — is what turns this "
                   "into a real verdict.")
    # auto auto auto 1fr: the three figures size to their content and cluster
    # left as a set; the caveat absorbs the rest. Spread across the card they
    # stop reading as one measurement.
    stats = (
        f'<div class="stat-tick"><b>{n_regimes} of {_REGIME_UNIVERSE}</b>'
        f"<span>market regimes seen</span></div>"
        f'<div class="stat-tick"><b>{total_matured}</b>'
        f"<span>matured calls</span></div>"
        f'<div class="stat-tick"><b>{decision_grade} of {scored}</b>'
        f"<span>signals decision-grade</span></div>"
    )
    # The caveat sits INSIDE the card on purpose: three tidy numbers invite a
    # false confidence, and the sentence that limits them must be impossible to
    # read separately from them. A hairline is enough to mark "different kind of
    # content" without splitting one reading into two cards.
    body = (f'<div class="rd-grid">{stats}'
            f'<p class="rd-verdict">{verdict}</p></div>')
    return card_container(eyebrow="Trust meter", body_html=body)
```

Delete the now-unused `tone` variable and the `.rd-meter.warn` path.

- [ ] **Step 4: Add the methodology paragraph builder**

Add to `components/signal_tracker.py`, directly below `_readiness_html`:

```python
def _method_html() -> str:
    """How to read the hit-rate tiles, in one paragraph.

    Exactly three phrases are bolded — what counts as right for each signal
    family, and that these are raw price moves rather than the benchmark-relative
    view. Those are the three things a reader must not misunderstand; everything
    else in the sentence can be skimmed.
    """
    return (
        '<p class="method">How often each signal went the right way, 5 sessions '
        "later. BUY / ACCUMULATE / WATCH count a <b>rise</b> as right; "
        "CAUTION / AVOID count a <b>drop</b> as right (you avoided it). This is "
        "<b>raw price direction</b> — the benchmark-relative view (alpha vs the "
        "market) is the Signal calibration row at the top of this page.</p>"
    )
```

- [ ] **Step 5: Wire the page head, marker and paragraph**

In `render_signal_tracker_page`, replace the opening `st.markdown(...)` section head (lines 674–678) with:

```python
    # Scope hook for the page's drawer grammar (spec 2026-07-25 §3.3) — the CSS
    # is keyed on .stApp:has(.tracker-page) so no other page's expanders move.
    st.markdown('<span class="tracker-page"></span>', unsafe_allow_html=True)
    render_section_head("Signal tracker", "Is the record big enough to trust?",
                        masthead=True)
```

Replace the `st.caption(...)` methodology block (lines 696–702) with:

```python
    st.markdown(_method_html(), unsafe_allow_html=True)
```

- [ ] **Step 6: Restyle the `.rd-*` block**

In `assets/theme.css`, replace `.rd-meter`, `.rd-meter.warn`, `.rd-stats`, `.rd-stat b`, `.rd-stat span` and `.rd-verdict` (2252–2270) with:

```css
.rd-grid { display: grid; grid-template-columns: repeat(3, auto) 1fr; gap: 0 26px; align-items: start; }
/* A hairline marks "different kind of content" (prose vs figures) inside one
   card, without splitting one reading into two cards. */
.rd-verdict {
  border-left: 1px solid var(--color-divider); padding-left: 24px;
  color: var(--color-text-2); font-size: 13px; line-height: 1.6;
  opacity: 0.78; margin: 0;
}
@media (max-width: 900px) {
  .rd-grid { grid-template-columns: repeat(2, auto); gap: 18px; }
  .rd-verdict { grid-column: 1 / -1; border-left: 0; padding-left: 0;
                border-top: 1px solid var(--color-divider); padding-top: 14px; }
}
/* Set for genuine paragraph reading, and capped so the measure stays readable. */
.method {
  font-size: 12.5px; line-height: 1.65; color: var(--color-text-2);
  opacity: 0.62; max-width: 104ch; margin: 14px 0 4px;
}
.method b { color: var(--color-text); font-weight: 600; opacity: 1; }
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_signal_tracker.py tests/test_app_pages.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add components/signal_tracker.py assets/theme.css tests/test_signal_tracker.py tests/test_app_pages.py
git commit -F <message-file>
```

Message: `feat(tracker): the trust meter keeps its caveat inside the frame`

---

## Task 4: §3 Hit-rate tiles and the HOLD footnote

**Files:**
- Modify: `components/signal_tracker.py:347-397` (`_scorecard_html`), `:707-709` (HOLD caption)
- Modify: `assets/theme.css:1941-1972`, `:2210-2213`, `:2217-2231`
- Test: `tests/test_signal_tracker.py`, `tests/test_design_tokens.py`, `tests/test_app_pages.py:91-103`

**Interfaces:**
- Consumes: `.hair-grid` and `.warn-thin` from Task 1.
- Produces: `_scorecard_html` returns `<div class="hair-grid calib-grid">…`; cells keep `class="calib-cell"` / `class="calib-cell thin"`; `_hold_footnote_html(n: int) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_signal_tracker.py`:

```python
# ── Redesign (spec 2026-07-25 §5.3): the hit-rate tiles ──
from components.signal_tracker import _hold_footnote_html


def test_tiles_are_five_cells_of_one_hairline_grid():
    """Five across is the point: the rates only compare if they share a row."""
    html = _scorecard_html(_acc_df("BUY", [1.0] * 10))
    assert 'class="hair-grid calib-grid"' in html
    assert html.count('class="calib-cell') == 5


def test_hit_rate_bars_are_brass_not_traffic_light():
    """A hit rate is calibration data, not a rating — so no signal hue and no
    green/red valence anywhere in the tile markup."""
    html = _scorecard_html(_acc_df("BUY", [1.0] * 10))
    assert STATUS_POS not in html and STATUS_NEG not in html
    assert "#f59e0b" not in html


def test_thin_cell_differs_in_three_redundant_ways():
    """Opacity (the .thin class), colour (.warn-thin) and a glyph — no single
    cue has to carry the caveat."""
    thin = _scorecard_html(_acc_df("CAUTION", [-3.0, -1.0, -2.0, 4.0]))  # n=4
    assert 'class="calib-cell thin"' in thin
    assert "warn-thin" in thin
    assert "⚠" in thin
    solid = _scorecard_html(_acc_df("BUY", [1.0] * 10))
    assert "warn-thin" not in solid and "holding up" in solid


def test_hold_is_a_footnote_not_a_sixth_tile():
    """HOLD makes no directional claim, so a cell with an empty percentage would
    imply a missing measurement rather than an inapplicable one."""
    note = _hold_footnote_html(188)
    assert "188" in note and "not scored" in note
    assert "calib-cell" not in note
    assert _hold_footnote_html(0) == ""
```

Append to `tests/test_design_tokens.py`:

```python
def test_tile_bar_fills_the_cell_so_lengths_compare():
    """47% vs 100% must read as a shape difference before either number is
    read, which a capped bar width prevents."""
    block = _THEME_CSS.split(".calib-cell .cbar {", 1)[1].split("}", 1)[0]
    assert "max-width" not in block


def test_tile_meaning_line_holds_a_shared_baseline():
    block = _THEME_CSS.split(".calib-cell .sc-verb {", 1)[1].split("}", 1)[0]
    assert "min-height: 24px" in block
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_signal_tracker.py tests/test_design_tokens.py -q`
Expected: FAIL — `ImportError: cannot import name '_hold_footnote_html'`.

- [ ] **Step 3: Rebuild `_scorecard_html`**

Replace the loop body and return in `components/signal_tracker.py::_scorecard_html`:

```python
    cells = ""
    for sig, mode, verb in _SCORECARD_SPECS:
        data = acc_df[acc_df["signal"] == sig] if not acc_df.empty else pd.DataFrame()
        valid5 = (data["return_5d"].dropna()
                  if "return_5d" in data.columns else pd.Series(dtype=float))
        n = len(valid5)
        color = SIGNAL_COLORS.get(sig, INK_FALLBACK)
        # A rate below the decision-grade floor ghosts the whole cell (see
        # .calib-cell.thin): any colour-coding would fight the number's own
        # prominence, whereas ghosting makes the untrustworthy figures
        # physically recede. The design enforces the caveat instead of printing
        # it.
        cell_thin = False

        if n >= MIN_SAMPLES:
            right = int((valid5 <= 0).sum() if mode == "avoid" else (valid5 > 0).sum())
            rate = right / n * 100
            # No inline colour: the bar is brass in CSS, because a hit rate is a
            # measurement and never a rating.
            val_html = (
                f'<div class="cval">{rate:.0f}%</div>'
                f'<div class="cbar"><i style="width:{rate:.0f}%;"></i></div>'
            )
            sub = f"right {right} of {n} · 5d"
            if n < DECISION_GRADE_MIN:
                cell_thin = True
                flag = f'<div class="sc-flag warn-thin">⚠ thin — only {n} calls</div>'
            else:
                flag = f'<div class="sc-flag">n={n} · holding up</div>'
        else:
            val_html = f'<div class="cval muted">{"Pending" if n else "—"}</div>'
            sub = f"{n} of {MIN_SAMPLES}+ needed"
            flag = '<div class="sc-flag">not enough yet</div>'

        cells += (
            f'<div class="calib-cell{" thin" if cell_thin else ""}">'
            f'<div class="clabel" style="color:{color};">'
            f'<span class="cdot" style="background:{color};"></span>{sig}</div>'
            f'<div class="sc-verb">{verb}</div>'
            f'{val_html}'
            f'<div class="csub">{sub}</div>'
            f'{flag}'
            f'</div>'
        )
    return f'<div class="hair-grid calib-grid">{cells}</div>'
```

- [ ] **Step 4: Add the HOLD footnote builder and wire it**

Add below `_scorecard_html`:

```python
def _hold_footnote_html(hold_count: int) -> str:
    """HOLD's exclusion, stated as a footnote rather than a sixth tile.

    HOLD carries no directional claim, so a cell with an empty percentage would
    read as a *missing* measurement rather than an inapplicable one. Empty
    string when there is nothing to exclude.
    """
    if not hold_count:
        return ""
    return (f'<p class="sc-hold">Hold · {hold_count} ticker-days · '
            "not scored (non-directional)</p>")
```

In `render_signal_tracker_page`, replace the HOLD `st.caption` (lines 707–709) with:

```python
        hold_count = len(sig_df[sig_df["signal"] == "HOLD"])
        note = _hold_footnote_html(hold_count)
        if note:
            st.markdown(note, unsafe_allow_html=True)
```

- [ ] **Step 5: Replace the tile CSS**

In `assets/theme.css`, delete the old `.calib-grid` / `.calib-cell` rules (1941–1972), the responsive block at 2210–2213, and the later additions at 2217–2231. Add in their place (at the end of the file, after Task 1's device block):

```css
/* ── Hit-rate tiles: five peer measurements, read left to right ──
   Order inside a tile is fixed: identity → plain English → the number → its
   shape → its arithmetic → whether to trust it. */
.calib-grid { grid-template-columns: repeat(5, 1fr); margin: 14px 0 6px; }
.calib-cell { padding: 14px 16px 16px; }
.calib-cell .clabel {
  font-family: var(--font-display); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase;
  display: flex; align-items: center; gap: 7px;
}
.calib-cell .cdot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
/* Verdict-first: the tile says what the signal tells you to do before it
   reports how often it was right. min-height keeps one- and two-line meanings
   from pushing the five percentages onto different baselines — the whole point
   of a 5-across grid is that the numbers align. */
.calib-cell .sc-verb {
  font-size: 9.5px; line-height: 1.3; color: var(--color-text-3);
  min-height: 24px; margin-top: 6px;
}
.calib-cell .cval {
  font-family: var(--font-display); font-size: 38px; font-weight: 600;
  letter-spacing: -0.02em; line-height: 1; margin-top: 4px;
  color: var(--color-text); font-variant-numeric: tabular-nums;
}
.calib-cell .cval.muted { font-size: 18px; color: var(--color-text-4); }
/* Brass: calibration data, not a rating. Full cell width so bar lengths are
   directly comparable across the five cells. */
.calib-cell .cbar { height: 4px; background: var(--color-divider); margin-top: 10px; }
.calib-cell .cbar > i { display: block; height: 100%; background: var(--brass); }
.calib-cell .csub {
  font-size: 11px; color: var(--color-text-2); margin-top: 8px;
  font-variant-numeric: tabular-nums;
}
.calib-cell .sc-flag {
  font-family: var(--font-display); font-size: 9.5px; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--color-text-3); margin-top: 5px;
}
/* Sample adequacy by opacity, never colour: AVOID's 100% is the least
   trustworthy figure on the page, and ghosting is the only cue that does not
   fight the number's own prominence. */
.calib-cell.thin .cval, .calib-cell.thin .cbar { opacity: 0.42; }
.sc-hold {
  font-family: var(--font-display); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--color-text-3); margin: 10px 0 0;
}
@media (max-width: 900px) {
  .calib-grid { grid-template-columns: repeat(2, 1fr); }
  .calib-cell { padding: 12px 14px 14px; }
}
```

- [ ] **Step 6: Update the page-level smoke assertions**

In `tests/test_app_pages.py`, change both assertions (lines 98 and 103) from `'class="calib-grid"'` to `'class="hair-grid calib-grid"'`, and update the docstring at line 91 to name the new attribute value.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_signal_tracker.py tests/test_design_tokens.py tests/test_app_pages.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add components/signal_tracker.py assets/theme.css tests/test_signal_tracker.py tests/test_design_tokens.py tests/test_app_pages.py
git commit -F <message-file>
```

Message: `feat(tracker): hit-rate tiles ghost the samples you cannot lean on`

---

## Task 5: §4 Paper book — headline sentence and stats grid

**Files:**
- Modify: `components/paper_book.py:155-176` (`verdict_bits`), `:196-226` (`_verdict_html`, `_stats_html`), `:913-920` (section head)
- Modify: `assets/theme.css:2272-2276`
- Test: `tests/test_paper_book.py:74-96`, `:252-263`

**Interfaces:**
- Consumes: `.hair-grid`, `.stat-tick`, `render_section_head(masthead=True)` from Task 1.
- Produces: `verdict_bits(block) -> tuple[str, str]` with tone ∈ {`"pos"`, `"neg"`, `""`} (unchanged signature, new copy); `_verdict_html` emits `.pb-verdict` with `.pb-val` / `.pb-ret` spans; `_stats_html` emits `<div class="hair-grid pb-stats">`.

- [ ] **Step 1: Write the failing tests**

Replace `test_verdict_trailing` / `test_verdict_leading` in `tests/test_paper_book.py` and append the rest:

```python
def test_verdict_trailing():
    text, tone = verdict_bits({"nav_return_pct": 4.2, "spy_return_pct": 6.1,
                               "inception": "2026-04-19"})
    assert "+4.2%" in text and "+6.1%" in text
    # Humanised inception: the section head already says "paper book", so the
    # sentence spends its words on the reading, not on ISO punctuation.
    assert "19 Apr 2026" in text
    assert "$100,000" in text and "$104,200" in text and "$106,100" in text
    assert "against SPY at" in text
    assert not text.startswith("Paper book:")
    assert "trailing" in text
    assert tone == "neg"


def test_verdict_leading():
    text, tone = verdict_bits({"nav_return_pct": 8.0, "spy_return_pct": 6.1})
    assert "leading" in text
    assert tone == "pos"


def test_verdict_html_trailing_clause_is_terracotta_not_caution_red():
    """A stress reading on the book's own performance — not a signal on any
    stock, so it must not borrow the CAUTION hue."""
    html = _verdict_html({"nav_return_pct": 4.2, "spy_return_pct": 6.1,
                          "inception": "2026-04-19"})
    assert "var(--stress)" in html
    assert STATUS_NEG not in html


def test_verdict_html_returns_carry_market_direction():
    html = _verdict_html({"nav_return_pct": 8.0, "spy_return_pct": 6.1})
    assert "var(--up)" in html


def test_stats_are_neutral_inputs_not_verdicts():
    """Cash / positions / entries / add-ons / stop-outs are counts. Colouring
    them would imply 15 stop-outs is 'bad'."""
    html = _stats_html({"cash_pct": 42.0, "n_positions": 7,
                        "trade_counts": {"buy_signal": 5, "accumulate_tranche": 3,
                                         "stop": 15}})
    assert 'class="hair-grid pb-stats"' in html
    assert html.count('class="stat-tick"') == 5
    for token in ("var(--up)", "var(--down)", "var(--stress)", "var(--brass)"):
        assert token not in html
```

Add `from components.paper_book import _stats_html, _verdict_html` and `from lib.charts import STATUS_NEG` to the imports if absent.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_paper_book.py -q`
Expected: FAIL — the sentence still reads `Paper book: … vs SPY (the S&P 500) → …` with the ISO date, and `_stats_html` still emits `.pb-stat` chips.

- [ ] **Step 3: Rewrite the headline sentence**

Replace `verdict_bits` (155–176) in `components/paper_book.py`:

```python
def _human_date(value: str | None) -> str:
    """'2026-04-19' → '19 Apr 2026'; anything unparseable passes through."""
    if not value:
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return f"{parsed.day} {parsed.strftime('%b')} {parsed.year}"


def verdict_bits(block: dict) -> tuple[str, str]:
    """(verdict sentence, tone) for the band's lead line.

    A full sentence, not a stat row, and verdict-first: the conclusion is the
    last clause. Tone ∈ {"pos", "neg", ""} colours that clause. A block whose
    returns are still ``None`` (seed day / no matured session) reads "seeded",
    mirroring the upstream Telegram glance line.
    """
    nav = block.get("nav_return_pct")
    spy = block.get("spy_return_pct")
    since = f" since {_human_date(block['inception'])}" if block.get("inception") else ""
    if nav is None or spy is None:
        return (f"Paper book seeded{since} — first fills pending.", "")
    nav_usd = _money(NOTIONAL_START * (1 + nav / 100.0))
    spy_usd = _money(NOTIONAL_START * (1 + spy / 100.0))
    body = (f"{_money(NOTIONAL_START)} → {nav_usd} ({nav:+.1f}%){since}, "
            f"against SPY at {spy_usd} ({spy:+.1f}%)")
    if nav > spy:
        return (f"{body} — leading the benchmark.", "pos")
    if nav < spy:
        return (f"{body} — trailing the benchmark.", "neg")
    return (f"{body} — tracking the benchmark.", "")
```

- [ ] **Step 4: Colour the sentence by role**

Replace `_verdict_html` (196–205):

```python
# The verdict clause by branch. "Trailing" is a trust limitation on the book's
# own performance → terracotta, never the CAUTION hue; "leading" is the same
# market-direction system the two returns use; "tracking" makes no reading.
_VERDICT_CLAUSE_COLOR = {"pos": "var(--up)", "neg": "var(--stress)"}


def _verdict_html(block: dict) -> str:
    """Band lead line — a full sentence, plain-English verdict last."""
    text, tone = verdict_bits(block)
    head, sep, tail = text.partition(" — ")
    head = _escape_dollars(head)
    # _escape_dollars turns "$" into "&#36;", so match on the escaped form.
    head = re.sub(r"&#36;[\d,]+", lambda m: f'<span class="pb-val">{m.group(0)}</span>', head)
    head = re.sub(r"\(([-+]\d+\.\d)%\)",
                  lambda m: '<span class="pb-ret" style="color:'
                            + ("var(--up)" if m.group(1).startswith("+") else "var(--down)")
                            + f'">({m.group(1)}%)</span>', head)
    tail_html = ""
    if sep:
        color = _VERDICT_CLAUSE_COLOR.get(tone)
        style = f' style="color:{color};"' if color else ""
        tail_html = f'<span class="pb-clause"{style}> — {_escape_dollars(tail)}</span>'
    return f'<p class="pb-verdict">{head}{tail_html}</p>'
```

Add `import re` to the module imports.

- [ ] **Step 5: Rebuild the stats as a hairline grid**

Replace the body-building lines of `_stats_html` (221–226):

```python
    body = "".join(
        f'<div class="stat-tick"><b>{_escape_dollars(v)}</b>'
        f"<span>{label}</span></div>"
        for v, label in chips
    )
    # Column count follows the chips: 5 on today's data, up to 7 when the
    # AVOID/delist exit reasons are present.
    return (f'<div class="hair-grid pb-stats" '
            f'style="grid-template-columns:repeat({len(chips)},1fr);">{body}</div>')
```

- [ ] **Step 6: Give the section head the masthead rule**

In `render_paper_book`, add `masthead=True` to the `render_section_head(...)` call at 913–917.

- [ ] **Step 7: Restyle `.pb-verdict` / `.pb-stats`**

In `assets/theme.css`, replace `.pb-verdict`, `.pb-stats`, `.pb-stat b` and `.pb-stat span` (2272–2276) with:

```css
/* A full sentence, not a stat row: the conclusion is the last clause and the
   only coloured words. */
.pb-verdict {
  font-family: var(--font-display); font-size: 20px; line-height: 1.45;
  color: var(--color-text); margin: 14px 0 12px; max-width: 88ch;
}
.pb-verdict .pb-val,
.pb-verdict .pb-ret { font-weight: 600; font-variant-numeric: tabular-nums; }
.pb-verdict .pb-clause { font-weight: 600; }
/* Inputs, not verdicts — all neutral. Colouring a count would imply 15
   stop-outs is "bad" when it is just how many there were. */
.pb-stats { margin: 0 0 16px; }
.pb-stats .stat-tick { padding: 12px 14px 14px; border-left-width: 2px; }
@media (max-width: 900px) {
  .pb-stats { grid-template-columns: repeat(2, 1fr) !important; }
}
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python -m pytest tests/test_paper_book.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add components/paper_book.py assets/theme.css tests/test_paper_book.py
git commit -F <message-file>
```

Message: `feat(paper-book): the headline is a sentence, the stats are counts`

---

## Task 6: §4 Paper book — chart chrome

**Files:**
- Modify: `components/paper_book.py:805-806` (`_ADVISORY_COLORS`), `:837-858` (`_nav_fig`), `:921-930` (chart render block)
- Modify: `assets/theme.css:197` (`.blueprint > .corner` → `.corner`), end of file (chart-card block)
- Test: `tests/test_paper_book.py`

**Interfaces:**
- Consumes: `.corner` marks from `lib/cards.py`'s blueprint grammar, `.tracker-page` scope from Task 3.
- Produces: `_legend_swatch(color: str, width: float, dash: bool) -> str`; `_chart_head_html(rebased: pd.DataFrame, advisory: pd.DataFrame | None) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_paper_book.py`:

```python
# ── Redesign (spec 2026-07-25 §6.3): chart chrome ──
from components.paper_book import _chart_head_html, _legend_swatch


def test_legend_swatch_is_a_real_line_sample():
    """Legend and plot must use identical encoding, so the swatch is the series'
    actual width and dash pattern — not a colour square."""
    solid = _legend_swatch("var(--brass)", 2.4, dash=False)
    dashed = _legend_swatch(CHART_MUTED, 1.4, dash=True)
    assert "<svg" in solid and "stroke-width=\"2.4\"" in solid
    assert "stroke-dasharray" in dashed
    assert "stroke-dasharray" not in solid
    assert "non-scaling-stroke" in solid


def test_chart_head_carries_the_axis_eyebrow_and_a_legend_entry_per_series():
    rebased = pd.DataFrame({"date": pd.to_datetime(["2026-04-19", "2026-04-20"]),
                            "Paper book": [100000.0, 99710.0],
                            "SPY": [100000.0, 104430.0]})
    html = _chart_head_html(rebased, None)
    assert "pb-chart-head" in html
    assert html.count("<svg") == 2
    assert "Paper book" in html and "SPY" in html
    assert "value of" in html.lower()          # the axis description
    assert html.count('class="corner') == 4    # blueprint registration marks


def test_nav_fig_hides_plotly_legend_and_ranks_series_by_weight():
    """Hierarchy by weight, not just hue: the subject is heaviest, the benchmark
    thinner, the hypothetical replays thinnest and dashed."""
    rebased = pd.DataFrame({"date": pd.to_datetime(["2026-04-19", "2026-04-20"]),
                            "Paper book": [100000.0, 99710.0],
                            "SPY": [100000.0, 104430.0]})
    fig = _nav_fig(rebased, None)
    assert fig.layout.showlegend is False
    widths = {tr.name: tr.line.width for tr in fig.data}
    assert widths["Paper book"] == 2.4
    assert widths["SPY"] == 1.6


def test_advisory_lanes_are_neutral_and_brass_not_two_more_categories():
    """Two arbitrary palette hues read as two more categories; neutral plus a
    brass tint reads as 'variants of the subject and the benchmark'. The tint is
    NOT the subject's own brass — the replay must not look like the book."""
    from components.paper_book import _ADVISORY_COLORS
    assert set(_ADVISORY_COLORS.values()) == {CHART_MUTED, CHART_ACCENT_SOFT}
    assert CHART_ACCENT not in _ADVISORY_COLORS.values()
```

Add `from lib.charts import CHART_ACCENT, CHART_ACCENT_SOFT, CHART_MUTED` to the test imports if absent.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_paper_book.py -q`
Expected: FAIL — `ImportError: cannot import name '_chart_head_html'`.

- [ ] **Step 3: Re-assign the advisory lane colours**

Add the brass tint to `lib/charts.py`, beside `CHART_ACCENT` (line 29):

```python
CHART_ACCENT_SOFT = "#9C8355"  # dimmed brass — hypothetical replays of the brass subject
```

Replace `components/paper_book.py:805-806`:

```python
# One neutral, one brass-tinted — variants of the subject and the benchmark,
# not two more categories. Two arbitrary palette hues (the old sage / dusty
# mauve) read as new series with their own meaning. The tint is dimmed, not
# CHART_ACCENT itself: a replay must never be mistaken for the book.
_ADVISORY_COLORS = {"ext-exit 10/5": CHART_MUTED,
                    "ext-exit 30/15": CHART_ACCENT_SOFT}
```

Update the `lib.charts` import list in the module to include `CHART_MUTED` and `CHART_ACCENT_SOFT`.

- [ ] **Step 4: Add the legend and header builders**

Add above `_nav_fig` in `components/paper_book.py`:

```python
# Series widths — hierarchy by weight, not just hue. A reader who knows nothing
# can still tell which line is the point.
_W_SUBJECT, _W_BENCH, _W_REPLAY = 2.4, 1.6, 1.4


def _legend_swatch(color: str, width: float, dash: bool) -> str:
    """An 18px rule at the series' real width and dash pattern.

    Actual line samples rather than colour squares, so the legend and the plot
    use identical encoding — the dashes say "hypothetical" before the caption
    is read.
    """
    dash_attr = ' stroke-dasharray="4 3"' if dash else ""
    return (
        '<svg class="pb-swatch" viewBox="0 0 18 6" width="18" height="6" '
        'aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" '
        f'stroke="{color}" stroke-width="{width}"{dash_attr} '
        'vector-effect="non-scaling-stroke"/></svg>'
    )


def _chart_head_html(rebased: pd.DataFrame,
                     advisory: pd.DataFrame | None) -> str:
    """Header row for the chart card: steel axis eyebrow left, legend right.

    Also carries the four blueprint registration marks, which position against
    the bordered container the chart sits in.
    """
    entries = []
    for name in [c for c in rebased.columns if c != "date" and c in _CHART_SERIES]:
        width = _W_SUBJECT if name == "Paper book" else _W_BENCH
        color = _SERIES_COLORS.get(name, CHART_LINE)
        entries.append((name, color, width, False))
    if advisory is not None and not advisory.empty:
        for name in [c for c in advisory.columns if c != "date"]:
            entries.append((name, _ADVISORY_COLORS.get(name, CHART_LINE),
                            _W_REPLAY, True))
    legend = "".join(
        f'<span class="pb-legend-item">{_legend_swatch(color, width, dash)}'
        f"{_escape_dollars(name)}</span>"
        for name, color, width, dash in entries
    )
    axis = _escape_dollars(f"Value of {_money(NOTIONAL_START)} invested at start")
    return (
        '<i class="corner tl"></i><i class="corner tr"></i>'
        '<i class="corner bl"></i><i class="corner br"></i>'
        '<div class="pb-chart-head">'
        f'<span class="eyebrow">{axis}</span>'
        f'<span class="pb-legend">{legend}</span>'
        "</div>"
    )
```

`_escape_dollars` is required on the axis line: a raw `$` in injected markdown is read as a LaTeX delimiter.

- [ ] **Step 5: Restyle the figure itself**

Replace `_nav_fig` (837–858):

```python
def _nav_fig(rebased: pd.DataFrame, advisory: pd.DataFrame | None = None):
    """The NAV plot as a line drawing: no axis box, no filled plot area, no
    Plotly legend (the header row above carries it, with real line samples)."""
    fig = go.Figure()
    for name in [c for c in rebased.columns
                 if c != "date" and c in _CHART_SERIES]:
        fig.add_scatter(
            x=rebased["date"], y=rebased[name], mode="lines", name=name,
            line=dict(color=_SERIES_COLORS.get(name, CHART_LINE),
                      width=_W_SUBJECT if name == "Paper book" else _W_BENCH),
        )
    if advisory is not None and not advisory.empty:
        for name in [c for c in advisory.columns if c != "date"]:
            fig.add_scatter(
                x=advisory["date"], y=advisory[name], mode="lines", name=name,
                line=dict(color=_ADVISORY_COLORS.get(name, CHART_LINE),
                          width=_W_REPLAY, dash="dash"),
            )
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=6, b=0),
                      showlegend=False)
    fig.update_xaxes(showline=False, zeroline=False)
    fig.update_yaxes(showline=False, zeroline=False, title=None)
    return style_fig(fig)
```

- [ ] **Step 6: Wrap the chart in the bordered container**

Replace the chart block in `render_paper_book` (921–930):

```python
    if not rebased.empty:
        # st.container(border=True) is the only wrapper a Plotly element can sit
        # inside; the tracker-scoped CSS turns it into the blueprint frame, and
        # the injected corner marks position against it.
        with st.container(border=True):
            st.markdown(_chart_head_html(rebased, advisory),
                        unsafe_allow_html=True)
            st.plotly_chart(_nav_fig(rebased, advisory),
                            use_container_width=True, config=PLOTLY_CONFIG)
        note = _soxx_note_html(rebased) + _advisory_note_html(advisory)
        if note:
            st.markdown(note, unsafe_allow_html=True)
        table = rebased
        if not advisory.empty:
            table = rebased.merge(advisory, on="date", how="left")
        chart_data_table(table)
```

Note: `rebased_fig :=` is only there to keep the call on one expression; if the linter objects, assign on the previous line instead.

- [ ] **Step 7: Free the corner marks from the `.blueprint` parent**

In `assets/theme.css`, change the four selectors at 197–216 from `.blueprint > .corner…` to `.corner…` (`.corner`, `.corner::before`, `.corner::after`, `.corner.tl` … `.corner.br`). `.corner` is only ever emitted by `card_container` and by `_chart_head_html`, so this widens nothing in practice and lets the marks position against the chart container.

Then append the chart-card block at the end of the file:

```css
/* ── Paper-book chart card ──
   The chart is a line drawing like everything else: a hairline frame, a header
   row, and a rule between the header and the plot. */
.stApp:has(.tracker-page) [data-testid="stVerticalBlockBorderWrapper"] {
  position: relative; border: 1px solid var(--color-divider);
  border-radius: 0; background: transparent;
}
.pb-chart-head {
  display: flex; justify-content: space-between; align-items: baseline;
  flex-wrap: wrap; gap: 10px;
  border-bottom: 1px solid var(--color-divider); padding-bottom: 8px;
}
.pb-legend { display: flex; flex-wrap: wrap; gap: 14px; }
.pb-legend-item {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-display); font-size: 10px; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--color-text-3);
}
.pb-swatch { flex: none; }
/* Both captions sit below the plot; terracotta marks a trust limitation, brass
   a measurement — never a rating in either case. */
.pb-chartnote { font-size: 12.5px; line-height: 1.5; color: var(--color-text-2);
                opacity: 0.66; margin: 8px 0 0; max-width: 96ch; }
.pb-chartnote .lim { color: var(--stress); }
.pb-chartnote .val { color: var(--brass); font-variant-numeric: tabular-nums; }
```

- [ ] **Step 8: Mark up the two caption lines**

In `_soxx_note_html`, wrap the figure: `f'<span class="val">{ret:+.1f}%</span>'`. In `_advisory_note_html`, wrap the caveat: `'<span class="lim">hypothesis-grade, one regime</span>'`.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `python -m pytest tests/test_paper_book.py -q`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add components/paper_book.py assets/theme.css tests/test_paper_book.py
git commit -F <message-file>
```

Message: `feat(paper-book): the NAV chart reads as a line drawing`

---

## Task 7: §4 Paper book — stop-rule lanes

**Files:**
- Modify: `components/paper_book.py:243-281` (`_variants_html`), `:229-234` (`_banner_html`)
- Modify: `assets/theme.css:2277-2283`
- Test: `tests/test_paper_book.py:111-160`

**Interfaces:**
- Consumes: `.hair-grid` + `[data-flag]` rail from Task 1.
- Produces: `_variants_html(block) -> str` emitting `<div class="hair-grid pb-lanes">` with one `.pb-lane` per lane; the headline lane carries `data-flag="1"`.

- [ ] **Step 1: Write the failing tests**

Replace the `_variants_html` tests in `tests/test_paper_book.py` (111–160) with:

```python
def test_lane_grid_renders_one_cell_per_lane():
    html = _variants_html({"variants": _VARIANTS, "nav_return_pct": 3.5,
                           "policy_id": "v1_flat10",
                           "trade_counts": {"stop": 15}})
    assert 'class="hair-grid pb-lanes"' in html
    assert html.count('class="pb-lane"') == 4      # three variants + headline
    assert "trail" in html and "+1.1%" in html and "18 stop-outs" in html
    assert "v1_wide10" not in html                 # labeled, not raw policy_id
    assert "verdict" not in html.lower()           # framing lives in the banner


def test_headline_lane_carries_the_steel_rail_and_says_so():
    """Without the flag a reader cannot tell which of five numbers is the real
    book — and +8.3% on the wide lane would look like the headline result."""
    html = _variants_html({"variants": _VARIANTS, "nav_return_pct": 3.5,
                           "policy_id": "v1_flat10",
                           "trade_counts": {"stop": 15}})
    assert 'data-flag="1"' in html
    assert html.count('data-flag="1"') == 1
    assert "· headline" in html


def test_lane_returns_are_brass_and_counts_neutral():
    html = _variants_html({"variants": _VARIANTS})
    assert 'class="pb-lane-ret"' in html
    assert 'class="pb-lane-stops"' in html
    assert STATUS_POS not in html and STATUS_NEG not in html


def test_variants_html_skips_malformed_and_escapes_unknown_ids():
    html = _variants_html({"variants": [
        "not-a-dict", {}, {"policy_id": "v1_x", "nav_return_pct": None},
        {"policy_id": "<script>", "nav_return_pct": 1.0},
    ]})
    assert "not-a-dict" not in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_variants_html_empty():
    assert _variants_html({}) == ""
    assert _variants_html(None) == ""


def test_variants_html_headline_alone_renders_nothing():
    """The band's lead number already carries the headline lane."""
    assert _variants_html({"nav_return_pct": 3.5, "policy_id": "v1_flat10"}) == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_paper_book.py -q`
Expected: FAIL — `_variants_html` still emits a single `.pb-variants` paragraph.

- [ ] **Step 3: Rebuild `_variants_html` as a cell grid**

Replace the body of `_variants_html` from `parts = []` to the return:

```python
    lanes = []
    for v in block.get("variants") or []:
        if not isinstance(v, dict) or not v.get("policy_id"):
            continue
        nav = v.get("nav_return_pct")
        if not isinstance(nav, (int, float)):
            continue
        label = (_LANE_LABELS.get(v["policy_id"])
                 or _escape_dollars(str(v["policy_id"])))
        lanes.append((label, nav, v.get("stops"), False))
    if not lanes:
        return ""
    head_nav = block.get("nav_return_pct")
    if isinstance(head_nav, (int, float)):
        label = (_LANE_LABELS.get(block.get("policy_id"))
                 or _escape_dollars(str(block.get("policy_id") or "book")))
        stops = (block.get("trade_counts") or {}).get("stop")
        lanes.insert(0, (label, head_nav, stops, True))

    cells = ""
    for label, nav, stops, is_head in lanes:
        stop_txt = (f'<span class="pb-lane-stops">{int(stops)} stop-outs</span>'
                    if isinstance(stops, (int, float)) else "")
        # Steel rail + the word: without it the reader cannot tell which of
        # these numbers is the real book. Never a ranking — the exported banner
        # below carries the caveat.
        flag = ' data-flag="1"' if is_head else ""
        suffix = ' <span class="pb-lane-head">· headline</span>' if is_head else ""
        cells += (
            f'<div class="pb-lane"{flag}>'
            f'<div class="pb-lane-label">{label}{suffix}</div>'
            f'<div class="pb-lane-ret">{nav:+.1f}%</div>'
            f"{stop_txt}</div>"
        )
    return (
        '<p class="pb-lane-eyebrow">Stop-rule lanes — same book, only the stop '
        "rule differs</p>"
        f'<div class="hair-grid pb-lanes" '
        f'style="grid-template-columns:repeat({len(lanes)},1fr);">{cells}</div>'
    )
```

- [ ] **Step 4: Style the lanes**

In `assets/theme.css`, replace `.pb-variants` and `.pb-variants b` (2281–2283) with:

```css
/* border-top: 0 so the grid butts directly against its own eyebrow rule — the
   label and the grid read as one object. */
.pb-lane-eyebrow {
  font-family: var(--font-display); font-size: 9.5px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--eyebrow);
  border-bottom: 1px solid var(--color-divider);
  padding-bottom: 6px; margin: 18px 0 0;
}
.pb-lanes { border-top: 0; }
.pb-lane { padding: 12px 14px 14px; }
.pb-lane-label {
  font-family: var(--font-display); font-size: 10px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--color-text-3);
}
.pb-lane-head { color: var(--accent); }
/* Measurements → brass; the stop-out count is an input → neutral. */
.pb-lane-ret {
  font-family: var(--font-display); font-size: 22px; font-weight: 600;
  color: var(--brass); font-variant-numeric: tabular-nums; margin-top: 6px;
}
.pb-lane-stops {
  display: block; font-size: 11px; color: var(--color-text-3); margin-top: 4px;
  font-variant-numeric: tabular-nums;
}
/* The only italic on the page — which is exactly why it is noticeable. */
.pb-banner { font-size: 12px; font-style: italic; color: var(--color-text-3);
             line-height: 1.5; margin: 10px 0 0; max-width: 96ch; }
@media (max-width: 900px) {
  .pb-lanes { grid-template-columns: repeat(2, 1fr) !important; }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_paper_book.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add components/paper_book.py assets/theme.css tests/test_paper_book.py
git commit -F <message-file>
```

Message: `feat(paper-book): stop-rule lanes flag which one is the real book`

---

## Task 8: §5 What we've changed — the date spine

**Files:**
- Modify: `components/signal_tracker.py:415-436` (`_changelog_strip_html`), `:723-734` (section head)
- Modify: `assets/theme.css:2233-2250` (`.chg-*` block)
- Test: `tests/test_signal_tracker.py:212-238`

**Interfaces:**
- Consumes: `.spine` from Task 1, `render_section_head(masthead=True)`.
- Produces: `_changelog_strip_html(entries) -> str` emitting `<div class="spine chg-log">`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_signal_tracker.py`:

```python
def test_changelog_is_a_date_spine_not_a_stack_of_cards():
    """A changelog is a list of records; framing each entry would make five
    paragraphs look like five products."""
    html = _changelog_strip_html([
        {"date": "2026-07-04", "title": "Honest flags", "note": "small-sample"},
        {"date": "2026-07-02", "title": "Older", "note": "note"},
    ])
    assert 'class="spine chg-log"' in html
    assert "blueprint" not in html and "card" not in html
    assert html.count('class="chg-item"') == 2


def test_changelog_entries_stay_plain_prose():
    """These entries describe the colour rules; demonstrating them inside the
    description would be noisy."""
    html = _changelog_strip_html(
        [{"date": "2026-07-04", "title": "Brass bars",
          "note": "brass rather than grey, deliberately not the signal palette"}]
    )
    assert "<b>" not in html
    assert "var(--brass)" not in html and "var(--stress)" not in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_signal_tracker.py -q`
Expected: FAIL — the wrapper is `class="chg-log"` without `spine`.

- [ ] **Step 3: Emit the spine wrapper**

In `components/signal_tracker.py::_changelog_strip_html`, change the return to:

```python
    return f'<div class="spine chg-log">{items}</div>' if items else ""
```

- [ ] **Step 4: Give the section head the masthead rule**

Replace the changelog section head block (723–734) with:

```python
    changelog = load_changelog()
    strip = _changelog_strip_html(changelog)
    if strip:
        render_section_head("What we've changed", _changelog_sub(changelog),
                            masthead=True)
        st.markdown(strip, unsafe_allow_html=True)
```

- [ ] **Step 5: Restyle the `.chg-*` block**

In `assets/theme.css`, replace `.chg-log`, `.chg-item`, `.chg-date` and the responsive rule (2233–2250) with:

```css
/* Layout comes from .spine (112px | 1fr). The tick is --color-divider, not
   accent: every entry is a peer, so the ticks give rhythm without hierarchy. */
.chg-log { margin-top: 4px; }
.chg-date {
  font-family: var(--font-display); font-size: 11px; letter-spacing: 0.06em;
  color: var(--color-text-3); border-left: 2px solid var(--color-divider);
  padding-left: 10px; font-variant-numeric: tabular-nums;
}
.chg-body { display: block; }
.chg-title {
  display: block; font-family: var(--font-display); font-size: 15px;
  font-weight: 600; color: var(--color-text); margin-bottom: 4px;
}
/* The only long-form prose on the site — a tighter measure and generous
   leading, set for genuine paragraph reading. */
.chg-note {
  display: block; font-size: 13px; line-height: 1.6;
  color: var(--color-text-2); opacity: 0.7; max-width: 96ch;
}
@media (max-width: 900px) {
  .spine > * { grid-template-columns: 1fr; gap: 6px; }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_signal_tracker.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add components/signal_tracker.py assets/theme.css tests/test_signal_tracker.py
git commit -F <message-file>
```

Message: `feat(tracker): the change log reads down a date spine`

---

## Task 9: Close-out — changelog entry, full suite, visual baselines

**Files:**
- Modify: `data/changelog.json`
- Modify: `tests/visual/baselines/signal-tracker.png`, `tests/visual/baselines/signal-tracker-ledger.png` (regenerated)

**Interfaces:**
- Consumes: everything from Tasks 1–8.
- Produces: nothing downstream.

- [ ] **Step 1: Add the reader-facing changelog entry**

`data/changelog.json` is a flat array of `{"date", "title", "note"}`, newest first, and already carries a `2026-07-25` entry (the macro-prints trend). Insert this **above** it — same date, and the strip shows the ten newest:

```json
  {
    "date": "2026-07-25",
    "title": "The Signal Tracker now shows how much to trust each number",
    "note": "The Signal Tracker has been rebuilt around one rule: a colour means only one thing. Hit rates, alpha figures and the stop-rule lane returns are now brass, because they are measurements of how the signals did - not ratings of them; the signal colours stay on the signal pills alone. Where a hit rate rests on too few calls to lean on, the number and its bar now visibly fade and the warning beside them turns terracotta, so a tidy-looking 100% off three calls can no longer read as confidently as a rate built on fifty. The five signals sit in one row so their rates compare at a glance, each with a plain-English line saying what the signal actually tells you to do. HOLD is stated as a footnote rather than an empty sixth cell, because it makes no directional claim to score. In the paper book, the headline is now a sentence you can read straight through, and the five stop-rule lanes are laid out side by side with the real book flagged - previously the best-looking lane could be mistaken for the headline result. Nothing was removed and no figure changed."
  },
```

Plain prose, no markup: the spine renders entries unstyled by design (the entries describe the colour rules, and demonstrating them inside the description would be noisy).

- [ ] **Step 2: Run the full non-visual suite**

Run: `python -m pytest tests/ -q --ignore=tests/visual`
Expected: PASS, no warnings about unused imports (`STATUS_POS`/`STATUS_NEG` may now be unused in `components/signal_tracker.py` — remove them from the import if so).

- [ ] **Step 3: Lint**

Run: `python -m ruff check .`
Expected: clean. Sort any import blocks ruff flags.

- [ ] **Step 4: Compare against the current baselines to see the intended diff**

Run (PowerShell, single line):

```
docker run --rm -v "${PWD}:/work" -w /work mcr.microsoft.com/playwright/python:v1.60.0-jammy bash -lc "pip install -q -r requirements.lock playwright==1.60.0 pytest-playwright pixelmatch pillow && python -m playwright install chromium && python -m pytest tests/visual -q"
```

Expected: FAIL on `signal-tracker` and `signal-tracker-ledger` (intended redesign), PASS on every other page — a failure anywhere else means the shared devices leaked off this page.

- [ ] **Step 5: Regenerate the baselines**

Run the same command with `VISUAL_UPDATE=1 python -m pytest tests/visual -q` as the final segment. Regen only rewrites baselines the capture no longer matches.

- [ ] **Step 6: Verify the regenerated run is clean**

Run the Step 4 command again.
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add data/changelog.json tests/visual/baselines
git commit -F <message-file>
```

Message: `test(visual): update baselines for the Signal Tracker redesign`

---

## Verification checklist

Run before declaring the branch done:

- [ ] `python -m pytest tests/ -q --ignore=tests/visual` passes
- [ ] `python -m pytest tests/visual -q` (in the pinned image) passes
- [ ] `python -m ruff check .` clean
- [ ] `grep -n "f59e0b\|STATUS_WARN" components/signal_tracker.py components/paper_book.py components/briefing/calibration.py` returns nothing
- [ ] The app renders: restart Streamlit (page modules are lazily imported and cached, so an edit will not show otherwise) and load the Signal Tracker page in both themes
