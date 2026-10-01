## Dev commands (read before running anything)

- Interpreter: `.venv\Scripts\python.exe` (this repo's venv; it is also what a
  bare `python` resolves to on this machine — the MarketReport pipeline uses
  anaconda3 instead, never mix them).
- Tests: `.venv\Scripts\python.exe -m pytest tests` — module form is required
  (puts the repo root on `sys.path`). Baseline 2026-10-01 (evening): 282 passed, ~6s.
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
