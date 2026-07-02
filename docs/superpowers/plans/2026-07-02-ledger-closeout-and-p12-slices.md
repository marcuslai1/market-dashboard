# Ledger Closeout + P1-2 Slices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every remaining actionable REVIEW.md item — P0-1 (project venv), P0-2 (lockfile), P7-2 (Signal-Tracker memoization), P8-4 (chart data-table fallbacks), P6-1 (hex-literal palette), plus native `st.navigation` (real URL routing + browser back/forward) — then ship the final P1-2 slices (vs-cluster, news sentiment, premarket in the drilldown) and document-drop the rest.

**Architecture:** Two branches. Branch 1 `ledger-closeout-2026-07-02`: infra + perf + a11y + palette + navigation. Branch 2 `p12-slices-2026-07-02`: drilldown feature slices + ledger close of P1-2. Navigation migrates from the `?page=` query-param radio (shipped earlier today) to `st.navigation`/`st.Page` with a hidden native nav and the masthead radio driving `st.switch_page` — spike-verified under AppTest (radio pattern with a `_nav_last` resync guard).

**Tech Stack:** Streamlit 1.50 (`st.navigation`, `st.Page`, `st.switch_page`), uv 0.10.8 (installed), system Python 3.10 (`C:\Program Files\Python310`), pytest, ruff, Playwright MCP for live verification.

## Global Constraints

- Baseline: **138 passed**, `ruff check .` clean — must hold after every task (in the old env AND the new `.venv`).
- `lib/catalog.py` stays data-only; palette constants extend `lib/charts.py` (the P6-1-partial precedent: `STATUS_POS/NEG/WARN`).
- `st.cache_data`: no `_`-prefixed key params; data args that shouldn't be hashed ARE `_`-prefixed; every cache carries `max_entries`.
- Do NOT touch base Anaconda. Do NOT commit `.venv/` or `CAPEX_CYCLE_IDEAS.md`.
- The CAPEX doc is brainstorm-stage feature work needing interactive design — explicitly out of scope for this autonomous pass.

---

## Branch 1 — `ledger-closeout-2026-07-02`

### Task 1: Project venv + lockfile (P0-1 local side + P0-2)

**Files:** Create `requirements.lock`, `.venv/` (untracked); Modify `.gitignore`, `.github/workflows/ci.yml`, `REVIEW.md` (in Task 6).

- [ ] `uv venv .venv --python 3.10`
- [ ] `uv pip compile requirements.txt --universal -o requirements.lock`
- [ ] `uv pip install -r requirements.lock pytest pytest-cov ruff --python .venv`
- [ ] `.venv/Scripts/python -m pytest -q` → expect 138 passed **on pandas 2.x locally** (first local proof; CI already proves it)
- [ ] Add `.venv/` to `.gitignore`
- [ ] ci.yml Test job: `pip install -r requirements.lock pytest pytest-cov` (lint job unchanged)
- [ ] Commit: `build: requirements.lock (uv, universal) + .venv workflow; CI installs the lock (P0-2)`

### Task 2: Memoize Signal-Tracker transforms (P7-2)

**Files:** Modify `lib/data_loader.py`, `dashboard.py:421-426`, `components/signal_tracker.py:513-590`; Test `tests/test_data_loader.py`.

**Interfaces:** `lib.data_loader.data_fingerprint() -> tuple` — `((path, mtime), …)` over report files + `market_data.csv`. `render_signal_tracker_page(reports, prices_df, cache_key: tuple | None = None)`.

- [ ] Failing test: `data_fingerprint` changes when a report file's mtime is bumped and when `market_data.csv` changes (tmp `DATA_DIR` monkeypatch, same `_bump` helper as the P2-5 tests)
- [ ] Implement `data_fingerprint()` in data_loader (reuse the glob from `load_all_reports`, append `(market_data.csv, mtime)`)
- [ ] signal_tracker: hoist the three derives into cached helpers keyed by `cache_key` (+ `selected` for episodes), data args underscore-prefixed:

```python
@st.cache_data(max_entries=4)
def _history_and_accuracy(cache_key: tuple, _reports: dict, _prices: pd.DataFrame):
    sig_df = extract_signal_history(_reports)
    acc_df = compute_signal_accuracy(sig_df, _prices)
    return sig_df, acc_df

@st.cache_data(max_entries=8)
def _episodes_for(cache_key: tuple, selected: tuple, _sig_df: pd.DataFrame,
                  _prices: pd.DataFrame) -> pd.DataFrame:
    return build_signal_episodes(_sig_df[_sig_df["ticker"].isin(selected)], _prices)
```

  `render_signal_tracker_page` uses them when `cache_key is not None`, else calls the raw transforms (keeps unit tests / other callers unchanged). dashboard.py passes `cache_key=(data_fingerprint(), DATE_START, DATE_END)`.
- [ ] Full suite + ruff → commit: `perf: memoize Signal-Tracker derives on the corpus fingerprint (P7-2)`

### Task 3: Chart data-table fallbacks (P8-4 remainder)

**Files:** Modify `lib/charts.py`, `components/scenario_log.py` (~:229), `components/pipeline_stats.py` (6 charts); Test: AppTest walk (existing).

- [ ] Add to `lib/charts.py`:

```python
def chart_data_table(df, label: str = "View data as table") -> None:
    """Screen-reader-parity fallback: the chart's source data as a real table."""
    import streamlit as st
    if df is None or len(df) == 0:
        return
    with st.expander(label):
        st.dataframe(df, width="stretch", hide_index=True)
```

- [ ] Call it after each `st.plotly_chart` with the frame that fed the figure (scenario prob-over-time; pipeline tokens, gen-time, cost, cumulative cost, cache, articles)
- [ ] Full suite (walk exercises both pages) + ruff → commit: `a11y: data-table fallback under every chart (P8-4)`

### Task 4: Palette pass (P6-1 remainder — 57 hex literals)

**Files:** Modify `lib/charts.py` (new constants), `components/watchlist/drilldown.py` (32), `components/terminology.py` (9), `components/scenario_log.py` (6), `components/briefing/action_card.py` (3), `components/briefing/contrarians.py` (2), `components/briefing/stance.py` (2), `components/signal_tracker.py` (1), `components/briefing/changes.py` (1), `components/briefing/calendar.py` (1).

- [ ] Extend `lib/charts.py` (values byte-identical to today's literals — rendering unchanged by construction):

```python
STATUS_INFO = "#3498db"       # informational / catalyst-override blue
STATUS_NEUTRAL = "#9ca3af"    # unknown / not-applicable gray
STATUS_MUTED = "#6b7280"      # terminal / disabled gray
STATUS_WARN_SOFT = "#fbb454"  # soft-warning amber (momentum_warn chips)
ACCENT_LINK = "#3b82f6"       # link-blue accents (graduation_watch)
INK_FALLBACK = "#9F988B"      # ink-3 fallback where CSS vars can't reach
```

- [ ] Replace every literal with the matching constant (f-strings interpolate the constant). `#22c55e/#ef4444/#f59e0b` → STATUS_POS/NEG/WARN; the rest per the table above. Leave `#1e1e2e` (single hoverlabel bg in terminology) as a named local if it resists a semantic name.
- [ ] `grep -roE "#[0-9a-fA-F]{6}" components/ --include="*.py"` → expect ~0 remaining (report any stragglers with reasons)
- [ ] Full suite + ruff; screenshot Watchlist drilldown + Briefing before/after → commit: `style: route remaining hex literals through the lib palette (P6-1)`

### Task 5: Native st.navigation (URL routing + back/forward)

**Files:** Modify `dashboard.py` (elif chain → page functions + `st.navigation`), `components/masthead.py` (nav radio pattern), `tests/test_app_pages.py` (replace query-param tests).

**Spike-verified pattern (AppTest-green):**

```python
# dashboard.py — after sidebar/theme, before page bodies
_PAGES = {
    "Briefing": st.Page(_page_briefing, title="Briefing", url_path="briefing", default=True),
    "Watchlist": st.Page(_page_watchlist, title="Watchlist", url_path="watchlist"),
    "Signal Tracker": st.Page(_page_signal_tracker, title="Signal Tracker", url_path="signal-tracker"),
    "Pipeline Stats": st.Page(_page_pipeline_stats, title="Pipeline Stats", url_path="pipeline-stats"),
    "Scenario Log": st.Page(_page_scenario_log, title="Scenario Log", url_path="scenario-log"),
    "Report Comparison": st.Page(_page_report_comparison, title="Report Comparison", url_path="report-comparison"),
    "Terminology": st.Page(_page_terminology, title="Terminology", url_path="terminology"),
}
_pg = st.navigation(list(_PAGES.values()), position="hidden")
_sel = render_masthead_and_nav(_pg.title)   # masthead returns the radio selection
if _sel != _pg.title:
    st.switch_page(_PAGES[_sel])
_pg.run()
```

```python
# masthead.py — replaces the query-param block
def render_masthead_and_nav(current: str) -> str:
    ...masthead markdown unchanged...
    if st.session_state.get("_nav_last") != current:
        # navigation changed outside the radio (deep link / browser back) — resync
        st.session_state.page_nav = current
        st.session_state._nav_last = current
    page = st.radio("Navigate", _NAV_PAGES, horizontal=True,
                    label_visibility="collapsed", key="page_nav")
    return page
```

- [ ] Convert each elif body to a `_page_*()` function verbatim (module globals `LIVE_PRICES`/`DATE_START`/`DATE_END` are set before `_pg.run()`, so call-time resolution is safe); sidebar/theme/masthead stay on the shared shell
- [ ] Remove the `?page=` query-param seed/mirror from masthead; replace `test_query_param_deep_links_to_page` / `test_invalid_query_param_falls_back_to_briefing` / write-back test with a radio round-trip test (Briefing → Signal Tracker → Briefing asserting page content); page-walk test unchanged (`at.radio(key="page_nav")` drive survives)
- [ ] Full suite + ruff → commit: `feat: native st.navigation — real URL per page, browser back/forward (replaces ?page=)`

### Task 6: Ledger close + verification + merge

- [ ] REVIEW.md: P0-2 → ✅ FIXED (uv universal lock, CI installs it); P0-1 → ✅ resolved-local (`.venv` py3.10/pandas 2.x; base Anaconda untouched); P7-2 → ✅ FIXED; P8-4 → ✅ FIXED; P6-1 → ✅ FIXED; addendum notes nav upgraded to st.navigation (supersedes the `?page=` note from this morning)
- [ ] Suite in `.venv` AND old env; live Playwright: each URL path loads its page, browser back/forward walks history, refresh stays on page, drilldown renders, chart tables expand, 0 console errors
- [ ] Merge `--no-ff` to main, push, watch CI green

---

## Branch 2 — `p12-slices-2026-07-02`

### Task 7: Drilldown slices — vs-cluster, news sentiment, premarket

**Files:** Modify `components/watchlist/drilldown.py`; Create `tests/test_drilldown.py`.

**Data shapes (verified against 2026-07-02 report):** `vs_cluster_chg_pct: float` (659 entries corpus-wide); `news_sentiment_skew: "bullish"|"bearish"|"mixed"|"neutral"` (933); `premarket: {phrase: "premarket -0.9% vs prior close", pm_chg_pct: float, ...}` (85 with phrase).

- [ ] Failing tests (shape: call `render_drilldown_detail_html(tk, d)` with minimal dicts):
  - `vs_cluster_chg_pct: 1.21` → output contains `vs cluster` and `+1.21%`; absent field → no `vs cluster` cell
  - `news_sentiment_skew: "bullish"` → chip text `news · bullish` colored STATUS_POS; `bearish` → STATUS_NEG; `mixed` → STATUS_WARN; `neutral` → STATUS_NEUTRAL; absent → no chip
  - `premarket: {"phrase": "premarket -0.9% vs prior close", "pm_chg_pct": -0.86}` → chip/line contains the phrase, colored by `pm_chg_pct` sign; `<script>` in phrase → escaped (security contract)
- [ ] Implement:
  - Technicals grid: `("vs cluster (1d)", f"{_sign(vsc)}{_fmt_num(vsc, 2)}%")` after "1-month return"
  - Status-chip strip: sentiment chip + premarket chip (reuse the existing chip markup, colors from `lib.charts` constants routed in Task 4; escape phrase with `_escape_dollars`)
- [ ] Full suite + ruff → commit per slice or one commit: `feat: drilldown surfaces vs-cluster, news sentiment, premarket (P1-2 final slices)`

### Task 8: Document-drop the remainder + close P1-2

- [ ] REVIEW.md P1-2: mark **CLOSED** — surfaced: clusters, calibration_insights, eps_trajectory, vs_cluster_chg_pct, news_sentiment_skew, premarket. Dropped-with-reasons: `thesis_highlights` (sparse, partially duplicates writeup, carries encoding artifacts `�`), `eps_surprise` (absent from current reports), `structural_conviction` (2 entries), `macro_context_line` (caveat prose, macro card already carries `macro_indicators`), `scheduled_tech_events` (2–3/82 forward-dated), `vs_cluster_5d/1mo` (not emitted in current reports — only `chg_pct` is)
- [ ] Live verify drilldown on the real Watchlist; merge `--no-ff`, push, CI green

## Self-review notes
- Type consistency: `data_fingerprint()` tuple feeds both Task 2's `cache_key` and existing `_load_all_reports_cached` fingerprint shape — they are separate values, no shared signature required.
- The Task 5 test replacement keeps the CI page-walk guard intact — verified by spike that `at.radio(key="page_nav")` still drives navigation.
- Task 4 before Task 7 so the drilldown slices use palette constants, not new literals.
