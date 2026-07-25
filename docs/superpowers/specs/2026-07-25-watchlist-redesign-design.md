# Watchlist redesign — design spec

**Date:** 2026-07-25
**Scope:** the Watchlist page (`dashboard.py::_page_watchlist`) — `components/watchlist/watchlist.py`, `components/watchlist/row.py`, `components/watchlist/drilldown.py`, `lib/cards.py`, `assets/theme.css`.
**Source:** the owner's full design account of the page (2026-07-25), reproduced in intent below. Where the account and the shipped code disagree, the account wins unless this spec says otherwise and gives the reason.
**Branch:** `watchlist-redesign`, in the worktree `.claude/worktrees/watchlist-redesign`, cut from `main`. Two other terminals hold `signal-tracker-redesign` and `review-redesign` in parallel — see §10 for the shared-file couplings that follow from that.

---

## 1. What the page is for

This is the **whole book** — every name, with enough per-row information to decide whether to open it. That makes it a different problem from every other page: it is not a narrative (Briefing), an argument (Tracker), or a record (Review). It is a **dense scanning surface**, and the design question is: *what does a reader need to triage 32 names in thirty seconds?*

The shipped version answers that as "a flat sorted table with eight numeric columns." Honest, but it makes the reader do all the work: the grouping is invisible, every number carries equal weight, and the one column that actually gates a trade is just a signed percentage among others.

The redesign **keeps the density** and adds three things: **structure** (explicit signal groups), **state** (a persistent "what changed" filter), and **one visual** (the extension gauge) so the page can be triaged rather than read.

Single-column, full-width, **no card wrapping the table**. A dense grid *is* the content; framing it would waste horizontal room the columns need.

---

## 2. The colour discipline (load-bearing)

This is the densest page on the site and therefore the one where colour discipline pays off most. A single row can simultaneously show a red CAUTION pill, a green +9.4% month, a terracotta +11.0% extension bar and a terracotta 77 RSI — four coloured elements, four different meanings, no ambiguity. That only works because each palette has exactly one job.

(The account writes "amber CAUTION pill" here; CAUTION is `#ef4444` in `SIGNAL_COLORS` and amber `#f59e0b` is WATCH. Corrected, because the paragraph's whole point is that each hue has one owner.)

| Role | Token | Where |
| --- | --- | --- |
| Signal rating | signal palette (`SIGNAL_COLORS` / `--buy`…`--avoid`) | row rails, pills, group dots + group headers |
| Price movement | `--up` / `--down` | day Δ, 1-month, the gauge's number, target / invalidation levels |
| Measurement | `--brass` | extension bar under threshold, R:R in the levels plate |
| Threshold crossed / gate / falsifier | `--stress` (terracotta) | extension at or past ±10%, RSI past 70/30, entry-block rail, thesis-break rail |
| Structure / navigation | `--accent` / `--eyebrow` (steel) | filter chips, changed-today dot, gauge zero line, drill-down eyebrows |
| Metadata | `--color-text-3/4`, explicit `opacity` | cluster, labels, adjusted-R:R note, counts |

Three consequences are corrections to shipped code, not new opinions:

- **The changed-signal marker is steel, not a signal colour.** "Something changed today" is a structural fact about the row, not a rating. Amber or red would compete with the pill sitting ~100px to its right.
- **RSI past its thresholds is terracotta, not red.** An overbought reading is a *data condition*. 77 on `D05.SI` is not a CAUTION rating, even though that name happens to carry one.
- **The extension gauge is never green/red.** A green/red gauge reads as "good/bad", which is wrong in both directions: −17.5% is not "bad", it is "not extended, but broken".

Opacity percentages quoted below are literal `opacity:` on the element, matching the convention the Tracker spec uses ("at 78% opacity"), not new colour tokens.

---

## 3. Page head

```python
render_section_head(
    "The Watchlist",
    "The whole book · click any row for the full read",
    masthead=True,
)
```

h2 at 30px / 600 with the right-aligned uppercase descriptor at 10px muted, over a **2px solid `--color-text`** rule. Identical to the Tracker and Review heads — the 2px masthead-weight rule is the site's marker for "top-level document surface", so all four pages announce themselves the same way.

The descriptor states both the scope and the interaction, so nothing else has to explain that rows expand.

**Deviation from the account, deliberate:** the account says `h1`. This ships as `<h2>` so `.section-head.masthead` stays *one* shared selector with the Tracker and Review rather than forking a near-identical rule; `render_section_head` is used many times per page elsewhere on the site, where multiple `h1`s would be wrong. The account's "h1" describes its mockup's markup, not the site's convention.

When viewing a historical report the descriptor gains `· viewing YYYY-MM-DD`, exactly as the current `sub_label` does.

---

## 4. Filter bar

A "Show" label, then joined-spacing chips, then a muted sort-explanation line.

### 4.1 Why chips

The option set is small and **the counts are themselves information**. `All · 32 / ● Changed · 6 / Watch · 1 / Hold · 10 / Caution · 21` is a distribution readout, so the filter bar doubles as the "shape of the book" summary that the Briefing's signal-count grid used to provide. One element, two jobs.

`gap: 8px` between chips — unlike the Review's joined `gap: 0` segments — because these are independent options rather than one exclusive time axis. Spacing says "separate options"; joining says "one control, one value".

### 4.2 The Changed chip is the important one

In the shipped source a changed signal gets `data-signal-changed="true"` and a CSS flash on first mount — which means **the information expires seconds after you land**. Promoting it to a persistent filter (and a persistent dot on the row) turns "what moved today" from something you must catch into something you can ask for. Its leading `●` mirrors the row marker so the connection is obvious without a legend.

### 4.3 Construction — `st.pills`, not CSS

`st.pills(label="Show", options=[...], selection_mode="single", default="all", key="wl_filter", label_visibility="collapsed")`, inside the existing fragment.

A pure-CSS filter (hidden radios + `:has()`) was rejected: the page body is an `st.fragment(run_every=60)` for live prices, so the markdown re-renders every minute and DOM-only filter state would **silently reset to All once a minute**. Session state survives the rerun; a fragment rerun is also cheap and does not repaint the masthead.

Filtering is **Python-side**, not CSS-hidden. When Watch is selected, only the Watch group renders and its header count is still the honest count for that group. Hiding rows with CSS would leave empty group headers behind.

Deselection: `st.pills` lets a user click the active chip off, returning `None`. That coalesces to `"all"` rather than rendering an empty book.

Chip options are built from the data, never hardcoded:

```
["all"] + (["changed"] if changed else []) + [signals present, in SIGNAL_SORT_RANK order]
```

The account's mockup shows five chips with a 3/6/6 spread. **That distribution does not exist in the corpus** — today is 1 WATCH / 10 HOLD / 21 CAUTION across 32 names — so the bar must be data-driven. A day with only CAUTION names shows two chips; a day with nothing changed shows no Changed chip.

### 4.4 Styling hook

Scoped through `.st-key-wl_filter`, the container class Streamlit stamps for any keyed widget. This is deliberately **not** a `data-testid` chain: the deployment carries a local 1.50 / CI 1.58 / cloud-latest version skew, and testids on button internals have moved between those versions while the key class has not.

- Active: 1px `--accent` border, 14% accent wash, full-strength text.
- Inactive: 1px `--color-divider` border, `--color-text-3`.
- Steel, because filtering is **navigation, never a rating**.
- The faint fill is the one place on the page with a background, justified because a selected chip among adjacent chips reads weakly on a border change alone.

### 4.5 The sort line

`Grouped by signal · then by one-month return · retired names excluded` — 9.5px, 45% opacity, directly beneath the chips.

Small, but it is the page's only statement of its own ordering **and its survivorship-bias exclusion**. On a dense table this matters: without it a reader cannot tell whether row order means anything.

---

## 5. Column header and the column set

```
grid-template-columns: 132px 108px 112px 74px 168px 52px 96px;
gap: 12px;
```

over a 1px `--color-text` top rule and a 1px `--color-divider` bottom rule.

**Two weights, on purpose.** The strong top rule opens the data zone (the same "shelf" logic as the Briefing's pulse tape); the faint bottom rule only separates labels from rows. Reading downward you get a firm start and a soft handoff into the data.

**All-fixed columns, no `1fr`.** Every cell is a number or a short token, and the whole point is that values line up down the page for comparison. A flexible column would let content reflow the grid and break vertical alignment across groups.

The set was cut and re-ordered by **decision relevance**, from the shipped `Ticker · Cluster · Signal · Last·Δ · 1mo · vs50 · RSI · R:R`:

| Column | Width | Change |
| --- | --- | --- |
| Ticker | 132px | now two lines — ticker + changed-dot above, cluster below |
| Signal | 108px | **moved to position two** |
| Last · Δ | 112px | retained, now two lines |
| 1 mo | 74px | retained |
| vs 50-day | 168px | **the gauge** — widest column on the page |
| RSI | 52px | retained |
| R:R | 96px | retained, now two lines |

- **Cluster is removed as a column** and demoted to a muted sub-line inside the ticker cell. It is context you want *while looking at a name*, not an axis you scan or sort by — and it was consuming 100+px of a width-constrained grid.
- That reclaimed width went to the gauge. A deliberate trade: the gauge earns more room than the cluster label because **it is the criterion that gates entry**.
- **Signal sits second, immediately after the ticker, because it is the row's verdict.** You should never read four numbers before learning what the call is.
- Nothing was dropped. Only relocated.

### 5.1 Width budget

Fixed tracks sum to 742px; six 12px gaps add 72px; total **814px**. `st.set_page_config(layout="wide")` gives ~1060px of content at a 1100px viewport, which is exactly where the desktop rule releases `.tk-scroll`'s `overflow-x` for the sticky header. Below 1100px the swipe canvas is still in force; below 720px the grid reflows to stacked cards. So the account's widths are safe as given — no trimming needed.

### 5.2 Phone reflow

`assets/theme.css`'s `Phone reflow — one-screen ledgers` block currently hardcodes `nth-child(1)…nth-child(8)` with per-cell `::before` labels. It is rewritten for **seven** cells with the new label set. The gauge cell drops its track on phones and renders the signed number alone — a 168px bar cannot survive a stacked card, and the number is the same information.

---

## 6. Group headers

Each signal group opens with `dot + name + count + a hairline rule that fills the remaining width`.

- The dot and the group name take the **signal palette** (amber WATCH, grey HOLD, red CAUTION). Legitimate: the group *is* a signal. This is also the only coloured text at heading scale on the page.
- **11px uppercase, not a real heading size.** These are dividers inside one table, not sections of a document; sizing them up would fragment the page into three tables. The design system's hierarchy comes from weight and colour, so 11px at weight 700 in the signal colour is plenty.
- The trailing `flex: 1` hairline turns the header into a full-width rule with a label at its left — the standard "labelled divider" pattern. It binds the label to the rows beneath it and gives each group a clean top edge **without a second border weight**.

**Why group at all, given the source already sorts by rank:** a sort is only legible if you already know the rank order. Explicit groups with counts make the ordering self-documenting, let a reader skip the 21 CAUTION names entirely, and give the eye rest points in a long scroll.

### 6.1 Construction constraint

Group headers are emitted **inline in the same single `st.markdown` blob** as the column header and every row. This is load-bearing and already documented in `watchlist.py`: a `<div>` opened in one `st.markdown` and closed in another does not wrap sibling Streamlit blocks — the browser auto-closes it. `.tk-scroll` must genuinely contain the rows in the DOM.

Under the **Changed** filter, rows still group by signal (a changed row is still a WATCH or a CAUTION), and each header's count is the count *within that filter*.

---

## 7. The row

`padding: 12px`, a 1px `--color-divider` bottom hairline, and a **3px left rail in the row's signal colour** — the same rail grammar as clusters, the Briefing shortlist and the Review's call rows. A coloured left edge always means "this row's state", everywhere on the site.

| Cell | Treatment | Why |
| --- | --- | --- |
| Ticker | ticker 14px / 700 / tabular, optional 6px **steel** dot beside it for a changed signal, cluster beneath at 9px / 45% uppercase | two lines, one cell — identity above, context below |
| Signal | full pill treatment (tinted background, rail text, dot) via `_signal_pill_html` | the canonical rating object, identical on every page |
| Last · Δ | price 13.5px on top, day change 11px beneath in up/down | keeps the price primary and the delta subordinate, and saves a column versus splitting them |
| 1 mo | single line, up/down colour | price moves are the delta system — distinct from the signal palette **by design**, and this page proves why: a CAUTION row can show a green 1-month return without contradiction |
| vs 50-day | the gauge (§8) | |
| RSI | bare number, turns **terracotta** at ≥70 or ≤30 | the threshold is what matters, not the value, so the colour does the interpreting |
| R:R | ratio 13px, `tight-stop adj.` at 8.5px / 42% beneath when the number was corrected | see below |

**The R:R qualifier is the one shipped bug this fixes.** Today it hides in a `title` attribute because the table had no room — invisible on touch and to anyone not hunting for it. Given a second line, the qualifier is **always visible** on the few rows it applies to, and it is the difference between a 1.5:1 that clears the gate and one that does not. The raw headline ratio stays on the `title` for grep-ability.

The `PRE` / `POST` extended-hours tag (`.ext-tag`) keeps its current position beside the day change.

---

## 8. The extension gauge — the page's one visual

A 168px-wide, 9px-tall hairline track with a steel 1px zero line at the centre, a fill bar growing left or right, and the signed percentage centred beneath it.

**Why this column gets a visual and no other does.** vs 50-day is the **mechanical block criterion** — the pipeline refuses entries on names too far extended above the average. Every other column is an input to judgment; this one is a rule. A signed number makes the reader compare `+14.3%` against a threshold they have to remember; a centred bar makes "too far right" a *shape*.

| Property | Value | Why |
| --- | --- | --- |
| Anchor | **centred**, not left | the quantity is signed and zero is meaningful — the 50-day is the reference. A left-anchored bar would imply a magnitude scale where "small" is the left end, which is wrong: below the average is the interesting other direction |
| Zero line | steel, 1px, `top:-2px; bottom:-2px` | extends past the track so it stays visible where a bar crosses it. Steel because it is a **structural reference mark, not data** |
| Scale | fixed `EXT_MAX = 20.0` for every row, clamped | a shared scale is what makes the bars comparable down the page; a per-row scale would be meaningless |
| Fill | `--brass` while `abs(v) < 10`, `--stress` at `abs(v) >= 10` | brass is the data axis; terracotta marks the threshold crossing. **Neither is a signal colour** — critical, because the gauge sits three columns from the signal pill |
| Number | 10.5px beneath, up/down colour | bar for the threshold read, number for the exact value — redundant encoding, the same principle as the Tracker's tiles |

**Clamping is accepted, not a flaw.** `CRWV` at −17.5% and a hypothetical −40% look the same: past the threshold, how far past stops changing the decision.

Geometry, as plain divs (not SVG — it is two rectangles and a rule):

```
frac = min(abs(v), EXT_MAX) / EXT_MAX
v > 0  →  left: 50%;  width: frac * 50%
v < 0  →  right: 50%; width: frac * 50%
v is None → no track, no bar, bare "—"
```

A missing `vs_sma50_pct` renders the em-dash alone. It must never print `—%` (the bug `tests/test_watchlist_row.py` already guards).

---

## 9. The expanded row

Every row has one. It is the `<details>` body that unfolds in place beneath whichever row is clicked — the account renders one detached specimen (MU) only so the collapsed grid and the full expanded structure fit on one screen without a click.

The shipped version stacks **fifteen undifferentiated `dd-section` blocks**. The redesign's main argument is reading order.

### 9.1 Reading order

1. **Blueprint card** carrying the row's signal rail on its left edge, so the expanded body is visibly the same object as the row that opened it.
2. **Header** — ticker at 22px + cluster muted, with last price and the signal pill right-aligned. Restates identity because an open drill-down can be taller than the viewport and lose its row.
3. **Status-chip strip** — the existing `caution_source` / momentum-warning / data-anomaly / news-skew / premarket chips, kept visible. These are *flags*, not detail; burying them in a drawer would hide the reason a name is rated the way it is. Their colours are re-based onto the §2 table (`STATUS_WARN`'s amber is WATCH's hue and moves to `--stress` in the data-quality chips; the news-skew and premarket chips keep up/down, which is genuine market direction).
4. **Entry-block warning** — a hairline box with a terracotta left rail. **First**, because it is the single most consequential fact: the trade is blocked. Terracotta because it is a gate condition, not a rating. States the number, the threshold and what clears it, preferring `entry_block_reader` with the raw rule on the `title` (shipped behaviour, unchanged).
5. **Verdict headline** at 21px in the heading font. Verdict-first, and the largest text in the block.
6. **What changed since yesterday** — `prior_period_delta_narrative`, italic muted, **the only italic in the block**, so it reads as a parenthetical update rather than part of the thesis.
7. **What to do** — 14px / 66ch. Larger and darker than any other prose in the block, because it is the actionable instruction. Everything below it is evidence.
8. **The levels plate** — §9.2.
9. **Two columns** — §9.3.
10. **Three collapsed drawers** — §9.4.

### 9.2 The levels plate

Trigger / target / invalidation / R:R in a **4-cell hairline grid** at 20px each.

| Cell | Source | Colour | Why |
| --- | --- | --- | --- |
| Trigger | `reentry_zone.level` | neutral | the level you are waiting on |
| Target | `risk_reward.upside_target` | `--up` | a price you are hoping for → market-direction colour |
| Invalidation | `risk_reward.invalidation` | `--down` | a price you are fearing → market-direction colour |
| R:R | `rr_display(risk_reward)` | `--brass` | a **measurement**, not a price |

Four colours, each by role. Promoted out of the section stack into a grid because **price levels are what you act on** — they should be findable without reading.

This extends the existing `_entry_target_invalidation_html` / `.ac-tri-*` device from `components/briefing/action_card.py` to a fourth cell rather than inventing a new one; the three-cell action-card usage is unchanged.

### 9.3 The two columns

**Left — Technicals + Valuation** as label/value pairs on **dashed** hairlines. Dashed, not solid, to distinguish "reference rows inside a card" from the solid row dividers of the table. Same field sets as today's `Technicals` and `Valuation` metric grids; the `Cluster` row drops out of Valuation (it is now in the card header and the row's ticker cell).

**Right — the thesis**, in this order:

1. **Numbered pillars** — `support_legs` as `01 02 03` in faint tabular. Numbering makes them a **finite argument** rather than a bullet dump.
2. **Thesis highlights** — the pipeline's guardrail bullets that matched the day's news (~5 of 32 names). *Deviation from the account, deliberate:* the account does not place these. They are thesis evidence, so they belong with the pillars, not in a drawer.
3. **Thesis-break condition** on a terracotta left rail, **last**, because it is the falsifier.

The single-leg fragility note keeps its current behaviour and moves to `--stress` (it is a gate, not a rating).

### 9.4 The drawers

Three raw `<details class="dd-drawer">`, collapsed by default, with the site's drawer grammar (hairline border, square corners, steel uppercase summary, caret rotating on `[open]`), so the drill-down has a floor.

| Drawer | Holds |
| --- | --- |
| Earnings | pre-earnings setup band (archetype, bull/bear cases, the six metrics) + the quarter-on-quarter earnings-history table and its sparkline |
| Risk & reward detail | the upside/invalidation prose lines, headline vs wide-stop vs structural-support metrics, and Key Levels (support / resistance zones) |
| Pipeline detail | ACCUMULATE gates, Regime Change Pending, catalyst context, avoid source, earnings result |

**Raw `<details>`, not `st.expander`** — these live inside a markdown-injected `<details>`, and `st.expander` cannot. Nested `<details>` is valid HTML and the drill-down already relies on `unsafe_allow_html`.

**Nothing is cut.** Every block the shipped drill-down renders still renders; the eight the account does not place are relocated per this section (owner's decision, 2026-07-25). Each keeps its existing absence behaviour — a block whose data is missing stays silent, and a drawer with no populated block does not render at all.

---

## 10. Footnotes and footer

**Method note** at 12.5px / 60%, bolding exactly three things to full text colour: **±10%**, **R:R is the tight-stop-corrected ratio**, and the **RSI 70/30 thresholds**. Those are the three pieces of encoding a reader cannot infer from looking — everything else on the page is self-evident. **Bolding is by what breaks comprehension if missed, never by keyword importance.**

**Footer** states the shown/total count and the meaning of the steel dot — the page's own legend, placed where a confused reader would look.

---

## 11. Page furniture — kept

The account describes the table region. The rest of the page is unchanged (owner's decision, 2026-07-25), consistent with the Tracker spec's no-IA-change rule:

- the report-date `st.selectbox` above the head,
- `_render_live_caption` (live-quote status),
- `render_pulse(benchmarks)` — the benchmark tape,
- `render_contrarian_candidates` below the grid.

The only replacement is `render_section_head(...)` gaining `masthead=True` and the new descriptor copy.

---

## 12. Data plumbing

No new upstream fields, no new dashboard arithmetic. Everything renders from what the page already reads.

| Element | Source |
| --- | --- |
| Rows | `report["watchlist"]`, minus `RETIRED_TICKERS`, sorted by `SIGNAL_SORT_RANK` then `-1mo_pct` |
| Changed set | already computed in `_page_watchlist` — signal differs from the prior report, structural appear/disappear excluded |
| Gauge | `vs_sma50_pct` |
| Levels plate | `reentry_zone.level`, `risk_reward.upside_target` / `.invalidation`, `rr_display(risk_reward)` |
| Drill-down | unchanged field reads; `earnings_history.csv` still threaded in by the caller so `drilldown.py` stays Streamlit-free |

Absence tiers are preserved exactly. Pre-adoption corpora must keep rendering: no block may start hard-failing on an older report, and the corpus spans 102 reports back to 2026-03-12.

---

## 13. Shared-file couplings (parallel branches)

Three terminals are open on three pages. Two files are genuinely shared:

- **`lib/cards.py` — `render_section_head(masthead=)`.** The Tracker branch adds the identical parameter. This branch replicates its implementation **verbatim** (`_section_head_html(title, sub, masthead)` returning the markup, `render_section_head` delegating to it) so git auto-merges identical hunks instead of conflicting. Likewise the two `.section-head.masthead` rules in `theme.css`.
- **`data/changelog.json`.** Its own commit, nothing else in it. An entry here moves the two Signal-Tracker visual baselines, so whichever branch lands second regenerates.

Rendering is done through the **Docker visual harness**, not the Playwright MCP browser: the MCP browser is single-instance and another terminal may hold the profile lock.

---

## 14. Testing

- **`tests/test_watchlist_row.py`** (7 existing tests must keep passing) extends to cover: the two-line ticker cell, the steel changed-dot present only when `signal_changed`, the visible `tight-stop adj.` sub-line, gauge markup, gauge clamping at ±20, brass-under/terracotta-at ±10, terracotta RSI at the 70/30 boundaries, and a `None` `vs_sma50_pct` producing a bare em-dash with no track.
- **`tests/test_watchlist_grid.py`** (new) covers the grid builder: chip options derived from the data (no Changed chip when nothing changed; only signals present get a chip), counts matching the filtered rows, group headers emitted in `SIGNAL_SORT_RANK` order, one blob containing header + groups + rows, and the footer's shown/total figures.
- **`tests/test_drilldown.py`** (27 existing tests) extends to cover: the levels plate's four cells and their colour roles, the entry-block box preceding the headline in source order, the three drawers, a drawer with no populated block not rendering, and every relocated block still appearing somewhere in the output.
- **Page smoke** — driven via `AppTest.from_function(_page_watchlist)`, not through `dashboard.py` nav (nav resets to the default page, so widgets on other pages are unreachable). Do not assert bare CSS class names that `theme.css` matches everywhere.
- **Security** — `tests/test_rendering_security.py` already asserts the drill-down escapes report-authored strings; the restructure keeps every `_escape_dollars` / `_escape_attr` call at its current boundary and the tests must pass unchanged.
- **Visual baselines** — regenerated **once, at the end**, after every section lands, through the Docker harness run from PowerShell. Regen skips unchanged PNGs. Affected: `watchlist`, `watchlist-nvda-drilldown`.

---

## 15. Sequencing

1. **Foundation** — `render_section_head(masthead=)` (verbatim replica), the `.section-head.masthead` rules, and the page head + descriptor copy.
2. **Grid shell** — the seven-column header, group headers, the single-blob emitter, footer. Rows still in their old shape.
3. **The row** — two-line ticker / Last·Δ / R:R cells, steel changed-dot, terracotta RSI.
4. **The gauge** — track, zero line, fill, clamping, number.
5. **Filter bar** — `st.pills`, data-driven options, Python-side filtering, chip CSS, sort line.
6. **The drill-down** — card + header, entry-block-first order, levels plate, two columns, three drawers.
7. **Phone reflow** — the seven-cell rewrite of the stacked-card block.
8. **Method note + footer copy.**
9. **Close-out** — `data/changelog.json` entry (own commit), full test run, visual baseline regen.

---

## 16. Out of scope

- No new signals, metrics or upstream fields — this is a presentation-layer change (the page's existing contract).
- No information-architecture change: no block is cut or moved between pages. Within the drill-down, blocks are **relocated** per §9, which is the redesign.
- No refactor of watchlist CSS blocks this work does not touch.
- Every other page is untouched, except `render_section_head` gaining a backwards-compatible optional argument and `_entry_target_invalidation_html` gaining a fourth-cell variant with the three-cell action-card call unchanged.
