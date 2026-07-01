# Signal-Calibration band on the Briefing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the pipeline's daily signal-accuracy self-assessment (the unused top-level `calibration_insights` key — review finding P1-2) as a confidence-gated, collapsible band on the Briefing page, anchored to today's live signals.

**Architecture:** One new self-contained component, `components/briefing/calibration.py`, split into **pure** builders (`_calibration_html` + small pure helpers — all tests target these, no Streamlit import) and a thin `render_calibration` Streamlit wrapper. Wired into the existing Briefing block in `dashboard.py` after `render_clusters`. Follows the established briefing-component pattern (`clusters.py`).

**Tech Stack:** Python 3.10+ (CI) / 3.9 (local), Streamlit, hand-built HTML strings via `st.markdown(..., unsafe_allow_html=True)`. No new dependencies.

## Global Constraints

*(Every task's requirements implicitly include this section.)*

- **No new dependencies.** Pure Python + existing `lib/` helpers only.
- **Escaping (review P4-1):** every report-derived string (`confidence_banner`, taxonomy `observed_ordering_str`, `data_window` dates) passes through `_escape_dollars(...)` before entering an HTML string. No pipeline prose in HTML attributes. Signal names come from the fixed `SIGNAL_ORDER` constant (safe); numbers go through `_fmt_num` / `_sign`, never raw.
- **Colors via tokens (review P6-1):** CSS uses existing custom properties only (`--ink`, `--ink-2`, `--ink-3`, `--rule`, `--paper-3`, `--mono`, `--caution`). Signal colors come from `_signal_pill_html` (already tokenized). No new hardcoded hex literals.
- **Green gates:** `python -m pytest -q` and `python -m ruff check .` must both pass after every task's commit.
- **Scope:** snapshot-only (today's report); no time-series; no new nav page. Band lives on the Briefing, inserted after `render_clusters`.
- **No ticker-key gotcha here:** `signal_performance` is keyed by **signal name** (`CAUTION`, `HOLD`, …), not ticker — the dot/underscore normalization that bit the cluster band does not apply. Today's exposure iterates `watchlist` values and reads `.signal`, so no normalization is needed either.
- **Confidence honesty:** the band must never present the numbers as more certain than the data earns. Low-confidence buckets (single-regime **or** thin-n) are visibly muted, `n` is always shown, and the `confidence_banner` caveat is always surfaced.

## File Structure

- **Create `components/briefing/calibration.py`** — the whole feature: constant `_MIN_MATURED_N`; pure helpers `_today_signal_counts`, `_is_low_confidence`, `_scorecard_rows`, `_taxonomy_line`, `_pct`, `_window_caption`, `_scorecard_table_html`, `_headline_html`, `_calibration_html`; plus the thin `render_calibration` wrapper. One clear responsibility: turn `calibration_insights` + `watchlist` into the Briefing band.
- **Create `tests/test_calibration.py`** — unit tests for the reducers/predicates and the pure builder (structure, ordering, confidence gating, key edge cases, hostile-payload escaping).
- **Modify `components/briefing/__init__.py`** — export `render_calibration`.
- **Modify `dashboard.py`** — import `render_calibration`; call it in the Briefing block after `render_clusters(...)`.
- **Modify `assets/theme.css`** — a small `.cal-*` style block (tokens only).

---

### Task 1: Reducers & predicates (pure)

**Files:**
- Create: `components/briefing/calibration.py`
- Test: `tests/test_calibration.py`

**Interfaces:**
- Consumes: `lib.catalog.SIGNAL_ORDER` (list, best→worst).
- Produces:
  - `_MIN_MATURED_N: int` — small-sample floor (30).
  - `_today_signal_counts(watchlist: dict) -> collections.Counter` — signal→count across watchlist entries, truthy signals only.
  - `_is_low_confidence(perf: dict) -> bool` — `True` if `single_regime` truthy OR `n_matured_10d < _MIN_MATURED_N` (or `perf` empty).
  - `_scorecard_rows(signal_performance: dict, today_counts) -> list[dict]` — one row dict per bucket present in `signal_performance`, ordered by `SIGNAL_ORDER`; keys: `signal, today, n, win, avg, alpha, low_conf`.
  - `_taxonomy_line(taxonomy: dict) -> str` — full-corpus ordering verdict, or `""`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_calibration.py`:

```python
"""Tests for the Briefing signal-calibration band (review P1-2)."""
from components.briefing.calibration import (
    _MIN_MATURED_N,
    _is_low_confidence,
    _scorecard_rows,
    _taxonomy_line,
    _today_signal_counts,
)


def test_today_signal_counts_skips_null_and_absent():
    wl = {
        "A": {"signal": "CAUTION"},
        "B": {"signal": "CAUTION"},
        "C": {"signal": None},
        "D": {},
    }
    counts = _today_signal_counts(wl)
    assert counts["CAUTION"] == 2
    assert sum(counts.values()) == 2  # null + absent contribute nothing


def test_is_low_confidence_single_regime_true_regardless_of_n():
    assert _is_low_confidence({"single_regime": True, "n_matured_10d": 500}) is True


def test_is_low_confidence_thin_n():
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": _MIN_MATURED_N - 1}
    ) is True


def test_is_low_confidence_decision_grade():
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": _MIN_MATURED_N}
    ) is False


def test_scorecard_rows_ordered_and_annotated():
    sp = {
        "CAUTION": {"n_matured_10d": 526, "win_rate_pct": 47.1, "avg_return_10d": 2.71,
                    "alpha_10d": -3.05, "single_regime": True},
        "BUY": {"n_matured_10d": 3, "win_rate_pct": 33.3, "avg_return_10d": -0.54,
                "alpha_10d": -0.46, "single_regime": True},
    }
    rows = _scorecard_rows(sp, {"CAUTION": 23})
    # BUY precedes CAUTION per SIGNAL_ORDER even with zero current exposure
    assert [r["signal"] for r in rows] == ["BUY", "CAUTION"]
    assert rows[0]["today"] == 0
    assert rows[1]["today"] == 23
    assert rows[0]["low_conf"] is True


def test_taxonomy_line_from_full_corpus():
    tax = {"full_corpus": {"observed_ordering_str": "HOLD -0.1 > CAUTION -2.6",
                           "monotonic": "PARTIAL"}}
    line = _taxonomy_line(tax)
    assert "HOLD -0.1 > CAUTION -2.6" in line
    assert "partially monotonic" in line


def test_taxonomy_line_empty_when_no_ordering():
    assert _taxonomy_line({}) == ""
    assert _taxonomy_line({"full_corpus": {"observed_ordering_str": ""}}) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_calibration.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'components.briefing.calibration'`.

- [ ] **Step 3: Write the minimal implementation**

Create `components/briefing/calibration.py`:

```python
"""Briefing · Signal-calibration band.

Surfaces ``calibration_insights`` — the pipeline's own signal-accuracy
self-assessment (per-signal win-rate / alpha, taxonomy ordering, confidence
caveat), present in ~44% of reports and rendered nowhere (review finding P1-2).
Confidence-gated (honest about the block's own "not yet decision-grade" caveat —
every bucket is single-regime today) and anchored to today's live signals so a
glance answers "how much should I trust the signals I'm acting on today?".
"""
from __future__ import annotations

from collections import Counter

from lib.catalog import SIGNAL_ORDER

# Small-sample floor for a proportion: buckets with fewer than this many matured
# observations are treated as low-confidence regardless of regime coverage.
_MIN_MATURED_N = 30


def _today_signal_counts(watchlist: dict) -> Counter:
    """Count truthy signals across today's watchlist entries.

    Null / absent signals are skipped — they are not actionable and would only
    dilute the "dominant signal today" headline.
    """
    counts: Counter = Counter()
    for entry in (watchlist or {}).values():
        sig = (entry or {}).get("signal")
        if sig:
            counts[sig] += 1
    return counts


def _is_low_confidence(perf: dict) -> bool:
    """True when a signal_performance bucket is single-regime or thin-n.

    The block self-flags every bucket single_regime today, so this honestly
    gates the whole card as low-confidence. ``_MIN_MATURED_N`` catches thin
    samples once multiple regimes have accumulated.
    """
    if not perf:
        return True
    if perf.get("single_regime"):
        return True
    return (perf.get("n_matured_10d") or 0) < _MIN_MATURED_N


def _scorecard_rows(signal_performance: dict, today_counts) -> list:
    """Ordered scorecard rows for every bucket present in *signal_performance*.

    Rows follow SIGNAL_ORDER (best→worst) so BUY/ACCUMULATE lead even at zero
    current exposure. Each row carries today's exposure count and a
    low-confidence flag.
    """
    sp = signal_performance or {}
    counts = today_counts or {}
    rows = []
    for sig in SIGNAL_ORDER:
        perf = sp.get(sig)
        if not perf:
            continue
        rows.append({
            "signal": sig,
            "today": int(counts.get(sig, 0)),
            "n": perf.get("n_matured_10d"),
            "win": perf.get("win_rate_pct"),
            "avg": perf.get("avg_return_10d"),
            "alpha": perf.get("alpha_10d"),
            "low_conf": _is_low_confidence(perf),
        })
    return rows


def _taxonomy_line(taxonomy: dict) -> str:
    """One-line "do better signals produce better outcomes?" verdict.

    Built from the *full_corpus* ordering (the *in_window* block is usually
    empty / INSUFFICIENT on the short lookback). Returns "" when unavailable so
    the caller omits the line. Plain text — the caller escapes it.
    """
    fc = (taxonomy or {}).get("full_corpus") or {}
    ordering = (fc.get("observed_ordering_str") or "").strip()
    if not ordering:
        return ""
    mono = (fc.get("monotonic") or "").strip().upper()
    mono_txt = {
        "YES": "monotonic",
        "PARTIAL": "partially monotonic",
        "NO": "not monotonic",
        "INSUFFICIENT": "insufficient data",
    }.get(mono, mono.lower())
    tail = f" · {mono_txt}" if mono_txt else ""
    return f"Signal ordering (full corpus): {ordering}{tail}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_calibration.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Run ruff**

Run: `python -m ruff check components/briefing/calibration.py tests/test_calibration.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add components/briefing/calibration.py tests/test_calibration.py
git commit -m "P1-2: calibration reducers (today-counts, confidence gate, scorecard rows, taxonomy)"
```

---

### Task 2: The pure `_calibration_html` builder

**Files:**
- Modify: `components/briefing/calibration.py`
- Test: `tests/test_calibration.py`

**Interfaces:**
- Consumes: Task 1's `_today_signal_counts`, `_scorecard_rows`, `_taxonomy_line`; `lib.formatters._escape_dollars`, `._fmt_num`, `._sign`; `lib.pills._signal_pill_html`.
- Produces:
  - `_pct(value, decimals=1) -> str` — signed percent like `+2.7%` / `-3.0%`, or `—`.
  - `_window_caption(data_window: dict) -> str` — `"60-day window · 2026-05-02 – 2026-07-01"`, or `""`.
  - `_scorecard_table_html(rows: list) -> str` — a `.ep-table` of the rows, low-conf rows carrying `data-lowconf="1"`; `""` when no rows.
  - `_headline_html(rows: list, today_counts) -> str` — collapsed-row headline anchored to today's dominant signal (fallback label when it has no row).
  - `_calibration_html(calibration_insights: dict, watchlist: dict) -> str` — full band (`<details class="cal-band cal-details">…`), or a `.cal-empty` placeholder when `signal_performance` is empty.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calibration.py`:

```python
from components.briefing.calibration import _calibration_html

_SP = {
    "CAUTION": {"n_matured_10d": 526, "win_rate_pct": 47.1, "avg_return_10d": 2.71,
                "alpha_10d": -3.05, "single_regime": True},
    "HOLD": {"n_matured_10d": 67, "win_rate_pct": 35.8, "avg_return_10d": -2.58,
             "alpha_10d": -6.34, "single_regime": True},
}
_CI = {
    "signal_performance": _SP,
    "taxonomy_discrimination": {
        "full_corpus": {"observed_ordering_str": "HOLD -0.1 > CAUTION -2.6",
                        "monotonic": "PARTIAL"},
    },
    "confidence_banner": "NOT yet decision-grade — single-regime.",
    "data_window": {"from": "2026-05-02", "to": "2026-07-01", "lookback_days": 60},
}
_WL = {"A": {"signal": "CAUTION"}, "B": {"signal": "CAUTION"}, "C": {"signal": "HOLD"}}


def test_calibration_html_has_scorecard_and_anchored_headline():
    out = _calibration_html(_CI, _WL)
    assert "cal-scorecard" in out
    # dominant today = CAUTION (2 names); headline names it with its 10d alpha
    assert "most common today (2&nbsp;names)" in out
    assert "-3.0% α" in out


def test_calibration_html_taxonomy_line_present_and_escaped():
    out = _calibration_html(_CI, _WL)
    assert "Signal ordering (full corpus):" in out
    assert "partially monotonic" in out
    assert "HOLD -0.1" in out
    assert "&gt;" in out  # the '>' in the ordering string is HTML-escaped


def test_calibration_html_caveat_and_window():
    out = _calibration_html(_CI, _WL)
    assert "NOT yet decision-grade" in out
    assert "60-day window" in out
    assert "2026-05-02" in out


def test_low_confidence_rows_muted():
    out = _calibration_html(_CI, _WL)
    # both buckets are single_regime -> every data row carries the flag
    assert 'data-lowconf="1"' in out


def test_empty_calibration_placeholder():
    assert "No calibration data" in _calibration_html({}, _WL)
    assert "No calibration data" in _calibration_html({"signal_performance": {}}, _WL)


def test_missing_taxonomy_and_window_tolerated():
    out = _calibration_html({"signal_performance": _SP}, _WL)
    assert "cal-scorecard" in out          # scorecard still renders
    assert "Signal ordering" not in out    # taxonomy line omitted
    assert "cal-caveat" not in out         # no caveat paragraph


def test_dominant_signal_without_bucket_falls_back():
    # today's dominant signal (WATCH) has no scorecard bucket -> generic headline
    ci = {"signal_performance": {"HOLD": _SP["HOLD"]}}
    wl = {"A": {"signal": "WATCH"}, "B": {"signal": "WATCH"}, "C": {"signal": "HOLD"}}
    out = _calibration_html(ci, wl)
    assert "Signal calibration · 60-day window" in out


def test_banner_and_ordering_escaped():
    ci = {
        "signal_performance": _SP,
        "taxonomy_discrimination": {"full_corpus": {
            "observed_ordering_str": "<img src=x onerror=alert(1)>", "monotonic": "NO"}},
        "confidence_banner": "<script>alert(1)</script>",
    }
    out = _calibration_html(ci, _WL)
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_calibration.py -q`
Expected: FAIL — `ImportError: cannot import name '_calibration_html'`.

- [ ] **Step 3: Write the minimal implementation**

In `components/briefing/calibration.py`, add the two import lines (merge into the existing block, keeping isort order — stdlib, then `lib.*` alphabetical):

```python
from lib.catalog import SIGNAL_ORDER
from lib.formatters import _escape_dollars, _fmt_num, _sign
from lib.pills import _signal_pill_html
```

Then append the builder functions to the end of the file:

```python
def _pct(value, decimals: int = 1) -> str:
    """Signed percentage like '+2.7%' / '-3.0%', or '—' when missing."""
    if value is None:
        return "—"
    return f"{_sign(value)}{_fmt_num(value, decimals)}%"


def _window_caption(data_window: dict) -> str:
    """'60-day window · 2026-05-02 – 2026-07-01' from data_window, or ''.

    ISO dates are shown as-is (robust + cross-platform); month-name humanizing
    is a deferred cosmetic nicety.
    """
    dw = data_window or {}
    days = dw.get("lookback_days")
    frm = dw.get("from")
    to = dw.get("to")
    bits = []
    if days:
        bits.append(f"{_fmt_num(days, 0)}-day window")
    if frm and to:
        bits.append(f"{_escape_dollars(str(frm))} – {_escape_dollars(str(to))}")
    return " · ".join(bits)


def _scorecard_table_html(rows: list) -> str:
    """A .ep-table of signal → today-count, n, win%, avg-10d, alpha.

    Low-confidence rows carry ``data-lowconf="1"`` for CSS muting. Returns ''
    when there are no rows.
    """
    if not rows:
        return ""
    trs = []
    for r in rows:
        lc = ' data-lowconf="1"' if r["low_conf"] else ""
        win = f'{_fmt_num(r["win"], 0)}%' if r["win"] is not None else "—"
        trs.append(
            f"<tr{lc}><td>{_signal_pill_html(r['signal'], small=True)}</td>"
            f'<td class="num">{r["today"]}</td>'
            f'<td class="num">{_fmt_num(r["n"], 0)}</td>'
            f'<td class="num">{win}</td>'
            f'<td class="num">{_pct(r["avg"])}</td>'
            f'<td class="num">{_pct(r["alpha"])}</td></tr>'
        )
    return (
        '<div class="tk-scroll"><table class="ep-table cal-scorecard">'
        '<thead><tr><th>Signal</th><th class="num">Today</th>'
        '<th class="num">n</th><th class="num">Win</th>'
        '<th class="num">Avg 10d</th><th class="num">α</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )


def _headline_html(rows: list, today_counts) -> str:
    """Collapsed-row headline anchored to today's dominant signal.

    Names the most common current signal (ties broken by SIGNAL_ORDER,
    best-first), its 10d alpha, and its confidence state. Falls back to a
    generic label when that signal has no scorecard row.
    """
    counts = today_counts or {}
    if counts:
        order = {s: i for i, s in enumerate(SIGNAL_ORDER)}
        dominant = sorted(counts, key=lambda s: (-counts[s], order.get(s, 99)))[0]
        row = next((r for r in rows if r["signal"] == dominant), None)
        if row is not None:
            conf = "low-confidence" if row["low_conf"] else "decision-grade"
            n = counts[dominant]
            names = "name" if n == 1 else "names"
            return (
                '<span class="cal-headline">'
                f"{_signal_pill_html(dominant, small=True)}"
                f'<span class="cal-head-txt">most common today ({n}&nbsp;{names}) · '
                f'{_pct(row["alpha"])} α / 10d · '
                f'<span class="cal-conf">{conf}</span></span></span>'
            )
    return '<span class="cal-headline cal-head-txt">Signal calibration · 60-day window</span>'


def _calibration_html(calibration_insights: dict, watchlist: dict) -> str:
    """Full calibration band HTML, or a muted placeholder when empty."""
    ci = calibration_insights or {}
    sp = ci.get("signal_performance") or {}
    if not sp:
        return '<div class="cal-band cal-empty">No calibration data in this report.</div>'

    today = _today_signal_counts(watchlist)
    rows = _scorecard_rows(sp, today)

    parts = [
        f'<summary class="cal-summary">{_headline_html(rows, today)}</summary>',
        '<div class="cal-body">',
        _scorecard_table_html(rows),
    ]

    tax_line = _taxonomy_line(ci.get("taxonomy_discrimination"))
    if tax_line:
        parts.append(f'<p class="cal-taxonomy">{_escape_dollars(tax_line)}</p>')

    banner = (ci.get("confidence_banner") or "").strip()
    window = _window_caption(ci.get("data_window"))
    if banner or window:
        caveat_bits = []
        if banner:
            caveat_bits.append(_escape_dollars(banner))
        if window:
            caveat_bits.append(window)  # dates already escaped inside
        parts.append(f'<p class="cal-caveat">{"&nbsp; ".join(caveat_bits)}</p>')

    parts.append("</div>")
    return f'<details class="cal-band cal-details">{"".join(parts)}</details>'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_calibration.py -q`
Expected: PASS (15 passed).

- [ ] **Step 5: Run ruff**

Run: `python -m ruff check components/briefing/calibration.py tests/test_calibration.py`
Expected: `All checks passed!` (fix any import-order finding before committing).

- [ ] **Step 6: Commit**

```bash
git add components/briefing/calibration.py tests/test_calibration.py
git commit -m "P1-2: pure _calibration_html builder + tests (anchor, gating, escaping)"
```

---

### Task 3: Wire the band into the Briefing (wrapper, export, dashboard, CSS)

**Files:**
- Modify: `components/briefing/calibration.py` (add `render_calibration`)
- Modify: `components/briefing/__init__.py`
- Modify: `dashboard.py` (import + call in the Briefing block, after `render_clusters`)
- Modify: `assets/theme.css`

**Interfaces:**
- Consumes: `_calibration_html` (Task 2); `lib.cards.render_section_head`; `streamlit`.
- Produces: `render_calibration(calibration_insights: dict | None, watchlist: dict) -> None`.

- [ ] **Step 1: Add the `render_calibration` wrapper**

In `components/briefing/calibration.py`, add these two imports (merge in isort order — `streamlit` is third-party and goes after the stdlib block and before the `lib.*` block; `lib.cards` sorts before `lib.catalog`). The final top-of-file import block must read exactly:

```python
from __future__ import annotations

from collections import Counter

import streamlit as st

from lib.cards import render_section_head
from lib.catalog import SIGNAL_ORDER
from lib.formatters import _escape_dollars, _fmt_num, _sign
from lib.pills import _signal_pill_html
```

Append the wrapper to the end of `components/briefing/calibration.py`:

```python
def render_calibration(calibration_insights: dict | None, watchlist: dict) -> None:
    """Briefing signal-calibration band — the pipeline's signal-accuracy
    self-assessment (review P1-2).

    Silent when the report carries no ``calibration_insights`` (older reports /
    the ~56% without it); on the latest report it is present.
    """
    ci = calibration_insights or {}
    if not ci.get("signal_performance"):
        return
    render_section_head("Signal Calibration", "How today's signals have actually performed")
    st.markdown(
        _calibration_html(ci, watchlist),
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: Export it**

Edit `components/briefing/__init__.py` — add the import (after the `action_card` import) and the `__all__` entry (keep `__all__` alphabetically sorted; ruff `RUF022` enforces it):

```python
from components.briefing.action_card import render_action_card
from components.briefing.calibration import render_calibration
from components.briefing.catalyst_playbook import render_catalyst_playbook
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
    "render_pulse",
]
```

- [ ] **Step 3: Call it in the Briefing block**

In `dashboard.py`, add `render_calibration` to the `from components.briefing import (...)` block (keep sorted — it goes right after `render_action_card`). Then, in the `if page == "Briefing":` block, insert the call immediately after the existing `render_clusters(...)` call and before `render_action_card(watchlist, events)`:

```python
    render_clusters(
        report.get("clusters", {}),
        watchlist,
        report.get("extension_regime"),
    )
    render_calibration(
        report.get("calibration_insights"),
        watchlist,
    )
    render_action_card(watchlist, events)
```

- [ ] **Step 4: Add the CSS**

Append to `assets/theme.css` (tokens only — no new hex):

```css
/* ── Briefing · Signal-calibration band (review P1-2: surface `calibration_insights`) ── */
.cal-band { margin: 6px 0 2px; }
.cal-details { padding: 4px 0 2px; }
.cal-summary {
  cursor: pointer; list-style: none;
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
}
.cal-summary::-webkit-details-marker { display: none; }
.cal-headline { display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: 6px; }
.cal-head-txt { font-family: var(--mono); font-size: 12px; color: var(--ink-2); }
.cal-conf { color: var(--caution); }
.cal-body { padding: 8px 2px 2px; }
.cal-scorecard { margin-top: 4px; }
.cal-scorecard tr[data-lowconf="1"] { color: var(--ink-3); }
.cal-taxonomy { color: var(--ink-2); font-size: 12px; line-height: 1.5; margin: 8px 0 4px; }
.cal-caveat { color: var(--ink-3); font-size: 11.5px; font-style: italic; line-height: 1.5; margin: 4px 0 0; }
.cal-empty { color: var(--ink-3); font-family: var(--mono); font-size: 12px; padding: 6px 0; }
```

- [ ] **Step 5: Verify the full suite + lint are green**

Run: `python -m pytest -q`
Expected: PASS — the prior 90 plus the new calibration tests (105 total), 0 failures.

Run: `python -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Real-report smoke — the band renders against live data**

Run:

```bash
python -c "
import json, glob
from components.briefing.calibration import _calibration_html
r = json.load(open(sorted(glob.glob('data/morning_report_*.json'))[-1], encoding='utf-8'))
html = _calibration_html(r.get('calibration_insights') or {}, r.get('watchlist') or {})
assert 'cal-scorecard' in html, 'scorecard missing on the latest report'
assert 'data-lowconf' in html, 'confidence gating not applied'
print('OK — calibration band renders; length', len(html))
"
```

Expected: `OK — calibration band renders; length <N>` (no assertion error). A real-data check like this caught a key-matching bug on the cluster slice.

- [ ] **Step 7: Manual smoke (optional but recommended)**

Run: `python -m streamlit run dashboard.py` (or use the `/run` skill). On the **Briefing** page, confirm a "Signal Calibration" section appears after the cluster band and before the action card: the collapsed row names today's dominant signal (CAUTION) with its 10d alpha and a "low-confidence" tag; expanding reveals the per-signal scorecard (with muted low-confidence rows), the taxonomy ordering line, and the caveat + window caption. Confirm no Streamlit exception in the terminal.

- [ ] **Step 8: Commit**

```bash
git add components/briefing/calibration.py components/briefing/__init__.py dashboard.py assets/theme.css
git commit -m "P1-2: surface the signal-calibration band on the Briefing"
```

---

## Self-Review

**1. Spec coverage** (checked against `docs/superpowers/specs/2026-07-02-calibration-scorecard-band-design.md`):
- Placement (Briefing, after `render_clusters`, before `render_action_card`) → Task 3 Step 3. ✓
- Collapsed headline anchored to today's dominant signal → `_headline_html`, tested. ✓
- Confidence gating (`single_regime` OR thin-n; `_MIN_MATURED_N`) → `_is_low_confidence` + `data-lowconf` muting, tested three ways. ✓
- Scorecard = all buckets, ordered by `SIGNAL_ORDER`, with Today column → `_scorecard_rows` / `_scorecard_table_html`, tested. ✓
- Taxonomy verdict from `full_corpus` (omit when empty) → `_taxonomy_line`, tested. ✓
- Caveat = `confidence_banner` + window caption → `_window_caption` + assembly, tested. ✓
- Scope = scorecard + taxonomy + caveat only (no caution_breakdown, no lessons) → builder omits them. ✓
- Error handling (empty, missing sections, dominant-without-bucket) → tests 5–7 in Task 2. ✓
- Security (P4-1 escaping of banner + ordering + dates) → `test_banner_and_ordering_escaped`; all prose via `_escape_dollars`. ✓
- Tokens not hex (P6-1) → CSS uses `--*` vars only; signal colors via `_signal_pill_html`. ✓

**2. Deviations from spec (intentional, noted):**
- **Integration check is a real-report smoke, not AppTest.** The repo has no `streamlit.testing`/`AppTest` harness (grep-confirmed), so the spec's "AppTest Briefing walk" isn't a real command. Task 3 Step 6 runs the pure builder against the latest `data/morning_report_*.json` instead — which is the check that actually caught the cluster key bug — plus an optional manual `streamlit run`.
- **Window caption shows ISO dates, not month names.** The spec mockup humanized to "May 2 – Jul 1, 2026"; the plan shows `2026-05-02 – 2026-07-01`. Reason: month-name humanizing needs `strftime` day-of-month formatting whose directive differs by platform (`%-d` POSIX vs `%#d` Windows) — a real cross-platform trap for a purely cosmetic gain. ISO is robust; humanizing is a deferred nicety.
- **Hostile-payload test lives in `tests/test_calibration.py`** (`test_banner_and_ordering_escaped`), not appended to `test_rendering_security.py` — mirroring how the cluster slice self-contained its `test_prose_is_escaped`. Same coverage, co-located with the component.

**3. Placeholder scan:** none — every step has concrete code/commands.

**4. Type consistency:** helper names/signatures are identical across defining and consuming tasks: `_today_signal_counts` (→`Counter`), `_is_low_confidence` (→`bool`), `_scorecard_rows` (→`list[dict]`, keys `signal/today/n/win/avg/alpha/low_conf`), `_taxonomy_line` (→`str`), `_pct`, `_window_caption`, `_scorecard_table_html`, `_headline_html`, `_calibration_html`, `render_calibration`. `_headline_html` and `_scorecard_table_html` both consume the row dicts produced by `_scorecard_rows`; `_calibration_html` threads `today` (a `Counter`) into both `_scorecard_rows` and `_headline_html`.
