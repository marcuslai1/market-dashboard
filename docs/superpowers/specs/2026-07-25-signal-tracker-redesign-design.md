# Signal Tracker redesign — design spec

**Date:** 2026-07-25
**Scope:** the Signal Tracker page (`dashboard.py::_page_signal_tracker`) — `components/signal_tracker.py`, `components/paper_book.py`, `components/trim_experiment.py`, `components/briefing/calibration.py`, `lib/cards.py`, `assets/theme.css`.
**Source:** the owner's full design account of the page (2026-07-25), reproduced in intent below. Where the account and the shipped code disagree, the account wins unless this spec says otherwise and gives the reason.

---

## 1. What the page is for

This is the **study page** — the opposite of the Briefing's two-minute glance. Readers come here to interrogate whether the signals can be trusted, so the page is a **descending trust argument**, read in sequence:

1. **Signal calibration** — how today's signals have actually performed.
2. **Signal tracker** — is the record big enough to trust? (trust meter, then the per-signal hit rates)
3. **Paper book** — what a rule-following portfolio actually did with them.
4. **What we've changed** — the methodology ledger.

Each section answers the doubt the previous one raises. It stays a single-column scroll; no two-column glance layout.

This ordering is what ships today (`dashboard.py:396-416`), so the redesign changes **construction and colour discipline, not information architecture**. No block is cut.

---

## 2. The colour discipline (load-bearing)

Every colour on the page is assigned by role. Roles never overlap. This is the rule the rest of the spec exists to enforce.

| Role | Token | Used for |
| --- | --- | --- |
| Signal rating | signal palette (`--caution`, `SIGNAL_COLORS`) | the CAUTION pill in §1, the five tile dots + names |
| Measurement / data | `--brass` | α figures, hit-rate bars, stop-lane returns, SOXX, the book's NAV line |
| Trust limitation | `--stress` (terracotta) | thin-sample warnings, "trailing the benchmark", "hypothesis-grade" |
| Structure / flagging | `--accent` / `--eyebrow` (steel) | eyebrows, the decision-grade chip, stat ticks, the headline-lane rail, drawer summaries |
| Market direction | `--up` / `--down` | the two returns in the paper-book headline sentence |
| Everything else | `--color-text-2/3/4` | labels, counts, captions, metadata |

Two consequences are corrections to shipped code, not new opinions:

- **Amber is WATCH.** `theme.css:2224` currently paints the thin-sample warning `#f59e0b`, which is the WATCH signal hue. A data-quality warning is not a signal → it moves to `--stress`. Same reasoning retires `.rd-meter.warn`'s amber left border.
- **A hit rate is a measurement, not a verdict.** `_scorecard_html` currently colours its bars green/red via `_rate_color()`. Bars become `--brass`. `_rate_color()` itself stays — `_winbar_html` (by-name ledger) still uses it, where higher genuinely is better and the reading *is* an outcome.

---

## 3. Foundation — shared devices

The account's argument is that repeated devices teach the reader a grammar ("a grid of cells always means peer measurements, compare across"). So the shared devices are extracted first, then consumed by each section.

### 3.1 `.hair-grid` — the hairline cell grid

Promote the construction already proven at `.fp-grid` (theme.css:1202) into a named class:

```css
.hair-grid {
  display: grid; gap: 1px;
  background: var(--color-divider);
  border: 1px solid var(--color-divider);
}
.hair-grid > * {
  background: var(--color-bg); min-width: 0;
  border-top: 2px solid transparent;   /* flag rail declared, not omitted */
}
```

The transparent top rail is why flagged and unflagged cells keep identical height. `.fp-grid` / `.fp-cell` become users of it (their `[data-key]` steel rail is the same device the stop-rule lanes need). Column count is the only per-consumer difference.

Consumers: FRED prints (existing), hit-rate tiles (§5), paper-book stats (§6.2), stop-rule lanes (§6.4).

### 3.2 `.stat-tick` — a discrete figure

26px value over a 9.5px uppercase muted label, value first (the site-wide value-over-label order), with a **2px** `--accent` left tick. Deliberately 2px, not the 3px used for signal rails on watchlist rows and clusters — its only job is "this is a discrete figure", and it must not be confused with signal-rail language.

### 3.3 Drawer grammar

Streamlit renders `st.expander` as a real `<details>/<summary>` (`data-testid="stExpander"`). So drawers are unified **in CSS only** — no conversion to raw HTML, which matters because "Signal changes" holds an `st.dataframe` that cannot live inside a markdown-injected `<details>`.

Hairline border, square corners, steel uppercase summary, caret rotating on `[open]`. Applied to the tracker page's drawers: paper-book positions/trades, extension lanes, trim experiment, by-name ledger, signal changes, and the chart data table.

### 3.4 `.spine` — the date ledger

`112px | 1fr` grid; date column left with a 2px `--color-divider` left tick, title + body right, 1px hairline between entries. Faint tick, not accent: every changelog entry is a peer, none is flagged.

### 3.5 Masthead section heads

The account specifies the four section heads as h2 30px/600 with a right-aligned 10px uppercase muted descriptor over a **2px solid `--color-text`** rule — the masthead weight, used four times to say "four peer documents stacked".

`.section-head` is site-wide (1px `--rule`, h2 1.4rem), so this must not change globally. `render_section_head()` gains an optional `masthead: bool = False` that emits `<div class="section-head masthead">`; the tracker's four heads pass it.

```css
.section-head.masthead { border-bottom: 2px solid var(--color-text); }
.section-head.masthead h2 { font-size: 1.875rem !important; font-weight: 600; }
```

### 3.6 Token hygiene

New and edited blocks use the `--color-*` / `--font-display` overhaul layer. The tracker's older CSS still uses the legacy `--ink` / `--serif` / `--rule` aliases; blocks touched by this work convert, blocks not touched are left alone (no unrelated refactor).

---

## 4. §1 Signal calibration — `components/briefing/calibration.py`

A single horizontal row, **not a card** — it is one sentence of state, so it gets no frame. It stays the `<summary>` of the existing `<details>`; the body survives (decision below).

| Element | Treatment | Why |
| --- | --- | --- |
| CAUTION pill | unchanged full signal treatment (tinted bg + rail text + dot) | this genuinely *is* a signal rating — the one place red belongs |
| "most common today (21 names)" | body text at 80%; the count in `.cal-count` at `--color-text-4` | parenthetical detail recedes without needing its own line |
| "−2.8% α / 10d" | `.cal-alpha` → `--brass`, weight 600, tabular | α is a *measurement* of the signal's performance. Red would read as a second CAUTION verdict; brass reads as an instrument reading. Loudest thing on the row after the pill, because it is the actual content |
| "decision-grade" | `.cal-conf` → steel **outline** chip: transparent fill, 1px `--accent` border, `--accent` text, 9.5px uppercase | confidence is a structural qualifier — how much to trust the number — so it takes the structural colour. Outlined, not filled: it qualifies the figure, it isn't the headline |

`.cal-conf` is `color: var(--caution)` today — the exact red the account rules out.

**Body kept and restyled.** It is the only benchmark-relative (α) view on the site, and §2's methodology paragraph explicitly tells the reader the tiles are *not* the alpha view — cutting the body would strand that sentence. Restyling: α columns in brass, `data-lowconf` rows muted by opacity rather than tint, caveat lines at the muted sizes.

The low-confidence word keeps its point-of-use `title` gloss.

---

## 5. §2–3 Signal tracker — trust meter and hit-rate tiles

One section head ("Signal tracker"), two blocks.

### 5.1 The trust meter — `signal_tracker.py::_readiness_html`

A single blueprint card (`lib/cards.py::card_container` — transparent fill, square corners, `+` registration marks) holding four items in `grid-template-columns: repeat(3, auto) 1fr`.

`auto auto auto` sizes the three figures to their content so they cluster left as a set; `1fr` gives the caveat all remaining width. Without this the three numbers spread across the card with big gaps and stop reading as one set.

- Three `.stat-tick` stats: *N of 3 market regimes seen*, *N matured calls*, *N of M signals decision-grade* (unchanged data, from `calibration_insights.signal_performance`).
- The caveat sentence occupies the `1fr` cell, separated by `border-left: 1px solid var(--color-divider)` + 24px padding, at 78% opacity. A hairline is enough to mark "different kind of content" (prose vs figures) inside one card without splitting it into two cards.
- **The caveat stays inside the card.** "2 of 3 regimes / 816 calls / 4 of 6 decision-grade" invites false confidence, and the sentence that limits it must be impossible to read separately from the numbers.
- `.rd-meter.warn`'s amber left border is removed. The warn state already swaps the sentence; that carries it without borrowing WATCH's hue.

### 5.2 The methodology paragraph

Moves out of `st.caption()` into `<p class="method">` below the card: 12.5px, 62% opacity, `max-width: 104ch`, with exactly **three** phrases bolded to full text colour — **rise**, **drop**, **raw price direction**. Those are the three things a reader must not misunderstand; bolding is by what breaks comprehension if missed, not by keyword importance.

**Factual fix:** the sentence currently sends readers to "the Briefing's calibration band" for the alpha view. That band is now §1 of this page (moved in the 2026-07 overhaul). It must point at §1 instead.

### 5.3 The hit-rate tiles — `signal_tracker.py::_scorecard_html`

Five equal cells: `<div class="hair-grid calib-grid">` at `repeat(5, 1fr)`.

`.calib-grid` is `repeat(4, 1fr)` today while `_SCORECARD_SPECS` emits five cells, so AVOID wraps onto a second row — the five-across comparison the section exists for is not currently possible. The class **name** is kept: `tests/test_app_pages.py` asserts on `class="calib-grid"`.

Fixed reading order inside each tile — identity, plain English, the number, its shape, its arithmetic, then whether to trust it:

1. **Signal dot + name** — 7px dot, 10.5px uppercase 600, in signal colour. Legitimate: the tile is *about* that signal.
2. **Meaning line** — "Enter now" / "Wait for the trigger" / "Wait quarters · story broken" at 9.5px muted, **`min-height: 24px`**. The min-height is load-bearing: without it, one-line and two-line meanings push the five percentages onto different baselines, and a 5-across grid exists so the numbers align. Including these at all is verdict-first — the tile says what the signal tells you to do before reporting how often it was right.
3. **Rate** — 38px, `letter-spacing: -0.02em`, tabular, neutral text colour. The largest type on the page, because it is what the section reports.
4. **Bar** — `--brass`, 4px tall, **full cell width** (currently `max-width: 120px`). Full width so lengths are directly comparable across cells: 47% vs 100% reads as a shape difference before either number is read.
5. **Basis** — "right 3 of 5 · 5d" in plain body text, tabular. Always shown, so no rate is a bare assertion.
6. **Sample quality** — see below.

**Sample adequacy is encoded by opacity, not colour.** Thin cells (`n < DECISION_GRADE_MIN`) drop both the percentage and the bar to 42%, and their warning line goes `--stress` with a ⚠. Adequate cells stay full strength with a neutral "n=43 · holding up".

Why: the honest problem with these tiles is that AVOID's 100% is the least trustworthy figure on the page and BUY's 60% is nearly as thin. Any colour-coding would fight the number's own prominence; ghosting makes untrustworthy figures physically recede, so the eye lands on the two you can actually lean on. The design enforces the caveat instead of printing it. Thin and adequate cells then differ in **three redundant ways** — opacity, colour, glyph — so no single cue carries it.

The `n < MIN_SAMPLES` "Pending" state keeps its existing behaviour.

### 5.4 The HOLD footnote

Below the grid as a 10px uppercase muted line — "Hold · N ticker-days · not scored (non-directional)" — **deliberately not a sixth tile**. HOLD makes no directional claim, so a cell with an empty percentage would imply a *missing measurement* rather than an inapplicable one. Demoting it to a footnote states the exclusion without implying a gap. Replaces the current `st.caption`.

---

## 6. §4 Paper book — `components/paper_book.py`

### 6.1 The headline sentence — `verdict_bits` / `_verdict_html`

A full sentence at 20px in the heading font, not a stat row:

> $100,000 → $99,710 (−0.3%) since 19 Apr 2026, against SPY at $104,430 (+4.4%) — **trailing the benchmark.**

Changes from shipped copy: drop the "Paper book:" prefix (the section head already says it), humanise the inception date (`19 Apr 2026`, not `2026-04-19`), and replace "vs SPY (the S&P 500) →" with "against SPY at".

Colour: values weight 600 tabular; the two returns in `--up` / `--down` (genuine market direction — the delta system, distinct from signals); the verdict clause weight 600. Verdict-first: the conclusion is the last clause and the only coloured words.

The verdict clause by branch — the account only shows the trailing case, so the other two are fixed here to keep the roles unambiguous:

| Branch | Colour | Why |
| --- | --- | --- |
| "trailing the benchmark" | `--stress` | a stress reading on the book's own performance, not a signal on any stock |
| "leading the benchmark" | `--up` | the same market-direction system the returns use |
| "tracking the benchmark" | neutral | no reading to make |

This replaces `STATUS_NEG` (`#ef4444`, the CAUTION hue) and `STATUS_POS` on the clause.

The "seeded / first fills pending" branch keeps its current neutral treatment.

### 6.2 The stats — `_stats_html`

Same hairline grid, `.stat-tick` value-over-label, **all neutral**. Cash / positions / entries / add-ons / stop-outs are *inputs, not verdicts*; colouring them would imply 15 stop-outs is "bad" when it is a count.

The chip list is data-driven (`cash_pct`, `n_positions`, then `_REASON_LABELS` hits), so it is 5 cells on today's data but can be up to 7. The grid takes its column count from the number of chips rather than hard-coding 5.

### 6.3 The chart

Plotly is **kept** for the plot (hover, and `chart_data_table`'s screen-reader parity, are worth more than literal SVG control). The blueprint chrome around it is built in HTML:

- The figure sits in a blueprint card.
- A header row above the plot: the axis description as a steel eyebrow on the left, the legend on the right, separated from the plot by a 1px hairline.
- **Legend swatches are actual line samples** — an 18px inline-SVG rule at the series' real width and dash pattern — not colour squares, so legend and plot use identical encoding. Plotly's own legend is switched off (`showlegend=False`).
- **Series hierarchy by weight, not just hue**: paper book `--brass` at 2.4px (the subject), SPY neutral at 1.6px (the benchmark), both ext-exit replays dashed at 1.4px. The dashes say "hypothetical" before the caption is read; the thin weight says "not the headline". A reader who knows nothing can still tell which line is the point.
- The replay lanes go **one neutral, one brass-tinted**, replacing today's sage / dusty-mauve `_ADVISORY_COLORS`: `ext-exit 10/5` → `CHART_MUTED` (neutral), `ext-exit 30/15` → a brass tint. Two arbitrary palette hues read as two more *categories*; neutral-plus-brass-tint reads as "variants of the subject and the benchmark", which is what they are.
- Grid lines at `--color-divider`, 11px muted tick labels, no axis box, no filled plot area — a line drawing like everything else on the page.

Precedent for the inline-SVG legend samples: `components/briefing/macro.py::_spark_svg`, including `vector-effect="non-scaling-stroke"`.

**SOXX stays excluded from the plot** and the exclusion stays stated in the caption, because a +32.1% series would flatten the book-vs-SPY gap the chart exists to show. Disclosed, never silent.

Two caption lines at 12.5px / 66%: the SOXX exclusion with its figure in brass, and the replay-lane caveat with "hypothesis-grade, one regime" in `--stress`. Terracotta again marks a trust limitation, never a rating.

### 6.4 Stop-rule lanes — `_variants_html`

Becomes a 5-cell `.hair-grid` with `border-top: 0` so it butts directly against its own eyebrow rule — label and grid read as one object. Currently a single mono paragraph.

- The headline lane carries a 2px `--accent` top rail and a "· headline" suffix; the other four carry the transparent rail (identical heights). Same flagging device as CPI / Fed-funds in the FRED grid.
- Lane returns in `--brass` (measurements); stop-out counts neutral.
- Without the rail a reader cannot tell which of five numbers is the real book — and `+5.3%` on the *wide* lane would look like the headline result.
- Lanes are never a ranking; the exported `banner` still renders beneath.

The single-regime disclaimer below is the **only italic on the page**, which is exactly why it is noticeable.

### 6.5 Drill-downs

Page-level `<details>` with the §3.3 grammar — hairline border (unlike the inline Week Ahead expander, because these are page-level sections rather than a detail inside a row), rotating caret, steel uppercase summary, **collapsed by default** so the study page still has a floor.

Per the owner's decision, every collapsed section on the page takes this treatment, and nothing is cut: paper-book positions/trades, extension lanes, the caution-trim experiment, the by-name ledger, signal changes, and the chart data table.

The name filter stays where it is — below the corpus-wide blocks, scoping only the by-name ledger and signal-changes drawers. Placing it above the corpus-wide scorecard would read as if it filtered that too (existing page contract, unchanged).

---

## 7. §5 What we've changed — `_changelog_strip_html`

A date-spine ledger (§3.4): `112px | 1fr`.

- The fixed date column creates a continuous vertical spine — you scan chronology first, then read across.
- Tick is `--color-divider` (faint), **not** accent: every entry is a peer, none is flagged, so the ticks give rhythm without hierarchy.
- Title in the heading font at 15px/600; body at 13px / 70% / `line-height: 1.6`, capped at 96ch. The tighter measure and generous leading are for genuine paragraph reading — this is the only long-form prose on the site.
- 1px hairline between entries only. **No cards** — a changelog is a list of records, and framing each one would make five paragraphs look like five products.
- Entries stay **plain prose, unstyled** — no bolding, no coloured terms. Deliberate: these entries *describe* the colour rules, and demonstrating them inside the description would be noisy. The page footer states the rule instead.

The section head keeps its `latest YYYY-MM-DD` sub, so a rotting log stays visibly stale.

---

## 8. Data plumbing

No new upstream fields, no new dashboard arithmetic. Everything renders from what the page already reads:

| Section | Source |
| --- | --- |
| §1 row + body | `calibration_insights` on the latest report (`signal_performance`, `signal_performance_decayed_full`, `taxonomy_discrimination`, `data_window`, `decay_shrinkage`, `confidence_banner`) |
| §2 trust meter | `calibration_insights.signal_performance` — `regimes_present`, `n_matured_10d`, `n_alpha_10d`, `single_regime` |
| §3 tiles | `compute_signal_accuracy()` → `return_5d` per signal |
| §4 paper book | `paper_portfolio` block + `data/paper_nav.csv`, `paper_trades.csv`, `paper_positions.csv` |
| §5 changelog | `data/changelog.json` |

Absence tiers are preserved exactly: each block already skips itself when its data is missing, and pre-adoption corpora must keep rendering. No section may start hard-failing on an older report.

---

## 9. Testing

- **Unit** — `tests/test_signal_tracker.py`, `tests/test_calibration.py`, `tests/test_paper_book.py` extend to cover: brass bars (no `STATUS_POS`/`STATUS_NEG` in tile markup), thin cells carrying both `.thin` and a `--stress` warning, five cells in one row, the steel decision-grade chip, the headline-lane rail on the correct lane, the new headline sentence copy, and the spine markup.
- **Colour discipline is testable** — `tests/test_design_tokens.py` gains an assertion that the tracker page's emitted HTML contains no WATCH amber (`#f59e0b` / `STATUS_WARN`) in data-quality contexts.
- **Page smoke** — `tests/test_app_pages.py` continues to assert `class="calib-grid"`; per `AppTest` constraints, drive the page via `AppTest.from_function` rather than through `dashboard.py` nav, and do not assert on bare CSS class names that `theme.css` matches everywhere.
- **Visual baselines** — regenerated once, at the end, after all sections land. Run via PowerShell (not Git Bash); regen skips unchanged PNGs.

---

## 10. Sequencing

1. **Foundation** — `.hair-grid`, `.stat-tick`, drawer grammar, `.warn-thin`, `.spine`, `.section-head.masthead`, `render_section_head(masthead=)`. `.fp-grid` re-based onto `.hair-grid` with no visual change.
2. **§1** — calibration row + body.
3. **§2–3** — trust meter, methodology paragraph (incl. the stale-pointer fix), hit-rate tiles, HOLD footnote.
4. **§4** — paper book: headline sentence, stats grid, chart chrome, stop-rule lanes, drawers.
5. **§5** — changelog spine.
6. **Close-out** — `data/changelog.json` entry, visual baseline regen, full test run.

---

## 11. Out of scope

- No new signals, metrics or upstream fields — this is a presentation-layer change (see the page's existing contract).
- No information-architecture change: no block is cut, moved between pages, or reordered.
- No refactor of tracker CSS blocks this work does not touch.
- The Briefing and every other page are untouched, except `render_section_head` gaining a backwards-compatible optional argument and `.fp-grid` being re-expressed in terms of `.hair-grid` with identical output.
