# PROGRESS — read me first on resume

**Last updated:** 2026-07-04 06:06 · Phase 1 COMPLETE (7/7); starting Phase 2 fixes
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
- [x] Phase 1 — page-by-page review (7/7 done)
- [~] Phase 2 — implement objectively-safe fixes on `ux-fix/*` branches
- [ ] Phase 3 — capstone: rank backlog, write summary, build visual Artifact

## Pages reviewed
- [x] briefing — findings BR-1..BR-6 logged (BR-1 truncated risk tag + BR-2 distorted R:R = P1)
- [x] watchlist — strong; R:R distortion folded into BR-2 (WL-1)
- [x] signal-tracker — rich/honest; ST-1 (P2) CAUTION return-coloring inverted
- [x] pipeline-stats — clean telemetry; PS-1 (verify) cost date-scope, PS-2 filter note
- [x] scenario-log — strong; math cross-checks; SC-1 (P3) wildcard colour cross-page
- [x] report-comparison — good; RC-1 (P2) underscore tickers (safe fix)
- [x] terminology + cross-cutting — excellent; TM-1 (folds BR-2/WL-1), CC-1/2/3

## Fix branches created
_(none yet — fix queue for Phase 2: BR-1 safe · BR-2 logic · BR-3 routing)_

## Next action (Phase 2 — each fix on its own `ux-fix/*` branch off main, with tests)
Safe-fix queue, easiest first:
1. RC-1 — `display_ticker()` in report_comparison (cosmetic, zero risk)
2. BR-1 — robust risk-tag heuristic in macro.py (no mid-word truncation)
3. BR-2/WL-1/TM-1 — surface `sizing_rr` (corrected R:R) where `rr_distorted`; drilldown wide-stop falls back to sizing_rr
4. BR-3 — `/briefing` deep-link (default-page url_path)
Then Phase 3 capstone: rank top findings + build visual Artifact.
Leave as proposals (do NOT auto-apply): ST-1, SC-1, BR-4, BR-5, BR-6, PS-1, PS-2, CC-2, CC-3.
