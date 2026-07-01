# Cluster band on the Briefing — design

- **Date:** 2026-07-01
- **Status:** Approved (brainstorm) — ready for implementation plan
- **Origin:** Review finding **P1-2** (produced-but-unconsumed report fields). `clusters`
  is present in 100% of reports and rendered nowhere. This is the first "surface the
  free data" slice; earnings/events and calibration are separate later slices.

## Problem

The pipeline writes a full per-cluster analysis into every report under the top-level
`clusters` key — a narrative `summary`, a `thesis_status`, a `key_development`, the
member `tickers`, and per-ticker `data_anchors` (`vs_sma50_pct`, `rsi_14`). The
dashboard consumes **none** of it. Each morning a paragraph of cluster-level reasoning
is computed and thrown away.

## Goal (v1)

Render the cluster analysis on the **Briefing** page as a compact, expandable band, and
make it *decision-useful* — pair the pipeline's prose with a small computed at-a-glance
derived from the cluster's own watchlist names, so a glance answers "what's the state of
this group and is anything actionable?"

Design principle (from `CAPEX_CYCLE_IDEAS.md`): *a metric earns its place only if it can
change a position decision.* A band that only echoes prose is decoration; the computed
at-a-glance is what makes it earn its place.

### Non-goals (v1) — documented follow-ups

- **Time dimension** (cluster trends over accumulated daily snapshots). This is the
  natural v2 and the point at which a dedicated "Clusters" page would earn its place.
  v1 is snapshot-only (today's report).
- **Earnings/events** (`scheduled_tech_events`) and **calibration** (`calibration_insights`)
  slices — separate features.
- **Wiring cluster state into scenario odds** (`CAPEX_CYCLE_IDEAS.md` §10.1) — a modeling
  effort, explicitly out of scope.
- No new nav page. Honors the "don't default to a new page / instrumentation creep"
  principle (`CAPEX_CYCLE_IDEAS.md` §9).

## Placement & UX

A new collapsible band on the **Briefing** page, inserted **after `render_changes`** and
before `render_action_card` (flow: live-caption → pulse → changes → **clusters** →
action card → catalyst playbook → contrarians). Order is easily adjustable.

One row per cluster, **collapsed by default** using a native `<details>` element (matching
the existing `.tk-details` accordion pattern):

```
▼ CLUSTERS
┌────────────────────────────────────────────────────────┐
│ Semiconductors   1 CAUTION · 6 AVOID · 4 —   6/11 ext.  │  ← collapsed row:
│   "AMD +7.5%; South Korea $1.3T plan lifts supply chain"│     name · at-a-glance · key_development
├────────────────────────────────────────────────────────┤
│ Singapore Banks  2 HOLD · 1 WATCH            0/3 ext.   │
│   "UOB upgraded to WATCH; still no workable R:R"         │
└────────────────────────────────────────────────────────┘
        (expand a row →)
        summary paragraph (full)
        thesis_status: "Structurally impaired — awaiting rate relief"
        ┌ ticker ┬ signal ┬ vs50  ┬ RSI ┐
        │ D05.SI │ [HOLD] │ +6.5% │ 61  │
        │ O39.SI │ [HOLD] │ +6.1% │ 60  │
        │ U11.SI │ [WATCH]│ +4.8% │ 63  │
        └────────┴────────┴───────┴─────┘
```

- **Collapsed row:** cluster display name · at-a-glance chips · `key_development` one-liner.
- **Expanded:** full `summary` paragraph · `thesis_status` line · anchor table joining
  `data_anchors` (`vs_sma50_pct`, `rsi_14`) with the live `signal` pill + price from the
  watchlist entry (reusing `_signal_pill_html`).

## Data mapping (zero pipeline work — all from today's report)

Source: the already-loaded latest report dict.

| Surface element | Source |
|---|---|
| Cluster name | `clusters` dict key, title-cased for display (e.g. `singapore` → `Singapore`) |
| Members | `clusters[name].tickers` (canonical dotted form, e.g. `D05.SI`) |
| Narrative | `clusters[name].summary`, `.thesis_status`, `.key_development` |
| Anchors | `clusters[name].data_anchors[<ticker>]{vs_sma50_pct, rsi_14}` |
| Live signal / price | `watchlist[ticker].{signal, price, currency, chg_pct}` |

**Key-normalization detail (avoids a silent "—" bug):** only `clusters[name].tickers` use the
**dotted** form (`D05.SI`, `000660.KS`). The `watchlist`, `data_anchors`, `TICKER_DISPLAY`,
and `extension_regime.blocked_tickers` maps are **all** keyed by the **underscore** form
(`D05_SI`, `000660_KS`). Normalize every ticker with `ticker.replace(".", "_")` before *any*
of those lookups (not just anchors) — otherwise dotted names silently fall into the null bucket.

### Computed at-a-glance (INCLUDED per design decision)

A pure reduction over the cluster's member tickers, using the watchlist entries:

1. **Signal mix** — count `watchlist[ticker].signal` across the cluster's `tickers`,
   grouped (e.g. `1 CAUTION · 6 AVOID · 4 —`). Null/absent signals bucket as `—`
   (defends the known P1-4 null-signal entry).
2. **Extension breadth** — `X/Y ext.`, where X = cluster members currently hard-blocked
   for extension and Y = cluster size. Source: intersect the cluster's tickers with
   `extension_regime.blocked_tickers` (normalized) when `extension_regime` is present;
   otherwise fall back to each entry's per-entry hard-block indicator (`entry_block`).

Best-actionable-name and R:R surfacing are intentionally deferred (keep v1 robust; avoids
the `risk_reward` presence dependency).

## Error handling & robustness

- `clusters` absent or empty (older reports) → the band renders a single muted line
  ("No cluster breakdown in this report"); never raises.
- Missing `key_development` / `summary` / `data_anchors` → omit that element via `.get()`;
  a cluster with no anchors still shows its narrative.
- A cluster ticker missing from the watchlist → skipped in the signal-mix and anchor join
  (no `KeyError`).
- Empty `tickers` list → cluster still renders its narrative; at-a-glance shows nothing.

## Security (review contract P4-1)

All pipeline prose (`summary`, `thesis_status`, `key_development`, cluster name) is
LLM-generated and MUST be escaped before entering the HTML string:

- Text nodes → `_escape_dollars(...)` (from `lib/formatters.py`).
- Any attribute value → `_escape_attr(...)`.

This is locked with hostile-payload tests (below) that extend `test_rendering_security.py`.
(The live data even carries stray/mis-rendered glyphs; escaping absorbs them safely.)

## Structure (follows existing conventions)

- **New file `components/briefing/clusters.py`:**
  - `render_clusters(clusters: dict, watchlist: dict, extension_regime: dict | None = None) -> None`
    — thin; calls `st.markdown(_clusters_html(...), unsafe_allow_html=True)`.
  - `_clusters_html(clusters: dict, watchlist: dict, extension_regime: dict | None = None) -> str`
    — **pure** builder (all testing targets this; no Streamlit dependency).
  - Small private helpers as needed: `_signal_mix(tickers, watchlist)`,
    `_extension_breadth(tickers, watchlist, extension_regime)`, `_anchor_row(...)`.
- **`components/briefing/__init__.py`:** export `render_clusters`.
- **`dashboard.py`:** in the Briefing block, after `render_changes(...)`, call
  `render_clusters(report.get("clusters", {}), watchlist, report.get("extension_regime"))`.
- **CSS (`assets/theme.css`):** reuse `.tk-details`, `.ep-table`, `.tk-scroll`. Add a
  minimal `.cl-row` / at-a-glance chip style only if needed. Colors go through
  `SIGNAL_COLORS` / the status tokens — **no hardcoded hex** (keeps `test_design_tokens`
  green; respects review finding P6-1).

## Testing (test-first; matches review conventions)

New `tests/test_clusters.py`, all against the pure `_clusters_html` builder:

1. `test_renders_cluster_name_and_summary` — fake `clusters` + `watchlist` → HTML contains
   the (escaped) name and summary.
2. `test_at_a_glance_signal_mix_counts` — known signals across members → correct grouped
   counts, including a `—` bucket for a null signal.
3. `test_extension_breadth_counts` — with `extension_regime.blocked_tickers` present →
   `X/Y ext.` correct; and the `entry_block` fallback path when `extension_regime` absent.
4. `test_anchor_key_normalization` — the dotted cluster ticker `D05.SI` resolves to `data_anchors["D05_SI"]` and `watchlist["D05_SI"]` via `_norm`.
5. `test_empty_clusters_returns_placeholder` — `{}` → muted placeholder, no raise.
6. `test_missing_data_anchors_tolerated` — cluster without `data_anchors` → narrative
   renders, no anchor table, no raise.
7. `test_ticker_not_in_watchlist_skipped` — member/anchor absent from watchlist → skipped,
   no `KeyError`.
8. `test_cluster_prose_escaped` — `<script>`, `<img onerror=...>`, and quote-breakout
   payloads in `summary` / `thesis_status` / `key_development` are neutralized (extends
   `test_rendering_security.py`).

Full suite (`pytest -q`) and `ruff check .` must stay green; `AppTest` Briefing render
must still walk without exception.

## Rollout

Single implementation plan, test-first:
1. Pure `_clusters_html` + helpers with the test list above (red → green).
2. `render_clusters` wrapper + `__init__` export.
3. Wire into `dashboard.py` Briefing; minimal CSS.
4. Verify: `pytest -q`, `ruff check .`, and an `AppTest`/manual Briefing render.
