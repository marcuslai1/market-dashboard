# AI Capex Pulse — datasheet legibility rework

Date: 2026-07-22 · Status: **approved design, pre-implementation**
Second legibility pass over the presentation of
`docs/superpowers/specs/2026-07-03-capex-pulse-redesign-design.md`. Same five
signals, same data, same "human-read cross-check, not a wired signal" contract.
Nothing here changes the scenario odds or adds an analytic signal.

## Problem

The 2026-07-03 pass fixed the band's self-contradiction **in the data** and the
owner still cannot read it. Reconfirmed 2026-07-22 against the live render.

1. **The reconciliation is the least visible thing on the card.** The gap hero
   prints `-18.6pp (rev +50.3% - capex +68.9%)`; the revenue chip 100px below
   prints `median +85.2%`. The sentence that reconciles them — "revenue has
   since risen to +85.2% … the next gap may narrow" — renders at 11.5px in
   `--ink-3`, the dimmest ink on the card. The reader takes the two numbers and
   never reaches the footnote. The 2026-07-03 decision was right; its *visual
   weight* was not.

2. **The figures are not self-explaining.** `PEG 0.63`, `80th pct 29.5`,
   `circularity node`, `fragile tier`, `-18.6pp` (points of what?) all assume
   vocabulary the reader does not have. `sub` exists but carries a *definition*
   ("combined MSFT/GOOG/AMZN/META capex, year-over-year"), not a consequence.

3. **Six boxes where one would do.** The band renders the verdict, the gap hero
   and four tiles as six separately bordered blocks — each `1px` framed with a
   `3px` colored left border — nested inside the page's filled `.card` surfaces.
   Boxes inside boxes read as clutter, and tone repeated six times as a colored
   border makes color noise rather than signal.

## Decisions resolved (this session)

| Decision | Resolution |
|---|---|
| Layout shape | **One datasheet plate.** Verdict header + a five-row table: `No · Measure · Value · What it means`. Chosen by the owner over "lead with the sentence" and "question and answer" treatments. |
| Where meaning lives | **A "What it means" column at full text weight**, one plain-English clause per row. Not a footnote, not a tooltip, not an expander. |
| The two revenue figures | **Reconciled inside row 03's remark**, in the same row as the number it qualifies. |
| Row order | **Inputs before the derived figure**: capex, customer sales, then the gap between them. Arithmetic in reading order. The gap loses its hero position. |
| Remark authorship | **Derived, never authored.** Every remark is a formatting of fields the chip builder already computes. No hand-curated prose, no new analysis. |
| Density and color | **Hairline rows inside one frame**; tone becomes a single dot per row instead of a 3px border on six blocks. |
| Jargon | Leaves the visible table; survives in the History expander and the a11y table. |

## 1 · The plate

```
AI CAPEX PULSE                    Digestion cross-check · as of 2026Q1
+- THE READ ---------------------------------------------------------+
| DIGESTING  Spending is outrunning the sales it buys - the cycle     |
|            is still growing, but the gap bears watching.            |
+----+-----------------+----------+----------------------------------+
| No | Measure         | Value    | What it means                    |
+----+-----------------+----------+----------------------------------+
| 01 | Capex growth    | +68.9%   | Up from +61.9% - still building  |
| 02 | Customer sales  | +85.2%   | Flat since May, still ahead      |
| 03 | Coverage gap    | -18.6pp  | Q1 only. Sales have since run to |
|    |   (2026Q1)      |          | +85.2%, so the next print likely |
|    |                 |          | narrows.                         |
| 04 | Chip valuations | 25.4x    | Mid of its own 3-year range      |
| 05 | Weakest borrower| CRWV     | Debt-funded; first to crack      |
+----+-----------------+----------+----------------------------------+
                                                         History >
```

`Measure` names are plain-English renames of the chip labels:

| chip key | current label | plate label |
|---|---|---|
| `capex` | Capex | Capex growth |
| `rev` | Beneficiary revenue | Customer sales |
| `gap` | Coverage gap | Coverage gap *(quarter appended)* |
| `val` | Valuation | Chip valuations |
| `fragile` | Fragile tier | Weakest borrower |

## 2 · Column contract

`build_chips` in `lib/capex.py` gains two derived fields per chip. Both are
formatting of inputs the builder already has; no new computation, no new data
source, and `tone` / `arrow` / `asof` logic is untouched.

- **`value`** — the bare figure, no prose. `"+68.9%"`, `"-18.6pp"`, `"25.4x"`,
  `"CRWV"`. `"—"` when the chip degrades.
- **`remark`** — one plain-English clause, target <= 90 chars (row 03 is the
  documented exception; its reconciliation runs longer and wraps).

`detail` and `sub` are retained unchanged — the History expander and the
accessibility table keep consuming them, and existing tests assert on them.

### Remark rules

Every remark must satisfy all four, enforced by unit test where mechanical:

1. **No undefined vocabulary.** No `PEG`, `pp`, `percentile`, `circularity
   node`, `fragile tier`, or a bare ticker without its role.
2. **Derived only.** Traceable to a field the chip builder computed. If it
   cannot be derived, the remark is `""` and the row shows value only.
3. **States the consequence, not the definition.** "Up from +61.9% — still
   building", not "combined MSFT/GOOG/AMZN/META capex, year-over-year".
4. **Never contradicts another row.** Row 03 must name the period mismatch that
   makes its figure disagree with row 02.

## 3 · What changes in `components/briefing/capex_pulse.py`

`_verdict_html`, `_hero_gap_html` and `_signals_html` are replaced by a single
`_datasheet_html(verdict, rows)`. The `● healthy · ● watch · ● stress · ▲▼ =
direction only` key strip is deleted — with a remark column the legend is
redundant.

Unchanged: `compute_verdict` and its "never fake a green light" INSUFFICIENT
DATA rule, `forward_revenue_note` (now feeding row 03's remark rather than a
footnote), the curation-overdue banner, the History expander and every chart in
it, and chip-by-chip degradation.

New styles go in `assets/theme.css` under a `.capex-sheet` block, using existing
tokens (`--rule`, `--ink-2`, `--ink-3`, `--mono`, `--radius-card`). No new tokens.

## 4 · Degradation

The band already degrades chip-by-chip and must continue to.

| Condition | Behaviour |
|---|---|
| A chip is missing | Its row is omitted; `No` renumbers so the sequence has no holes. |
| All chips missing | `render_capex_pulse` returns early, as today. |
| `gap_available` false | Verdict shows INSUFFICIENT DATA; row 03 omitted. |
| `forward_revenue_note` is None | Row 03's remark states the quarter only, with no forward clause. |

## 5 · Testing

- Unit tests for `value` / `remark` derivation per chip key, including every
  degraded path in §4.
- A unit test asserting no remark contains the vocabulary banned by §2 rule 1.
- An AppTest asserting the section renders its rows and that the verdict label
  still appears.
- `tests/visual/baselines/briefing.png` regenerated in the pinned image.
- Existing `tests/test_design_tokens.py` must stay green — no signal-palette edits.

## 6 · Typographic contract

The owner's "more compact" means Industry's *discipline*, not merely tighter
spacing — declared geometry, one rhythm, contrast chosen per step. Compactness
alone would make the card denser, not clearer.

**Fixed geometry.** The plate is `table-layout: fixed` with an explicit
`<colgroup>`; every column is a declared width. This is the specific fix for
"the boxes are all differently sized" — today's four tiles are
`flex: 1 1 200px; min-width: 190px`, so each sizes to its own content and no two
match. Nothing in the plate may size to content.

| column | width |
|---|---|
| `No` | 3.5ch |
| `Measure` | 22% |
| `Value` | 14%, `white-space: nowrap`, tabular figures |
| `What it means` | remainder |

**One rhythm.** A 22px leading unit (14px body at 1.5, the existing
`.card-body` metric). Every vertical padding and margin in the plate is a whole
or half unit — 11px or 22px, nothing else. A single-line row is therefore 44px
and row 03 grows by whole units as it wraps, so the rules stay on the lattice.

**Ink per step**, measured on `--paper-2` (#1B1B16):

| element | token | ratio |
|---|---|---|
| Value | `--ink` | 15.06:1 |
| Measure, **What it means** | `--ink-2` | 9.75:1 |
| Column headers, `as of` furniture | `--ink-3` | 5.03:1 |
| — | `--ink-4` | 2.51:1 — **fails; banned for text in this plate** |

Putting the remark at `--ink-2` body size is the whole point of the rework: the
clause that reconciles rows 02 and 03 currently renders at 11.5px in `--ink-3`,
the dimmest ink on the card.

**Rules, not boxes.** One `1px solid var(--rule)` frame around the plate;
hairline row separators inside it. No per-row borders, no `3px` colored left
borders, no nested filled surfaces. Tone appears once per row as an 8px dot in
the `No` cell.

## Out of scope

- **Macro Trigger Map current lean.** The owner wants to know which way each
  event is pointing. `macro_trigger_map` entries carry only `event`, `date`,
  `bullish_outcome`, `bullish_upgrades`, `bearish_outcome`, `bearish_impact` —
  perfectly symmetric, with no lean field. Showing one would require either
  inventing a signal (violating the presentation-layer contract) or adding a
  field upstream in the `MarketReport` pipeline. Tracked separately.
- **Rolling the datasheet grammar to other sections.** Deliberately a pilot;
  reassess after this ships.
- **Page-wide density and color harmonisation.** The compactness win here is
  local to this card.
- **Briefing section order.** Confirmed natural as-is; the 2026-07-22 inversion
  experiment on branch `briefing-reorder` is rejected and will not ship.
