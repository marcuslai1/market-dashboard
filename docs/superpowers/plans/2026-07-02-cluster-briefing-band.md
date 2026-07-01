# Cluster band on the Briefing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the pipeline's daily per-cluster analysis (the unused top-level `clusters` key — review finding P1-2) as a collapsible band on the Briefing page, each row pairing the prose with a computed at-a-glance (signal mix + extension breadth).

**Architecture:** One new self-contained component, `components/briefing/clusters.py`, split into a **pure** HTML builder (`_clusters_html` + small pure helpers — all tests target this, no Streamlit import) and a thin `render_clusters` Streamlit wrapper. Wired into the existing Briefing block in `dashboard.py` after `render_changes`. Follows the established briefing-component pattern (`changes.py`, `contrarians.py`).

**Tech Stack:** Python 3.9+ (local) / 3.10+3.12 (CI), Streamlit, hand-built HTML strings via `st.markdown(..., unsafe_allow_html=True)`. No new dependencies.

## Global Constraints

*(Every task's requirements implicitly include this section.)*

- **No new dependencies.** Pure Python + existing `lib/` helpers only.
- **Escaping (review P4-1):** every report-derived string (`summary`, `thesis_status`, `key_development`, cluster name, ticker) passes through `_escape_dollars(...)` (text nodes) before entering an HTML string. No user prose in HTML attributes.
- **Colors via tokens (review P6-1):** CSS uses existing custom properties only (`--ink`, `--ink-2`, `--ink-3`, `--rule`, `--paper-3`, `--mono`, `--caution`). No new hardcoded hex literals.
- **Green gates:** `python -m pytest -q` and `python -m ruff check .` must both pass after every task's commit.
- **Scope:** snapshot-only (today's report); no time-series; no new nav page. Band lives on the Briefing, inserted after `render_changes`.
- **Data key normalization:** only `clusters[].tickers` use the **dotted** form (`D05.SI`); `watchlist`, `data_anchors`, `TICKER_DISPLAY`, and `extension_regime.blocked_tickers` are all keyed by the **underscore** form (`D05_SI`). Normalize every ticker via `_norm` (`ticker.replace(".", "_")`) before *any* of those lookups.

## File Structure

- **Create `components/briefing/clusters.py`** — the whole feature: pure helpers `_norm`, `_signal_mix`, `_extension_breadth`, `_anchor_table_html`, `_glance_html`, `_cluster_details_html`, `_clusters_html`; plus the thin `render_clusters` wrapper. One clear responsibility: turn `clusters` + `watchlist` into the Briefing band.
- **Create `tests/test_clusters.py`** — unit tests for the reducers and the pure builder (structure, at-a-glance counts, key normalization, edge cases, hostile-payload escaping).
- **Modify `components/briefing/__init__.py`** — export `render_clusters`.
- **Modify `dashboard.py`** — import `render_clusters`; call it in the Briefing block after `render_changes(...)`.
- **Modify `assets/theme.css`** — a small `.cl-*` style block (tokens only).

---

### Task 1: At-a-glance reducers (pure)

**Files:**
- Create: `components/briefing/clusters.py`
- Test: `tests/test_clusters.py`

**Interfaces:**
- Consumes: `lib.catalog.SIGNAL_ORDER` (list, best→worst).
- Produces:
  - `_norm(ticker: str) -> str` — dotted → underscore key form.
  - `_signal_mix(tickers: list, watchlist: dict) -> list[tuple[str, int]]` — signal→count, ordered best→worst per `SIGNAL_ORDER`, with a `"—"` bucket (null/absent signals, incl. tickers missing from `watchlist`) sorted last.
  - `_extension_breadth(tickers: list, extension_regime) -> tuple[int, int] | None` — `(#blocked, #members)` using `extension_regime["blocked_tickers"]` (normalized); `None` when `extension_regime` is falsy.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_clusters.py`:

```python
"""Tests for the Briefing cluster band (review P1-2)."""
from components.briefing.clusters import (
    _extension_breadth,
    _norm,
    _signal_mix,
)


def test_norm_dot_to_underscore():
    assert _norm("D05.SI") == "D05_SI"
    assert _norm("000660.KS") == "000660_KS"


def test_signal_mix_orders_best_to_worst():
    wl = {"A": {"signal": "AVOID"}, "B": {"signal": "WATCH"}, "C": {"signal": "WATCH"}}
    # WATCH ranks above AVOID in SIGNAL_ORDER, so it comes first.
    assert _signal_mix(["A", "B", "C"], wl) == [("WATCH", 2), ("AVOID", 1)]


def test_signal_mix_buckets_null_and_missing_last():
    wl = {"A": {"signal": "HOLD"}, "B": {"signal": None}}
    # "C" is absent from the watchlist -> also counts toward the "—" bucket.
    assert _signal_mix(["A", "B", "C"], wl) == [("HOLD", 1), ("—", 2)]


def test_extension_breadth_counts_blocked_normalized():
    er = {"blocked_tickers": ["D05_SI", "000660_KS"]}
    assert _extension_breadth(["D05.SI", "O39.SI", "000660.KS"], er) == (2, 3)


def test_extension_breadth_none_without_regime():
    assert _extension_breadth(["D05.SI"], None) is None
    assert _extension_breadth(["D05.SI"], {}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_clusters.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'components.briefing.clusters'`.

- [ ] **Step 3: Write the minimal implementation**

Create `components/briefing/clusters.py`:

```python
"""Briefing · Cluster band.

Surfaces the per-cluster analysis the pipeline writes into every report under
the top-level ``clusters`` key (summary / thesis_status / key_development /
data_anchors) — previously computed daily and rendered nowhere (review finding
P1-2). Each cluster is a collapsible row: the pipeline's prose paired with a
computed at-a-glance (signal mix + extension breadth) derived from the cluster's
own watchlist names.
"""
from __future__ import annotations

from collections import Counter

from lib.catalog import SIGNAL_ORDER


def _norm(ticker: str) -> str:
    """Anchor / blocked-ticker key form: dotted ticker -> underscore form."""
    return str(ticker).replace(".", "_")


def _signal_mix(tickers: list, watchlist: dict) -> list:
    """Signal -> count across *tickers*, ordered best->worst per SIGNAL_ORDER.

    Null/absent signals (and tickers missing from *watchlist*) fall into a
    ``"—"`` bucket that sorts last.
    """
    counts: Counter = Counter()
    for tk in tickers:
        sig = (watchlist.get(tk) or {}).get("signal")
        counts[sig if sig else "—"] += 1
    ordered = [(s, counts[s]) for s in SIGNAL_ORDER if counts.get(s)]
    if counts.get("—"):
        ordered.append(("—", counts["—"]))
    return ordered


def _extension_breadth(tickers: list, extension_regime) -> tuple | None:
    """(#hard-blocked-for-extension, #members), or None when no regime data.

    Uses ``extension_regime['blocked_tickers']`` (underscore key form) as the
    precise source. Returns None when the regime block is absent so the caller
    omits the chip rather than guessing.
    """
    if not extension_regime:
        return None
    blocked = {str(t) for t in (extension_regime.get("blocked_tickers") or [])}
    n = sum(1 for tk in tickers if _norm(tk) in blocked)
    return (n, len(tickers))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_clusters.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add components/briefing/clusters.py tests/test_clusters.py
git commit -m "P1-2: cluster band reducers (signal mix + extension breadth)"
```

---

### Task 2: The pure `_clusters_html` builder

**Files:**
- Modify: `components/briefing/clusters.py`
- Test: `tests/test_clusters.py`

**Interfaces:**
- Consumes: Task 1's `_norm`, `_signal_mix`, `_extension_breadth`; `lib.catalog.TICKER_DISPLAY`; `lib.formatters._escape_dollars`, `._fmt_num`, `._sign`; `lib.pills._signal_pill_html`.
- Produces: `_clusters_html(clusters: dict, watchlist: dict, extension_regime=None) -> str` — full band HTML (a `.cl-band` wrapper of `<details class="cl-details">` blocks), or a `.cl-empty` placeholder when `clusters` is empty. Private helpers `_anchor_table_html`, `_glance_html`, `_cluster_details_html`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_clusters.py`:

```python
from components.briefing.clusters import _clusters_html

_WL = {
    "D05.SI": {"signal": "HOLD", "price": 47.0, "currency": "SGD", "chg_pct": -0.3},
    "O39.SI": {"signal": "WATCH", "price": 17.0, "currency": "SGD"},
}
_CLUSTERS = {
    "singapore": {
        "tickers": ["D05.SI", "O39.SI"],
        "summary": "Banks near overbought.",
        "thesis_status": "Structurally impaired",
        "key_development": "UOB upgraded to WATCH.",
        "data_anchors": {
            "D05_SI": {"vs_sma50_pct": 6.47, "rsi_14": 61.5},
            "O39_SI": {"vs_sma50_pct": 6.07, "rsi_14": 60.3},
        },
    }
}


def test_renders_name_summary_thesis_dev():
    out = _clusters_html(_CLUSTERS, _WL)
    assert "Singapore" in out            # title-cased key
    assert "Banks near overbought." in out
    assert "Structurally impaired" in out
    assert "UOB upgraded to WATCH." in out


def test_renders_at_a_glance_counts():
    out = _clusters_html(_CLUSTERS, _WL)
    assert "1&nbsp;WATCH" in out
    assert "1&nbsp;HOLD" in out


def test_extension_breadth_chip_rendered():
    out = _clusters_html(_CLUSTERS, _WL, {"blocked_tickers": ["D05_SI"]})
    assert "1/2&nbsp;ext." in out


def test_anchor_row_uses_normalized_key():
    out = _clusters_html(_CLUSTERS, _WL)
    assert "+6.5%" in out    # D05_SI anchor vs_sma50_pct 6.47 -> +6.5%
    assert "62" in out       # rsi_14 61.5 -> "62" at 0 decimals


def test_empty_clusters_placeholder():
    assert "No cluster breakdown" in _clusters_html({}, _WL)


def test_missing_data_anchors_no_table_no_raise():
    c = {"x": {"tickers": ["D05.SI"], "summary": "S"}}
    out = _clusters_html(c, _WL)
    assert "ep-table" not in out
    assert "S" in out


def test_ticker_missing_from_watchlist_degrades_gracefully():
    c = {"x": {"tickers": ["ZZZ"], "summary": "S",
               "data_anchors": {"ZZZ": {"vs_sma50_pct": 1.0, "rsi_14": 50}}}}
    out = _clusters_html(c, {})   # empty watchlist -> no KeyError
    assert "ep-table" in out      # anchor row still renders (no signal pill)
    assert "50" in out


def test_prose_is_escaped():
    c = {"x": {"tickers": [],
               "summary": "<script>alert(1)</script>",
               "thesis_status": "<img src=x onerror=alert(1)>",
               "key_development": '"><script>evil</script>'}}
    out = _clusters_html(c, {})
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_clusters.py -q`
Expected: FAIL — `ImportError: cannot import name '_clusters_html'`.

- [ ] **Step 3: Write the minimal implementation**

Add to `components/briefing/clusters.py` — new imports at the top (merge with the existing import block) and the builder functions at the end:

```python
# add to the imports at the top of the file:
from lib.catalog import SIGNAL_ORDER, TICKER_DISPLAY
from lib.formatters import _escape_dollars, _fmt_num, _sign
from lib.pills import _signal_pill_html
```

```python
# append to the end of the file:
def _anchor_table_html(cluster: dict, watchlist: dict) -> str:
    """A .ep-table of ticker -> live signal pill, vs-50, RSI (or '' if none)."""
    anchors = cluster.get("data_anchors") or {}
    if not anchors:
        return ""
    rows = []
    for tk in cluster.get("tickers", []) or []:
        a = anchors.get(_norm(tk))
        if not a:
            continue
        sig = (watchlist.get(tk) or {}).get("signal")
        pill = _signal_pill_html(sig, small=True) if sig else "—"
        vs50 = a.get("vs_sma50_pct")
        rsi = a.get("rsi_14")
        vs50_str = f"{_sign(vs50)}{_fmt_num(vs50, 1)}%" if vs50 is not None else "—"
        rows.append(
            f"<tr><td>{_escape_dollars(TICKER_DISPLAY.get(tk, tk))}</td>"
            f"<td>{pill}</td>"
            f'<td class="num">{vs50_str}</td>'
            f'<td class="num">{_fmt_num(rsi, 0)}</td></tr>'
        )
    if not rows:
        return ""
    return (
        '<div class="tk-scroll"><table class="ep-table cl-anchors">'
        "<thead><tr><th>Ticker</th><th>Signal</th>"
        '<th class="num">vs 50</th><th class="num">RSI</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _glance_html(tickers: list, watchlist: dict, extension_regime) -> str:
    """Computed at-a-glance chips: signal mix, then extension breadth."""
    chips = [
        f'<span class="cl-chip">{n}&nbsp;{_escape_dollars(sig)}</span>'
        for sig, n in _signal_mix(tickers, watchlist)
    ]
    breadth = _extension_breadth(tickers, extension_regime)
    if breadth is not None:
        n, total = breadth
        warn = ' data-warn="1"' if n else ""
        chips.append(f'<span class="cl-chip cl-ext"{warn}>{n}/{total}&nbsp;ext.</span>')
    return f'<span class="cl-glance">{"".join(chips)}</span>'


def _cluster_details_html(name: str, cluster: dict, watchlist: dict,
                          extension_regime) -> str:
    tickers = cluster.get("tickers", []) or []
    dev = cluster.get("key_development") or ""
    summary = cluster.get("summary") or ""
    thesis = cluster.get("thesis_status") or ""
    dev_html = f'<span class="cl-dev">{_escape_dollars(dev)}</span>' if dev else ""
    body = []
    if thesis:
        body.append(f'<p class="cl-thesis">{_escape_dollars(thesis)}</p>')
    if summary:
        body.append(f'<p class="cl-sum">{_escape_dollars(summary)}</p>')
    body.append(_anchor_table_html(cluster, watchlist))
    return (
        '<details class="cl-details"><summary class="cl-summary">'
        f'<span class="cl-name">{_escape_dollars(str(name).title())}</span>'
        f"{_glance_html(tickers, watchlist, extension_regime)}{dev_html}"
        f'</summary><div class="cl-body">{"".join(body)}</div></details>'
    )


def _clusters_html(clusters: dict, watchlist: dict, extension_regime=None) -> str:
    if not clusters:
        return '<div class="cl-band cl-empty">No cluster breakdown in this report.</div>'
    blocks = [
        _cluster_details_html(name, c, watchlist, extension_regime)
        for name, c in clusters.items()
        if isinstance(c, dict)
    ]
    if not blocks:
        return '<div class="cl-band cl-empty">No cluster breakdown in this report.</div>'
    return f'<div class="cl-band">{"".join(blocks)}</div>'
```

Note: the file's original `from lib.catalog import SIGNAL_ORDER` (from Task 1) is replaced by the combined `from lib.catalog import SIGNAL_ORDER, TICKER_DISPLAY` — do not leave a duplicate import (ruff `F811`/`I001` will fail).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_clusters.py -q`
Expected: PASS (13 passed).

- [ ] **Step 5: Run ruff**

Run: `python -m ruff check components/briefing/clusters.py tests/test_clusters.py`
Expected: `All checks passed!` (fix any import-order/unused-import findings before committing).

- [ ] **Step 6: Commit**

```bash
git add components/briefing/clusters.py tests/test_clusters.py
git commit -m "P1-2: pure _clusters_html builder + tests (escaping, edge cases)"
```

---

### Task 3: Wire the band into the Briefing (wrapper, export, dashboard, CSS)

**Files:**
- Modify: `components/briefing/clusters.py` (add `render_clusters`)
- Modify: `components/briefing/__init__.py`
- Modify: `dashboard.py` (import + call in the Briefing block, ~line 300)
- Modify: `assets/theme.css`

**Interfaces:**
- Consumes: `_clusters_html` (Task 2); `lib.cards.render_section_head`; `streamlit`.
- Produces: `render_clusters(clusters: dict, watchlist: dict, extension_regime=None) -> None`.

- [ ] **Step 1: Add the `render_clusters` wrapper**

Add to the top imports of `components/briefing/clusters.py`:

```python
import streamlit as st

from lib.cards import render_section_head
```

Append to `components/briefing/clusters.py`:

```python
def render_clusters(clusters: dict, watchlist: dict, extension_regime=None) -> None:
    """Briefing cluster band — the daily per-cluster analysis (review P1-2).

    Silent when the report carries no ``clusters`` block (older reports); on the
    latest report this is always present.
    """
    if not clusters:
        return
    render_section_head("Clusters", "Where each group stands today")
    st.markdown(
        _clusters_html(clusters, watchlist, extension_regime),
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: Export it**

Edit `components/briefing/__init__.py` — add the import and the `__all__` entry (keep `__all__` alphabetically sorted; ruff `RUF022` enforces it):

```python
from components.briefing.clusters import render_clusters
```

`__all__` becomes:

```python
__all__ = [
    "render_action_card",
    "render_catalyst_playbook",
    "render_changes",
    "render_clusters",
    "render_contrarian_candidates",
    "render_pulse",
]
```

- [ ] **Step 3: Call it in the Briefing block**

In `dashboard.py`, add `render_clusters` to the `from components.briefing import (...)` block (keep sorted). Then, in the `if page == "Briefing":` block, insert the call immediately after the existing `render_changes(...)` call and before `render_action_card(watchlist, events)`:

```python
    render_changes(
        watchlist,
        prev_report.get("watchlist", {}) if prev_report else {},
    )
    render_clusters(
        report.get("clusters", {}),
        watchlist,
        report.get("extension_regime"),
    )
    render_action_card(watchlist, events)
```

- [ ] **Step 4: Add the CSS**

Append to `assets/theme.css` (tokens only — no new hex):

```css
/* ── Briefing · Cluster band (review P1-2: surface the daily `clusters` data) ── */
.cl-band { margin: 6px 0 2px; }
.cl-details { border-bottom: 1px solid var(--rule); padding: 9px 0; }
.cl-details:last-child { border-bottom: 0; }
.cl-summary {
  cursor: pointer; list-style: none;
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
}
.cl-summary::-webkit-details-marker { display: none; }
.cl-name { font-family: var(--mono); font-weight: 600; color: var(--ink); font-size: 13px; }
.cl-glance { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.cl-chip {
  font-family: var(--mono); font-size: 10.5px; color: var(--ink-3);
  background: var(--paper-3); padding: 1px 6px; border-radius: 3px;
}
.cl-ext[data-warn="1"] { color: var(--caution); }
.cl-dev { color: var(--ink-2); font-size: 12.5px; line-height: 1.5; }
.cl-body { padding: 8px 2px 2px; }
.cl-thesis { color: var(--ink-3); font-size: 12px; font-style: italic; margin: 0 0 6px; }
.cl-sum { color: var(--ink-2); font-size: 13px; line-height: 1.55; margin: 0 0 8px; }
.cl-anchors { margin-top: 4px; }
.cl-empty { color: var(--ink-3); font-family: var(--mono); font-size: 12px; padding: 6px 0; }
```

- [ ] **Step 5: Verify the full suite + lint are green**

Run: `python -m pytest -q`
Expected: PASS — the prior 75 plus the new cluster tests (88 total), 0 failures.

Run: `python -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Manual smoke — the band renders**

Run: `python -m streamlit run dashboard.py` (or use the `/run` skill). In the browser, confirm on the **Briefing** page: a "Clusters" section appears after the "Since yesterday" changes ribbon; each cluster row shows the name, at-a-glance chips (signal mix + `X/Y ext.`), and the `key_development` line; expanding a row reveals the thesis + summary + the ticker/signal/vs-50/RSI table. Confirm no Streamlit exception in the terminal.

- [ ] **Step 7: Commit**

```bash
git add components/briefing/clusters.py components/briefing/__init__.py dashboard.py assets/theme.css
git commit -m "P1-2: surface the cluster band on the Briefing"
```

---

## Self-Review

**1. Spec coverage** (checked against `docs/superpowers/specs/2026-07-01-cluster-briefing-band-design.md`):
- Placement (Briefing, after `render_changes`) → Task 3 Step 3. ✓
- Collapsed row (name · at-a-glance · key_development) → `_cluster_details_html` summary. ✓
- Expanded (summary · thesis_status · anchor table with live signal pill) → `_cluster_details_html` body + `_anchor_table_html`. ✓
- At-a-glance = signal mix + extension breadth → Task 1 reducers, rendered in `_glance_html`. ✓
- Key normalization (dot↔underscore) → `_norm`, tested (`test_anchor_row_uses_normalized_key`, `test_extension_breadth_counts_blocked_normalized`). ✓
- Error handling (empty clusters, missing anchors, ticker not in watchlist) → tests 6–8 in Task 2. ✓
- Security (P4-1 escaping) → `test_prose_is_escaped`; all prose via `_escape_dollars`. ✓
- Tokens not hex (P6-1) → CSS uses `--*` vars only. ✓
- Testing plan → `tests/test_clusters.py` covers all listed cases. ✓

**2. Deviations from spec (intentional, noted):**
- Extension breadth: the spec offered an `entry_block` fallback when `extension_regime` is absent. The plan instead **omits the chip** when the regime block is absent. Reason: `entry_block` is a truthy *any-block* string (confirmed in `row.py`), so it would over-count non-extension blocks and mislabel the chip. Omission is precise and graceful. `extension_regime` is present on the latest report, where the band lives.
- Empty `clusters`: `render_clusters` returns silently (no section head) rather than drawing the muted placeholder, to avoid noise on the (hypothetical) empty day. The `_clusters_html` placeholder remains for defensive/direct use and is tested.

**3. Placeholder scan:** none — every step has concrete code/commands.

**4. Type consistency:** helper names and signatures (`_norm`, `_signal_mix`, `_extension_breadth`, `_anchor_table_html`, `_glance_html`, `_cluster_details_html`, `_clusters_html`, `render_clusters`) are identical across the tasks that define and consume them. `_signal_mix` returns `list[tuple[str,int]]` (consumed by `_glance_html`); `_extension_breadth` returns `tuple|None` (None-checked in `_glance_html`).
