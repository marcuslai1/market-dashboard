# Pipeline health — redesign

**Date:** 2026-07-25
**Surface:** `components/pipeline_stats.py`, new `lib/pipeline_metrics.py`, `assets/theme.css`, `lib/charts.py`
**Status:** design approved, ready to build

---

## 1. The premise

**This is the only page whose reader is the operator, not the investor.** Every
other page is written for someone deciding what to do with money. This one is
written for the person who runs the pipeline and pays for it. That single fact
drives almost every decision below, including the colour freedom this page has
and the others don't.

The current page is telemetry: seven charts, 21 metric tiles, eight inline data
tables, and no statement anywhere of whether something is wrong. It plots
everything it can measure and leaves interpretation to the reader.

The redesign asks one question — **is the pipeline healthy, and is it costing
what it should?** — and structures everything around answering it.

**Reading order:** verdict → unit economics → cost → cache → prompt → volume.
Most valuable first. Today prompt composition, the thing that actually drives
cost, is dead last below six other charts.

---

## 2. What the real data says

The design account this spec derives from was written against sample figures.
Bound to `data/pipeline_stats.csv` and `data/claude_analysis.csv` as they
actually stand (97 rows, 62 post-cutover, 2026-03-16 → 2026-07-24), several of
its numbers do not survive. **Every figure on the page is computed; none is
transcribed from the account.**

| Account says | Data says |
| --- | --- |
| `$0.0235` a run, ceiling `$0.035` | latest `$0.0445`; last-7 mean `$0.0573`; last-28 p50 `$0.0544`, p90 `$0.0677` |
| `148 s` generation | last-28 p50 `353 s`, p90 `481 s` |
| `⚠ 1 validator warning` | latest run carries **71** warnings across 10 checks; median run has 26 |
| `✓ 14 of 14 scheduled runs` | no "scheduled" field exists. 62 runs over 59 weekdays, 2 weekdays with no run |
| cache "working as intended" | true on average (p50 71–74%) but **some runs in the last 28 sit at 0.0%** |

Two consequences:

1. **A `$0.035` ceiling would read as permanently breached.** Thresholds are set
   from the observed distribution and declared as operator budget, not smuggled
   in as facts. See §6.
2. **The reliability line must be honest.** "1 validator warning" would be a
   fabrication. It reports the real count and check-count, and the run gap is
   phrased against weekdays because that is the only denominator the data
   supports.

That the cache genuinely hits 0.0% on some runs is the strongest argument *for*
the diagnosis panel in §9 — it is a live failure mode, not a hypothetical.

---

## 3. Architecture

The page module is 339 lines of mixed arithmetic and rendering and will grow.
Split it:

| Module | Owns |
| --- | --- |
| `lib/pipeline_metrics.py` (new) | Every derived figure — cost stats, cache stats, prompt composition, reliability, threshold evaluation, status. Pure pandas, no Streamlit, unit-testable. |
| `components/pipeline_stats.py` | Rendering only. |

The arithmetic is where this page has been wrong (see §7), so the arithmetic is
what gets tests.

---

## 4. Page head and the verdict band

**Head.** The shared `render_section_head(..., masthead=True)` device — 1.875rem
over a 2px `--color-text` rule, same as every other top-level page.

**Date-range chip**, hairline-bordered, top right, tabular figures. The current
page repeats "Totals cover the N reports in the selected range, not all-time"
under multiple sections while the control lives in the sidebar. State the window
once and every number below inherits it.

**The verdict band** is a blueprint card (`auto | 1fr`, hairline divider) — the
site's device for "a discrete object". It is the one element that must not be
skimmed past; everything below is plain, because it is the evidence.

- *Left — status.* A 9px dot plus one word at 26px. `Healthy` / `Watch` /
  `Over budget`, on the steel → gold → terracotta health axis. Steel for healthy
  because "fine" is the structural default, not an achievement. The operator's
  first question is binary and should be answerable from the top of the viewport
  without reading a number.
- *Right — the thesis*, 19px: costing $X a run with Y% of input served from
  cache — about $Z a month at this cadence. Verdict-first, plain English; the
  same figures appear structured below.
- *Reliability line*, computed: runs in range, weekdays with no run, and the
  validator-warning count with its check count. Reliability precedes cost for a
  daily job — "did every run succeed?" comes before "what did it cost?"

---

## 5. The unit-economics strip — five metric identities

Five equal cells, `gap: 1px` over a `--color-divider` ground, each cell
`--color-bg`. The site's standard hairline grid: a grid of cells always means
"peer measurements, compare across".

### The metric-family palette

| Metric | Light | Dark |
| --- | --- | --- |
| Cost / run | gold `#8a6520` | `#e0bd74` |
| Cache hit | teal `#1d6b64` | `#63c6ba` |
| Input tokens | indigo `#3f5f9e` | `#8fb2ee` |
| Gen time | violet `#63478c` | `#b7a3e6` |
| Articles fed | moss `#4d6b38` | `#a6ca86` |

**Why this is legal here and nowhere else.** Green/red are reserved for market
direction; the signal palette is reserved for ratings. This page has no signal
pills and no price moves, so neither reserved palette is in play and the hues
cannot be misread. The investor pages can't do this; that is precisely why this
one can.

**Why identity-hue rather than good/bad colouring.** Every metric here does have
a fixed valence, so green/red would be internally consistent. Two reasons not
to: a reader crossing from a green `+9.4%` on a Watchlist row to a green `▼12%`
here has to switch interpretive modes silently; and colouring all five implies
all five need reacting to, when `articles — flat` changes nothing. Hue says
*which metric*, not *whether it is good* — and identity is what a five-cell strip
needs.

All five sit on one chroma/lightness band so no cell shouts louder than another.
They should read as a technical legend, not a category chart.

**Tokens, not hex.** `tests/test_design_tokens.py` forbids raw hex in
components, so these land as `--metric-cost` … `--metric-articles` two-theme
pairs in `theme.css`, plus a `METRIC_COLORS` map in `lib/charts.py` for the
Plotly side. Adding them is a shared-file change, deliberately.

### Inside each cell

Fixed reading order: swatch + label → value → delta → trend → threshold.

- **6px square swatch** beside the label, both in the hue, plus a **2px top
  rail**. Three placements of one hue give the cell a spine.
- **Value at 29px**, unit split out at 14px muted (`71.0` + `%`). The number is
  the content; the unit is a qualifier.
- **Delta row:** arrow + magnitude in the hue, then the comparison basis in tiny
  muted caps. A delta without a denominator is an assertion, so the basis is
  always stated. Flat gets a neutral arrow — "nothing happened" should not wear
  the accent.
- **Filled-area sparkline**, full-bleed: 1.75px line in the hue over a 17% wash,
  with a hollow endpoint dot pinning the latest value. The wash gives each cell
  a silhouette; five bare lines read as five identical squiggles. The dot is an
  **HTML element over a `position: relative` clipped wrapper**, not an SVG
  circle — the sparkline uses `preserveAspectRatio: none`, which would stretch a
  circle into an oval and paint it past the cell edge.
- **Threshold line** at 9.5px / 62% (~5.5:1). Deliberately not the faintest text
  in the cell: it is the payload of the feature.

### The breach override

If a metric crosses its limit, rail, swatch, label, line, fill, dot, arrow,
delta and status all flip to terracotta with a `⚠` prefix. Same exception rule
as extension past ±10% on the Watchlist — one colour meaning "this needs
attention", used identically site-wide.

If a breached cell kept its hue and only gained a glyph, the page's most
important state would be its subtlest. The exception must beat the identity.

---

## 6. Thresholds

Declared constants in `lib/pipeline_metrics.py`, set from the observed
post-cutover distribution and documented as **operator budget, not measurement**:

| Metric | Limit | Basis |
| --- | --- | --- |
| Cost / run | ceiling `$0.08` | ~1.2× last-28 p90 (`$0.0677`), above the observed max (`$0.0709`) |
| Cache hit | floor `40%` | p50 is 74%; 0% runs are the failure mode this catches |
| Input tokens | ceiling `220,000` | ~1.17× p90 (`188k`) |
| Gen time | ceiling `600 s` | ~1.25× p90 (`481 s`) |
| Articles fed | floor `5` | p50 is 24; the last 28 contain runs at 0 |

Every threshold is printed next to its metric, so the reader sees the budget and
the reading together and can judge the budget too.

---

## 7. Unit cost, and the arithmetic fix

Four tiles chosen for actionability, not availability: **latest run** (gold,
7-day average beneath), **run rate** projected to `$/mo` — cost per run is
meaningless to a human until projected, nobody reasons in fractions of a cent —
**without cache** as a counterfactual in muted neutral (the only greyed value in
the row, because it is not a real measurement) with the per-run saving in teal
beneath, and **spent since cutover**.

One chart survives from seven: cost per run over the last 28, gold bars with a
neutral 7-day average line, legend swatches that are actual samples of the marks
they describe. Bars vary opacity above the median so expensive runs read at a
glance without a second colour. Token count and generation time are
near-constants dressed as trends — a 300px chart for a number that moves 5% is a
waste of scroll, and they are sparklines in the strip now.

**The cumsum fix.** `cost_usd.cumsum()` currently runs across *all* rows,
including pre-2026-05-05 runs the code's own comment says overstate spend ~10×,
so the cumulative chart contradicts the "Total (post-cutover)" tile directly
above it. A running total spanning two pricing regimes is not a number.
Pre-cutover history moves behind an expander and is excluded from every total,
average and cumulative figure; the expander says why. **This changes a
user-visible figure**, so it goes in the changelog.

---

## 8. Prompt cache

Verdict-first headline, then a 20px hairline-bordered composition bar — teal for
hits, neutral 20% for misses. Misses are neutral rather than a second hue
because a miss is not a category, it is the absence of a hit. Three tiles:
latest ratio, average ratio, saved to date. Latest *and* average because a
single day's ratio can mislead.

---

## 9. The diagnosis panel

The current page buries this in an 11px chart caption:

> If hit ratio sits near 0%, the user prompt's first dynamic block is breaking
> the prefix immediately — reorder static blocks above the `data_json` block…

That is a diagnosis with a fix, sitting where you put things nobody needs to
read. It becomes a steel-railed panel headed "If the ratio falls near zero",
with the block names in mono and gold so they read as code references rather
than prose. Steel because it is structural guidance, not a warning about current
state. The savings assumption is disclosed at the bottom.

It stays visible even when the cache is healthy: it is the runbook entry for the
failure mode, needed at the moment it breaks — which is exactly when nobody
wants to go hunting for it.

---

## 10. What's in the prompt

Promoted from last to third, because input size is what drives unit cost. Shown
as shares of one run rather than five stacked time series: the question is what
dominates, not how each moved. The time series answers a real but secondary
question, so it goes behind an expander.

**A single ordered ramp, not five hues.** These are parts of one whole; five
arbitrary categorical colours say "five unrelated categories". Indigo rather
than gold so composition reads apart from money, and because it ties to the
strip's input-tokens cell — the metric this section explains.

**Making the bands discernible.** A single-hue ramp is hard to discriminate at
adjacent steps, so the encoding is made redundant four times over:

1. Wider spread — steps run 100 → 22, not 100 → 30.
2. Hairline dividers in the page ground between segments, so even close
   neighbours have a hard edge.
3. **Percentages printed inside the bar** on the three largest bands — reversed
   to paper on the darkest two. This is the real fix: you read the split without
   matching colour to a legend at all. The bar grows to 40px to hold them.
4. **Per-row share bars** replacing swatches. Length comparison is a stronger
   read than hue matching ever was.

Rows are `rank | name | bar | % | chars | note`.

**The principle:** when a colour encoding is hard to discriminate, don't just
tune the colours — add an encoding that doesn't depend on them. Position, length
and printed value now all carry the same information.

---

## 11. Ingest volume

Four rows — fetched / after filter / blocked / yFinance — one line each, no
chart, no colour. It is the least actionable material on the page and is sized
accordingly.

---

## 12. Expanders

The eight inline `chart_data_table` blocks become the site's standard door:
hairline box, 10.5px steel uppercase summary, rotating caret, no fill.
Auditability is preserved, page length roughly halves, and a door sized to the
eyebrow label declares itself as chrome rather than content.

---

## 13. Colour assignment

| Role | Colour | Where |
| --- | --- | --- |
| Metric identity | gold / teal / indigo / violet / moss | strip cells, and each section tied to its metric |
| Share of a whole | ordered indigo ramp | prompt composition |
| Threshold breached | terracotta | any strip cell over its limit |
| Health / structure / guidance | steel | status dot, eyebrows, diagnosis rail, doors |
| Counterfactual | muted neutral | "without cache", cache misses |
| Metadata | `--color-text-3/4` | labels, notes, ranges, raw counts |

No signal colours and no up/down green-red anywhere on this page — **stated in
the page footer**, because a reader arriving from the Watchlist needs to know
the rules changed. That is the honest cost of giving one page its own palette,
and the footer is where it is paid.

---

## 14. Testing

**Unit (`tests/test_pipeline_metrics.py`, new):** cost stats exclude pre-cutover
rows from total/mean/cumulative; the monthly projection matches cadence ×
mean; cache ratio and savings; prompt composition shares sum to 100% and sort
descending; threshold evaluation returns breach for a known-bad row and clear
for a known-good one; the reliability count reads real warning JSON; empty and
single-row frames don't raise.

**Page (`tests/test_app_pages.py`):** the page still boots via AppTest; the
verdict band renders one of the three status words; no pre-cutover row reaches
a total.

**Tokens:** the five metric pairs exist in `theme.css` for both themes and match
`lib/charts.METRIC_COLORS`; the no-raw-hex rule still passes.

**Live DOM (`tests/visual/test_pipeline_dom.py`, new):** the endpoint dot stays
circular (width == height) and inside its cell at two viewport widths — the bug
that motivated the HTML-element dot; the threshold line clears its contrast
floor; a breached cell paints terracotta on rail, label and dot together.

**Visual:** `pipeline-stats` is in the baseline set and gets regenerated.

**Changelog:** the cutover arithmetic change is user-visible and lands an entry.

---

## 15. Out of scope

- Changing what the pipeline records. This page renders existing columns.
- Retro-fitting the metric palette to any other page. It is legal here *because*
  this page has no signals.
- Reworking the sidebar range control.
