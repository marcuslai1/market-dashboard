# AI Capex Pulse — approved design

Date: 2026-07-03 · Status: **approved design, pre-implementation**
Source thinking: `CAPEX_CYCLE_IDEAS.md` (brainstorm doc). This spec resolves that
doc's open decisions (§10) and covers its v1 + v2 scope only.

## Purpose

The dashboard answers "is the AI trade still intact, and what breaks it?" Capex is
the load-bearing variable, but today it exists only as free text in the reports.
This feature adds a **human-read digestion scorecard** — the coverage gap between
what hyperscalers spend and what the beneficiaries book as revenue — rendered next
to the scenario odds it exists to cross-check, plus **earnings-cascade pre-wiring**
so each key earnings date carries its ex-ante bull/bear read and blast radius.

## Decisions resolved

| Open decision (ideas doc §10) | Resolution |
|---|---|
| Gauge role | **Human-read check.** Scorecard renders near the scenario-odds bar; odds stay narrative-authored. No mechanical wiring. |
| Build scope | **v1 + v2** (corpus-derived trends + cascades; hand-maintained capex file + coverage gap). v3 explicitly out of scope. |
| Data source | **Hand-maintained** quarterly file. Curation is the analysis at this scale (deciding what counts as AI capex is judgment). |
| Spender scope | Core gap = **MSFT, GOOG, AMZN, META** (META not held, but its capex is the beneficiaries' revenue — the signal needs it). **CRWV tracked separately as fragile tier**, never blended into the gap. |
| Home | **Briefing band ("AI Capex Pulse")** near the Macro Note. No new page until the instrument proves it moves decisions. |

## 1 · Data

Two new hand-maintained files + one corpus derivation. All loading goes through
`lib/data_loader.py` with the existing mtime-keyed cache pattern.

### `data/capex_quarterly.json`

```json
{
  "core_spenders": ["MSFT", "GOOG", "AMZN", "META"],
  "fragile_tier": ["CRWV"],
  "beneficiaries": ["NVDA", "AMD", "AVGO", "TSM", "MU", "000660.KS", "LITE"],
  "methodology": "Capex = purchases of PP&E incl. finance leases where disclosed. One line per reported quarter; what counts as AI capex is a curation judgment — record it here when it matters.",
  "series": {
    "MSFT": [
      {"cq": "2026Q1", "fiscal_label": "FY26Q3", "reported": "2026-04-29",
       "capex_usd_b": 21.4, "guide": "FY26 ~$80B reaffirmed", "source": "10-Q",
       "note": ""}
    ],
    "CRWV": [
      {"cq": "2026Q1", "reported": "2026-05-14", "capex_usd_b": 5.1,
       "flag": "amber", "note": "debt-funded; watch raise cadence", "source": "10-Q"}
    ]
  }
}
```

- `cq` is the **calendar quarter**, stored explicitly so no code ever does fiscal
  math (MSFT FY26Q3 = calendar 2026Q1); `fiscal_label` is display-only.
- YoY growth is **computed by the loader** when the prior-year `cq` exists — never
  hand-entered.
- Fragile-tier entries carry a manual `flag` (`green`/`amber`/`red`) — the
  curation judgment, not a computed state.
- Seeded at build time with the last ~5 reported quarters per name, values taken
  from actual filings/earnings releases (web-verified during implementation).
- Loader validation: known tickers, `cq` matches `YYYYQ[1-4]`, `capex_usd_b`
  positive number, `reported` parses as a date. On failure: log, drop the bad row,
  return the rest (degrade, don't crash).

### `data/earnings_cascades.json`

```json
{
  "MU": {
    "why": "MU + SK Hynix are the memory cycle; HBM ASPs proxy AI demand intensity.",
    "bull": {"read": "Beat + HBM guide raise confirms Layer-2 demand; reinforces NVDA/AVGO datacenter thesis.",
             "tickers": ["000660.KS", "NVDA", "AVGO", "TSM"],
             "scenario_hint": "base/optimistic firm"},
    "bear": {"read": "Guide miss / HBM ASPs soften — earliest crack in the coverage gap; pressures the semis cluster.",
             "tickers": ["000660.KS", "NVDA", "AVGO", "TSM"],
             "scenario_hint": "pessimistic up"}
  }
}
```

- Hand-maintained: the ex-ante judgment **is** the content. Initial coverage: the
  key reporters (MU, NVDA, TSM, ASML, AVGO, the four hyperscalers, CRWV).
- Joined to `scheduled_tech_events` earnings entries by reporter ticker at render
  time. Entries with no cascade config render exactly as today.

### Beneficiary time-series (no new data)

Corpus walk of `data/morning_report_*.json` (the Signal-Tracker pattern), memoized
on the corpus fingerprint (P7-2 pattern). Per date/ticker, extract from
`valuation`: `revenue_growth_pct`, `analyst_consensus.earnings_growth_pct`,
`fcf_yield_pct`, `forward_pe`, `peg_ratio`; aggregate to cluster medians via
`cluster_name`. Reports predating these fields simply leave gaps.

## 2 · Computation — new `lib/capex.py`

- **Spender capex YoY** per `cq`: sum of core spenders' `capex_usd_b` vs the same
  sum four quarters earlier. Undefined until all core spenders have both quarters
  (partial quarters render as "awaiting N of 4 spenders", never a fake number).
- **Coverage gap** per `cq` = (median `revenue_growth_pct` across the file's
  `beneficiaries` list — per-ticker, not a cluster median — taken from the first
  report on/after the date the last core spender reported that quarter, falling
  back to the latest available report if none exists yet) − (core capex YoY).
  Positive = revenue outrunning capex = healthy (ideas doc §4).
- **Current read** = latest daily beneficiary median − latest complete quarter's
  capex YoY, labeled with both as-of dates.
- **Scorecard chips** — display-only states (✅ / ⚠ / ▲ / —), each with a one-line
  reason and as-of date. Thresholds are named constants in `lib/capex.py`,
  documented as presentation choices, not calibrated signals:
  - **Capex direction**: last two capex YoY readings — accelerating (▲, +2pp or
    more), steady, decelerating.
  - **Coverage gap**: widening ⚠ when the gap fell ≥3pp vs the prior reading or is
    negative; otherwise stable/closing ✅.
  - **Beneficiary revenue trend**: cluster median now vs ~60 days ago — rising /
    flat / falling.
  - **Valuation**: Semis-cluster median `forward_pe` and `peg_ratio` vs their own
    corpus history — ✅ at/below corpus median, ⚠ above the 80th percentile.
  - **Fragile tier**: surfaces CRWV's latest quarter, manual `flag` color, and note.
  - The ideas-doc example had a "margins" chip — **cut**: margins aren't in any
    schema we have. No chip renders from data we don't hold.

## 3 · UI

- New `components/briefing/capex_pulse.py`, composed into the Briefing via
  `dashboard.py` like the other bands (`card_container`, lane placement near the
  Macro Note / scenario odds).
- Band contents: chip-row scorecard with "as of Q1 FY26 earnings" framing → compact
  coverage-gap chart (capex YoY vs beneficiary revenue growth, gap shaded; palette
  through `lib`, data-table fallback per the P8-4 convention) → expander
  **"Cluster fundamentals over time"** with small-multiple trends (revenue growth,
  earnings growth, FCF yield, forward PE) per cluster, so the band stays lean.
- **Cascades get no new surface**: `components/briefing/earnings.py` renders the
  bull/bear reads + affected-ticker chips on earnings entries that match the
  cascade config.
- Chart work follows the dataviz skill at implementation time.

## 4 · Honesty & degradation

- **Curation staleness** (this design's main failure mode is quiet rot): if the
  newest core-spender `reported` date is >110 days old, the band shows a
  "curation overdue" tag — same release-aware semantics as the macro-prints STALE
  fix (stale = a newer print should exist, hyperscalers report quarterly).
- Missing/absent/malformed `capex_quarterly.json` → band still renders the chips
  that have data; gap chip reads "needs capex data". Never crashes the Briefing.
- Cascade config naming tickers outside the watchlist → still renders (the cascade
  read is about the reporter; chips for unknown tickers render unlinked).
- All degraded states have explicit copy — no silent blanks.

## 5 · Testing

TDD throughout (red before green):

- `lib/capex.py` unit tests: gap math, missing prior-year quarter, partial-quarter
  "awaiting spenders" state, chip-state boundaries, staleness threshold.
- Component render tests in the `test_macro_prints.py` style: full band, each
  degraded state, cascade-annotated vs plain earnings entries.
- Extend the existing AppTest page-walk to assert the band renders on the Briefing.
- Seed-data sanity: loader accepts the seeded file; spot values match filings.

## Out of scope (deliberate)

- v3 entirely: credit spreads, circular-financing tracker, power-chain metrics.
- Mechanical wiring of the gauge into scenario odds (revisit with more history).
- Cascade surfacing in the watchlist drilldown (Briefing-side only for now).
- Margins / book-to-bill / HBM ASP chips (no data source in the pipeline).
- API sourcing for capex (revisit only if the name count grows).

## Curation workflow (the ongoing cost, stated plainly)

~4×/year, in earnings season: add one row per spender to `capex_quarterly.json`
(~10 min/name from the release), refresh `flag`/`note` on the fragile tier, and
revisit cascade reads before major reports. The band's curation-overdue tag is the
backstop if a quarter is skipped.
