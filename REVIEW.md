# Codebase Review Ledger

> **Status: CLOSED (2026-07-01).** 8/8 phases done · tests 13 → 75 · `ruff` clean ·
> CI green (py3.10/3.12 + lint). All safe/actionable findings fixed and merged.
> Only **decisions** (P1-2 surface-or-drop; P0-1 local-env upgrade) and explicitly
> **deferred/accepted** items remain — see *Final synthesis*. Resume by reading this
> file in a fresh session.
>
> **Resume verification (2026-07-01):** re-walked every remaining thread against the
> code. Confirmed `pytest -q` → **75 passed** locally (py3.9 / pandas 1.4.2 — the
> P0-1 env, hence the cosmetic `np.find_common_type` warnings) and `ruff check .`
> clean. Reconciled 6 stale per-finding headers that still read *OPEN* but had
> shipped: **P0-3** (CI), **P0-4** (ruff gate), **P1-3** (legacy-format tests),
> **P1-6** (schema guard — verified running against the real 82-file dataset, not
> skipping), plus **P2-1** (live-quote deadline — had a ✅ update block below) and
> **P2-3** (I/O-layer tests). Re-checked **P8-2**: still only 2 consumers, deferral
> holds. Nothing
> else was both worth-doing and doable without a product (P1-2) or machine (P0-1)
> decision, so the rest is left as-is. **Review complete.**
>
> **Post-close addendum (2026-07-02):** two passes shipped after the ledger closed
> and are reconciled in *Post-close addendum* below — the performance pass (merge
> `2746889`) and the review-gap pass (this one: **P2-5 fixed**, the P5-2 page-walk
> committed as a real test, Watchlist fragment parity, app-wide `display_ticker`
> cleanup, nav deep-linking). Suite now **138 passing**.

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

**Update (2026-07-02, closeout pass) — ✅ resolved locally without touching base
Anaconda:** a project `.venv` (system Python 3.10, gitignored) installed from the new
`requirements.lock` now runs the suite on pandas 2.3.3 / streamlit 1.58 — first
green local run on the declared 2.x line. Base Anaconda is unchanged; run the app
from `.venv\Scripts\python -m streamlit run dashboard.py` for a CI-matching env.

### P0-2 · minor · unpinned dependencies / no lockfile — ✅ FIXED (2026-07-02)
All deps used `>=`; no lock/constraints file → non-reproducible builds and silent
transitive drift. **Fixed:** `requirements.lock` compiled with
`uv pip compile requirements.txt --universal -o requirements.lock`; CI's test job
installs the lock, `requirements.txt` stays the human-edited floors source.

### P0-3 · minor · no CI — ✅ FIXED
No `.github/workflows`. Tests and lint aren't enforced on push. **Fixed:**
`.github/workflows/ci.yml` runs `pytest -q` on Python 3.10 + 3.12 (installing the
declared `requirements.txt` floors) plus a blocking `ruff check .` lint job, on push
to `main` and every PR.

### P0-4 · minor · ruff configured but not enforced (11 pre-existing violations) — ✅ FIXED
`pyproject` defines a rich ruff config, but the tree had 11 standing violations:
import sorting (`I001`) in several files, `RUF013` implicit-Optional in
`macro.py:110,277`, `RUF003` ambiguous unicode in `report_comparison.py:25-26`
comments, `RUF022` unsorted `__all__` in two `__init__.py`. **Fixed (adopt-and-clean):**
autofixed imports/`__all__`, made the `macro.py` Optionals explicit, and ignored
`RUF003` for the intentional arrow glyphs — tree is now `ruff check .` clean and the
CI `lint` job is blocking.

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

### P1-2 · minor · large "produced but never consumed" surface — ✅ CLOSED (2026-07-02, six slices surfaced + remainder documented-dropped)
Report fields the pipeline emits that **no code reads** (grep-confirmed, refs=0):
`clusters` (top-level, 100%), `calibration_insights` (43%), `extension_regime`
(40%), `scheduled_tech_events` (25%), `macro_context_line` (23%),
`news_sentiment_skew` (51%), `thesis_highlights` (18%), `vs_cluster_chg_pct/5d/1mo`
(36%), `premarket`/`pm_price`/`pm_chg_pct`/`market_state` (~21%), `eps_trajectory`,
`eps_surprise`, `structural_conviction`. (Internal `_telemetry`/`_signal_mutations`
are underscore-prefixed and intentionally not for display — ignore.) **Action:**
product decision to surface or drop; at minimum document so the gap is intentional.

**Update (2026-07-02) — first slice surfaced (merge `9efe4e7`):** `clusters` is now
rendered as the **Briefing cluster band** (collapsed row = name + computed at-a-glance
[signal mix + extension breadth] + `key_development`; expands to `thesis_status` +
`summary` + a per-name anchor table). That band also consumes
`extension_regime.blocked_tickers` for the breadth chip. So `clusters` is fully
consumed and `extension_regime` is now partially consumed (the rest —
`hard_block_count`/`pct`/`active` — still unused). **Remaining unconsumed (~11):**
`calibration_insights`, `scheduled_tech_events`, `macro_context_line`,
`news_sentiment_skew`, `thesis_highlights`, `vs_cluster_chg_pct/5d/1mo`,
`premarket`/`pm_*`/`market_state`, `eps_trajectory`, `eps_surprise`,
`structural_conviction`. Next candidate slices: earnings/events
(`scheduled_tech_events`) and the calibration scorecard (`calibration_insights`).
Design + plan: `docs/superpowers/specs/2026-07-01-cluster-briefing-band-design.md`,
`docs/superpowers/plans/2026-07-02-cluster-briefing-band.md`.

**Update (2026-07-02) — second slice surfaced (merge `59b32e5`):** `calibration_insights`
is now rendered as the **Briefing signal-calibration band** (placed after the cluster
band): a confidence-gated scorecard anchored to today's live signals — collapsed headline
(today's dominant signal + its 10d alpha + confidence state), expands to a per-signal track
record (n / win-rate / avg-10d / alpha, all buckets by `SIGNAL_ORDER`, low-confidence rows
muted), the full-corpus taxonomy verdict, and the `confidence_banner` caveat. So
`calibration_insights` is now fully consumed. **Remaining unconsumed (~10):**
`scheduled_tech_events`, `macro_context_line`, `news_sentiment_skew`, `thesis_highlights`,
`vs_cluster_chg_pct/5d/1mo`, `premarket`/`pm_*`/`market_state`, `eps_trajectory`,
`eps_surprise`, `structural_conviction`. Next candidate slice: the genuinely-free earnings
piece is `eps_trajectory` (beat/miss history for MU / SK Hynix / LITE / PLTR) — note
`scheduled_tech_events` is sparse (only 2/82 reports carry a *future* event) and
`macro_trigger_map` is **already** consumed via `render_catalyst_playbook`, so the earnings
slice is narrower than it first looked. Design + plan:
`docs/superpowers/specs/2026-07-02-calibration-scorecard-band-design.md`,
`docs/superpowers/plans/2026-07-02-calibration-scorecard-band.md`.

**Update (2026-07-02) — third slice surfaced (merge `193d09c`):** `eps_trajectory` is now
rendered as the **Briefing earnings-scorecard band** (placed after the calibration band): a
collapsible beat/miss track record for the AI beneficiaries carrying the field (MU / SK Hynix /
LITE / PLTR) — collapsed corpus headline (*"N of M beat last quarter · K accelerating"*), expands
to a per-ticker scorecard (latest surprise + the 4-quarter surprise trend, beat green / miss red)
plus the `accel_reason` lines for accelerating names. So `eps_trajectory` is now fully consumed.
The ledger correction was **verified against the data first**: `scheduled_tech_events` is present
in 21/82 reports but only **2–3/82 carry a forward-dated event** (the rest are `"released"`
back-recaps), and `macro_trigger_map` is confirmed consumed (`dashboard.py:250`→`:316`
`render_catalyst_playbook`) — so `eps_trajectory` was the genuinely-free piece. Two real-data
gotchas surfaced during TDD: `watchlist` is a **dict keyed by ticker** (not a list), and
`TICKER_DISPLAY` is a **sparse** override map that omits plain underscore-for-dot keys
(`000660_KS`) — so a local `_display_ticker` fallback restores the dotted `000660.KS` the cluster
band already shows (note: the sibling `changes` band still leaked the underscore key — fixed
2026-07-02 by promoting the helper to `lib.formatters.display_ticker` and routing all 8 raw
`TICKER_DISPLAY.get(tk, tk)` callsites through it; see the addendum). **Remaining unconsumed (~8):** `scheduled_tech_events`
(sparse — forward-events dead-end), `macro_context_line`, `news_sentiment_skew`,
`thesis_highlights`, `vs_cluster_chg_pct/5d/1mo`, `premarket`/`pm_*`/`market_state`,
`eps_surprise`, `structural_conviction`. Design + plan:
`docs/superpowers/specs/2026-07-02-earnings-scorecard-band-design.md`,
`docs/superpowers/plans/2026-07-02-earnings-scorecard-band.md`.

**Final update (2026-07-02, slices pass — CLOSED):** three more slices shipped into
the watchlist **drill-down** (`vs_cluster_chg_pct` → "vs cluster (1d)" Technicals
cell, 659 entries corpus-wide; `news_sentiment_skew` → lean-colored status chip,
933; `premarket.phrase` → sign-colored status chip, 85 — snapshot-time context by
design). The remainder is **documented-dropped**, each with a reason:
- `thesis_highlights` — sparse (~6 names/day), partially duplicates the writeup,
  and the strings carry `�` encoding artifacts (pipeline-side bug; fix there first).
- `eps_surprise` — absent from current reports (superseded by `eps_trajectory`,
  which is fully consumed by the earnings band).
- `structural_conviction` — 2 entries in the latest report; too thin to design for.
- `macro_context_line` — caveat prose; the macro card already carries
  `macro_indicators` and the summary. Adding a second caveat line dilutes it.
- `scheduled_tech_events` — only 2–3/82 reports carry a forward-dated event.
- `vs_cluster_5d/1mo` — not emitted by the current pipeline (only `chg_pct` is);
  wire the drilldown cells if the pipeline starts producing them.
Every remaining unconsumed field is now an intentional, documented drop — P1-2 done.

### P1-3 · minor · legacy format paths are LIVE — must stay tested — ✅ FIXED
Dual-format handling is genuinely exercised, not dead code: **548 entries** still
use legacy `signal_rationale` (vs 1197 new `writeup` dict), and **5 reports** use
`geopolitical.scenarios`-only (legacy) vs 76 new `probabilities`. The legacy
branches in `_writeup_for_render`, `_get_probs`, `extract_scenario_history` are
required. **Fixed:** `test_writeup.py` pins the `signal_rationale` shim
(headline/body split, single-sentence, HOLD + CAUTION-hard-block suppression, both
`_legacy_rationale_from` directions); `test_scenario_log.py` adds
`test_get_probs_legacy_range_midpoint` and `test_extract_history_legacy_scenarios_only`
for the scenarios-only path.

### P1-4 · minor · schema redundancy + one null signal — OPEN
Data carries overlapping fields (`vs_50sma` **and** `vs_sma50_pct`; `sma50_warning`
alongside the `momentum_warn*` the code actually uses); one watchlist entry has
`signal: null` (handled defensively downstream). Not a code bug — flag to the
pipeline side to avoid future reader confusion.

### P1-5 · info · CSV schemas healthy
All code-referenced columns exist in `market_data.csv`, `pipeline_stats.csv` (44
cols; code back-fills a subset), `claude_analysis.csv`, `signal_log.csv`. Low drift
risk today.

### P1-6 · minor · no schema validation (silent `.get()` defaulting) — ✅ FIXED
Every reader tolerates missing keys via `.get(...)`, so schema drift fails silently
(a renamed field just renders as "—"). **Fixed:** `tests/test_schema.py` validates
the newest `data/morning_report_*.json` against the required core schema — top-level
keys (`meta`/`benchmarks`/`watchlist`/`geopolitical`/`events_this_week`/
`portfolio_snapshot`), `meta.report_date`/`market_date`, and per-entry
`price`/`currency`/`signal` — so drift fails loudly in CI. Confirmed executing
against the real 82-file dataset (not skipping).

---

## Findings — Phase 2 (data layer & external I/O)

### P2-1 · major · `fetch_live_quotes` has no bounded deadline — ✅ FIXED (see P2-1 update below)
`live_prices._fetch_one` calls `yf.Ticker(sym).fast_info` with no request timeout,
and `fetch_live_quotes` uses `as_completed(futures)` with **no `timeout=`**. Live
prices are **on by default** and fetched on the Briefing/Watchlist first render, so
a slow or hanging Yahoo endpoint stalls the whole page until every one of ~40
symbols resolves (or the OS socket eventually gives up) — tens of seconds in the
bad case, repeated every 60s cache miss. **Fix:** put an overall wall-clock deadline
on `as_completed(..., timeout=T)`, catch `TimeoutError`, and return whatever
completed (the caller already treats a partial/empty dict as "some/all frozen").
Optionally pass a per-call network timeout to yfinance.

### P2-2 · minor · `st.*` calls inside `@st.cache_data` functions — OPEN (accepted — no change)
`load_all_reports` and the new `_safe_read_csv` call `st.sidebar.warning(...)` from
inside cached functions. Streamlit discourages emitting UI from cached code — it
only runs on a cache miss and can trigger a "calling st commands inside a cached
function" warning, and the message won't reappear on cache hits (so a persistent
bad file goes quiet after the first miss). **Fix:** return a status/error from the
loader and render the warning in the page layer, outside the cache.

### P2-3 · minor · no tests for the I/O layer — ✅ FIXED
`overlay_live` (pure, trivially testable), `fetch_live_quotes` meta/partial-fill,
and `_safe_read_csv` had zero coverage (`data_loader` 27%). **Fixed:**
`tests/test_live_prices.py` covers `overlay_live` (benchmark+watchlist merge,
partial fill, empty-live passthrough returning the same object — no mutation) and
`_safe_read_csv` (missing/malformed → empty frame, no raise).

### P2-4 · info · `overlay_live` merge is currency-safe (reviewed clean)
Live quotes overlay only `price`/`chg_pct`; `currency` and all snapshot fields
(sma/rsi/1mo/…) stay frozen. Yahoo returns the instrument's **native** currency,
which matches the report entry's `currency`, so the `_ccy_prefix`/symbol stays
correct (SGD→S$, KRW→₩, …). It shallow-copies before mutating, so the cached report
object isn't corrupted, and unmatched keys fall back per-key. No corruption path
found. (After P1-1, `SNDK` now overlays live too.)

### P2-5 · minor · report/price cache TTL lag — ✅ FIXED (2026-07-02)
All file loaders used `ttl=300`; a fresh pipeline run was invisible for up to 5 min
unless the user hit a Refresh button (which clears all caches). **Fixed:** every
loader is now mtime-keyed (stat()-ing wrapper over a cached impl taking
`(path, mtime)`, the pattern `_read_text_asset` proved) — a regenerated file busts
its entry on the next rerun, no TTL, no manual refresh needed. `load_all_reports`
keys on a whole-corpus (path, mtime) fingerprint; `list_report_dates` keys on the
data dir's mtime; all caches carry `max_entries`. Staleness pinned by 4 tests in
`test_data_loader.py`.

### P2-6 · info · caching mutation safety (reviewed clean)
Callers `.copy()` cached frames before mutating (`pipeline_stats`), and the analytics
transforms build new frames rather than mutating in place, so cached objects aren't
corrupted across reruns.

### P2-1 update · ✅ FIXED
`fetch_live_quotes` now runs under an 8s wall-clock deadline
(`as_completed(timeout=…)` + `shutdown(wait=False, cancel_futures=True)`), returning
partial results instead of blocking the render. `overlay_live` / `_safe_read_csv`
now have tests (P2-3 ✅). P2-2 (st.* in cached fns) and P2-5 (TTL lag) remain open.
*(Post-close: the perf pass tightened the deadline to **4s** and moved the Briefing
fetch into a fragment; the 2026-07-02 gap pass gave the Watchlist the same fragment
treatment and fixed P2-5 — see the addendum.)*

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
*(Post-close correction: that drive was ad-hoc and never landed in the suite — CI
couldn't catch a crash in the render-only components. Fixed 2026-07-02:
`tests/test_app_pages.py` walks all 7 pages with live quotes stubbed, and the guard
was verified to bite via an injected crash.)*

### P5-3 · minor · `date_input` single-date state — OPEN (low risk)
Mid-selection Streamlit can return a 1-tuple from the range picker; the code falls
back to the preset range when `len != 2`, so a half-selected range momentarily shows
the default window rather than erroring. Acceptable; documented.

---

## Findings — Phase 6 (design system & theming, code-level)

### P6-1 · minor · ~71 hardcoded hex colors bypass the token system — ✅ FIXED (2026-07-02)
`grep` finds ~71 six-digit hex literals in `components/` (32 in `watchlist/drilldown.py`
alone; also `signal_tracker`, `action_card`, `scenario_log`), many duplicating the
canonical `#22c55e/#ef4444/#f59e0b/#3498db` signal tokens. They can't drift-check
against `catalog.json`. **Fix (deferred, high-churn/low-risk):** route status colors
through `SIGNAL_COLORS` / a small `lib` palette; keep the `test_design_tokens` guard.

**Update (2026-07-02, closeout pass) — ✅ FIXED:** every component hex literal now
routes through `lib/charts` semantic constants (values byte-identical, rendering
unchanged by construction). `terminology.py` is the one sanctioned exception (static
HTML/CSS block); two new `test_design_tokens` guards enforce the invariant —
components stay hex-free, and terminology's static colors must match the palette.

### P6-2 · info · token single-source is intact for what's consumed
`test_design_tokens` confirms `theme.css --buy…--avoid` mirror `catalog.json` (AVOID
color included after this review's `SIGNAL_ORDER` change). AVOID pill tint reads from
`catalog` (Python), so no unused `--avoid-tint` CSS var is required.

---

## Findings — Phase 7 (performance & scalability)

### P7-1 · info · current scale is comfortable
Full dataset builds 352 episodes / 221 accuracy rows in well under 100 ms; file
loads are `@st.cache_data`-backed. `filter_prices` now computes `.dt.date` once.

### P7-2 · minor · recompute-per-rerun won't scale linearly — ✅ FIXED (2026-07-02)
`extract_signal_history → build_signal_episodes → compute_signal_accuracy` ran on
every Signal-Tracker rerun (filter/toggle) and are `O(reports × tickers)`. **Fixed:**
the derives now memoize via `st.cache_data` keyed on
`(data_fingerprint(), DATE_START, DATE_END)` — a cheap (path, mtime) signature over
the report corpus + `market_data.csv` — with the heavy frames passed as
underscore-prefixed (unhashed) args. `cache_key=None` keeps tests/ad-hoc callers on
the uncached path.

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

### P8-4 · minor · accessibility completeness — ✅ FIXED (2026-07-02)
Real tables now carry `scope="col"`; div-grids carry `role=table/row/columnheader`;
pulse cells have `aria-label`; and descriptive `st.caption` text alternatives were
added to the previously-captionless charts (scenario prob-over-time; pipeline
tokens/gen-time/articles/prompt-breakdown). **Closeout pass:** the remaining nicety
shipped — `chart_data_table` (lib/charts) renders each chart's exact source frame
behind a collapsed expander, applied to all 7 charts for full data parity.

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
  *(Closeout pass: resolved via the project `.venv` — see the P0-1 update.)*
- **P1-2** surface-or-drop the **remaining ~8** "produced but unconsumed" report
  fields — three slices shipped 2026-07-02: the `clusters` cluster band (merge `9efe4e7`,
  also consuming `extension_regime.blocked_tickers`), the `calibration_insights`
  signal-calibration band (merge `59b32e5`), and the `eps_trajectory` earnings-scorecard
  band (merge `193d09c`). *(Closed later the same day by the slices pass: three drill-down
  slices shipped + every remaining field documented-dropped with a reason — see the
  P1-2 final update.)*

**Deferred (churn / low value):** P8-2 (editorial-table builder — no 2nd consumer).
*(P6-1 remainder was here; fixed in the closeout pass.)*

**Accepted / monitor:** P3-3 (row-offset), P5-3 (date_input tuple).
*(P2-5 and P7-2 were on this list; both fixed 2026-07-02 — see addendum.)*

---

## Post-close addendum (2026-07-02)

Two passes shipped after the ledger closed. Recorded here so this file stays the
source of truth.

### A. Performance pass (merge `2746889`, not previously in the ledger)
Cost model: Streamlit reruns the whole script per interaction. Three fixes:
- **Briefing body in `st.fragment(run_every=60)`** — the Yahoo fetch left the main
  script run; masthead/nav/sidebar paint immediately and live prices refresh in
  isolation. `_FETCH_DEADLINE_S` tightened **8s → 4s** (supersedes the P2-1 text).
- **`load_text_asset`** — mtime-keyed cached read of the ~49KB `theme.css` (a
  `stat()` per rerun instead of a full decode; edits still hot-reload).
- **Lazy report loaders** — `list_report_dates` / `load_report` so hot-path pages
  (masthead, Briefing, Watchlist) stop parsing all ~80 reports. Suite 75 → 121.

### B. Review-gap pass (this branch)
An audit of this ledger against the tree found four real gaps; all fixed:
- **P2-5 → ✅ FIXED** — every loader mtime-keyed; TTL removed (details at P2-5).
- **P5-2 page-walk → committed** — `tests/test_app_pages.py` (the ledger cited an
  AppTest drive that was never in the suite); guard verified to bite.
- **Watchlist fragment parity** — the perf pass fragmented only the Briefing; the
  Watchlist page's live fetch blocked its render and never auto-refreshed.
- **`display_ticker` centralized** (`lib/formatters.py`) — the 8 raw
  `TICKER_DISPLAY.get(tk, tk)` callsites (changes ribbon, watchlist row, action
  card, contrarians, cluster anchors, Signal Tracker ×3) leaked underscore keys
  like `000660_KS`; flagged in the P1-2 third-slice note, now routed.
- Plus one small feature: **nav deep-linking** — the active page persists in
  `?page=`, so browser refresh / shared URLs no longer reset to the Briefing.

Suite after this pass: **138 passing**; `ruff check .` clean.

### Skipped knowingly (statuses at the time of the gap pass, with reasons)
- **P0-1** — local env is base Anaconda (not a venv); upgrading pandas/plotly there
  is a machine-level call only the user should make. CI still proves 2.x compat.
- **P0-2** — lockfile needs a tooling decision (uv / pip-tools) from the user.
- **P7-2** — transforms still <100 ms on the full corpus; memoization complexity
  not yet paid for. Monitor stands.
- **P6-1 remainder / P8-4 remainder** — need visual review / are niceties.
- **P1-2 remaining ~8 fields** — product decisions (next natural slices:
  `vs_cluster_chg_pct` in the drilldown, `news_sentiment_skew` chips,
  `premarket`/`market_state` masthead indicator; or document-and-drop).

*(All five were subsequently closed the same day by the **closeout pass** below,
after the user approved the recommendations.)*

### C. Ledger-closeout pass (2026-07-02, branch `ledger-closeout-2026-07-02`)
User-approved "do all of it" pass over the skip list:
- **P0-2 → ✅** `requirements.lock` (uv, `--universal`); CI test job installs it.
- **P0-1 → ✅ (local)** project `.venv` on system Python 3.10 from the lock — first
  local suite run on pandas 2.3.3 / streamlit 1.58, green; base Anaconda untouched.
- **P7-2 → ✅** Signal-Tracker derives memoized on `(data_fingerprint(), date range)`.
- **P8-4 → ✅** `chart_data_table` fallback under all 7 charts.
- **P6-1 → ✅** all component hexes routed through `lib/charts` constants;
  terminology.py sanctioned-exception + two drift guards in `test_design_tokens`.
- **Navigation upgraded again:** the morning's `?page=` mechanism is replaced by
  native `st.navigation`/`st.Page` — real URL per page (`/briefing`, …), browser
  back/forward and refresh are Streamlit-native; the masthead radio mirrors the
  navigation state and issues `st.switch_page`.

### D. P1-2 slices pass (2026-07-02, branch `p12-slices-2026-07-02`)
Final P1-2 work: `vs_cluster_chg_pct` / `news_sentiment_skew` / `premarket.phrase`
surfaced in the watchlist drill-down (tests in `test_drilldown.py`); the remaining
unconsumed fields documented-dropped with reasons (see the P1-2 final update).
**With this, every finding in this ledger is either fixed, consciously accepted, or
documented-dropped — nothing is left open.** Suite: 151 passing.

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
All 8 phases complete. Findings fixed this review: P0-3, P0-4, P1-1, P1-3, P1-6,
P2-1, P2-3, P3-1, P5-1, plus the escaping/analytics/currency fixes from the earlier
merged pass. Remaining work is captured in **Final synthesis — open backlog** above,
and is entirely **decisions** (P0-1 local-env upgrade — machine-side; P1-2
surface-or-drop) plus explicitly **deferred/accepted/monitor** items (P0-2 lockfile,
P1-4, P2-2, P3-3, P5-3, P6-1 remainder, P7-2, P8-2, P8-4 remainder) — none of
which is newly actionable in-repo without your input. Review verified and complete
(see *Resume verification* at top; post-close work is reconciled in the
*Post-close addendum*, which also fixed P2-5).
