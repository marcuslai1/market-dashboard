# Codebase Review Ledger

> **Status: CLOSED (2026-07-01).** 8/8 phases done · tests 13 → 75 · `ruff` clean ·
> CI green (py3.10/3.12 + lint). All safe/actionable findings fixed and merged.
> Only **decisions** (P1-2 surface-or-drop; P0-1 local-env upgrade) and explicitly
> **deferred/accepted** items remain — see *Final synthesis*. Resume by reading this
> file in a fresh session.

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
| 2 | Data layer & external I/O | ✅ done |
| 3 | Analytics correctness core | ✅ done |
| 4 | Rendering & security surface | ✅ done |
| 5 | UI state, interaction & orchestration | ✅ done |
| 6 | Design system & theming (code-level) | ✅ done |
| 7 | Performance & scalability | ✅ done |
| 8 | Maintainability, architecture & synthesis | ✅ done |

> Prior work (not re-reviewed): UI/UX visual pass (merged) and the
> code-quality/correctness pass merged as `c7d2bad`.

---

## Baseline metrics (Phase 0 deliverable)
- **Tests:** 75 passing (`pytest -q`) — up from 13 at review start. New files this
  review: `test_formatters`, `test_catalog`, `test_signal_tracker`, `test_filters`,
  `test_live_prices`, `test_rendering_security`, `test_schema`, `test_writeup` (plus
  additions to `test_scenario_log`).
- **Lint:** `ruff check .` clean; CI `lint` job is blocking.
- **Coverage:** started 21%; render-path + I/O + filters + scenario now exercised.
  Still thin: `pipeline_stats`, `terminology`, `masthead` (render-only).
- **Environment (installed vs declared):** streamlit 1.50.0, pandas **1.4.2**,
  plotly **5.6.0**, yfinance 1.2.0. See P0-1.
- **CI:** none. **Lint gate:** none (ruff present in `pyproject` but not enforced).
- **Secrets:** clean — `.streamlit/secrets.toml` gitignored; no creds tracked.

---

## Findings — Phase 0 (baseline & harness)

### P0-1 · major · environment drift from declared deps — ⚠️ mostly resolved
`requirements.txt` floors are `pandas>=2.0.0`, `plotly>=5.18.0`, but the *local* dev
env runs **pandas 1.4.2** and **plotly 5.6.0** — below the floors (source of the
`np.find_common_type` warnings). The worry was "green locally ≠ green on the declared
2.x." **Now verified:** the CI added this review installs the declared deps and the
suite passes on **Python 3.10 and 3.12** (run `28520419857`+ green), so the code is
compatible with pandas ≥2.0. **Remaining (local hygiene, your machine):** upgrade the
local env to the declared floors so local runs match CI (I can't change your env from
here). Optional: pin/lock exact versions (P0-2).

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

### P2-1 update · ✅ FIXED
`fetch_live_quotes` now runs under an 8s wall-clock deadline
(`as_completed(timeout=…)` + `shutdown(wait=False, cancel_futures=True)`), returning
partial results instead of blocking the render. `overlay_live` / `_safe_read_csv`
now have tests (P2-3 ✅). P2-2 (st.* in cached fns) and P2-5 (TTL lag) remain open.

---

## Findings — Phase 3 (analytics correctness core)

### P3-1 · major · `_get_probs` crashed on a non-numeric probability — ✅ FIXED
The new-format branch did `float(v)` with no guard (unlike its sibling
`extract_scenario_history`), so a malformed `probabilities` value would raise and
take down the Report-Comparison drift table. **Fixed:** guarded `float()` (→ `mid=None`)
and normalized the display to `"NN%"`; added `test_get_probs_*`.

### P3-2 · info · episode/accuracy math verified (reviewed clean, now tested)
Added characterization + edge tests: empty inputs → empty frames; `None` entry
price → no return (no crash); HOLD non-directional; WATCH missed-vs-quiet at the 5%
run threshold; accuracy skips `None` signal price; insufficient forward rows → `None`.
All pass — the trade-economics logic (with the P1/earlier ticker+AVOID fixes) is sound.

### P3-3 · minor · row-offset forward returns assume gap-free rows — OPEN (accepted)
`compute_signal_accuracy` still measures "N sessions later" by row offset with no
gap detection (documented as intended). Left as-is; noted so it's a conscious
limitation, not a latent surprise.

---

## Findings — Phase 4 (rendering & security surface)

### P4-1 · info · escaping contract holds end-to-end — ✅ locked with tests
Added `test_rendering_security.py`: hostile payloads through the real builders —
`<script>`/`<img onerror>` in writeup/support_legs/avoid_source, `javascript:` and
attribute-breakout URLs in catalyst links, `<script>` in macro/calendar — are all
neutralized. These lock the fixes from the earlier pass against regression. No new
unescaped sink found in the audit.

---

## Findings — Phase 5 (UI state, interaction & orchestration)

### P5-1 · minor · date filters were coupled to module globals / untestable — ✅ FIXED
`filter_reports`/`filter_prices` lived in `dashboard.py` reading module-global
`DATE_START/END`, so they couldn't be unit-tested without running the whole app.
**Fixed:** extracted to pure `lib/filters.py` taking explicit `(start, end)`; call
sites pass the sidebar range; added `test_filters.py` (inclusive boundaries, non-ISO
keys skipped, empty passthrough). Also removed the now-unused `pandas` import from
`dashboard.py` and compute `.dt.date` once (minor P7 win).

### P5-2 · info · rerun determinism + page walk verified
`AppTest` drives every page (initial + all 7 nav targets) with no exception, across
live-on default, after the filter refactor and the `mark_mounted` relocation. Widget
keys are unique; first-mount gating flips before any `st.stop()` (earlier fix).

### P5-3 · minor · `date_input` single-date state — OPEN (low risk)
Mid-selection Streamlit can return a 1-tuple from the range picker; the code falls
back to the preset range when `len != 2`, so a half-selected range momentarily shows
the default window rather than erroring. Acceptable; documented.

---

## Findings — Phase 6 (design system & theming, code-level)

### P6-1 · minor · ~71 hardcoded hex colors bypass the token system — OPEN
`grep` finds ~71 six-digit hex literals in `components/` (32 in `watchlist/drilldown.py`
alone; also `signal_tracker`, `action_card`, `scenario_log`), many duplicating the
canonical `#22c55e/#ef4444/#f59e0b/#3498db` signal tokens. They can't drift-check
against `catalog.json`. **Fix (deferred, high-churn/low-risk):** route status colors
through `SIGNAL_COLORS` / a small `lib` palette; keep the `test_design_tokens` guard.

### P6-2 · info · token single-source is intact for what's consumed
`test_design_tokens` confirms `theme.css --buy…--avoid` mirror `catalog.json` (AVOID
color included after this review's `SIGNAL_ORDER` change). AVOID pill tint reads from
`catalog` (Python), so no unused `--avoid-tint` CSS var is required.

---

## Findings — Phase 7 (performance & scalability)

### P7-1 · info · current scale is comfortable
Full dataset builds 352 episodes / 221 accuracy rows in well under 100 ms; file
loads are `@st.cache_data`-backed. `filter_prices` now computes `.dt.date` once.

### P7-2 · minor · recompute-per-rerun won't scale linearly — OPEN (monitor)
`extract_signal_history → build_signal_episodes → compute_signal_accuracy` run on
every Signal-Tracker rerun (filter/toggle) and are `O(reports × tickers)`. Fine now;
as history grows to multiple years, memoize on a cheap signature. Not cached today
because the transforms take a `dict` of reports (`st.cache_data` can't hash it) —
caching would need a hashable key (e.g. the sorted date span + selected tickers).

---

## Findings — Phase 8 (maintainability, architecture & synthesis)

### P8-1 · minor · dead-in-app briefing orchestration — ✅ FIXED (deleted)
`render_briefing` (never invoked), `render_interconnected` (zero call sites), and the
wrappers that existed only to serve them (`render_stance`/`render_macro`/
`render_calendar`/`render_action_summary`) were removed, along with the now-unused
`interconnected.py` module and dangling `streamlit`/`render_section_head` imports.
`dashboard.py` continues to hand-call the sub-renderers + `*_html` builders. Verified
ruff-clean, 75 tests green, all 7 pages render via AppTest.

### P8-2 · polish · duplicated HTML-table builder — OPEN
`report_comparison._editorial_table` and the `signal_tracker` grid builders repeat
the `tk-scroll`/`ep-table` pattern. Consolidate into `lib/` if a third consumer appears.

### P8-3 · info · typing & docstrings healthy
81/91 functions in `components/`+`lib/` carry return annotations (~89%); module and
function docstrings are thorough and current.

### P8-4 · minor · accessibility completeness — PARTIAL
Real tables now carry `scope="col"`; div-grids carry `role=table/row/columnheader`;
pulse cells have `aria-label`; and descriptive `st.caption` text alternatives were
added to the previously-captionless charts (scenario prob-over-time; pipeline
tokens/gen-time/articles/prompt-breakdown). Still open (nicety): a per-chart data-table
fallback for full screen-reader parity.

---

## Final synthesis — backlog status

**✅ Safe cleanups done this pass:**
- **P0-4** — tree is now ruff-clean (autofixed imports/`__all__`; fixed implicit
  `Optional` in `macro.py`; `RUF003` ignored for the intentional arrow glyphs). CI
  `lint` job flipped to **blocking**.
- **P0-2** — added upper version bounds (`pandas<3`, `plotly<7`, `streamlit<2`,
  `yfinance<2`) to cap surprise majors. (Full pin/lockfile still pending the P0-1
  floor decision.)
- **P1-3** — legacy-format regression tests added (`test_writeup.py` for the
  `signal_rationale` shim; legacy scenarios-only in `test_scenario_log.py`).
- **P6-1 (partial)** — added `STATUS_POS/NEG/WARN` to `lib/charts.py` and routed the
  analytics color helpers (`_rate_color`, `_ret_color`, episode verdicts) through
  them. ~60 context-specific shade literals remain (deferred, needs visual review).
- **P8-4 (partial)** — descriptive `st.caption` alternatives added to the charts
  that had none (scenario prob-over-time; pipeline tokens/gen-time/articles/prompt).
  A per-chart data-table fallback is still a future nicety.

**Reviewed → acceptable (no change):**
- **P2-2** — `st.sidebar.warning` inside `@st.cache_data`: Streamlit caches & replays
  static elements, so it renders on every run, not just the miss. Not a defect; kept
  for the data-visibility it gives.

**Decisions still needed (yours):**
- **P0-1** — code is CI-verified on the declared deps (py3.10/3.12 green). Only local
  action left: upgrade your local pandas/plotly so local runs match CI (machine-side).
- **P1-2** surface-or-drop the ~13 "produced but unconsumed" report fields.

**Deferred (churn / low value):** P8-2 (editorial-table builder — no 2nd consumer),
P6-1 remainder (context-specific shades).

**Accepted / monitor:** P2-5 (TTL lag), P3-3 (row-offset), P5-3 (date_input tuple),
P7-2 (recompute at scale).

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

## Status
All 8 phases complete. Findings fixed this review: P1-1, P2-1, P2-3, P3-1, P5-1,
plus the escaping/analytics/currency fixes from the earlier merged pass. Remaining
work is captured in **Final synthesis — open backlog** above (decisions + cleanups
+ small robustness items). Resume there.
