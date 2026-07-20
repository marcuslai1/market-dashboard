# Reader Retrospective page — design

**Date:** 2026-07-20
**Origin:** MarketReport capability-gap survey 2026-07-19, item #8 ("Reader-facing
periodic retrospective" — PARTIAL: accuracy tables exist; no periodic "what we
called / what happened" narrative digest; presentation feature; must carry the
single-regime honesty banner).
**Decisions taken with user 2026-07-20:** dashboard-side templated narrative
(no upstream change, no LLM) · monthly cadence with archive · new page ·
call-ledger derivation from `signal_log.csv` · scope = signal narrative + one
paper-book line.

## Purpose

A dedicated page that tells, in plain language, month by month: what calls the
pipeline made, and what actually happened to them. The existing accuracy
surfaces (Signal Tracker scorecard/ledger, Briefing calibration band) answer
"is the system any good" in aggregate numbers; this page answers "what did you
tell me in June, and were you right?" as a readable story. Verdict-first,
jargon-free, honest about immaturity.

## Placement & architecture

- New module `components/retrospective.py` exposing
  `render_retrospective_page(...)`.
- Registered in `dashboard.py` (`_page_retrospective`,
  `url_path="retrospective"`, nav title **"Retrospective"**); masthead nav
  picks it up from the `_PAGES` registry.
- Inputs (all existing loaders, no new data files):
  - `load_signal_log()` — `data/signal_log.csv`, the pipeline's exported call
    ledger: per-day rows with `date, ticker, signal, entry_price,
    invalidation, upside_target, price_after_5d/10d/20d, hit_invalidation,
    hit_upside_target`.
  - `load_paper_nav()` — paper-book NAV; the headline book is chosen with the
    Paper Book band's own `select_policy` rule so both surfaces always
    describe the same lane.
  - Latest report's `calibration_insights.confidence_banner` — the honesty
    banner text.
- All derivation lives in pure functions (testable without Streamlit);
  rendering is templated HTML using existing theme primitives plus a small
  `retro-*` class family in `theme.css`. Single-column list layout — no wide
  tables, so no special mobile reflow.

## Derivation rules

1. **One row per call (dedupe).** The CSV logs each actionable signal daily;
   collapse consecutive same-`(ticker, signal)` runs to their first row —
   the same rule `compute_signal_accuracy` uses. Directional calls only:
   BUY / ACCUMULATE / CAUTION / AVOID. WATCH and HOLD are excluded, with a
   one-line caption saying so (non-directional / not scored here).
2. **Month attribution.** A call belongs to the calendar month of its first
   day. Verdicts come only from the call's own fixed 5/10/20-session window —
   never re-marked to the latest price — so a finished month's story never
   changes afterwards.
3. **Verdicts.**
   - **BUY / ACCUMULATE:** `hit_upside_target` → ✓ "hit its target";
     `hit_invalidation` → ✗ "stopped out"; **both** flags set (window touched
     both levels, order unknown) → scored by the sign of the 20-session
     return, with a "hit both levels" note; neither flag but
     `price_after_20d` present → verdict by return sign ("up/down X% after
     20 sessions"); otherwise ⏳ too early.
   - **CAUTION / AVOID:** verdict by 20-session return sign — fell →
     ✓ "staying out was right"; rallied → ✗ "rallied X% instead" (a
     cautioned name running up through its upside level reads as exactly
     that). No 20-session price yet → ⏳ too early.
4. **Sentence shape.** Each entry is one plain sentence carrying the concrete
   call: signal pill, ticker (via `display_ticker`), entry price, target/stop
   where present, outcome with the realized percentage. Example:
   "✓ ACCUMULATE AMD @ $203.43 (target $218.84) — hit its target inside 20
   sessions (+16.4%)."
5. **Paper-book line.** Headline book's NAV percent change over the month
   (last NAV at-or-before month start → last NAV in month) vs SPY and SOXX
   from the same CSV's `spy_close` / `soxx_close`. Omitted when the month has
   no NAV rows.

## Page layout (top to bottom)

1. **Honesty banner** — always rendered, above everything: the latest
   report's `confidence_banner` verbatim when present, else the fixed
   fallback "Track record spans mostly a single market regime — read these
   verdicts as provisional, not proven."
2. **Month picker** — newest first, default = current month, labeled
   "<Month> so far — month in progress" while incomplete.
3. **Headline verdict line** — "N new calls, M resolved, K went our way ·
   paper book +x% vs SPY +y%, SOXX +z%".
4. **Three groups** — **What worked** / **What didn't** / **Too early to
   judge**, each a list of verdict sentences.
5. **Caption** — returns here are raw price direction, not
   benchmark-relative; points at the Briefing calibration band for the alpha
   view (mirrors the Signal Tracker's wording so the surfaces cannot
   contradict each other). Also notes WATCH/HOLD exclusion.

## Honesty & edge cases

- The banner precedes the picker, so no month renders without it.
- **Retired tickers stay in.** The page is about what we *said*; filtering
  `RETIRED_TICKERS` here would be survivorship bias. Deliberate divergence
  from the Watchlist filter — documented in a code comment.
- Empty states: missing/empty `signal_log.csv` → honest "no calls logged
  yet" page, no crash. A month whose calls are all unresolved still renders
  ("0 resolved so far"). Missing prices coerce to NaN → ⏳ bucket.
- Malformed rows (non-numeric prices) are coerced, never raised.

## Testing & rollout

- `tests/test_retrospective.py`:
  - unit tests for the pure builders — streak dedupe, month attribution,
    every verdict branch (target hit, stop hit, both-flags, return-sign,
    too-early), CAUTION/AVOID inversion, paper-book month return;
  - `AppTest.from_function` smoke test on the page (nav-reset gotcha; no
    bare CSS-class assertions).
- Same-session chores: `data/changelog.json` entry; visual-baseline regen
  for the new page (Docker via PowerShell); Streamlit server restart needed
  to see the new lazily-imported page module.

## Out of scope (recorded, not planned)

- Scenario recap and methodology-changes fold-in (user declined for v1).
- Upstream-authored (LLM) narrative block — templated dashboard-side prose
  chosen instead; no render hook reserved.
- WATCH scoring ("the one that got away") — excluded from v1.
- Any new upstream export or `signal_log.csv` schema change.
