# PROGRESS — read me first on resume

**Last updated:** 2026-07-04 05:26 (session start)
**Branch (docs/screens):** `ux-review/overnight-2026-07-04`
**Server:** `http://localhost:8501` — launched in background.

## How to resume (if context reset / new turn)
1. Read this file, then `BACKLOG.md`.
2. Check the server is still up: navigate Playwright to `http://localhost:8501/briefing`.
   If down, relaunch:
   `./.venv/Scripts/python.exe -m streamlit run dashboard.py --server.headless true --server.port 8501 --browser.gatherUsageStats false` (run_in_background).
3. Continue at the first unchecked page below.

## Phase
- [x] Phase 0 — scaffolding, branch, server, task list
- [ ] Phase 1 — page-by-page review (screenshots + findings)
- [ ] Phase 2 — implement objectively-safe fixes on `ux-fix/*` branches
- [ ] Phase 3 — capstone: rank backlog, write summary, build visual Artifact

## Pages reviewed
- [ ] briefing (default; bands: stance, pulse, action card, clusters, calibration,
      capex pulse, catalyst playbook, changes, contrarians, earnings, macro, calendar)
- [ ] watchlist (+ drilldown)
- [ ] signal-tracker
- [ ] pipeline-stats
- [ ] scenario-log
- [ ] report-comparison
- [ ] terminology

## Fix branches created
_(none yet)_

## Next action
Navigate to `/briefing`, screenshot desktop + narrow, begin findings.
