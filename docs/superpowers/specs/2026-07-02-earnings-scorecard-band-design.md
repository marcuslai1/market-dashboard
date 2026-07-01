# Earnings-Scorecard band on the Briefing — design

- **Date:** 2026-07-02
- **Status:** Approved (brainstorm) — ready for implementation plan
- **Origin:** Review finding **P1-2** (produced-but-unconsumed report fields). `eps_trajectory`
  is present per-watchlist-entry in the **5 latest reports** (2026-06-26 → 07-01), for
  **MU / 000660_KS / LITE / PLTR**, and rendered nowhere. This is the **third** "surface the
  free data" slice, after the cluster band (merge `9efe4e7`) and the calibration band (merge
  `59b32e5`).

## Problem

The pipeline recently began emitting, on each of the four core AI-beneficiary names, a compact
earnings track record under `watchlist[TICKER].eps_trajectory`:

```json
"eps_trajectory": {
  "quarters": [
    {"quarter": "2025-09-23", "eps_actual": 3.03,  "eps_estimate": 2.86,  "surprise_pct": 5.9},
    {"quarter": "2025-12-17", "eps_actual": 4.78,  "eps_estimate": 3.96,  "surprise_pct": 20.7},
    {"quarter": "2026-03-18", "eps_actual": 12.2,  "eps_estimate": 9.16,  "surprise_pct": 33.2},
    {"quarter": "2026-06-24", "eps_actual": 25.11, "eps_estimate": 20.71, "surprise_pct": 21.2}
  ],
  "accelerating": true,
  "accel_reason": "EPS 4.78 -> 12.2 -> 25.11 over 3 qtrs; latest beat +21.2%"
}
```

Four quarters of beat/miss (actual vs estimate + `surprise_pct`), plus a boolean `accelerating`
and a human `accel_reason`. The dashboard consumes **none** of it. This is precisely the
earnings-cascade idea from `CAPEX_CYCLE_IDEAS.md` §6/§11-v1 ("track the important players'
earnings, then understand the result") — and, per §2, the cleanest **Layer-3 digestion proxy**
we have for free: *are the beneficiaries actually beating, and is the beat accelerating?*

### Correction carried from the ledger (verified this session)

The earnings/events candidate is narrower than §6 first framed it. Two of the three fields §6
leaned on are **not** free:

- **`scheduled_tech_events` is a dead end for a *forward* driver.** Present in 21/82 reports, but
  only **2–3/82 carry a forward-dated event** — the rest are `"status": "released"` with negative
  `days_until` (backward-looking conference recaps). Not a basis for an "upcoming earnings" band.
- **`macro_trigger_map` is already consumed.** `dashboard.py:250` reads it and `:316` renders it
  via `render_catalyst_playbook` (the "Macro Trigger Map" bull/bear band). Done, not free.

So the genuinely-free earnings piece is **`eps_trajectory`** — historical beat/miss only.

## Goal (v1)

Render the beat/miss track record on the **Briefing** page as a compact, expandable band that
answers at a glance: *"Are the AI beneficiaries beating estimates, and are the beats
accelerating?"* — the fundamental-performance complement to the calibration band's
signal-performance read.

Design principle (`CAPEX_CYCLE_IDEAS.md`): *a metric earns its place only if it can change a
position decision.* A beneficiary that keeps beating and accelerating (MU, SK Hynix) confirms the
Layer-2 demand thesis and firms the base case; a decelerating or missing beat is the earliest
crack in the coverage gap. That read belongs next to the signals you act on.

### Non-goals (v1) — documented follow-ups

- **The forward "if beat / if miss → cascade to these tickers" war-gaming** (`CAPEX_CYCLE_IDEAS.md`
  §6). That is *ex-ante* scenario wiring; `eps_trajectory` is *ex-post* actuals. The cascade needs
  data the field does not carry — explicitly deferred.
- **EPS/estimate absolute values and revisions** — the field carries `eps_actual`/`eps_estimate`,
  but the decision-relevant signal is the **surprise trend**, not the raw cents. Show surprise%;
  keep the actuals available in tooltip/reason text only. (Revisions aren't in the data.)
- **Cross-report time-series** of surprises — the field is only 5 days old (5/82 reports); a
  snapshot-over-time chart is premature. The per-entry `quarters[]` already *is* a 4-quarter
  time-series, which is enough for v1. This mirrors the same v2 "time dimension" follow-up the
  prior two bands deferred.
- **No new nav page.** Honors the "don't default to a new page / instrumentation creep" principle
  (`CAPEX_CYCLE_IDEAS.md` §9). A third Briefing band is the consistent home.

## Placement & UX

A new collapsible band on the **Briefing** page, inserted **after `render_calibration`** and
before `render_action_card` (flow: … clusters → calibration → **earnings** → action card →
catalyst playbook → contrarians). This groups the two "how are we doing" bands — calibration
grades the *signals*, earnings grades the *fundamentals* — so the reading order is
*orient → calibrate trust → check the earnings backing → act*.

A single native `<details>` element (matching the `.cal-details` accordion pattern), **collapsed
by default**:

```
▼ EARNINGS SCORECARD   Beat/miss track record for the AI beneficiaries
┌────────────────────────────────────────────────────────────────────────┐
│ 4 of 4 beat last quarter · 4 accelerating                              │  ← collapsed:
│                                                                          │     corpus headline
├────────────────────────────────────────────────────────────────────────┤
│  Ticker      Latest    Surprise trend (oldest → latest)      Accel      │  ← expanded:
│  000660.KS   +41.6%    +2.5 → +41.8 → +20.8 → +41.6          ▲          │     scorecard table
│  MU          +21.2%    +5.9 → +20.7 → +33.2 → +21.2          ▲          │     (accel-first,
│  PLTR        +17.9%    +14.3 → +23.5 → +8.7 → +17.9          ▲          │      then surprise desc;
│  LITE         +4.4%    +8.6 → +6.8 → +18.4 → +4.4            ▲          │      beat green/miss red)
│                                                                          │
│  ▲ 000660.KS — EPS 17850 → 21522 → 56670 over 3 qtrs; latest beat +41.6%│  ← accel_reason lines
│  ▲ MU — EPS 4.78 → 12.2 → 25.11 over 3 qtrs; latest beat +21.2%         │     (accelerating names)
│  ▲ PLTR / LITE — …                                                      │
└────────────────────────────────────────────────────────────────────────┘
```

(All four names happen to be accelerating and beating on the latest report, so today the headline
reads uniformly green and the accel-first tiebreak is a no-op — ordering falls to `latest_surprise`
desc. The point of the ordering rule is the day one name *stops* beating or accelerating: it sinks,
and the headline drops to e.g. *"3 of 4 beat · 2 accelerating"* — the decision-relevant shift.)

- **Collapsed row:** a corpus headline — *"N of M beat last quarter · K accelerating"* — the
  one-glance state of the beneficiary earnings backing.
- **Expanded:** the per-ticker scorecard (latest surprise + the 4-quarter surprise trend, beats
  green / misses red) · the `accel_reason` lines for the accelerating names.

**`accelerating` ≠ surprise trend — do not conflate or recompute it.** `accelerating` is the
field's own boolean, tracking **EPS-level growth** (its `accel_reason` cites EPS values, e.g.
`4.78 → 12.2 → 25.11`). It is *independent* of the surprise trend: LITE is `accelerating: true`
even though its surprise *shrank* (+18.4% → +4.4%) — EPS still grew, it just beat by less. The band
shows **both** signals (surprise magnitude in the trend cells; EPS trajectory in the ▲ flag +
reason) because they answer different questions. The reducer reads `accelerating` verbatim; it
never derives it from `surprise_pct`.

## Data mapping (zero pipeline work — all from today's report)

Source: the already-loaded latest report dict. **The `watchlist` is a dict keyed by ticker**
(`{"MU": {...}, "000660_KS": {...}}`) — not a list; `eps_trajectory` is a sibling of `signal` /
`valuation` inside each entry.

| Surface element | Source |
|---|---|
| Per-ticker quarters | `watchlist[T].eps_trajectory.quarters[]{quarter, eps_actual, eps_estimate, surprise_pct}` |
| Accel flag / reason | `watchlist[T].eps_trajectory.{accelerating, accel_reason}` |
| Ticker label | `TICKER_DISPLAY[T]` (restores dots: `000660_KS` → `000660.KS`) |

**The ticker-key gotcha (the same one that bit the cluster band).** Watchlist keys are
underscore-normalized (`000660_KS`); the display map converts back (`000660.KS`). We iterate
`watchlist.items()` and map keys through `TICKER_DISPLAY` for the label. No join against
signal/cluster data is needed (v1 shows only the earnings rows), so no further normalization.

### Computed at-a-glance

1. **`_eps_rows(watchlist)`** — a small reduction over `watchlist.items()`: for every entry whose
   `eps_trajectory.quarters` is non-empty, emit one row `{ticker (display), quarters,
   latest_surprise, beats, n, accelerating, accel_reason}` where `latest_surprise` is the last
   quarter's `surprise_pct`, `beats` counts quarters with `surprise_pct > 0`, and `n = len(quarters)`.
   Entries without the field (or with empty `quarters`) are skipped.
2. **Order** — **accelerating-first**, then **`latest_surprise` desc**, then **ticker asc** for
   determinism. Puts the strongest, still-accelerating beats at the top; a decelerating/missing
   name sinks — the visual hierarchy *is* the read.
3. **Headline** — `_headline(rows)`: *"{beat_now} of {n} beat last quarter · {accel} accelerating"*
   where `beat_now` = rows with `latest_surprise > 0` and `accel` = rows with `accelerating`.
   Empty rows → generic *"Earnings scorecard"* (never reached in render — the wrapper guards — but
   defined for the pure builder / tests).

## Error handling & robustness

- No watchlist entry carries `eps_trajectory` (77/82 older reports) → `render_earnings` returns
  silently (matching `render_calibration`); the pure `_earnings_html({})` returns a muted
  placeholder ("No earnings data in this report") and never raises.
- `eps_trajectory` present but `quarters` empty/missing → that ticker is skipped (no row).
- A `surprise_pct` of `None` → rendered "—", uncolored; never interpolated into arithmetic.
- `accelerating` absent/falsey → treated as flat (— , not ▲); `accel_reason` absent → no reason line.
- 1–4 quarters tolerated (don't assume exactly 4); the trend cell renders whatever is present.

## Security (review contract P4-1)

All pipeline strings are LLM/pipeline-generated and MUST be escaped before entering the HTML
string:

- Text nodes (`accel_reason`, and the ticker label out of `TICKER_DISPLAY`) → `_escape_dollars(...)`
  (from `lib/formatters.py`).
- No pipeline prose enters an HTML attribute.
- Numbers (`surprise_pct`) are formatted through `_fmt_num` / `_sign`, never interpolated raw.

Locked with a hostile-payload test (a `<script>`/`<img onerror=…>` in `accel_reason` is
neutralized), consistent with `test_rendering_security.py`.

## Structure (follows the calibration-band conventions)

- **New file `components/briefing/earnings.py`:**
  - `render_earnings(watchlist: dict) -> None` — thin; returns silently when no entry carries
    `eps_trajectory`, else `render_section_head(...)` +
    `st.markdown(_earnings_html(watchlist), unsafe_allow_html=True)`.
  - `_earnings_html(watchlist: dict) -> str` — **pure** builder (all tests target this; no
    Streamlit dependency).
  - Pure helpers: `_eps_rows`, `_headline`, `_trend_cells_html`, `_scorecard_table_html`.
- **`components/briefing/__init__.py`:** export `render_earnings` (keep `__all__` sorted — ruff
  `RUF022`).
- **`dashboard.py`:** in the Briefing block, after `render_calibration(...)`, call
  `render_earnings(watchlist)`; add the import to the `components.briefing` block.
- **CSS (`assets/theme.css`):** reuse `.tk-scroll`, `.ep-table`, and the `<details>`/`summary`
  pattern; add a minimal `.eps-*` block (headline, summary, beat/miss cell coloring, accel/reason
  lines) mirroring the `.cal-*` block. Beat/miss colors route through the existing `--buy` /
  `--avoid` tokens — **no hardcoded hex** (keeps `test_design_tokens` green; respects P6-1).

## Testing (test-first; matches review conventions)

New `tests/test_earnings.py`, all against the pure builders:

1. `test_eps_rows_collects_only_entries_with_trajectory` — entries lacking `eps_trajectory` (or
   with empty `quarters`) are skipped; present ones produce a row.
2. `test_eps_rows_computes_latest_and_beats` — `latest_surprise` = last quarter's `surprise_pct`;
   `beats` counts `surprise_pct > 0`; `n = len(quarters)`.
3. `test_eps_rows_ordered_accel_first_then_surprise` — accelerating names precede non-accelerating;
   within a group, higher `latest_surprise` first; ties broken by ticker.
4. `test_eps_rows_display_name_mapping` — `000660_KS` row carries label `000660.KS`.
5. `test_headline_counts` — *"3 of 4 beat last quarter · 2 accelerating"* phrasing from mixed rows;
   empty rows → generic label.
6. `test_earnings_html_full` — output contains the scorecard table, each ticker label, colored
   beat/miss surprise cells, the accel marker (▲), and the `accel_reason` lines.
7. `test_earnings_html_empty_placeholder` — `{}` and a watchlist with no trajectories → muted
   placeholder, no raise.
8. `test_surprise_none_tolerated` — a `None` `surprise_pct` renders "—", uncolored, no raise.
9. `test_accel_reason_escaped` — a `<script>`/`<img onerror=…>` payload in `accel_reason` is
   neutralized (`&lt;script&gt;`), consistent with `test_rendering_security.py`.

Full suite (`pytest -q`) and `ruff check .` must stay green; the `AppTest` Briefing render must
still walk without exception; and a **real-report smoke test** (load the latest
`data/morning_report_*.json`) must produce the band — a real-data check caught a key-matching bug
on the cluster slice, and the dict-keyed-watchlist gotcha here is the same shape of risk.

## Rollout

Single implementation plan, test-first, one commit per task (mirrors the prior two slices):
1. Pure reducers (`_eps_rows`, `_headline`) with their tests (red → green), incl. the
   dict-keyed-watchlist collection, ordering, beat-count, and display-name mapping.
2. The pure `_earnings_html` builder (`_trend_cells_html`, `_scorecard_table_html`, assembly) +
   the escaping / `None`-surprise / empty-placeholder tests.
3. `render_earnings` wrapper + `__init__` export + wire into `dashboard.py` Briefing + minimal
   CSS; verify `pytest -q`, `ruff check .`, and a manual/AppTest + real-report Briefing render.
