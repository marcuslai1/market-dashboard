# AI Capex Pulse — legibility redesign

Date: 2026-07-03 · Status: **approved design, pre-implementation**
Supersedes the presentation of: `docs/superpowers/specs/2026-07-03-capex-pulse-design.md`
(the original band design). This is a **legibility rework only** — same five
signals, same data, no new files. Nothing here changes the scenario odds or the
"human-read cross-check, not a wired signal" contract.

## Problem

The band renders five computed chips but is hard to read — confirmed by its own
owner. Three concrete failures:

1. **No bottom line.** The original design's deliverable was
   *"Capex accelerating ▲ · Gap widening ⚠ · … → 'Cycle intact, watch the gap.'"*
   — note the `→` verdict. The chips shipped; the synthesizing line never did, so
   the reader assembles five signals into a judgment unaided every time.
2. **The band contradicts itself on its headline signal.** The Coverage-gap chip
   shows **−18.6pp** (revenue +50.3% *as of when Q1 was reported* − capex +68.9%),
   while the "Current read" caption computes **≈ +16pp** (today's revenue +85.2% −
   that same Q1 capex). Opposite signs, side by side, unreconciled — it reads as a
   bug and erodes trust.
3. **Color means different things per chip.** ✅ rising revenue = good, ⚠ rising
   valuation = bad, ▲ accelerating capex = accent/neutral. "Up" is good in one
   chip and bad in another, so the color carries no consistent meaning.

## Decisions resolved (this session)

| Decision | Resolution |
|---|---|
| Surface vs fold | **Keep all five signals visible every time**, made legible, with a summary line on top. No collapsing behind an expander. |
| The two conflicting gap figures | **One dated gap + a separate forward note.** Show a single coverage gap anchored to the last reported quarter; present today's higher revenue as a forward-looking note, never as a competing gap number. |
| Layout shape | **Verdict + refined list** (smallest safe change). Reuse the existing chip + degradation logic; add a verdict line, promote the gap to an accented hero item, add plain sublabels, unify color. |
| Verdict authorship | **Auto-derived from the chip states** (not hand-written) — cannot contradict the chips, adds no curation chore. |

## 1 · The verdict line (new)

A headline state + one-sentence gloss, rendered on top of the chips. Derived
purely from the computed signals via a new pure function in `lib/capex.py`:

```
pulse_verdict(gap_available, gap_pp, rev_falling, fragile_red) -> {state, gloss}
```

State rule — the **digestion axis** (gap + revenue + fragile); valuation is
narrated in the gloss but never sets the state on its own:

- **INSUFFICIENT DATA** — `not gap_available` (the core signal is missing; never
  fake a green light).
- **CRACKING** (red) — `fragile_red` **or** (`gap_pp < 0` **and** `rev_falling`).
- **INTACT** (green) — `gap_pp >= 0` **and** `not rev_falling` **and** `not
  fragile_red`.
- **DIGESTING** (amber) — anything in between (today's state: gap negative but
  revenue rising, valuation rich, CRWV amber).

Inputs come from the existing computations: `gap_pp`/`gap_available` from the last
row of `coverage_gap_series`; `rev_falling` from the revenue-trend delta
(`<= -REV_FLAT_PP`, the `_rev_chip` logic); `fragile_red` from the fragile chip's
`flag == "red"`.

Gloss is a static sentence per state (numbers live in the chips, so the verdict
stays qualitative). Baseline copy — refine wording at implementation:

- INTACT — "Revenue is keeping pace with the spending it's built on — cycle looks intact."
- DIGESTING — "Spending is outrunning the revenue it produces — the cycle is still growing, but the gap bears watching."
- CRACKING — "The spend/revenue gap is opening while the demand or the fragile name is under stress — treat as an early crack."
- INSUFFICIENT DATA — "Not enough complete capex quarters yet — showing the signals we have."

The rule is a **documented presentation choice, not a calibrated signal** — same
disclaimer `lib/capex.py` already carries for its thresholds.

## 2 · Coverage gap → hero item (kills the contradiction)

Rendered first and visually accented. **One dated number + a separate forward
note**, never a second subtracted gap:

```
COVERAGE GAP   ● −18.6pp   as of Q1 FY26 earnings
               (rev +50.3% − capex +68.9%)
  ↳ revenue has since risen to +85.2% (2026-07-03); the matching
    capex quarter isn't reported yet, so the next gap may narrow
```

Code change: today's `current_read()` subtracts *today's* revenue from *last
quarter's* capex to produce the misleading +16pp gap. Replace it with:

```
forward_revenue_note(capex, fund_df) -> dict | None
```

- Anchored figure = last `coverage_gap_series` row's `rev_growth_pct` + `rev_asof`.
- Live figure = `_median_rev_growth(fund_df, beneficiaries)` with no anchor →
  `(now_date, now_med)`.
- Return `None` when `now_date <= rev_asof` (no fresher data) or when the move is
  within `±REV_FLAT_PP` (flat — no note).
- Otherwise `direction = "risen"` (→ "may narrow") if `now_med > anchor +
  REV_FLAT_PP`, else `"fallen"` (→ "may widen").

This reuses exactly the two numbers that currently look contradictory (+50.3
anchored, +85.2 live), reframed as **then → now** rather than a phantom gap. The
gap's own "widening / narrowing / stable" word stays and is clearly the
quarter-over-quarter trend.

## 3 · The other four, made legible + one color model

**color = health, arrow = direction.** They are decoupled:

- **● dot** = health only: `good` (green `STATUS_POS`) · `watch` (amber
  `STATUS_WARN`) · `stress` (red `STATUS_NEG`) · `neutral`/`na` (grey
  `INK_FALLBACK`). No new color constants.
- **▲ / ▼** = direction, purely informational (or absent).

Per-chip tone assignment:

| Chip | tone | arrow | sublabel (plain, on the surface) |
|---|---|---|---|
| Capex | **always `neutral`** — accel is neither good nor bad; the gap judges it | ▲ accel / ▼ decel / none steady | "combined MSFT/GOOG/AMZN/META capex, year-over-year" |
| Coverage gap | `good` if `gap_pp >= 0` and not narrowing-fast, else `watch`; `na` if no data | none | "beneficiary revenue growth minus capex growth — negative = spend outrunning sales" |
| Revenue | `good` if rising/flat, `watch` if falling, `na` | ▲ rising / ▼ falling / none | "median sales growth of the chip names that sell into that capex" |
| Valuation | `good` within range, `watch` if rich, `na` | none | "Semis forward P/E vs its own recent range" |
| Fragile | `stress` red, `watch` amber, `good` green, `na` unflagged/none | none | "the debt-funded name most likely to crack first; NVDA–CRWV circularity node" |

A one-line key row spells it out: `● healthy · ● watch · ● stress   ▲▼ = direction only`.

Chip dict shape changes from `{state, detail}` to
`{key, label, sub, tone, arrow, detail, asof}`. `build_chips` still returns all
five (gap included); the component pulls the gap chip out to render as the hero
and renders the other four as the keyed list.

## 4 · UI composition (`components/briefing/capex_pulse.py`)

Order within the band:

1. `render_section_head("AI Capex Pulse", "Digestion cross-check — human-read, not a wired signal")` (unchanged).
2. Curation-overdue banner (unchanged).
3. **Verdict band** — colored dot + STATE + gloss.
4. **Hero gap row** — label, tone dot, dated number, arithmetic, `↳` forward note when present.
5. **The four** — capex, revenue, valuation, fragile as a legible list (dot + label + arrow + value + sub), then the key row.
6. Coverage-gap chart + data table (**unchanged**).
7. "Cluster fundamentals over time" expander (**unchanged**).

## 5 · Honesty & degradation (preserve existing discipline)

- Every chip still degrades to explicit `na` copy — never a silent blank.
- Verdict degrades to **INSUFFICIENT DATA** when the gap (core signal) is missing,
  rather than defaulting to INTACT.
- Forward note is omitted when there is no fresher revenue or the move is flat.
- Curation-overdue tag and all `parse_capex` warning surfacing are unchanged.
- Detail/sub text keeps going through `_escape_dollars` / HTML-escaping (the
  existing `<script>` escaping test must still pass).

## 6 · Testing (TDD, red before green)

`tests/test_capex.py` (pure functions):
- `pulse_verdict`: INTACT (gap≥0, rev not falling, fragile not red), DIGESTING
  (gap<0, rev rising), CRACKING via `fragile_red`, CRACKING via (gap<0 & rev
  falling), INSUFFICIENT DATA (gap unavailable); boundary at `gap_pp == 0`.
- `forward_revenue_note`: risen→"narrow", fallen→"widen", flat→None, no-fresher-data→None.
- chip fields: capex tone always `neutral`; revenue falling→`watch`; valuation
  rich→`watch`; fragile red→`stress`, amber→`watch`, green→`good`; every chip has
  a non-empty `sub`.

`tests/test_capex_pulse.py` (HTML helpers — extend, and **update the existing
`CHIPS` fixture / ▲⚠ assertions** to the new chip shape):
- verdict HTML renders the state word + gloss; escapes embedded HTML.
- the four-item list renders tone dots, direction arrows, and sublabels.
- degraded: empty capex → verdict "INSUFFICIENT DATA", gap reads "needs capex
  data", band does not crash.
- forward note present when fresher revenue exists; absent otherwise.

`tests/test_app_pages.py`: existing Briefing page-walk still asserts the band
renders (extend to assert the verdict text appears).

## Files touched

- `lib/capex.py` — add `pulse_verdict`; replace `current_read` with
  `forward_revenue_note`; add `tone`/`arrow`/`sub` to each chip in `build_chips`.
- `components/briefing/capex_pulse.py` — verdict band, hero gap row, keyed
  four-item list, color key; chart + expander untouched.
- `tests/test_capex.py`, `tests/test_capex_pulse.py` — per §6.

## Out of scope (deliberate)

- The coverage-gap chart, the cluster-fundamentals expander, the earnings
  cascades, and the `capex_quarterly.json` / corpus data — all unchanged.
- Mechanical wiring of the verdict into scenario odds (stays advisory, per the
  original design).
- Any new chip or data source (margins / book-to-bill / HBM ASP remain out).
