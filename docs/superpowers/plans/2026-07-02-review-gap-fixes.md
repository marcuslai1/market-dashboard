# Review-Gap Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the actionable gaps found when auditing REVIEW.md against the current tree: the never-committed page-walk test (P5-2), the Watchlist page's un-fragmented live fetch, the accepted 5-minute cache staleness (P2-5), the app-wide `TICKER_DISPLAY.get(tk, tk)` underscore-key leak, lost nav state on browser refresh, and the stale ledger itself.

**Architecture:** Six independent, individually-committable fixes on one branch. Data-loader caches move from `ttl=300` to the mtime-keyed pattern already proven by `_read_text_asset`. The Watchlist page body adopts the same `st.fragment` isolation the Briefing got in the perf pass. A shared `display_ticker` helper in `lib/formatters.py` replaces eight raw `TICKER_DISPLAY.get(tk, tk)` callsites. Nav state syncs to `st.query_params`. A parametrized AppTest walk of all 7 pages becomes a committed regression test.

**Tech Stack:** Python 3.9+ (local) / 3.10+3.12 (CI), Streamlit 1.50 (`st.fragment`, `st.query_params`, `streamlit.testing.v1.AppTest`), pytest, ruff.

## Global Constraints

- `lib/catalog.py` is data-only by contract ("Contains only data — no Streamlit calls and no functions") — the display helper goes in `lib/formatters.py`, NOT catalog.
- `st.cache_data` drops `_`-prefixed params from the cache key — mtime/fingerprint params must NOT start with underscore (regression documented in `_read_text_asset`).
- All caches that replace `ttl=300` must stay bounded: pass `max_entries` so mtime churn can't grow memory unbounded.
- Tests must not hit the network: AppTest tests monkeypatch `live_prices.fetch_live_quotes`.
- Suite baseline: 121 passed, `ruff check .` clean. Both must hold after every task.
- Do NOT commit the untracked `CAPEX_CYCLE_IDEAS.md` (user's working notes).

**Explicitly out of scope (recorded here so the decision is visible):** P0-1 local env upgrade (local Python is base anaconda, not a venv — upgrading pandas there is the user's call); P0-2 lockfile (needs a tooling decision); P7-2 Signal-Tracker memoization (measured <100 ms, ledger status "monitor" — complexity not yet paid for); P6-1 hex-literal remainder (needs visual review); P8-4 chart data-table fallback (nicety); remaining P1-2 slices (product decisions).

---

### Task 1: Shared `display_ticker` helper

**Files:**
- Modify: `lib/formatters.py` (add helper near `_escape_dollars`)
- Modify: `components/briefing/earnings.py:26-36` (delete local `_display_ticker`, import shared)
- Modify: `components/briefing/changes.py:29`
- Modify: `components/watchlist/row.py:33`
- Modify: `components/briefing/action_card.py:56`
- Modify: `components/briefing/contrarians.py:29`
- Modify: `components/briefing/clusters.py:73`
- Modify: `components/signal_tracker.py:459,597,688`
- Test: `tests/test_formatters.py`

**Interfaces:**
- Produces: `lib.formatters.display_ticker(tk: str) -> str` — override map hit → override (`CL_F` → `CL=F`); miss → underscores restored to dots (`000660_KS` → `000660.KS`); plain tickers unchanged.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_formatters.py`)

```python
from lib.formatters import display_ticker


def test_display_ticker_uses_override_map():
    # CL_F carries a special display glyph in catalog.json
    assert display_ticker("CL_F") == "CL=F"


def test_display_ticker_restores_dots_for_unmapped_keys():
    assert display_ticker("000660_KS") == "000660.KS"


def test_display_ticker_plain_ticker_unchanged():
    assert display_ticker("NVDA") == "NVDA"
```

- [ ] **Step 2: Run to verify they fail** — `pytest tests/test_formatters.py -q` → ImportError: cannot import name 'display_ticker'

- [ ] **Step 3: Implement** — in `lib/formatters.py` (import `TICKER_DISPLAY` from `lib.catalog` at top):

```python
def display_ticker(tk: str) -> str:
    """Human display form of a watchlist key, e.g. ``000660_KS`` -> ``000660.KS``.

    ``TICKER_DISPLAY`` is a *sparse* override map — it only lists tickers whose
    display needs special glyphs (``CL_F`` -> ``CL=F``, ``VIX`` -> ``^VIX``). It
    does **not** carry the plain underscore-for-dot names, so a raw
    ``TICKER_DISPLAY.get(tk, tk)`` leaks the munged key into the UI for those.
    Prefer the override, then fall back to restoring the dot.
    """
    return TICKER_DISPLAY.get(tk) or str(tk).replace("_", ".")
```

- [ ] **Step 4: Route the callsites.** earnings.py: delete `_display_ticker` + its `TICKER_DISPLAY` import, `from lib.formatters import display_ticker`, call site `_eps_rows` uses `display_ticker(tk)`. changes.py:29 → `display_tk = display_ticker(tk)`. row.py:33 → `_escape_dollars(display_ticker(tk))`. action_card.py:56 → `_escape_dollars(display_ticker(tk))`. contrarians.py:29 → `_escape_dollars(display_ticker(ticker))`. clusters.py:73 → `_escape_dollars(display_ticker(_norm(tk)))`. signal_tracker.py:459 → `_escape_dollars(display_ticker(ticker))`, :597 → `display_ticker(ticker)`, :688 → `.map(display_ticker)`. Remove now-unused `TICKER_DISPLAY` imports where nothing else uses them.

- [ ] **Step 5: Verify** — `pytest -q` → 124 passed; `ruff check .` → clean.

- [ ] **Step 6: Commit** — `git commit -m "fix: centralize display_ticker; stop leaking underscore keys in 8 callsites"`

---

### Task 2: mtime-keyed caches replace ttl=300 (fixes P2-5)

**Files:**
- Modify: `lib/data_loader.py` (all `ttl=300` loaders)
- Test: `tests/test_data_loader.py`

**Interfaces:**
- Public signatures unchanged: `list_report_dates() -> list[str]`, `load_report(date_str) -> dict`, `load_all_reports() -> dict`, `load_sqlite_prices/load_pipeline_stats/load_token_usage/load_signal_log() -> pd.DataFrame`, `load_report_memory() -> dict`.
- Pattern: public wrapper stats the file/dir, passes `(path_str, mtime)` (no underscore prefix!) to a cached private impl with `max_entries`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_data_loader.py`; monkeypatch `lib.data_loader.DATA_DIR` to `tmp_path`)

```python
import json

import lib.data_loader as dl


def _bump(path, seconds=5):
    t = time.time() + seconds
    os.utime(path, (t, t))


def test_load_report_reflects_rewritten_file(tmp_path, monkeypatch):
    """P2-5: a regenerated report must show up without waiting out a TTL."""
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "morning_report_2026-01-01.json"
    f.write_text(json.dumps({"watchlist": {"A": {}}}), encoding="utf-8")
    assert "A" in dl.load_report("2026-01-01")["watchlist"]
    f.write_text(json.dumps({"watchlist": {"B": {}}}), encoding="utf-8")
    _bump(f)
    assert "B" in dl.load_report("2026-01-01")["watchlist"]


def test_list_report_dates_sees_new_file_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "morning_report_2026-01-01.json").write_text("{}", encoding="utf-8")
    _bump(tmp_path)
    assert dl.list_report_dates() == ["2026-01-01"]
    (tmp_path / "morning_report_2026-01-02.json").write_text("{}", encoding="utf-8")
    _bump(tmp_path, 10)
    assert dl.list_report_dates() == ["2026-01-01", "2026-01-02"]


def test_load_all_reports_reflects_rewritten_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "morning_report_2026-01-01.json"
    f.write_text(json.dumps({"meta": {"v": 1}}), encoding="utf-8")
    assert dl.load_all_reports()["2026-01-01"]["meta"]["v"] == 1
    f.write_text(json.dumps({"meta": {"v": 2}}), encoding="utf-8")
    _bump(f)
    assert dl.load_all_reports()["2026-01-01"]["meta"]["v"] == 2


def test_load_sqlite_prices_reflects_rewritten_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    f = tmp_path / "market_data.csv"
    f.write_text("date,ticker\n2026-01-01,NVDA\n", encoding="utf-8")
    assert list(dl.load_sqlite_prices()["ticker"]) == ["NVDA"]
    f.write_text("date,ticker\n2026-01-01,AMD\n", encoding="utf-8")
    _bump(f)
    assert list(dl.load_sqlite_prices()["ticker"]) == ["AMD"]
```

- [ ] **Step 2: Run to verify the mutation tests fail** — with `ttl=300` the second assert in each serves the stale cached value → 4 FAILs.

- [ ] **Step 3: Implement.** In `lib/data_loader.py`: for each loader, split into cached impl + stat-ing wrapper. Shape (report loader shown; same shape for the rest):

```python
@st.cache_data(show_spinner=False, max_entries=128)
def _load_report_cached(path_str: str, mtime: float) -> dict:
    try:
        return json.loads(Path(path_str).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_report(date_str: str) -> dict:
    path = DATA_DIR / f"morning_report_{date_str}.json"
    if not path.exists():
        return {}
    return _load_report_cached(str(path), path.stat().st_mtime)
```

`list_report_dates`: wrapper stats `DATA_DIR` (`0.0` if missing) → `_list_report_dates_cached(dir_str, dir_mtime)` globs+sorts, `max_entries=8`. `load_all_reports`: wrapper builds `fingerprint = tuple((str(f), f.stat().st_mtime) for f in sorted(DATA_DIR.glob("morning_report_*.json")))` → `_load_all_reports_cached(fingerprint)` parses each path in the fingerprint (keep the `st.sidebar.warning` fail-soft — P2-2 accepted), `max_entries=2`. CSV loaders: wrapper stats the CSV (`0.0` if missing) → cached impl `(path_str, mtime)` doing the existing read+transform, `max_entries=4` each. `load_report_memory`: same, resolving the two candidate paths in the wrapper. Update the module docstring (no more TTL).

- [ ] **Step 4: Verify** — `pytest -q` → 128 passed; `ruff check .` clean.

- [ ] **Step 5: Commit** — `git commit -m "perf: mtime-keyed data caches — fresh pipeline output visible immediately (fixes P2-5)"`

---

### Task 3: AppTest page-walk smoke test (closes the P5-2 gap)

**Files:**
- Create: `tests/test_app_pages.py`

**Interfaces:**
- Consumes: `dashboard.py` at repo root; nav radio `key="page_nav"`; `live_prices.fetch_live_quotes`.

- [ ] **Step 1: Write the test**

```python
"""AppTest smoke-walk of every page (review finding P5-2, now a committed test).

The review verified rerun determinism with an ad-hoc AppTest drive that was
never committed — so CI could not catch a crash in the render-only components
(pipeline_stats, terminology, masthead, watchlist drilldown). This walk boots
the real dashboard.py and visits all 7 nav targets. Live quotes are stubbed:
no network in CI.
"""
import glob

import pytest
from streamlit.testing.v1 import AppTest

import live_prices

PAGES = [
    "Briefing", "Watchlist", "Signal Tracker", "Pipeline Stats",
    "Scenario Log", "Report Comparison", "Terminology",
]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(live_prices, "fetch_live_quotes", lambda: {})


def _boot() -> AppTest:
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = _boot()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    if page != "Briefing":  # Briefing is the boot default
        at.radio(key="page_nav").set_value(page).run()
    assert not at.exception, f"{page}: {[e.value for e in at.exception]}"
    assert len(at.markdown) > 0  # something actually rendered
```

- [ ] **Step 2: Run** — `pytest tests/test_app_pages.py -q` → 7 passed (these pass immediately; the value is the CI guard).

- [ ] **Step 3: Sanity-check the guard bites** — temporarily inject `raise RuntimeError` at the top of `components/terminology.py:render_terminology_page`, rerun, expect the Terminology case to FAIL, then revert.

- [ ] **Step 4: Verify full suite + lint** — `pytest -q` → 135 passed; `ruff check .` clean.

- [ ] **Step 5: Commit** — `git commit -m "test: AppTest page-walk of all 7 pages (commits the P5-2 verification)"`

---

### Task 4: Watchlist page — fragment-isolate the live fetch

**Files:**
- Modify: `dashboard.py:379-415` (Watchlist branch)

**Interfaces:**
- Consumes: `st.fragment`, `load_report`, `fetch_live_quotes`, `overlay_live` — same pattern as the Briefing branch at `dashboard.py:268`.

- [ ] **Step 1: Restructure.** Keep the date selectbox + `_is_latest` + `_prev_date` derivation on the main run (so changing the date redefines the fragment with the right `run_every`); move report load, live fetch, diff, and rendering into the fragment:

```python
elif page == "Watchlist":
    _dates_desc = list_report_dates()[::-1]  # newest first for the selector
    if not _dates_desc:
        st.error("No report files found in market_data/.")
        st.stop()
    selected_date = st.selectbox(
        "Report date", _dates_desc, index=0, key="watchlist_date"
    )
    _is_latest = selected_date == _dates_desc[0]
    sel_idx = _dates_desc.index(selected_date)
    _prev_date = _dates_desc[sel_idx + 1] if sel_idx + 1 < len(_dates_desc) else None

    # Same treatment the Briefing got in the perf pass: the Yahoo fetch runs
    # inside a fragment so a live-quote cache miss can't block the masthead/
    # sidebar paint, and live prices auto-refresh every 60s in isolation. The
    # selectbox stays on the main run so picking a date redefines the fragment
    # with the right run_every (historical dates never fetch or auto-refresh).
    @st.fragment(run_every=(60 if (LIVE_PRICES and _is_latest) else None))
    def _render_watchlist_body() -> None:
        report = load_report(selected_date)
        _live = fetch_live_quotes() if (LIVE_PRICES and _is_latest) else {}
        if _live:
            report = overlay_live(report, _live)
        watchlist = report.get("watchlist", {})
        benchmarks = report.get("benchmarks", {})

        # Signal-change diff vs the immediately-prior report date. Tickers that
        # newly appeared / disappeared (signal "—") are excluded so we don't
        # flash rows whose change is structural rather than analytical.
        prev_wl = load_report(_prev_date).get("watchlist", {}) if _prev_date else {}
        changed = {
            tk for tk in watchlist
            if prev_wl.get(tk, {}).get("signal", "—") != watchlist.get(tk, {}).get("signal", "—")
            and prev_wl.get(tk, {}).get("signal", "—") != "—"
            and watchlist.get(tk, {}).get("signal", "—") != "—"
        }

        sub_label = f"{sum(1 for tk in watchlist if tk not in RETIRED_TICKERS)} names · click any row to expand"
        if not _is_latest:
            sub_label += f" · viewing {selected_date}"
        render_section_head("The Watchlist", sub_label)
        _render_live_caption(_live, LIVE_PRICES and _is_latest)
        render_pulse(benchmarks)
        render_watchlist(watchlist, changed_tickers=changed)

    _render_watchlist_body()
```

- [ ] **Step 2: Verify** — `pytest -q` (the Task-3 walk exercises this page) → all green; `ruff check .` clean.

- [ ] **Step 3: Commit** — `git commit -m "perf: fragment-isolate the Watchlist live fetch (parity with the Briefing)"`

---

### Task 5: Nav persistence via query params

**Files:**
- Modify: `components/masthead.py` (around the radio at :70-78)
- Test: `tests/test_app_pages.py`

**Interfaces:**
- Produces: URL `?page=<Name>` deep-links; browser refresh keeps the active page.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_app_pages.py`)

```python
def test_query_param_deep_links_to_page():
    if not glob.glob("data/morning_report_*.json"):
        pytest.skip("no report data checked out")
    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.query_params["page"] = "Signal Tracker"
    at.run()
    assert not at.exception
    assert at.radio(key="page_nav").value == "Signal Tracker"


def test_nav_selection_written_back_to_query_params():
    at = _boot()
    at.radio(key="page_nav").set_value("Terminology").run()
    assert not at.exception
    assert at.query_params.get("page") == "Terminology"
```

- [ ] **Step 2: Run to verify they fail** — deep-link lands on "Briefing"; query params never written.

- [ ] **Step 3: Implement** — in `render_masthead_and_nav`, around the existing radio:

```python
    # Deep-linking: seed the nav radio from ?page=… exactly once (before the
    # widget key exists), and mirror the selection back so a browser refresh
    # or a shared URL restores the active page instead of resetting to Briefing.
    _qp_page = st.query_params.get("page")
    if "page_nav" not in st.session_state and _qp_page in _NAV_PAGES:
        st.session_state.page_nav = _qp_page

    st.markdown('<div class="topnav-wrap">', unsafe_allow_html=True)
    page = st.radio(
        "Navigate",
        _NAV_PAGES,
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
    return page
```

- [ ] **Step 4: Verify** — `pytest -q` → 137 passed; `ruff check .` clean.

- [ ] **Step 5: Commit** — `git commit -m "feat: persist active page in ?page= query param (deep links, refresh-safe nav)"`

---

### Task 6: REVIEW.md post-close addendum

**Files:**
- Modify: `REVIEW.md` (header note + new addendum section above *Reference appendix*; reconcile P2-1, P2-5, P5-2 texts)

- [ ] **Step 1: Reconcile stale statements.** Header status line: append that a post-close perf pass and a 2026-07-02 gap-fix pass are recorded in the addendum. P2-1 update block: note deadline tightened 8s→4s and Briefing+Watchlist fragment isolation. P2-5: flip to `✅ FIXED` (mtime-keyed caches; TTL removed). P5-3/P5-2: note the page-walk is now `tests/test_app_pages.py` in CI.

- [ ] **Step 2: Add the addendum section** — dated 2026-07-02, listing: (a) perf pass `2746889` (fragment Briefing, mtime CSS cache, lazy report loaders, deadline 4s, tests 75→121); (b) this pass: P2-5 fixed, P5-2 test committed, Watchlist fragment parity, `display_ticker` centralization (ledger's "app-wide display cleanup"), nav deep-linking, tests → 137; (c) explicitly-skipped items with reasons (P0-1 base-anaconda env, P0-2 lockfile decision, P7-2 monitor, P6-1 remainder, P8-4 remainder, P1-2 remaining slices).

- [ ] **Step 3: Commit** — `git commit -m "Ledger: post-close addendum — perf pass + 2026-07-02 gap fixes recorded"`

---

## Final verification & integration

- [ ] `pytest -q` → 137 passed; `ruff check .` → clean.
- [ ] Live smoke: run the app, confirm Briefing + Watchlist render, nav deep-link works, no console errors.
- [ ] Merge branch into `main` with a `Merge: …` no-ff commit (repo convention), push `main`.
