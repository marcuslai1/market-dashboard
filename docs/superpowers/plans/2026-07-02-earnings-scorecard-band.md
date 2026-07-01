# Earnings-Scorecard band on the Briefing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the pipeline's per-ticker beat/miss track record (the unused `watchlist[T].eps_trajectory` field — review finding P1-2) as a collapsible "Earnings Scorecard" band on the Briefing page, for the AI beneficiaries that carry it (MU / SK Hynix / LITE / PLTR).

**Architecture:** One new self-contained component, `components/briefing/earnings.py`, split into **pure** builders (`_earnings_html` + small pure helpers — all tests target these, no Streamlit import) and a thin `render_earnings` Streamlit wrapper. Wired into the existing Briefing block in `dashboard.py` after `render_calibration`. Follows the established briefing-component pattern (`calibration.py`).

**Tech Stack:** Python 3.10+ (CI) / 3.9 (local), Streamlit, hand-built HTML strings via `st.markdown(..., unsafe_allow_html=True)`. No new dependencies.

## Global Constraints

*(Every task's requirements implicitly include this section.)*

- **No new dependencies.** Pure Python + existing `lib/` helpers only.
- **Escaping (review P4-1):** every report-derived string (`accel_reason`, the ticker label from `TICKER_DISPLAY`) passes through `_escape_dollars(...)` before entering an HTML string. No pipeline prose in HTML attributes. Numbers (`surprise_pct`) go through `_fmt_num` / `_sign`, never raw.
- **Colors via tokens (review P6-1):** CSS uses existing custom properties only (`--ink-2`, `--ink-3`, `--rule`, `--mono`, `--buy`, `--avoid`). No new hardcoded hex literals.
- **Green gates:** `python -m pytest -q` and `python -m ruff check .` must both pass after every task's commit.
- **Scope:** snapshot-only (today's report); no cross-report time-series; no new nav page. Band lives on the Briefing, inserted after `render_calibration`.
- **The ticker-key gotcha:** `watchlist` is a **dict keyed by ticker** with underscore-normalized keys (`000660_KS`). Iterate `watchlist.items()` and map the key through `TICKER_DISPLAY` for the label (`000660_KS` → `000660.KS`).
- **`accelerating` ≠ surprise trend:** read `eps_trajectory.accelerating` verbatim — it tracks EPS-level growth, not the surprise trend. Never recompute it from `surprise_pct`.

## File Structure

- **Create `components/briefing/earnings.py`** — the whole feature: pure helpers `_pct`, `_eps_rows`, `_headline`, `_trend_cells_html`, `_scorecard_table_html`, `_reason_lines_html`, `_earnings_html`; plus the thin `render_earnings` wrapper. One clear responsibility: turn `watchlist` (its per-entry `eps_trajectory`) into the Briefing band.
- **Create `tests/test_earnings.py`** — unit tests for the reducers and the pure builder (collection, ordering, beat-count, display-name mapping, coloring, empty placeholder, `None` tolerance, hostile-payload escaping).
- **Modify `components/briefing/__init__.py`** — export `render_earnings`.
- **Modify `dashboard.py`** — import `render_earnings`; call it in the Briefing block after `render_calibration(...)`.
- **Modify `assets/theme.css`** — a small `.eps-*` style block (tokens only).

---

### Task 1: Reducers (pure)

**Files:**
- Create: `components/briefing/earnings.py`
- Test: `tests/test_earnings.py`

**Interfaces:**
- Consumes: `lib.catalog.TICKER_DISPLAY` (dict), `lib.formatters._fmt_num`, `._sign`.
- Produces:
  - `_pct(value, decimals=1) -> str` — signed percent like `+41.6%` / `-3.0%`, or `—` when `None`.
  - `_eps_rows(watchlist: dict) -> list[dict]` — one row per entry carrying `eps_trajectory.quarters`; keys: `ticker` (display), `surprises` (list), `latest`, `beats`, `n`, `accelerating`, `accel_reason`. Ordered accelerating-first, then `latest` desc, then `ticker`.
  - `_headline(rows: list) -> str` — `"N of M beat last quarter · K accelerating"`, or `"Earnings scorecard"` when empty.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_earnings.py`:

```python
"""Tests for the Briefing earnings-scorecard band (review P1-2)."""
from components.briefing.earnings import _eps_rows, _headline


def _entry(quarters, accelerating=False, accel_reason=""):
    return {"eps_trajectory": {"quarters": quarters,
                               "accelerating": accelerating,
                               "accel_reason": accel_reason}}


def test_eps_rows_collects_only_entries_with_trajectory():
    wl = {
        "MU": _entry([{"surprise_pct": 5.9}, {"surprise_pct": 21.2}]),
        "TSM": {"signal": "BUY"},                      # no eps_trajectory -> skipped
        "AMD": {"eps_trajectory": {"quarters": []}},   # empty quarters -> skipped
    }
    rows = _eps_rows(wl)
    assert [r["ticker"] for r in rows] == ["MU"]


def test_eps_rows_computes_latest_beats_and_n():
    wl = {"MU": _entry([{"surprise_pct": 5.9}, {"surprise_pct": -2.0},
                        {"surprise_pct": 21.2}])}
    (row,) = _eps_rows(wl)
    assert row["latest"] == 21.2
    assert row["n"] == 3
    assert row["beats"] == 2  # 5.9 and 21.2 are > 0; -2.0 is not


def test_eps_rows_ordered_accel_first_then_surprise_desc():
    wl = {
        "LITE": _entry([{"surprise_pct": 4.4}], accelerating=True),
        "MU": _entry([{"surprise_pct": 21.2}], accelerating=True),
        "PLTR": _entry([{"surprise_pct": 99.0}], accelerating=False),  # bigger, not accel
    }
    rows = _eps_rows(wl)
    # accelerating names first (MU 21.2 before LITE 4.4); non-accel PLTR last
    assert [r["ticker"] for r in rows] == ["MU", "LITE", "PLTR"]


def test_eps_rows_display_name_mapping():
    wl = {"000660_KS": _entry([{"surprise_pct": 41.6}], accelerating=True)}
    (row,) = _eps_rows(wl)
    assert row["ticker"] == "000660.KS"


def test_headline_counts():
    rows = [
        {"latest": 21.2, "accelerating": True},
        {"latest": 4.4, "accelerating": True},
        {"latest": -1.0, "accelerating": False},
        {"latest": 8.0, "accelerating": False},
    ]
    # 3 of 4 beat (21.2, 4.4, 8.0 > 0; -1.0 not); 2 accelerating
    assert _headline(rows) == "3 of 4 beat last quarter · 2 accelerating"


def test_headline_empty_generic():
    assert _headline([]) == "Earnings scorecard"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'components.briefing.earnings'`.

- [ ] **Step 3: Write the minimal implementation**

Create `components/briefing/earnings.py`:

```python
"""Briefing · Earnings-scorecard band.

Surfaces per-ticker ``eps_trajectory`` — the pipeline's beat/miss track record
for the core AI beneficiaries (MU / SK Hynix / LITE / PLTR), emitted on the
latest reports and rendered nowhere (review finding P1-2, third "surface the
free data" slice). Answers at a glance: are the beneficiaries beating
estimates, and are the beats accelerating? — the fundamental-performance
complement to the signal-calibration band.
"""
from __future__ import annotations

from lib.catalog import TICKER_DISPLAY
from lib.formatters import _fmt_num, _sign


def _pct(value, decimals: int = 1) -> str:
    """Signed percentage like '+41.6%' / '-3.0%', or '—' when missing."""
    if value is None:
        return "—"
    return f"{_sign(value)}{_fmt_num(value, decimals)}%"


def _eps_rows(watchlist: dict) -> list:
    """One scorecard row per watchlist entry carrying ``eps_trajectory.quarters``.

    Ordered accelerating-first, then latest surprise% desc, then ticker (for
    determinism). Entries without the field — or with empty ``quarters`` — are
    skipped. ``accelerating`` is read verbatim: it tracks EPS-level growth, not
    the surprise trend, and is never recomputed from ``surprise_pct`` here.
    """
    rows = []
    for tk, entry in (watchlist or {}).items():
        eps = (entry or {}).get("eps_trajectory") or {}
        quarters = eps.get("quarters") or []
        if not quarters:
            continue
        surprises = [q.get("surprise_pct") for q in quarters]
        latest = surprises[-1] if surprises else None
        beats = sum(1 for s in surprises if s is not None and s > 0)
        rows.append({
            "ticker": TICKER_DISPLAY.get(tk, tk),
            "surprises": surprises,
            "latest": latest,
            "beats": beats,
            "n": len(quarters),
            "accelerating": bool(eps.get("accelerating")),
            "accel_reason": (eps.get("accel_reason") or "").strip(),
        })
    rows.sort(key=lambda r: (
        not r["accelerating"],
        -r["latest"] if r["latest"] is not None else float("inf"),
        r["ticker"],
    ))
    return rows


def _headline(rows: list) -> str:
    """Collapsed corpus headline: 'N of M beat last quarter · K accelerating'.

    'beat' = latest surprise > 0; 'accelerating' = the field's own flag. Generic
    label when there are no rows (the render wrapper guards that path).
    """
    if not rows:
        return "Earnings scorecard"
    n = len(rows)
    beat = sum(1 for r in rows if r["latest"] is not None and r["latest"] > 0)
    accel = sum(1 for r in rows if r["accelerating"])
    return f"{beat} of {n} beat last quarter · {accel} accelerating"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_earnings.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Run ruff**

Run: `python -m ruff check components/briefing/earnings.py tests/test_earnings.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add components/briefing/earnings.py tests/test_earnings.py
git commit -m "P1-2: earnings reducers (_eps_rows collection/ordering, _headline)"
```

---

### Task 2: The pure `_earnings_html` builder

**Files:**
- Modify: `components/briefing/earnings.py`
- Test: `tests/test_earnings.py`

**Interfaces:**
- Consumes: Task 1's `_pct`, `_eps_rows`, `_headline`; `lib.formatters._escape_dollars`.
- Produces:
  - `_trend_cells_html(surprises: list) -> str` — the surprise%-per-quarter sequence, beat green / miss red / flat muted, joined by `→`; `""` when empty.
  - `_scorecard_table_html(rows: list) -> str` — a `.ep-table` of ticker → latest, trend, accel flag; `""` when no rows.
  - `_reason_lines_html(rows: list) -> str` — muted `▲ TICKER — reason` lines for accelerating names carrying a reason; `""` when none.
  - `_earnings_html(watchlist: dict) -> str` — full band (`<details class="eps-band eps-details">…`), or a `.eps-empty` placeholder when no rows.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_earnings.py`:

```python
from components.briefing.earnings import _earnings_html

_WL = {
    "000660_KS": _entry(
        [{"surprise_pct": 2.5}, {"surprise_pct": 41.8},
         {"surprise_pct": 20.8}, {"surprise_pct": 41.6}],
        accelerating=True, accel_reason="EPS 17850 -> 21522 -> 56670 over 3 qtrs",
    ),
    "MU": _entry(
        [{"surprise_pct": 5.9}, {"surprise_pct": 20.7},
         {"surprise_pct": 33.2}, {"surprise_pct": 21.2}],
        accelerating=True, accel_reason="EPS 4.78 -> 12.2 -> 25.11 over 3 qtrs",
    ),
    "LITE": _entry(
        [{"surprise_pct": 8.6}, {"surprise_pct": 6.8},
         {"surprise_pct": 18.4}, {"surprise_pct": 4.4}],
        accelerating=False,
    ),
}


def test_earnings_html_full():
    out = _earnings_html(_WL)
    assert "eps-scorecard" in out
    assert "000660.KS" in out and "MU" in out and "LITE" in out
    # headline: all three latest > 0, two accelerating
    assert "3 of 3 beat last quarter · 2 accelerating" in out
    assert "eps-beat" in out          # positive surprises are green
    assert "▲" in out                 # accel marker present
    assert "EPS 4.78" in out          # accel_reason line for an accelerating name


def test_earnings_html_empty_placeholder():
    assert "No earnings data" in _earnings_html({})
    assert "No earnings data" in _earnings_html({"MU": {"signal": "BUY"}})


def test_surprise_none_tolerated():
    wl = {"MU": _entry([{"surprise_pct": None}, {"surprise_pct": 21.2}],
                       accelerating=True)}
    out = _earnings_html(wl)
    assert "—" in out                 # the None surprise renders as a dash
    assert "eps-scorecard" in out
    (row,) = _eps_rows(wl)
    assert row["latest"] == 21.2
    assert row["beats"] == 1          # only the non-None positive counts


def test_miss_colored_red():
    wl = {"MU": _entry([{"surprise_pct": -3.0}], accelerating=False)}
    out = _earnings_html(wl)
    assert "eps-miss" in out
    assert "0 of 1 beat last quarter · 0 accelerating" in out


def test_accel_reason_escaped():
    wl = {"MU": _entry([{"surprise_pct": 10.0}], accelerating=True,
                       accel_reason="<script>alert(1)</script><img src=x onerror=alert(1)>")}
    out = _earnings_html(wl)
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings.py -q`
Expected: FAIL — `ImportError: cannot import name '_earnings_html'`.

- [ ] **Step 3: Write the minimal implementation**

In `components/briefing/earnings.py`, merge `_escape_dollars` into the formatters import (keeping alphabetical order):

```python
from lib.formatters import _escape_dollars, _fmt_num, _sign
```

Then append the builder functions to the end of the file:

```python
def _trend_cells_html(surprises: list) -> str:
    """Surprise%-per-quarter, oldest→latest, beat green / miss red / flat muted.

    ``None`` renders as a muted '—'. Cells are joined by '→'. '' for empty input.
    """
    if not surprises:
        return ""
    cells = []
    for s in surprises:
        if s is None:
            cells.append('<span class="eps-flat">—</span>')
        elif s > 0:
            cells.append(f'<span class="eps-beat">{_pct(s)}</span>')
        elif s < 0:
            cells.append(f'<span class="eps-miss">{_pct(s)}</span>')
        else:
            cells.append(f'<span class="eps-flat">{_pct(s)}</span>')
    return '<span class="eps-trend">' + " → ".join(cells) + "</span>"


def _latest_cell_html(latest) -> str:
    """The latest-surprise cell — the same beat/miss/flat coloring as a trend cell."""
    if latest is None:
        return '<span class="eps-flat">—</span>'
    if latest > 0:
        return f'<span class="eps-beat">{_pct(latest)}</span>'
    if latest < 0:
        return f'<span class="eps-miss">{_pct(latest)}</span>'
    return f'<span class="eps-flat">{_pct(latest)}</span>'


def _scorecard_table_html(rows: list) -> str:
    """A .ep-table of ticker → latest surprise, 4-qtr trend, accel flag.

    Returns '' when there are no rows.
    """
    if not rows:
        return ""
    trs = []
    for r in rows:
        accel_html = (
            '<span class="eps-accel">▲</span>' if r["accelerating"]
            else '<span class="eps-flat">—</span>'
        )
        trs.append(
            f'<tr><td>{_escape_dollars(r["ticker"])}</td>'
            f'<td class="num">{_latest_cell_html(r["latest"])}</td>'
            f'<td>{_trend_cells_html(r["surprises"])}</td>'
            f'<td class="num">{accel_html}</td></tr>'
        )
    return (
        '<div class="tk-scroll"><table class="ep-table eps-scorecard">'
        '<thead><tr><th>Ticker</th><th class="num">Latest</th>'
        '<th>Surprise trend (oldest → latest)</th>'
        '<th class="num">Accel</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )


def _reason_lines_html(rows: list) -> str:
    """Muted '▲ TICKER — reason' lines for accelerating names with a reason.

    Returns '' when no accelerating row carries a reason.
    """
    lines = [
        f'<p class="eps-reason">▲ {_escape_dollars(r["ticker"])} — '
        f'{_escape_dollars(r["accel_reason"])}</p>'
        for r in rows
        if r["accelerating"] and r["accel_reason"]
    ]
    return "".join(lines)


def _earnings_html(watchlist: dict) -> str:
    """Full earnings-scorecard band HTML, or a muted placeholder when empty."""
    rows = _eps_rows(watchlist)
    if not rows:
        return '<div class="eps-band eps-empty">No earnings data in this report.</div>'
    parts = [
        f'<summary class="eps-summary">{_escape_dollars(_headline(rows))}</summary>',
        '<div class="eps-body">',
        _scorecard_table_html(rows),
        _reason_lines_html(rows),
        "</div>",
    ]
    return f'<details class="eps-band eps-details">{"".join(parts)}</details>'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_earnings.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Run ruff**

Run: `python -m ruff check components/briefing/earnings.py tests/test_earnings.py`
Expected: `All checks passed!` (fix any import-order finding before committing).

- [ ] **Step 6: Commit**

```bash
git add components/briefing/earnings.py tests/test_earnings.py
git commit -m "P1-2: pure _earnings_html builder + tests (trend coloring, accel, escaping)"
```

---

### Task 3: Wire the band into the Briefing (wrapper, export, dashboard, CSS)

**Files:**
- Modify: `components/briefing/earnings.py` (add `render_earnings`)
- Modify: `components/briefing/__init__.py`
- Modify: `dashboard.py` (import + call in the Briefing block, after `render_calibration`)
- Modify: `assets/theme.css`

**Interfaces:**
- Consumes: `_eps_rows` + `_earnings_html` (Tasks 1–2); `lib.cards.render_section_head`; `streamlit`.
- Produces: `render_earnings(watchlist: dict) -> None`.

- [ ] **Step 1: Add the `render_earnings` wrapper**

In `components/briefing/earnings.py`, add the two imports (merge in isort order — `streamlit` is third-party and goes after `__future__` and before the `lib.*` block; `lib.cards` sorts before `lib.catalog`). The final top-of-file import block must read exactly:

```python
from __future__ import annotations

import streamlit as st

from lib.cards import render_section_head
from lib.catalog import TICKER_DISPLAY
from lib.formatters import _escape_dollars, _fmt_num, _sign
```

Append the wrapper to the end of `components/briefing/earnings.py`:

```python
def render_earnings(watchlist: dict) -> None:
    """Briefing earnings-scorecard band — per-ticker ``eps_trajectory`` (review P1-2).

    Silent when no watchlist entry carries ``eps_trajectory`` (older reports);
    on the latest reports MU / SK Hynix / LITE / PLTR carry it.
    """
    if not _eps_rows(watchlist):
        return
    render_section_head("Earnings Scorecard", "Beat/miss track record for the AI beneficiaries")
    st.markdown(_earnings_html(watchlist), unsafe_allow_html=True)
```

- [ ] **Step 2: Export it**

Edit `components/briefing/__init__.py` — add the import (alphabetically, after the `contrarians` import → `earnings` sorts after `contrarians` and before `pulse`) and the `__all__` entry (keep `__all__` sorted; ruff `RUF022` enforces it):

```python
from components.briefing.contrarians import render_contrarian_candidates
from components.briefing.earnings import render_earnings
from components.briefing.pulse import render_pulse
```

`__all__` becomes:

```python
__all__ = [
    "render_action_card",
    "render_calibration",
    "render_catalyst_playbook",
    "render_changes",
    "render_clusters",
    "render_contrarian_candidates",
    "render_earnings",
    "render_pulse",
]
```

- [ ] **Step 3: Call it in the Briefing block**

In `dashboard.py`, add `render_earnings` to the `from components.briefing import (...)` block (keep sorted — it goes right after `render_contrarian_candidates`). Then, in the `if page == "Briefing":` block, insert the call immediately after the existing `render_calibration(...)` call and before `render_action_card(watchlist, events)`:

```python
    render_calibration(
        report.get("calibration_insights"),
        watchlist,
    )
    render_earnings(watchlist)
    render_action_card(watchlist, events)
```

- [ ] **Step 4: Add the CSS**

Append to `assets/theme.css` (tokens only — no new hex):

```css
/* ── Briefing · Earnings-scorecard band (review P1-2: surface per-ticker `eps_trajectory`) ── */
.eps-band { margin: 6px 0 2px; }
.eps-details { padding: 4px 0 2px; }
.eps-summary {
  cursor: pointer; list-style: none;
  font-family: var(--mono); font-size: 12px; color: var(--ink-2);
}
.eps-summary::-webkit-details-marker { display: none; }
.eps-body { padding: 8px 2px 2px; }
.eps-scorecard { margin-top: 4px; }
.eps-trend { font-family: var(--mono); font-size: 11.5px; white-space: nowrap; }
.eps-beat { color: var(--buy); }
.eps-miss { color: var(--avoid); }
.eps-accel { color: var(--buy); font-weight: 600; }
.eps-flat { color: var(--ink-3); }
.eps-reason { color: var(--ink-2); font-size: 11.5px; line-height: 1.5; margin: 6px 0 0; }
.eps-empty { color: var(--ink-3); font-family: var(--mono); font-size: 12px; padding: 6px 0; }
```

- [ ] **Step 5: Verify the full suite + lint are green**

Run: `python -m pytest -q`
Expected: PASS — the prior suite plus the 11 new earnings tests, 0 failures.

Run: `python -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Real-report smoke — the band renders against live data**

Run:

```bash
python -c "
import json, glob
from components.briefing.earnings import _earnings_html, _eps_rows
r = json.load(open(sorted(glob.glob('data/morning_report_*.json'))[-1], encoding='utf-8'))
wl = r.get('watchlist') or {}
rows = _eps_rows(wl)
html = _earnings_html(wl)
assert 'eps-scorecard' in html, 'scorecard missing on the latest report'
assert rows, 'no eps rows on the latest report'
print('OK — earnings band renders;', len(rows), 'rows:', [x['ticker'] for x in rows])
"
```

Expected: `OK — earnings band renders; 4 rows: ['000660.KS', 'MU', 'PLTR', 'LITE']` (order may vary with the data, but all four present). A real-data check like this caught a key-matching bug on the cluster slice — and here it confirms the dict-keyed-watchlist iteration works against real keys.

- [ ] **Step 7: Manual smoke (optional but recommended)**

Run: `python -m streamlit run dashboard.py` (or use the `/run` skill). On the **Briefing** page, confirm an "Earnings Scorecard" section appears after the Signal Calibration band and before the action card: the collapsed row reads e.g. "4 of 4 beat last quarter · 4 accelerating"; expanding reveals the per-ticker table (latest surprise + colored 4-quarter trend + ▲ accel flag) and the accel_reason lines. Confirm no Streamlit exception in the terminal.

- [ ] **Step 8: Commit**

```bash
git add components/briefing/earnings.py components/briefing/__init__.py dashboard.py assets/theme.css
git commit -m "P1-2: surface the earnings-scorecard band on the Briefing"
```

---

## Self-Review

**1. Spec coverage** (checked against `docs/superpowers/specs/2026-07-02-earnings-scorecard-band-design.md`):
- Placement (Briefing, after `render_calibration`, before `render_action_card`) → Task 3 Step 3. ✓
- Collapsed corpus headline ("N of M beat · K accelerating") → `_headline`, tested. ✓
- Per-ticker scorecard (latest + 4-qtr surprise trend, beat green / miss red) → `_scorecard_table_html` / `_trend_cells_html`, tested. ✓
- Accel flag (▲) + `accel_reason` lines → `_scorecard_table_html` accel column + `_reason_lines_html`, tested. ✓
- Order = accel-first, then latest surprise desc, then ticker → `_eps_rows` sort, tested. ✓
- Dict-keyed watchlist + display-name mapping (`000660_KS` → `000660.KS`) → `_eps_rows` via `TICKER_DISPLAY`, tested. ✓
- `accelerating` read verbatim (not derived from surprises) → `_eps_rows` reads the field; the LITE fixture (accel=True with a shrinking surprise) documents the distinction. ✓
- Error handling (field absent, empty quarters, `None` surprise) → `_eps_rows` skips / `_pct` + cell helpers tolerate `None`; tested. ✓
- Security (P4-1 escaping of `accel_reason` + ticker) → `test_accel_reason_escaped`; all prose via `_escape_dollars`. ✓
- Tokens not hex (P6-1) → CSS uses `--*` vars only (`--buy`/`--avoid`/`--ink-*`/`--mono`). ✓
- No new nav page, snapshot-only → band on the Briefing, no cross-report series. ✓

**2. Deviations from spec (intentional, noted):**
- **Integration check is a real-report smoke, not AppTest.** The repo has no `AppTest` harness (grep-confirmed on the calibration slice); Task 3 Step 6 runs the pure builder against the latest `data/morning_report_*.json` instead — the check that actually caught the cluster key bug — plus an optional manual `streamlit run`.
- **A `_latest_cell_html` helper was added** (not named in the spec) so the "latest surprise" cell shares the exact beat/miss/flat coloring logic with the trend cells (DRY); it is a private one-liner, covered transitively by `test_earnings_html_full` / `test_miss_colored_red`.

**3. Placeholder scan:** none — every step has concrete code/commands.

**4. Type consistency:** helper names/signatures are identical across defining and consuming tasks: `_pct(value, decimals=1)→str`, `_eps_rows(watchlist)→list[dict]` (keys `ticker/surprises/latest/beats/n/accelerating/accel_reason`), `_headline(rows)→str`, `_trend_cells_html(surprises)→str`, `_latest_cell_html(latest)→str`, `_scorecard_table_html(rows)→str`, `_reason_lines_html(rows)→str`, `_earnings_html(watchlist)→str`, `render_earnings(watchlist)→None`. `_scorecard_table_html` and `_reason_lines_html` both consume the row dicts produced by `_eps_rows`; `_earnings_html` threads `rows` into both and into `_headline`.
