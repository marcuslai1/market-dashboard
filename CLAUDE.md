## Dev commands (read before running anything)

- Interpreter: `.venv\Scripts\python.exe` (this repo's venv; it is also what a
  bare `python` resolves to on this machine — the MarketReport pipeline uses
  anaconda3 instead, never mix them).
- Tests: `.venv\Scripts\python.exe -m pytest tests` — module form is required
  (puts the repo root on `sys.path`). Baseline 2026-11-24: 385 passed, ~9s, after the layout review (`ccd8876`: the Watchlist toolbar and two-line phone rows, the pinned opened row, the briefing card's two columns, long notes as lists; `tests/test_layout_batch1.py`, `test_layout_batch2.py`, `test_readable_text.py`) (331 earlier that day, after the look review's second batch: tablet columns, 44px tap targets, the past-report strip; `tests/test_look_batch2.py`) (318 on 2026-11-23 after the stale chip's colour test; 316 on 2026-11-20, after the briefing card's level tiles, VIX note and latched-day notice; 312 on 2026-10-10; 302 on 2026-10-06, after the experimental growth sort ; 287 before it; 283 before the revenue-estimate rows) (289 on 2026-10-02, before the market-read card went 2026-10-03).
  `tests/visual` is excluded by `pyproject.toml` and is ON-DEMAND only
  (`workflow_dispatch`; the weekly sweep was switched off 2026-10-01 — it renders
  the live `data/`, so it went stale daily); never regenerate pixel baselines for an
  ordinary UI change — eyeball locally, run the unit + AppTest suites, ship.
- Lint: `.venv\Scripts\python.exe -m ruff check .` — config in `pyproject.toml`,
  must stay clean (`tests/test_lint.py` enforces it).
- **Stay on `main`.** Streamlit Cloud deploys from `main` and the pipeline's
  `export_to_dashboard` pushes `origin main` every weekday ~12:12 SGT; a stray
  branch checkout strands the day's data (guarded, but the cure is: stay on
  main). Streamlit Cloud sometimes does not redeploy on push — the owner
  reboots from share.streamlit.io.
- `data/` is pipeline-written (CSV + JSON exports); the dashboard is READ-ONLY
  over it. Pipeline logic, signal rules and schema live in `../MarketReport`
  (see that repo's `CLAUDE.md` and the `market-report-bot` skill); UI/layout
  conventions live in the `streamlit-dashboard` skill there.

## Working style

Same as MarketReport: proceed on low-risk, reversible UI changes; discuss first
for anything that changes what a number MEANS, or that touches the data
contract with the pipeline export. Since 2026-10-01 the site is information
only (MarketReport spec 2026-10-01-info-only-watchlist): no pipeline signal
label, rating, ranking or bucket on any page (Yahoo's sell-side consensus is a
quoted third-party figure), and never a local hit-rate headline —
bringing any of them back is a discussion, not a UI change.
