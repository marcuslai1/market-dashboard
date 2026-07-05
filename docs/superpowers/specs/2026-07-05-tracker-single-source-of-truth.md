# Signal Tracker · one measurement engine — design

- **Date:** 2026-07-05
- **Status:** Proposed — needs pipeline-side work (upstream repo); dashboard side is staged to be safe at every step
- **Origin:** Review of the 7eab190→0fc84b1 tracker simplification arc. Each commit in that arc
  (readiness meter, raw-vs-alpha caption, ghosted thin cells) patched *coherence between two
  measurement systems* with labels. This spec removes the second system instead.

## Problem

The tracker page runs its own performance math, in the presentation layer:

- `compute_signal_accuracy` (`components/signal_tracker.py`) — re-derives **5-session raw price
  direction** per signal from the SQLite price table, per render (cached per corpus fingerprint).
- `build_signal_episodes` — trade-economics episodes carrying **position semantics** (BUY/ACCUMULATE
  held through HOLD/WATCH, closed by the next CAUTION/AVOID; CAUTION measured until the next
  BUY/ACCUMULATE). That is strategy logic, not presentation.

Meanwhile the pipeline exports its own disciplined self-assessment —
`calibration_insights.signal_performance` (10d matured calls, win rate, **alpha vs benchmark**,
regimes) — rendered on the Briefing's calibration band, and since 0f1da44 framing the tracker via
the readiness meter.

So one page shows numbers from **two engines**: the meter says "713 matured calls" (pipeline, 10d)
while the cell under it says "right 4 of 7 · 5d" (dashboard, 5d). A reader cannot reconcile them;
the caption pointing at the Briefing is a disclaimer, not a fix. The engines can silently drift
(different maturation rules, windows, sample floors) — on the page whose entire job is credibility.
It also violates the repo's own division of labor: the dashboard renders upstream reports; it does
not measure.

## Goal

One measurement engine — the pipeline. The dashboard renders exported numbers and keeps zero
return-math of its own. The tracker's local computations survive only as a **labeled fallback** for
reports that predate the new export.

## The page contract (what each tier answers — the yardstick for future edits)

| Tier | Question it answers | Scope | Deliberate properties |
|---|---|---|---|
| 1a. Readiness meter | "Can I trust any of this yet?" | corpus | regimes seen / matured / decision-grade; warns until ≥2 regimes |
| 1b. Scorecard | "Which call types work?" | corpus | **unaffected by the name filter** — calibration is a property of the system, not a hand-picked subset; thin cells ghosted |
| 2. What we've changed | "Is the methodology stable?" | — | hand-maintained `data/changelog.json`; staleness surfaced via "latest YYYY-MM-DD" in the header |
| 3. Drawers (collapsed) | "Which names? What flipped?" | name-filtered | filter lives *here*, scoping only these |

Deliberately excluded (do not re-add without revisiting this spec):
- The paper-trade-outcomes block — cut 2026-07-04 as a third scoring system; `signal_log.csv`
  still exports. If realised P&L returns, it is **one line in the scorecard**, not a table.
- Raw-sign coloring of returns (ST-1) — a correct CAUTION call must never render red.

## Pipeline export additions (`calibration_insights`, upstream repo)

1. **Scorecard cells** — per signal bucket, alongside the existing 10d fields:

   ```json
   "signal_performance": {
     "BUY": {
       "n_matured_10d": 10, "win_rate_pct": 50.0, "alpha_10d": -0.5, "...": "...",
       "raw_direction_5d": {"n": 7, "right": 4}
     }
   }
   ```

   Same dedup rule the dashboard uses today (first day of each consecutive same-signal streak),
   computed from the pipeline's price series. Optionally also `raw_direction_10d` so the tracker
   can one day offer the same window as the Briefing band instead of the 5d/10d split.

2. **Episodes** — the trade-economics ledger rows, semantics identical to
   `build_signal_episodes` (its docstring is the normative text; port the dashboard's episode
   tests — active-position latest-price, AVOID-closes-BUY, verdict rules — with it):

   ```json
   "episodes": [
     {"ticker": "NVDA", "signal": "BUY", "start": "2026-05-02", "end": "2026-05-20",
      "entry_price": 100.0, "exit_price": 112.0, "exit_date": "2026-06-01",
      "return_pct": 12.0, "peak_run_pct": 15.0, "is_active": false, "verdict": "✓ profit"}
   ]
   ```

   Tickers in report style (underscores), matching `watchlist` keys — the dot/underscore
   conversion (`_report_ticker_to_db`) then dies with the dashboard-side math.

## Dashboard migration (staged; each step ships alone and is revertible)

1. **Scorecard adapter.** `_scorecard_cells(latest_report, sig_df, prices_df)` prefers
   `raw_direction_5d` from the latest report; falls back to `compute_signal_accuracy` when absent
   (all 85 existing reports). Fallback renders exactly today's output → **no visual change** until
   the pipeline ships. When falling back, the scorecard caption appends "computed by the dashboard
   (older report)" so the source is never ambiguous.
2. **Ledger adapter.** Same pattern for episodes: prefer `calibration_insights.episodes`, fall back
   to `build_signal_episodes`. The sidebar date filter and the name filter keep working — they
   become plain row filters over exported episodes (presentation-layer filtering is fine; the
   *math* is what moves upstream).
3. **Retire the fallbacks** once every report in the default rendered window carries the export.
   `compute_signal_accuracy`, `build_signal_episodes`, `_report_ticker_to_db` and their tests move
   to the pipeline or are deleted; the tracker keeps only HTML builders and reducers.
4. **(Optional, cheap honesty)** While both sources coexist in CI: a test fixture with one report
   carrying `raw_direction_5d` asserts the adapter's preference order, and one real-corpus test
   asserts fallback output still matches today's golden numbers — drift between engines becomes a
   red test, not a silent divergence.

## Error handling

- `calibration_insights` absent / old schema → fallback path, labeled (step 1); never raises.
- `raw_direction_5d.n == 0` or missing bucket → the existing "not enough yet" cell.
- `episodes` present but empty → the existing "No actionable episodes" info line.
- Malformed episode rows (missing keys) → skipped row-wise with `.get()`, same tolerance the
  changelog strip has for malformed entries.

## Testing

- Adapter unit tests: prefer-exported / fallback-local / mixed-corpus (dashboard repo).
- Golden fixture: one frozen real report + the new keys → scorecard and ledger HTML snapshot
  (string-level, not pixels).
- Episode-semantics tests ported upstream with the math (the normative suite).
- Visual baselines: unchanged at step 1 (fallback is byte-identical); one deliberate regen when
  the exported numbers first differ from locally computed ones — expected and called out in the
  step-2 commit message.
- `pytest -q`, `ruff check .`, AppTest page walk stay green throughout.

## Non-goals

- No change to what the pipeline *measures* — only where already-defined measurements are computed.
- No new page, no new metrics, no 5d→10d window switch in v1 (a labeled follow-up once
  `raw_direction_10d` exists).
- The Briefing calibration band is untouched — it already reads the pipeline directly.
