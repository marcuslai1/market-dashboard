# Codebase Review Ledger

Standing record for the phased full-codebase review. Resume-friendly: each phase
has a status, and every finding has a stable ID, severity, and fix.

## How this runs
1. Each **phase** is a self-contained read-only pass → a prioritized findings list here.
2. Fixes are implemented test-first, on a branch, only after sign-off.
3. This file is the source of truth — update status/severity as findings are fixed.

## Severity legend
- **blocker** — breaks the app or opens a security hole.
- **major** — wrong output, silent corruption, or resilience gap that will bite.
- **minor** — real but bounded; correctness/robustness/maintainability.
- **polish** — cleanup, consistency, nice-to-have.
- **info** — reviewed-clean note or product decision, no defect.

## Phase tracker
| Phase | Title | Status |
|-------|-------|--------|
| 0 | Baseline & review harness | ✅ done (this pass) |
| 1 | Data contract & schema | ✅ done (this pass) |
| 2 | Data layer & external I/O | ✅ done (this pass) |
| 3 | Analytics correctness core | ⬜ pending |
| 4 | Rendering & security surface | ⬜ pending |
| 5 | UI state, interaction & orchestration | ⬜ pending |
| 6 | Design system & theming (code-level) | ⬜ pending |
| 7 | Performance & scalability | ⬜ pending |
| 8 | Maintainability, architecture & synthesis | ⬜ pending |

> Prior work (not re-reviewed): UI/UX visual pass (merged) and the
> code-quality/correctness pass merged as `c7d2bad`.

---

## Baseline metrics (Phase 0 deliverable)
- **Tests:** 39 passing (`pytest -q`). Files: `test_formatters`, `test_catalog`,
  `test_signal_tracker`, `test_scenario_log`, `test_macro_prints`, `test_design_tokens`.
- **Coverage:** **21% total** (1844 stmts, 1452 missed). Well-covered: `lib/catalog`
  100%, `lib/charts` 76%, `lib/cards` 57%, `lib/formatters` 47%, `components/signal_tracker`
  38%. **0%**: `report_comparison`, `pipeline_stats`, `terminology`, `masthead`,
  `state`, `watchlist/*` (all render-only, no render tests yet).
- **Environment (installed vs declared):** streamlit 1.50.0, pandas **1.4.2**,
  plotly **5.6.0**, yfinance 1.2.0. See P0-1.
- **CI:** none. **Lint gate:** none (ruff present in `pyproject` but not enforced).
- **Secrets:** clean — `.streamlit/secrets.toml` gitignored; no creds tracked.

---

## Findings — Phase 0 (baseline & harness)

### P0-1 · major · environment drift from declared deps — OPEN
`requirements.txt` floors are `pandas>=2.0.0`, `plotly>=5.18.0`, but the dev env
runs **pandas 1.4.2** and **plotly 5.6.0** — *below* the floors. Tests pass on
versions the project claims not to support; pandas 1.x↔2.x differ in `groupby`,
`to_datetime`, empty-reduction, and `.iloc[].get()` behavior, so green here ≠ green
on a compliant install (also the source of the `np.find_common_type` warnings).
**Fix:** either bring the env up to the declared floors, or pin `requirements.txt`
to versions actually used/tested; ideally a CI matrix on both.

### P0-2 · minor · unpinned dependencies / no lockfile — OPEN
All deps use `>=`; no lock/constraints file → non-reproducible builds and silent
transitive drift. **Fix:** pin exact versions or add a lockfile
(`requirements.lock` / `pip-tools` / `uv`).

### P0-3 · minor · no CI — OPEN
No `.github/workflows`. Tests and lint aren't enforced on push. **Fix:** add a
workflow running `pytest -q` (and decide on the ruff gate, P0-4) on PRs.

### P0-4 · minor · ruff configured but not enforced (11 pre-existing violations) — OPEN
`pyproject` defines a rich ruff config, but the tree has 11 standing violations:
import sorting (`I001`) in several files, `RUF013` implicit-Optional in
`macro.py:110,277`, `RUF003` ambiguous unicode in `report_comparison.py:25-26`
comments, `RUF022` unsorted `__all__` in two `__init__.py`. **Fix:** decide
adopt-and-clean (then gate in CI) or trim the ruleset to what you'll enforce.

### P0-5 · info · secrets handling is clean
`.streamlit/secrets.toml` is gitignored; no credentials tracked. (A grep hit on
`test_design_tokens.py` was a false positive on the word "token".)

---

## Findings — Phase 1 (data contract & schema)

### P1-1 · major · `SNDK` is an active ticker absent from `catalog.json` — ✅ FIXED
`SNDK` appeared in watchlist data but was missing from **all** catalog maps
(`cluster`, `yahoo`, `display`). Consequences: no live-price overlay
(`live_prices` couldn't map it → always frozen snapshot), and a **blank sector**
everywhere (`CLUSTER_MAP.get("SNDK","")`). **Fixed:** added `SNDK` → `Semis`
(cluster) and `SNDK` → `SNDK` (yahoo); added a guard test
(`test_every_active_ticker_has_cluster_and_yahoo`) that fails if any non-retired
watchlist ticker is missing from the cluster or yahoo maps.

### P1-2 · minor · large "produced but never consumed" surface — OPEN (product call)
Report fields the pipeline emits that **no code reads** (grep-confirmed, refs=0):
`clusters` (top-level, 100%), `calibration_insights` (43%), `extension_regime`
(40%), `scheduled_tech_events` (25%), `macro_context_line` (23%),
`news_sentiment_skew` (51%), `thesis_highlights` (18%), `vs_cluster_chg_pct/5d/1mo`
(36%), `premarket`/`pm_price`/`pm_chg_pct`/`market_state` (~21%), `eps_trajectory`,
`eps_surprise`, `structural_conviction`. (Internal `_telemetry`/`_signal_mutations`
are underscore-prefixed and intentionally not for display — ignore.) **Action:**
product decision to surface or drop; at minimum document so the gap is intentional.

### P1-3 · minor · legacy format paths are LIVE — must stay tested — OPEN
Dual-format handling is genuinely exercised, not dead code: **548 entries** still
use legacy `signal_rationale` (vs 1197 new `writeup` dict), and **5 reports** use
`geopolitical.scenarios`-only (legacy) vs 76 new `probabilities`. The legacy
branches in `_writeup_for_render`, `_get_probs`, `extract_scenario_history` are
required. **Fix:** add regression tests pinning legacy behavior (only the
new-format scenario path is currently tested).

### P1-4 · minor · schema redundancy + one null signal — OPEN
Data carries overlapping fields (`vs_50sma` **and** `vs_sma50_pct`; `sma50_warning`
alongside the `momentum_warn*` the code actually uses); one watchlist entry has
`signal: null` (handled defensively downstream). Not a code bug — flag to the
pipeline side to avoid future reader confusion.

### P1-5 · info · CSV schemas healthy
All code-referenced columns exist in `market_data.csv`, `pipeline_stats.csv` (44
cols; code back-fills a subset), `claude_analysis.csv`, `signal_log.csv`. Low drift
risk today.

### P1-6 · minor · no schema validation (silent `.get()` defaulting) — OPEN
Every reader tolerates missing keys via `.get(...)`, so schema drift fails silently
(a renamed field just renders as "—"). **Fix (optional Phase-1 deliverable):** a
lightweight validator over the latest report asserting the required core schema, run
as a test, so drift fails loudly.

---

## Findings — Phase 2 (data layer & external I/O)

### P2-1 · major · `fetch_live_quotes` has no bounded deadline — OPEN
`live_prices._fetch_one` calls `yf.Ticker(sym).fast_info` with no request timeout,
and `fetch_live_quotes` uses `as_completed(futures)` with **no `timeout=`**. Live
prices are **on by default** and fetched on the Briefing/Watchlist first render, so
a slow or hanging Yahoo endpoint stalls the whole page until every one of ~40
symbols resolves (or the OS socket eventually gives up) — tens of seconds in the
bad case, repeated every 60s cache miss. **Fix:** put an overall wall-clock deadline
on `as_completed(..., timeout=T)`, catch `TimeoutError`, and return whatever
completed (the caller already treats a partial/empty dict as "some/all frozen").
Optionally pass a per-call network timeout to yfinance.

### P2-2 · minor · `st.*` calls inside `@st.cache_data` functions — OPEN
`load_all_reports` and the new `_safe_read_csv` call `st.sidebar.warning(...)` from
inside cached functions. Streamlit discourages emitting UI from cached code — it
only runs on a cache miss and can trigger a "calling st commands inside a cached
function" warning, and the message won't reappear on cache hits (so a persistent
bad file goes quiet after the first miss). **Fix:** return a status/error from the
loader and render the warning in the page layer, outside the cache.

### P2-3 · minor · no tests for the I/O layer — OPEN
`overlay_live` (pure, trivially testable), `fetch_live_quotes` meta/partial-fill,
and `_safe_read_csv` have zero coverage (`data_loader` 27%). **Fix:** unit-test
`overlay_live` (benchmark+watchlist merge, partial fill, empty-live passthrough,
no mutation of the input report) and `_safe_read_csv` (missing/malformed/empty →
empty frame, no raise).

### P2-4 · info · `overlay_live` merge is currency-safe (reviewed clean)
Live quotes overlay only `price`/`chg_pct`; `currency` and all snapshot fields
(sma/rsi/1mo/…) stay frozen. Yahoo returns the instrument's **native** currency,
which matches the report entry's `currency`, so the `_ccy_prefix`/symbol stays
correct (SGD→S$, KRW→₩, …). It shallow-copies before mutating, so the cached report
object isn't corrupted, and unmatched keys fall back per-key. No corruption path
found. (After P1-1, `SNDK` now overlays live too.)

### P2-5 · minor · report/price cache TTL lag — OPEN (accept or tune)
All file loaders use `ttl=300`; a fresh pipeline run is invisible for up to 5 min
unless the user hits a Refresh button (which clears all caches). Fine for a
once-per-session pipeline, but document the expectation or lower the TTL if faster
pickup is wanted.

### P2-6 · info · caching mutation safety (reviewed clean)
Callers `.copy()` cached frames before mutating (`pipeline_stats`), and the analytics
transforms build new frames rather than mutating in place, so cached objects aren't
corrupted across reruns.

---

## Reference appendix

### Observed report schema (82 files)
- **Always present (100%):** `meta`, `benchmarks`, `macro_summary`, `commodities_note`,
  `watchlist`, `clusters`, `interconnected`, `geopolitical`, `events_this_week`,
  `portfolio_snapshot`, `action_summary`.
- **Sometimes:** `macro_trigger_map` 85%, `_telemetry`/`calibration_insights` 43%,
  `extension_regime` 40%, `macro_indicators` 26%, `scheduled_tech_events` 25%,
  `contrarian_candidates` 23%, `macro_context_line` 23%, `accumulate_paper_status` 10%.
- **`meta.*`:** `report_date`/`market_date`/`generated_at`/`timezone` 100%;
  `data_coverage`/`prev_snapshot_status` 19%.

### Watchlist entry — key fields (1746 entries)
- **Core (100%):** price, currency, chg_pct, 5d_pct, 1mo_pct, sma10/50/100/200,
  vs_sma50_pct, rsi_14, rsi_zone, volume, vol_ratio, volume_signal, raw_signal,
  days_above_sma50, sma50_rising, entry_block.
- **Common:** signal 99%, valuation 95%, risk_reward 93%, accumulate_gates 78%,
  writeup(dict) 68%, momentum_warn 65%, signal_rationale(legacy) 31%.
- **Rare:** pre_earnings_band 3%, rcp_state 2%, support_legs 1%, catalyst <1%,
  earnings_results_in_news <1%, avoid_source <1%.
- **Currencies:** USD 1328, SGD 286, EUR 70, KRW 44, TWD 18 (TWD only via retired 2308_TW).

### Catalog coverage
- Watchlist tickers seen: 35. Missing from cluster+yahoo maps: **`SNDK`** (P1-1).
- No orphans (every cluster-mapped ticker appears in data).

### Format distribution
- writeup dict 1197 / legacy signal_rationale 548 entries.
- geopolitical.probabilities 76/82 / scenarios-only 5.

---

## Full phase plan (for resuming)
**P3 Analytics core** — episodes/accuracy/scenario/drift math; property tests; trading-day semantics.
**P4 Rendering & security** — enumerate all ~57 `unsafe_allow_html` sinks; prove the escaping contract.
**P5 UI state & orchestration** — rerun determinism, widget keys, filter parity, session lifecycle.
**P6 Design system** — token single-source (extend guard), hardcoded hex, chart/card/pill consistency.
**P7 Performance** — rerun cost, O(reports×tickers) recompute, caching boundaries, scale to years.
**P8 Maintainability & synthesis** — module boundaries, DRY, dead exports, typing, a11y completeness, final backlog.

Suggested order: 0→1 (done) → 2 → 3 → 4 → 5 → 6 → 7 → 8. Minimum path: 3 + 4 next.
