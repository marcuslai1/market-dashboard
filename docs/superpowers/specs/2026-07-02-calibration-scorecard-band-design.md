# Signal-Calibration band on the Briefing — design

- **Date:** 2026-07-02
- **Status:** Approved (brainstorm) — ready for implementation plan
- **Origin:** Review finding **P1-2** (produced-but-unconsumed report fields). `calibration_insights`
  is present in 36/82 reports (incl. the latest) and rendered nowhere. This is the **second**
  "surface the free data" slice, after the cluster band (merge `9efe4e7`).

## Problem

Every ~44% of reports the pipeline writes a full self-assessment of its own signal accuracy
under the top-level `calibration_insights` key — a per-signal track record (win-rate, average
forward return, and **alpha vs benchmark**), a breakdown of *why* CAUTION fired, a taxonomy
check on whether better signals actually produce better outcomes, ten plain-text lessons, and a
`confidence_banner` caveat. The dashboard consumes **none** of it. The block's own embedded
`note` says: *"Treat as a reader-facing self-knowledge summary."* — it is literally built to be
shown, and it is thrown away every morning.

## Goal (v1)

Render the calibration self-assessment on the **Briefing** page as a compact, expandable band,
**confidence-gated** (honest about the data's own "not yet decision-grade" caveat) and
**anchored to today's live signals**, so a glance answers: *"How much should I trust the signals
I'm about to act on today?"*

Design principle (from `CAPEX_CYCLE_IDEAS.md`): *a metric earns its place only if it can change a
position decision.* The signals **are** the product; a track record that grades them — and is
honest about when it can't — is the sharpest possible "should I act on this?" input.

### The defining tension: honesty

This block is unusually self-aware. Today **every** `signal_performance` bucket carries
`single_regime: true` (only a `trend_up` market has been observed), and `confidence_banner`
states outright: *"NOT yet decision-grade — alpha figures are benchmark-relative; single-regime
samples carry no out-of-regime evidence."* Most of the ten `lessons` read *"INSUFFICIENT DATA …
do not adjust stance based on this."* A naïve scorecard that prints "CAUTION: 47% win-rate, −3%
alpha" would imply more certainty than the data earns — a **misleading** feature. So the spine
must carry the confidence signal, not just the numbers.

### Non-goals (v1) — documented follow-ups

- **`caution_breakdown` table** (CAUTION split by reason: extension / rsi / valuation / override).
  Genuinely useful since CAUTION dominates — the natural **v1.1** expand-later.
- **`lessons` list** — mostly "INSUFFICIENT DATA" noise today; deferred.
- **Calibration time-series** (accuracy trend across accumulated daily snapshots) — the v2
  "time dimension", the same follow-up the cluster band deferred; the point a dedicated page
  would earn its place.
- **Wiring calibration into scenario odds / auto-adjusting signals** (`CAPEX_CYCLE_IDEAS.md`
  §10.1) — a modeling effort, explicitly out of scope.
- **No new nav page.** Honors the "don't default to a new page / instrumentation creep"
  principle (`CAPEX_CYCLE_IDEAS.md` §9).

## Placement & UX

A new collapsible band on the **Briefing** page, inserted **after `render_clusters`** and before
`render_action_card` (flow: live-caption → pulse → changes → clusters → **calibration** → action
card → catalyst playbook → contrarians). This groups the two "orientation" bands (clusters =
where each group stands; calibration = how much to trust the signals) so the reading order is
*orient → calibrate trust → act*, priming the reliability caveat right before the action card.

A single native `<details>` element (matching the `.tk-details` / `.cl-details` accordion
pattern), **collapsed by default**:

```
▼ SIGNAL CALIBRATION   How today's signals have actually performed
┌──────────────────────────────────────────────────────────────────────┐
│ CAUTION — most common today (23 names) · −3.0% α / 10d · low-conf ⚠   │  ← collapsed:
│                                                                        │     anchored headline
├──────────────────────────────────────────────────────────────────────┤
│  Signal      Today   n     Win%   Avg 10d   α vs bench                 │  ← expanded:
│  [BUY]        0      3      33%    −0.5%     −0.5%   ·low-conf          │     scorecard table
│  [ACCUM]      1      4      50%    −3.3%     −5.4%   ·low-conf          │     (all buckets, ordered
│  [WATCH]      3      72     50%    −0.8%     −3.4%   ·low-conf          │      by SIGNAL_ORDER;
│  [HOLD]       2      67     36%    −2.6%     −6.3%   ·low-conf          │      low-conf rows muted)
│  [CAUTION]    23     526    47%    +2.7%     −3.0%   ·low-conf          │
│                                                                        │
│  Signal ordering (full corpus): HOLD −0.1 > ACCUMULATE −1.5 >          │  ← taxonomy verdict
│    CAUTION −2.6 > WATCH −3.5 · partially monotonic                     │
│                                                                        │
│  ⚠ Not yet decision-grade — single-regime samples carry no            │  ← caveat (verbatim)
│    out-of-regime evidence.  60-day window · May 2 – Jul 1, 2026        │     + window caption
└──────────────────────────────────────────────────────────────────────┘
```

- **Collapsed row:** the anchored headline — today's dominant signal, how many current names
  carry it, its 10-day alpha, and its confidence state.
- **Expanded:** the per-signal scorecard table · the one-line taxonomy verdict · the
  `confidence_banner` caveat + window caption.

Note the CAUTION row illustrates *why alpha earns its place*: the names rose **+2.7%** on average
yet **lagged their benchmark by 3.0%** — "up but behind" is invisible in raw return alone.

## Data mapping (zero pipeline work — all from today's report)

Source: the already-loaded latest report dict.

| Surface element | Source |
|---|---|
| Per-signal stats | `calibration_insights.signal_performance[SIG]{n_matured_10d, win_rate_pct, avg_return_10d, alpha_10d, single_regime}` |
| Taxonomy verdict | `calibration_insights.taxonomy_discrimination.full_corpus.{observed_ordering_str, monotonic}` |
| Caveat | `calibration_insights.confidence_banner` (verbatim) |
| Window caption | `calibration_insights.data_window.{from, to, lookback_days}` |
| Today's exposure | computed locally from `watchlist[t].signal` (a small `_today_signal_counts` reduction) |

**Why `full_corpus`, not `in_window`, for the taxonomy line:** `taxonomy_discrimination` carries
two sub-blocks. `in_window` is scoped to the (short) lookback and is usually empty /
`monotonic: "INSUFFICIENT"` today (`observed_ordering_str: ""`); `full_corpus` carries the real
ordering (`"HOLD -0.1 > ACCUMULATE -1.5 > CAUTION -2.6 > WATCH -3.5"`, `monotonic: "PARTIAL"`).
Read `full_corpus`; when its ordering string is empty, omit the taxonomy line.

**No ticker-key gotcha here.** `signal_performance` is keyed by **signal name** (`CAUTION`,
`HOLD`, …), not ticker — so the dot/underscore normalization that bit the cluster band does not
apply to the scorecard. It *does* apply if we ever join per-ticker; we don't in v1. Today's
exposure counts iterate `watchlist` values (already underscore-keyed) and read `.signal`, so no
normalization is needed there either.

### Computed at-a-glance — anchor to today's live signals

Mirroring the cluster band's principle (a small reduction over the watchlist, so the band is
about *your* book, not an abstract table):

1. **`_today_signal_counts(watchlist)`** — `Counter` of `watchlist[t].signal` across all entries,
   truthy signals only (null/absent skipped). Kept **local** to `calibration.py` rather than
   importing `clusters._signal_mix` — a *third* shared consumer would be the trigger to lift a
   shared counter into `lib/` (review P8-2 convention: consolidate on the third consumer).
2. **Headline** — the dominant current signal (highest today-count; ties broken by `SIGNAL_ORDER`,
   best-first, for determinism) named with its `alpha_10d` + confidence state. Falls back to a
   generic *"Signal calibration · 60-day window"* when the dominant signal has no
   `signal_performance` bucket.
3. **Scorecard rows** — **all** buckets present in `signal_performance`, ordered by `SIGNAL_ORDER`
   (so `BUY`/`ACCUMULATE` lead even with zero current exposure — the reader may act on one
   tomorrow). The **`Today` column** shows how many current watchlist names carry each signal
   (0 shown muted), tying the historical track record to present exposure; the headline supplies
   the today-emphasis, the table stays the complete self-knowledge summary.

### Confidence gating (the honesty spine)

A pure predicate over each bucket:

- **`_is_low_confidence(perf)`** → `True` if `perf["single_regime"]` is truthy **OR**
  `n_matured_10d < _MIN_MATURED_N`. `_MIN_MATURED_N` is a **named module constant (default 30)** —
  a conventional small-sample floor for a proportion, trivially tunable; not a magic literal.
- Today every bucket is `single_regime` → the whole card honestly reads low-confidence.
- **Visual:** low-confidence rows are muted and carry a marker via a `data-lowconf="1"` attribute
  (CSS mutes through tokens — same mechanism as the cluster band's `cl-ext[data-warn]`). `n` is
  **always** shown so thin samples are self-evident.
- The `confidence_banner` is **always** surfaced — the pipeline's own nuance is never hidden.

## Error handling & robustness

- `calibration_insights` absent/empty (46/82 reports, older reports) → `render_calibration`
  returns silently (matching `render_clusters`); the pure `_calibration_html({}, …)` returns a
  muted placeholder ("No calibration data in this report") and never raises.
- `signal_performance` missing/empty → placeholder, no table.
- Missing per-bucket fields (`win_rate_pct`, `alpha_10d`, …) → `.get()` → "—"; no `KeyError`.
- `taxonomy_discrimination` / `full_corpus` absent, or `observed_ordering_str` empty → omit the
  taxonomy line.
- `data_window` absent → omit the caption.
- A signal in use **today** but absent from `signal_performance` (no matured history) → it gets
  no scorecard row (nothing to show), and the headline fallback prevents a crash.

## Security (review contract P4-1)

All pipeline strings are LLM/pipeline-generated and MUST be escaped before entering the HTML
string:

- Text nodes (`confidence_banner`, `observed_ordering_str`, signal names, `monotonic`) →
  `_escape_dollars(...)` (from `lib/formatters.py`).
- No pipeline prose enters an HTML attribute.
- Numbers are formatted through `_fmt_num` / `_sign`, never interpolated raw.

The live `confidence_banner` even carries stray/mis-encoded glyphs (e.g. a `�` replacement char);
escaping absorbs them safely. Locked with a hostile-payload test extending
`test_rendering_security.py`.

## Structure (follows the cluster-band conventions)

- **New file `components/briefing/calibration.py`:**
  - `render_calibration(calibration_insights: dict | None, watchlist: dict) -> None` — thin;
    returns silently when the block is absent, else `render_section_head(...)` +
    `st.markdown(_calibration_html(...), unsafe_allow_html=True)`.
  - `_calibration_html(calibration_insights: dict, watchlist: dict) -> str` — **pure** builder
    (all tests target this; no Streamlit dependency).
  - Pure helpers: `_today_signal_counts`, `_is_low_confidence`, `_scorecard_rows`,
    `_scorecard_table_html`, `_taxonomy_line`, `_headline_html`.
- **`components/briefing/__init__.py`:** export `render_calibration` (keep `__all__` sorted —
  ruff `RUF022`).
- **`dashboard.py`:** in the Briefing block, after `render_clusters(...)`, call
  `render_calibration(report.get("calibration_insights"), watchlist)`.
- **CSS (`assets/theme.css`):** reuse `.tk-scroll`, `.ep-table`, and the `<details>`/`summary`
  pattern; add a minimal `.cal-*` block (headline, low-conf muting, taxonomy/caveat lines).
  Colors go through `_signal_pill_html` / status tokens — **no hardcoded hex** (keeps
  `test_design_tokens` green; respects P6-1).

## Testing (test-first; matches review conventions)

New `tests/test_calibration.py`, all against the pure builders:

1. `test_today_signal_counts` — counts watchlist signals; null/absent signals skipped.
2. `test_is_low_confidence_single_regime` — `single_regime: True` → low-confidence regardless of n.
3. `test_is_low_confidence_thin_n` — `single_regime: False` but `n_matured_10d < _MIN_MATURED_N`
   → low-confidence; and `False` + `n ≥ floor` → **not** low-confidence.
4. `test_scorecard_rows_ordered_and_annotated` — rows ordered by `SIGNAL_ORDER`, each carrying its
   today-count and low-conf flag.
5. `test_taxonomy_line_from_full_corpus` — builds the ordering + monotonic line; empty ordering
   → `""`.
6. `test_headline_names_dominant_today_signal` — dominant today signal named with its alpha +
   confidence; and the fallback when that signal has no bucket.
7. `test_calibration_html_full` — output contains the scorecard table, the taxonomy line, the
   (escaped) `confidence_banner`, and the window caption.
8. `test_low_confidence_rows_muted` — `data-lowconf="1"` present for single-regime buckets.
9. `test_empty_calibration_placeholder` — `{}` → muted placeholder, no raise.
10. `test_missing_sections_tolerated` — no `taxonomy` / no `data_window` → those elements omitted,
    no raise.
11. `test_banner_and_ordering_escaped` — `<script>`, `<img onerror=...>`, quote-breakout payloads
    in `confidence_banner` / `observed_ordering_str` are neutralized (extends
    `test_rendering_security.py`).

Full suite (`pytest -q`) and `ruff check .` must stay green; the `AppTest` Briefing render must
still walk without exception; and a **real-report smoke test** (load the latest
`data/morning_report_*.json`) must produce the band — a real-data check caught a key-matching bug
on the cluster slice.

## Rollout

Single implementation plan, test-first, one commit per task (mirrors the cluster slice):
1. Pure reducers/predicates (`_today_signal_counts`, `_is_low_confidence`, `_scorecard_rows`,
   `_taxonomy_line`) with their tests (red → green).
2. The pure `_calibration_html` builder (`_headline_html`, `_scorecard_table_html`, assembly) +
   the escaping/edge-case tests.
3. `render_calibration` wrapper + `__init__` export + wire into `dashboard.py` Briefing +
   minimal CSS; verify `pytest -q`, `ruff check .`, and a manual/AppTest + real-report Briefing
   render.
