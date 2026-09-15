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
  are **Python 3.9** — `lib/paper_metrics.py` uses `zip(strict=)` (3.10+),
  so ~20 paper tests fail there with "zip() takes no keyword arguments".
  That is environment noise, NOT a regression. The gate that matches CI
  (3.10 / 3.12, `.github/workflows/ci.yml`) is a Python 3.10 interpreter
  with `requirements.lock` installed; the task brief names the one to use.
- Tests: `<py310> -m pytest tests -q` — module form is required (puts the
  repo root on `sys.path`). `tests/visual` is excluded by `pyproject.toml`.
  Baseline 2026-09-15 (post-R12 batch): **718 passed / 1 skipped** on Python 3.10.
- Lint: `<py310> -m ruff check .` — config in `pyproject.toml`
  (line-length 100, `E501` ignored); `tests/test_lint.py` enforces it.
- `tests/test_schema.py` reads the newest `data/morning_report_*.json` and
  skips when none is checked out.

## Runtime shape (facts a reviewer needs — read before modelling a scenario)

- **Data arrives once per weekday.** `../MarketReport/pipeline/output.py::
  export_to_dashboard` (called from step 10 of the pipeline, ~12:10 SGT)
  writes: the day's `morning_report_<date>.json` (through a privacy wall),
  `report_memory.json`, and CSVs re-exported IN FULL from the pipeline's
  SQLite DB each run — `market_data.csv`, `pipeline_stats.csv`,
  `claude_analysis.csv`, `signal_log.csv`, `paper_nav.csv`,
  `paper_trades.csv`, `paper_positions.csv`, `earnings_history.csv` — then
  `git add data/ && git commit && git push origin main`. A skipped slot (US
  holiday) writes nothing that day. `capex_quarterly.json`, `changelog.json`
  and `earnings_cascades.json` are hand-curated by the owner;
  `market_reads.json` is written by a separate owner-run script.
- **Every number on a page is either read from a report JSON, read from a
  CSV, or derived in `lib/` / `components/` from those.** The pipeline's
  `calibration_insights` block inside each report JSON (since 2026-07-02)
  carries the pipeline's own signal-accuracy figures; since 2026-08-27 the
  Tracker tiles show THOSE (benchmark-relative `alpha_10d`), and locally
  computed price-direction rates are a demoted popover only.
- **Rendering path:** `dashboard.py` registers pages with `st.navigation`;
  the Briefing and Watchlist wrap their bodies in `st.fragment(run_every=60)`
  when live prices are on and overlay Yahoo quotes onto the LATEST report
  only (`live_prices.overlay_live` replaces `price` / `chg_pct`, nothing
  else). The sidebar date range filters the Tracker / Compare corpora;
  Briefing / Watchlist / Review are not range-filtered.
- **Caches:** every loader in `lib/data_loader.py` is `st.cache_data`
  keyed on `(path, mtime)`; a rewritten file busts its entry on the next
  rerun. `fetch_live_quotes` is `ttl=60`.
- **Clock:** `lib/clock.today()` honours `TEST_DATE=YYYY-MM-DD`; production
  never sets it. `LIVE_QUOTES_DISABLED=1` skips the Yahoo batch.
- **Ticker keys:** report JSONs and `signal_log.csv` / `paper_*.csv` use
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

- **Tracker tiles read the pipeline's `alpha_10d`** (owner decision
  2026-08-27, "option C"). Do not reintroduce a locally computed hit-rate
  headline; the local 5/20-session direction view lives in the popover only.
- **Colour is a claim** (owner decision 2026-09-01): green/red on the paper
  scorecard only where a significance / qualification test passes (deflated-
  Sharpe ≥ 95 %, R-multiple n ≥ 5, Default book + Twins only); neutral is
  the default. Do not relax a gate because a number "looks strong".
- **Visual pixel-diff is on-demand** (2026-08-29); AppTest + DOM suites are
  the gate.
- **1200 px measure, plain-language labels, drawers ordered by importance**
  (2026-09-01) — layout decisions, not review targets.
- **Paper-book parameters, lane sets and the headline lane
  (`v2_starter_b15_tb_fees`) are the pipeline's**; the dashboard names them
  in `components/paper_book.py` but does not define them.
- The Review page keeps RETIRED tickers in its call ledger on purpose
  (survivorship); the Watchlist / price frames drop them on purpose.

## How to work here

- Default to READ-ONLY. Findings beat fixes. If a fix is wanted, the task
  will say so.
- Write failing tests for defects you find rather than patching the code,
  unless told otherwise; keep them standalone and ruff-clean.
- Verify claims by grep before asserting an absence or a behaviour.
- State assumptions inline. Do not ask permission mid-task; do not stop
  early.
