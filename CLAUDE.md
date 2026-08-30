## Dev commands (read before running anything)

- Interpreter: `.venv\Scripts\python.exe` (this repo's venv; it is also what a
  bare `python` resolves to on this machine — the MarketReport pipeline uses
  anaconda3 instead, never mix them).
- Tests: `.venv\Scripts\python.exe -m pytest tests` — module form is required
  (puts the repo root on `sys.path`). Baseline 2026-08-31: 656 passed, ~33s.
  `tests/visual` is excluded by `pyproject.toml` and is ON-DEMAND only (weekly
  CI sweep + `workflow_dispatch`); never regenerate pixel baselines for an
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
for anything that changes what a number MEANS (tracker tiles read pipeline
alpha — never reintroduce a local hit-rate headline), or that touches the
data contract with the pipeline export.
