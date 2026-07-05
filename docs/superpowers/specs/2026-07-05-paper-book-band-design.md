# Paper-book band + thin/episodes adoption — design

- **Date:** 2026-07-05
- **Status:** Approved (brainstorm 2026-07-05)
- **Origin:** The upstream bot-paper-portfolio spec (`MarketReport/docs/superpowers/specs/
  2026-07-05-bot-paper-portfolio-design.md`) ships the engine and defers one item here:
  *"Dashboard band later (separate repo; joins the deferred thin/episodes rendering queue)."*
  This spec is that item: render the paper book, and adopt the new per-cell thin/episodes
  calibration fields (upstream commit 5dc0fa3).

## Context

The pipeline now runs a mechanical paper portfolio (`policy_id = "v1_flat10"`, replay-seeded
from 2026-04-19, Measurement-Gate-exempt). It stores trades/positions/NAV in SQLite and attaches
a summary block to each report. The dashboard renders none of it yet:

- **`report.paper_portfolio`** (ships with the next pipeline run): `nav_pct, cash_pct,
  n_positions, nav_return_pct, spy_return_pct, soxx_return_pct, positions[] (ticker, weight_pct,
  stop, tranches, max_dd_pct), trades_today[], trade_counts, inception, as_of, banner, policy_id`.
  Summary only — no series.
- **`paper_portfolio_nav`** (SQLite, upstream): the daily NAV curve, including the ~2.5 months of
  replay-seeded history. Not exported by `export_to_dashboard` today.
- **`calibration_insights.signal_performance.per_signal`** now also carries `thin`, `n_episodes`,
  `alpha_episode_mean_10d`, `alpha_median_10d`, `alpha_min_10d`, `alpha_max_10d` (5dc0fa3).
  No report in the current corpus (≤ 2026-07-04) has these fields or the portfolio block.

## Decisions (brainstorm 2026-07-05)

1. **NAV source:** upstream exports `data/paper_nav.csv` (new ~5-line addition to
   `export_to_dashboard`, same pattern as the existing four CSV exports). Full curve including
   seeded history; the pipeline stays the single measurement engine.
2. **Home:** Signal Tracker page — its whole job is "can I trust the bot's calls?"; the NAV curve
   is the end-to-end answer.
3. **Thin/episodes:** adopted as the honesty gate on the Briefing calibration band, with the
   local heuristic as the labeled fallback for older reports.

## Page-contract revision (Signal Tracker)

The 2026-07-05 tracker single-source-of-truth spec excluded the paper-trade-outcomes block as
"a third scoring system" and said not to re-add it without revisiting that spec. **This is that
revisit.** The excluded thing was *dashboard-computed* trade economics from `signal_log.csv` —
a third engine. The paper book is the pipeline's own single-engine measurement, exported like
everything else the page renders; the exclusion's rationale (no dashboard-side scoring math) is
preserved. The contract gains one tier:

| Tier | Question it answers | Scope | Deliberate properties |
|---|---|---|---|
| 1c. Paper book | "Does the judgment compound into money?" | corpus | unaffected by the name filter (same rationale as the scorecard); pipeline numbers only; single-regime banner rendered verbatim |

Position on the page: between the scorecard (1b) and "What we've changed" (2).

## Data contract

- **`data/paper_nav.csv`** — `policy_id, date, nav_units, cash_units, n_positions, spy_close,
  soxx_close`, one row per session since inception (2026-04-19), mirroring the
  `paper_portfolio_nav` schema. Integer units as stored; the dashboard divides at the render
  edge (upstream convention). The dashboard filters to the `policy_id` named by the latest
  report block; when the block is absent, the curve renders only if the CSV carries exactly one
  distinct `policy_id` (otherwise skip — never mix side-by-side policy variants into one curve).
- **Dashboard math budget:** rebasing the three series (NAV, SPY, SOXX) to 100 at their own
  first row — a presentation transform of exported values. No maturation rules, no win/loss
  scoring, no position semantics, no other return math. This keeps the band inside the
  single-source-of-truth line: the dashboard renders measurements, it doesn't make them.

## The band

New module `components/paper_book.py` (HTML builders + one Plotly figure + reducers), rendered
by the tracker page. New loader `lib/data_loader.load_paper_nav()` — mtime-keyed
`st.cache_data`, `_safe_read_csv`, like the other loaders.

- **Verdict line first** (house style): e.g. **"Paper book +4.2% since Apr 19 vs SPY +6.1% —
  trailing the benchmark."** Tone from the sign of NAV−SPY return (leading / tracking /
  trailing); "seeded — first fills pending" wording when returns are None (seed day), mirroring
  the upstream Telegram line.
- **Curve:** NAV vs SPY vs SOXX, rebased to 100, x = date. Plotly, consistent with the capex
  band's figure conventions; follow the dataviz skill at build time.
- **Stat row:** cash %, open positions, trade counts by reason (from `trade_counts`).
- **Banner:** the exported single-regime caveat string rendered verbatim — honesty inherited,
  not re-derived.
- **Drawer (collapsed, joins the tier-3 drawers):** open positions table (ticker, weight %,
  stop, tranches, max intra-hold drawdown) + today's trades with reasons. Corpus-scoped: the
  name filter does **not** apply (contract above).
- **Absence tiers:** CSV + block → full band. Block only → summary band, no curve. CSV only
  (report predates the block) → curve only — stats and banner need the block. Neither → the
  band is skipped entirely, so the 85 existing reports render exactly as today.

## Thin/episodes adoption (Briefing calibration band)

Per row of `signal_performance`, when the new fields are present:

- The pipeline's `thin` flag drives the low-confidence styling for that row, replacing the local
  `single_regime or n<30` heuristic (`_is_low_confidence`) — the pipeline's gate is stricter and
  better-informed (alpha-n floor AND ≥5 independent episodes).
- The sample column renders "n=555 · 12 episodes" so overlapping daily rows can't pose as
  independent observations.
- `alpha_episode_mean_10d` displays alongside the row mean (one episode, one vote).

Rows/reports without the fields keep today's local heuristic and today's exact output — the
fallback path is byte-identical, so visual baselines don't churn until real data lands.

## Error handling

- Missing/malformed `paper_nav.csv` → empty frame via `_safe_read_csv` → curve omitted; never
  raises.
- Malformed `positions[]` / `trades_today[]` rows → skipped row-wise with `.get()` (changelog-
  strip tolerance).
- `nav_return_pct` / `spy_return_pct` None → "seeded" wording, no verdict tone.
- Absent `banner` → no banner line (never invent a caveat string dashboard-side).

## Testing

- Band reducers: verdict line + tone, rebasing, `policy_id` filtering, all four absence tiers.
- Calibration honesty gate: preference order (new fields win; fallback matches today's golden
  output on a frozen real report — drift becomes a red test).
- AppTest page walk stays green; on the current corpus the band's absence is asserted, not
  worked around.
- Visual baselines: unchanged now; one deliberate regen when the first real export lands
  (slow-host regen via PowerShell/Docker, per the established gotcha).
- Upstream: one test asserting `paper_nav.csv` lands in the export set.
- `pytest -q` + `ruff check .` green in both repos.

## Upstream prerequisite (MarketReport repo)

Add `paper_portfolio_nav` → `data/paper_nav.csv` to `export_to_dashboard`
(`pipeline/output.py`), all columns, ordered by `policy_id, date` — plus the export test above.
Ships independently of the dashboard work; the band's absence tiers make order irrelevant.

## Non-goals (v1)

- No Briefing glance line for the paper book (tracker-only was the decision; revisit if the
  walk-to-the-tracker friction proves real).
- No cash-weight series chart, no closed-trade hit rate, no drawdown aggregates dashboard-side —
  rendered only if/when the pipeline exports them.
- No policy-variant comparison UI (one policy exists; variants are an upstream future).
- No change to the tracker scorecard/ledger fallback plan — the single-source-of-truth
  migration (raw_direction_5d / episodes exports) proceeds separately as specced.
