# AGENTS.md — read fully before touching anything

This repo is the PUBLIC half of a private daily market-intelligence pipeline:
a Streamlit front end plus the data files that pipeline publishes here every
weekday. Nothing in this repo computes a trading signal; everything in it
RENDERS numbers the pipeline computed, and the standing rule is that a
rendered number, its label and its colour must not claim more than the
pipeline's number supports. `CLAUDE.md` (same rules, more context) and the
`streamlit-dashboard` skill in `../MarketReport/.claude/skills/` are the
fuller project instructions.

## Hard stops (never do these)

1. **No commits, no pushes, no branch changes.** Streamlit Cloud deploys
   from `main`; the pipeline's `export_to_dashboard` commits `data/` and
   pushes `origin main` every weekday ~12:12 SGT and refuses to run off
   `main`. Leave the working tree on `main` exactly as you found it apart
   from the files the task tells you to create.
2. **`data/` is pipeline-written and READ-ONLY here.** Never edit, regenerate
   or "fix" a CSV/JSON under `data/`; never write fixtures into it. Build
   fixtures in memory or under `tests/` / a temp dir.
3. **Do not run the Streamlit server** (`streamlit run dashboard.py`). The
   test seam is `streamlit.testing.v1.AppTest` (see `tests/test_app_pages.py`).
4. **Never regenerate visual baselines** (`tests/visual/`, `VISUAL_UPDATE=1`)
   and do not run `tests/visual` at all — it needs Docker + a pinned
   Playwright image and is ON-DEMAND by owner decision (2026-08-29).
5. **Do not send anything anywhere**: no network calls, no external POST.
   `live_prices.py` calls Yahoo; with the network off it returns `{}` by
   design — that is not a defect.
6. **Do not touch `../MarketReport`** except to READ it (the export code and
   the pipeline conventions live there). Its own `AGENTS.md` hard stops
   apply if you go further than reading — in particular never invoke
   `morning_pipeline.py`.

## Environment

- Interpreter: the repo's own `.venv` and the machine's default `python`
  may not match CI. (Until 2026-10-01 a 3.9 interpreter failed ~20
  `lib/paper_metrics.py` tests on `zip(strict=)`; that module was removed
  with the paper book.) The gate that matches CI
  (3.10 / 3.12, `.github/workflows/ci.yml`) is a Python 3.10 interpreter
  with `requirements.lock` installed; the task brief names the one to use.
- Tests: `<py310> -m pytest tests -q` — module form is required (puts the
  repo root on `sys.path`). `tests/visual` is excluded by `pyproject.toml`.
  Baseline 2026-10-01 (info-only S1; Tracker / Review tests went with the pages): **253 passed** on Python 3.10.
- Lint: `<py310> -m ruff check .` — config in `pyproject.toml`
  (line-length 100, `E501` ignored); `tests/test_lint.py` enforces it.
- `tests/test_schema.py` reads the newest `data/morning_report_*.json` and
  skips when none is checked out.

## Runtime shape (facts a reviewer needs — read before modelling a scenario)

- **Data arrives once per weekday.** `../MarketReport/pipeline/output.py::
  export_to_dashboard` (called from step 10 of the pipeline, ~12:10 SGT)
  writes: the day's `morning_report_<date>.json` (re-serialised as the
  pipeline wrote it; it has carried no private key since 2026-09-16) and two
  CSVs re-exported IN FULL from the pipeline's SQLite DB each run —
  `market_data.csv` (read since 2026-10-01 by the drill-down price chart:
  `date`, `ticker`, `last_price`, `sma_50`, `sma_200`; its `signal` column,
  never read, is dropped from the 2026-10-02 run) and `earnings_history.csv` —
  then `git add data/ && git commit && git push origin main`. A skipped slot (US
  holiday) writes nothing that day. `briefings.json` and `market_reads.json`
  are written by separate owner-run scripts (`scripts/briefing.py publish`,
  `scripts/market_read.py publish`); `revenue_estimates.json` is
  hand-curated. Exports and files that went: `report_memory.json` (export
  stopped 2026-09-28), `claude_analysis.csv` / `pipeline_stats.csv` (exports
  removed 2026-09-30 / 10-01), the paper CSVs (2026-10-01), `signal_log.csv`
  (export stopped at the pipeline's information-only cutover, MarketReport
  `6d1e184`; file deleted here 2026-10-01), and the unread
  hand-curated `capex_quarterly.json`, `changelog.json` and
  `earnings_cascades.json` (deleted 2026-10-01; git history keeps them).
- **Every number on a page is either read from a report JSON, read from a
  CSV, or derived in `lib/` / `components/` from those.** **Facts only since
  2026-10-01** (MarketReport spec 2026-10-01-info-only-watchlist; tag
  `pre-label-removal`): no page renders a pipeline signal label, rating,
  ranking, bucket, gate, R:R or entry verdict, for any report date (Yahoo's
  sell-side consensus is shown as a sourced third-party figure). Reports up to the
  pipeline cutover still carry those keys (and `calibration_insights`) in
  their JSON; nothing reads them. The Signal Tracker and Review pages went
  with the labels.
- **Rendering path:** `dashboard.py` registers pages with `st.navigation`;
  the Briefing and Watchlist wrap their bodies in `st.fragment(run_every=60)`
  when live prices are on and overlay Yahoo quotes onto the LATEST report
  only (`live_prices.overlay_live` replaces `price` / `chg_pct`, nothing
  else). No page is date-range filtered (the sidebar range fed only the
  Tracker and went with it); the Watchlist has its own report-date picker.
- **Caches:** every loader in `lib/data_loader.py` is `st.cache_data`
  keyed on `(path, mtime)`; a rewritten file busts its entry on the next
  rerun. `fetch_live_quotes` is `ttl=60`.
- **Clock:** `lib/clock.today()` honours `TEST_DATE=YYYY-MM-DD`; production
  never sets it, and since 2026-10-01 no page reads it (inert test seam).
  `LIVE_QUOTES_DISABLED=1` skips the Yahoo batch.
- **Ticker keys:** report JSONs and `signal_log.csv` use
  sanitized keys (`000660_KS`, `SOI_PA`); `market_data.csv` uses the
  provider's dotted symbols (`000660.KS`, `SOI.PA`); `assets/catalog.json`
  maps report keys → Yahoo symbols / display names / clusters and lists
  `retired` tickers.

## Reviewer rules (bounded review briefs)

- **Reachability first.** A defect claim cites the reachable path from a
  live entry point (a page function in `dashboard.py`, a loader, the export
  producer) to the consumer, the supported input producer, and the contract
  violated. A failing synthetic assertion establishes behaviour, not a defect.
- **Label the scenario class**: supported runtime path / operator action /
  malformed external state / hypothetical future producer. Only the first
  is a defect by default; say which one you are in.
- **Severity**: High = reachable AND the page shows a wrong number, a wrong
  label, or a colour/verdict the underlying test does not support (this
  repo's "delivery" is the public page). Medium = reachable, internal only
  (cache, test seam, dead branch). Low = hardening. Documented design
  decisions go under "by design, noted" unless the brief asks otherwise.
- **Brief vs code conflicts**: if the brief asserts a contract the code
  documents differently, report the conflict — do not silently pick the
  stronger contract. The code wins; the conflict is useful output.
- **Evidence vs severity stay separate.** You cannot open the pipeline's DB
  or logs; the brief supplies bounded occurrence counts where they matter,
  and the CSVs under `data/` are the public projection of that DB — count
  in them freely (read-only) and state the predicate you used.
- **Consequence and occurrence are separate cells.** State the consequence
  class first (page number / page label / colour-verdict / internal), then
  the occurrence evidence. "0 observed" changes priority, never the class.
- **Reviewer-generated attacks.** The brief's attack list was written by the
  code's author. Reserve one section of the report for contracts the brief
  did NOT ask about, and say which you chose and why. A "could not
  reproduce" list clears the attack list, not the module.
- If you think an item on the CLOSED list below is wrong, say so with
  evidence rather than staying silent; do not build it.

## Things that are CLOSED — do not reopen or "improve"

- **Information only — no labels on any page** (owner decision 2026-10-01,
  MarketReport spec 2026-10-01-info-only-watchlist O1–O8): no pipeline signal,
  rating, ranking, bucket, gate, R:R or entry instruction (the sourced Yahoo
  sell-side consensus stays); the Watchlist keeps ONE fixed
  cluster order; the Tracker and Review pages are removed (tag
  `pre-label-removal` restores them). Signal accuracy is neither shown nor
  refuted — never describe the change as "signals proven inaccurate".
  Re-introducing a label or ranking is the pipeline's Measurement Gate's call.
  (It superseded the 2026-08-27 "Tracker tiles read `alpha_10d`" rule along
  with the tiles; a local hit-rate headline stays banned.)
- **Colour is a claim** (owner decision 2026-09-01): green/red only where a
  significance / qualification test passes (it was written for the paper
  scorecard — deflated-Sharpe ≥ 95 %, R-multiple n ≥ 5 — removed 2026-10-01);
  neutral is the default. Do not relax a gate because a number "looks strong".
- **Visual pixel-diff is on-demand** (2026-08-29); AppTest + DOM suites are
  the gate.
- **1200 px measure, plain-language labels, drawers ordered by importance**
  (2026-09-01) — layout decisions, not review targets.
- **Paper books FROZEN, dashboard paper surfaces REMOVED** (owner decision
  2026-10-01, MarketReport PIPELINE_FEATURES §116): the Tracker's paper band,
  the trim experiment, the Review page's paper panel, the drill-down's
  `book_stop` line and the `paper_*.csv` exports are gone (pipeline stops
  writing them from the 2026-10-02 run). The record stays in the pipeline's
  SQLite and in git (tag `pre-paper-freeze`).
- The Watchlist drops RETIRED tickers on purpose (the Review page, which
  kept them for survivorship, went 2026-10-01).

## How to work here

- Default to READ-ONLY. Findings beat fixes. If a fix is wanted, the task
  will say so.
- Write failing tests for defects you find rather than patching the code,
  unless told otherwise; keep them standalone and ruff-clean.
- Verify claims by grep before asserting an absence or a behaviour.
- State assumptions inline. Do not ask permission mid-task; do not stop
  early.
