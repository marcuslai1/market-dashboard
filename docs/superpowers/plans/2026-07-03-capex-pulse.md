# AI Capex Pulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the human-read capex digestion scorecard ("AI Capex Pulse" Briefing band) plus earnings-cascade pre-wiring, per the approved spec `docs/superpowers/specs/2026-07-03-capex-pulse-design.md`.

**Architecture:** Pure computation in a new `lib/capex.py` (no Streamlit — the `lib/formatters.py` convention); thin mtime-cached loaders added to `lib/data_loader.py`; a new Streamlit band component `components/briefing/capex_pulse.py`; cascade annotations rendered inside the existing Week-Ahead calendar (`components/briefing/calendar.py`). Two hand-maintained JSON data files seed the quarterly capex series and the cascade config.

**Tech Stack:** Python 3.10+, Streamlit, pandas, Plotly, pytest (run as `python -m pytest`).

## Global Constraints

- **pandas floor is 1.4.2 locally** (base Anaconda) — use only APIs that exist in 1.4: `groupby(...).median()`, `.unstack()`, `.quantile()` are fine; do NOT use pandas-2-only APIs. CI proves 2.x compat; local must not break.
- **`lib/capex.py` MUST NOT import streamlit** (same rule as `lib/formatters.py`) — everything in it is unit-testable pure Python/pandas.
- **All report-derived or file-derived text injected via `unsafe_allow_html` goes through `lib.formatters._escape_dollars`** (text nodes) — never raw.
- **No hex literals in components** (review P6-1): colors come from `lib.charts` constants (`STATUS_POS`, `STATUS_NEG`, `STATUS_WARN`, `CHART_ACCENT`, `CHART_MUTED`, `CHART_PALETTE`, `INK_FALLBACK`, `SURFACE_2_FALLBACK`).
- **Plotly calls follow the house pattern:** `st.plotly_chart(style_fig(fig), use_container_width=True, config=PLOTLY_CONFIG)` and every chart gets a `chart_data_table(df)` fallback (review P8-4).
- **`st.cache_data` mtime/fingerprint contract** (`lib/data_loader.py` docstring): cache-key params must NOT be `_`-prefixed; heavy non-key params MUST be `_`-prefixed; always set `max_entries`.
- **Thresholds are presentation constants, not calibrated signals** — the band is a human-read cross-check; nothing here feeds scenario odds.
- **Ticker keys:** data files use the raw watchlist key form (`000660_KS`); display always via `lib.formatters.display_ticker`.
- **Commit after every task.** All commits end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and the session trailer already used in this repo's recent commits.
- Full suite must stay green: `python -m pytest -q` → currently 158 passed.

---

### Task 1: Capex file parsing + seed data

**Files:**
- Create: `lib/capex.py`
- Create: `data/capex_quarterly.json`
- Create: `tests/test_capex.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `parse_capex(raw: dict) -> dict` returning `{"core": list[str], "fragile": list[str], "beneficiaries": list[str], "series": dict[str, list[dict]], "warnings": list[str]}`; each series row is `{"cq": str, "reported": datetime.date, "capex_usd_b": float, "fiscal_label": str, "guide": str, "note": str, "flag": str, "source": str}`, rows ascending by `cq`.
  - `curation_age_days(capex: dict, today: datetime.date) -> int | None`
  - Constants: `ACCEL_PP = 2.0`, `GAP_WIDEN_PP = 3.0`, `REV_TREND_WINDOW_DAYS = 60`, `REV_FLAT_PP = 1.0`, `VAL_WARN_QUANTILE = 0.80`, `CURATION_OVERDUE_DAYS = 110`, `SEMIS_CLUSTER = "Semis"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_capex.py`:

```python
"""Tests for lib.capex — pure computations behind the AI Capex Pulse band."""
import json
from datetime import date
from pathlib import Path

from lib.capex import curation_age_days, parse_capex


def _raw(series=None):
    return {
        "core_spenders": ["MSFT", "GOOG"],
        "fragile_tier": ["CRWV"],
        "beneficiaries": ["NVDA", "MU"],
        "series": series or {},
    }


def test_parse_capex_empty_input_returns_empty_structure():
    for bad in ({}, None, []):
        out = parse_capex(bad)
        assert out["core"] == [] and out["series"] == {} and out["warnings"] == []


def test_parse_capex_valid_row_normalized_and_sorted():
    out = parse_capex(_raw({"MSFT": [
        {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 30.88},
        {"cq": "2025Q4", "reported": "2026-01-29", "capex_usd_b": 37.5},
    ]}))
    rows = out["series"]["MSFT"]
    assert [r["cq"] for r in rows] == ["2025Q4", "2026Q1"]  # ascending
    assert rows[1]["reported"] == date(2026, 4, 29)
    assert rows[1]["capex_usd_b"] == 30.88
    assert out["warnings"] == []


def test_parse_capex_drops_bad_rows_with_warnings_never_raises():
    out = parse_capex(_raw({
        "MSFT": [
            {"cq": "bad", "reported": "2026-04-29", "capex_usd_b": 30.9},
            {"cq": "2026Q1", "reported": "not-a-date", "capex_usd_b": 30.9},
            {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": -3},
            "not-a-dict",
            {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 30.88},
        ],
        "UNKNOWN": [{"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 1.0}],
    }))
    assert [r["cq"] for r in out["series"]["MSFT"]] == ["2026Q1"]
    assert "UNKNOWN" not in out["series"]
    assert len(out["warnings"]) == 5


def test_curation_age_uses_newest_core_reported_date():
    out = parse_capex(_raw({
        "MSFT": [{"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 30.88}],
        "GOOG": [{"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 35.67}],
        "CRWV": [{"cq": "2026Q1", "reported": "2026-06-30", "capex_usd_b": 6.8}],
    }))
    # fragile-tier CRWV must NOT count toward core curation freshness
    assert curation_age_days(out, date(2026, 7, 3)) == 65


def test_curation_age_none_when_no_core_rows():
    assert curation_age_days(parse_capex(_raw()), date(2026, 7, 3)) is None


def test_seed_file_parses_clean():
    raw = json.loads(Path("data/capex_quarterly.json").read_text(encoding="utf-8"))
    out = parse_capex(raw)
    assert out["core"] == ["MSFT", "GOOG", "AMZN", "META"]
    assert out["fragile"] == ["CRWV"]
    assert out["warnings"] == []
    assert all(len(out["series"][tk]) == 9 for tk in out["core"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -q`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'lib.capex'` (and the seed-file test fails on missing file).

- [ ] **Step 3: Write the implementation**

Create `lib/capex.py`:

```python
"""Capex-cycle computations for the AI Capex Pulse band.

Spec: docs/superpowers/specs/2026-07-03-capex-pulse-design.md. Pure functions —
no Streamlit imports (the ``lib/formatters.py`` rule) so everything is
trivially unit-testable. The thresholds below are presentation constants
(display colors on a human-read cross-check), NOT calibrated signals; by
design nothing here feeds the scenario odds.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pandas as pd

ACCEL_PP = 2.0             # capex-YoY delta at/above this → "accelerating"
GAP_WIDEN_PP = 3.0         # gap fell by at least this vs prior → "widening"
REV_TREND_WINDOW_DAYS = 60
REV_FLAT_PP = 1.0          # |median move| under this → "flat"
VAL_WARN_QUANTILE = 0.80   # fwd-PE/PEG above this corpus quantile → warn
CURATION_OVERDUE_DAYS = 110
SEMIS_CLUSTER = "Semis"

_CQ_RE = re.compile(r"^\d{4}Q[1-4]$")


def parse_capex(raw) -> dict:
    """Validate the hand-maintained capex file into a normalized structure.

    Never raises on malformed input: bad rows are dropped with a human-readable
    warning (the band surfaces them), good rows survive. ``cq`` is the calendar
    quarter (``YYYYQn``) — lexicographic order IS chronological order, which the
    sort below relies on.
    """
    out = {"core": [], "fragile": [], "beneficiaries": [], "series": {},
           "warnings": []}
    if not isinstance(raw, dict) or not raw:
        return out
    out["core"] = [t for t in (raw.get("core_spenders") or []) if isinstance(t, str)]
    out["fragile"] = [t for t in (raw.get("fragile_tier") or []) if isinstance(t, str)]
    out["beneficiaries"] = [t for t in (raw.get("beneficiaries") or []) if isinstance(t, str)]
    known = set(out["core"]) | set(out["fragile"])
    series = raw.get("series") if isinstance(raw.get("series"), dict) else {}
    for tk, rows in series.items():
        if tk not in known:
            out["warnings"].append(f"{tk}: not in core_spenders/fragile_tier — skipped")
            continue
        clean = []
        for i, r in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(r, dict):
                out["warnings"].append(f"{tk}[{i}]: not an object — dropped")
                continue
            cq = r.get("cq")
            if not isinstance(cq, str) or not _CQ_RE.match(cq):
                out["warnings"].append(f"{tk}[{i}]: bad cq {cq!r} — dropped")
                continue
            try:
                reported = datetime.strptime(str(r.get("reported")), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                out["warnings"].append(f"{tk} {cq}: bad reported date — dropped")
                continue
            capex = r.get("capex_usd_b")
            if isinstance(capex, bool) or not isinstance(capex, (int, float)) or capex <= 0:
                out["warnings"].append(f"{tk} {cq}: bad capex_usd_b — dropped")
                continue
            clean.append({
                "cq": cq, "reported": reported, "capex_usd_b": float(capex),
                "fiscal_label": r.get("fiscal_label") or "",
                "guide": r.get("guide") or "",
                "note": r.get("note") or "",
                "flag": r.get("flag") or "",
                "source": r.get("source") or "",
            })
        clean.sort(key=lambda row: row["cq"])
        if clean:
            out["series"][tk] = clean
    return out


def curation_age_days(capex: dict, today: date) -> int | None:
    """Days since the newest *core-spender* ``reported`` date; None if no rows.

    Past ``CURATION_OVERDUE_DAYS`` a newer quarter has likely been reported and
    the file missed it — the band's honest-staleness tag keys off this (same
    semantics as the macro-prints release-aware STALE fix).
    """
    latest = [rows[-1]["reported"] for tk, rows in capex["series"].items()
              if tk in capex["core"] and rows]
    if not latest:
        return None
    return (today - max(latest)).days
```

- [ ] **Step 4: Create the seed data file**

Create `data/capex_quarterly.json`. Values marked `"provisional"` in `note` are best-known estimates pending IR verification (see Step 6); all others are from earnings releases/filings.

```json
{
  "core_spenders": ["MSFT", "GOOG", "AMZN", "META"],
  "fragile_tier": ["CRWV"],
  "beneficiaries": ["NVDA", "AMD", "AVGO", "TSM", "MU", "000660_KS", "LITE"],
  "methodology": "Capex = purchases of PP&E as reported; MSFT rows include finance leases (their reported total capex framing). What counts as AI capex is a curation judgment — record it in note when it matters. cq is the CALENDAR quarter; fiscal_label is display-only.",
  "series": {
    "MSFT": [
      {"cq": "2024Q1", "fiscal_label": "FY24Q3", "reported": "2024-04-25", "capex_usd_b": 14.0, "source": "FY24Q3 earnings", "note": ""},
      {"cq": "2024Q2", "fiscal_label": "FY24Q4", "reported": "2024-07-30", "capex_usd_b": 19.0, "source": "FY24Q4 earnings", "note": ""},
      {"cq": "2024Q3", "fiscal_label": "FY25Q1", "reported": "2024-10-30", "capex_usd_b": 20.0, "source": "FY25Q1 earnings", "note": ""},
      {"cq": "2024Q4", "fiscal_label": "FY25Q2", "reported": "2025-01-29", "capex_usd_b": 22.6, "source": "FY25Q2 earnings", "note": ""},
      {"cq": "2025Q1", "fiscal_label": "FY25Q3", "reported": "2025-04-30", "capex_usd_b": 21.4, "source": "FY25Q3 earnings", "note": ""},
      {"cq": "2025Q2", "fiscal_label": "FY25Q4", "reported": "2025-07-30", "capex_usd_b": 24.2, "source": "FY25Q4 earnings", "note": ""},
      {"cq": "2025Q3", "fiscal_label": "FY26Q1", "reported": "2025-10-29", "capex_usd_b": 34.9, "source": "FY26Q1 earnings", "note": ""},
      {"cq": "2025Q4", "fiscal_label": "FY26Q2", "reported": "2026-01-29", "capex_usd_b": 37.5, "source": "FY26Q2 earnings", "note": "provisional — verify vs FY26Q2 IR release"},
      {"cq": "2026Q1", "fiscal_label": "FY26Q3", "reported": "2026-04-29", "capex_usd_b": 30.88, "guide": "CY2026 tracking ~$190B", "source": "FY26Q3 earnings (web-verified 2026-07-03)", "note": ""}
    ],
    "GOOG": [
      {"cq": "2024Q1", "reported": "2024-04-25", "capex_usd_b": 12.0, "source": "Q1'24 earnings", "note": ""},
      {"cq": "2024Q2", "reported": "2024-07-23", "capex_usd_b": 13.2, "source": "Q2'24 earnings", "note": ""},
      {"cq": "2024Q3", "reported": "2024-10-29", "capex_usd_b": 13.1, "source": "Q3'24 earnings", "note": ""},
      {"cq": "2024Q4", "reported": "2025-02-04", "capex_usd_b": 14.3, "source": "Q4'24 earnings", "note": ""},
      {"cq": "2025Q1", "reported": "2025-04-24", "capex_usd_b": 17.2, "source": "Q1'25 earnings", "note": ""},
      {"cq": "2025Q2", "reported": "2025-07-23", "capex_usd_b": 22.4, "source": "Q2'25 earnings", "note": ""},
      {"cq": "2025Q3", "reported": "2025-10-28", "capex_usd_b": 24.0, "source": "Q3'25 earnings", "note": ""},
      {"cq": "2025Q4", "reported": "2026-02-03", "capex_usd_b": 28.0, "source": "Q4'25 earnings", "note": "provisional — verify vs Q4'25 IR release"},
      {"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 35.67, "guide": "FY26 $180-190B (raised at Q1)", "source": "Q1'26 earnings (web-verified 2026-07-03)", "note": ""}
    ],
    "AMZN": [
      {"cq": "2024Q1", "reported": "2024-04-30", "capex_usd_b": 15.0, "source": "Q1'24 earnings", "note": ""},
      {"cq": "2024Q2", "reported": "2024-08-01", "capex_usd_b": 17.6, "source": "Q2'24 earnings", "note": ""},
      {"cq": "2024Q3", "reported": "2024-10-31", "capex_usd_b": 22.6, "source": "Q3'24 earnings", "note": ""},
      {"cq": "2024Q4", "reported": "2025-02-06", "capex_usd_b": 27.8, "source": "Q4'24 earnings", "note": ""},
      {"cq": "2025Q1", "reported": "2025-05-01", "capex_usd_b": 25.0, "source": "Q1'25 earnings", "note": ""},
      {"cq": "2025Q2", "reported": "2025-07-31", "capex_usd_b": 31.4, "source": "Q2'25 earnings", "note": ""},
      {"cq": "2025Q3", "reported": "2025-10-30", "capex_usd_b": 34.2, "source": "Q3'25 earnings", "note": ""},
      {"cq": "2025Q4", "reported": "2026-02-05", "capex_usd_b": 34.4, "source": "Q4'25 earnings", "note": "provisional — verify vs Q4'25 IR release"},
      {"cq": "2026Q1", "reported": "2026-04-30", "capex_usd_b": 44.20, "guide": "FY26 ~$200B", "source": "Q1'26 earnings (web-verified 2026-07-03)", "note": ""}
    ],
    "META": [
      {"cq": "2024Q1", "reported": "2024-04-24", "capex_usd_b": 6.7, "source": "Q1'24 earnings", "note": ""},
      {"cq": "2024Q2", "reported": "2024-07-31", "capex_usd_b": 8.5, "source": "Q2'24 earnings", "note": ""},
      {"cq": "2024Q3", "reported": "2024-10-30", "capex_usd_b": 9.2, "source": "Q3'24 earnings", "note": ""},
      {"cq": "2024Q4", "reported": "2025-01-29", "capex_usd_b": 14.8, "source": "Q4'24 earnings", "note": ""},
      {"cq": "2025Q1", "reported": "2025-04-30", "capex_usd_b": 13.7, "source": "Q1'25 earnings", "note": ""},
      {"cq": "2025Q2", "reported": "2025-07-30", "capex_usd_b": 17.0, "source": "Q2'25 earnings", "note": ""},
      {"cq": "2025Q3", "reported": "2025-10-29", "capex_usd_b": 19.4, "source": "Q3'25 earnings", "note": ""},
      {"cq": "2025Q4", "reported": "2026-01-28", "capex_usd_b": 22.1, "source": "derived: verified FY25 $72.2B minus Q1-Q3", "note": ""},
      {"cq": "2026Q1", "reported": "2026-04-29", "capex_usd_b": 19.8, "guide": "FY26 $125-145B (raised from 115-135)", "source": "Q1'26 earnings (web-verified 2026-07-03)", "note": ""}
    ],
    "CRWV": [
      {"cq": "2025Q4", "reported": "2026-02-10", "capex_usd_b": 8.2, "flag": "amber", "source": "Q4'25 earnings (web-verified 2026-07-03)", "note": "FY25 capex $14.9B total; debt-funded ramp"},
      {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 6.8, "flag": "amber", "source": "Q1'26 earnings (web-verified 2026-07-03)", "note": "FY26 capex guide $31-35B, debt-funded; Q2 guide $7-9B — circularity node (NVDA investee & customer)"}
    ]
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 6 passed.

- [ ] **Step 6: Verify provisional rows (web search if available in your session)**

The three rows whose `note` says `provisional` (MSFT/GOOG/AMZN 2025Q4) are estimates. If web search is available: search `"<company> Q4 2025 capital expenditures billion earnings release"` for each, correct `capex_usd_b` and `reported` to the IR release values, and clear the `note`. If web search is NOT available in your session, leave the rows as-is (the `note` field preserves the caveat in-file) and say so in your task report. Re-run `python -m pytest tests/test_capex.py -q` after any edit.

- [ ] **Step 7: Commit**

```bash
git add lib/capex.py data/capex_quarterly.json tests/test_capex.py
git commit -m "feat: capex file parser + seeded quarterly capex series (Capex Pulse task 1)"
```

---

### Task 2: Core capex YoY + pending-quarter status

**Files:**
- Modify: `lib/capex.py` (append functions)
- Test: `tests/test_capex.py` (append tests)

**Interfaces:**
- Consumes: `parse_capex` output shape (Task 1).
- Produces:
  - `core_capex_yoy(capex: dict) -> list[dict]` — ascending, one entry per quarter where **every** core spender has a row: `{"cq": str, "total_b": float, "prior_b": float | None, "yoy_pct": float | None}` (`yoy_pct` None when the prior-year quarter isn't complete).
  - `pending_quarter(capex: dict) -> dict | None` — `{"cq": str, "have": list[str], "missing": list[str]}` for the newest quarter with partial core coverage, else None.
  - `_prior_cq(cq: str) -> str` (module-private helper).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_capex.py`)

```python
from lib.capex import core_capex_yoy, pending_quarter


def _two_spender_capex(msft, goog):
    """Build parsed capex for core=[MSFT, GOOG] from {cq: capex_b} dicts."""
    def rows(m):
        return [{"cq": cq, "reported": "2026-04-29", "capex_usd_b": v}
                for cq, v in m.items()]
    return parse_capex(_raw({"MSFT": rows(msft), "GOOG": rows(goog)}))


def test_core_capex_yoy_computes_only_complete_quarters():
    capex = _two_spender_capex(
        {"2025Q1": 10.0, "2026Q1": 15.0},
        {"2025Q1": 10.0},  # GOOG missing 2026Q1 → that quarter incomplete
    )
    out = core_capex_yoy(capex)
    assert [r["cq"] for r in out] == ["2025Q1"]
    assert out[0]["total_b"] == 20.0
    assert out[0]["yoy_pct"] is None  # no 2024Q1 anywhere


def test_core_capex_yoy_pct_math():
    capex = _two_spender_capex(
        {"2025Q1": 10.0, "2026Q1": 15.0},
        {"2025Q1": 10.0, "2026Q1": 19.0},
    )
    out = core_capex_yoy(capex)
    latest = out[-1]
    assert latest["cq"] == "2026Q1"
    assert latest["total_b"] == 34.0 and latest["prior_b"] == 20.0
    assert latest["yoy_pct"] == 70.0


def test_pending_quarter_reports_missing_spenders():
    capex = _two_spender_capex(
        {"2025Q1": 10.0, "2026Q1": 15.0},
        {"2025Q1": 10.0},
    )
    assert pending_quarter(capex) == {"cq": "2026Q1", "have": ["MSFT"],
                                      "missing": ["GOOG"]}


def test_pending_quarter_none_when_complete():
    capex = _two_spender_capex({"2025Q1": 10.0}, {"2025Q1": 10.0})
    assert pending_quarter(capex) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 4 new FAIL/ERROR (`ImportError: cannot import name 'core_capex_yoy'`), 6 prior pass.

- [ ] **Step 3: Write the implementation** (append to `lib/capex.py`)

```python
def _prior_cq(cq: str) -> str:
    """Same calendar quarter one year earlier: '2026Q1' -> '2025Q1'."""
    return f"{int(cq[:4]) - 1}{cq[4:]}"


def core_capex_yoy(capex: dict) -> list[dict]:
    """Aggregate core-spender capex per quarter with YoY growth, ascending.

    A quarter appears only when EVERY core spender has its row — a partial sum
    would understate the aggregate and fake a deceleration. ``yoy_pct`` is None
    until the prior-year quarter is also complete.
    """
    core = capex["core"]
    if not core:
        return []
    by_tk = {tk: {r["cq"]: r["capex_usd_b"] for r in capex["series"].get(tk, [])}
             for tk in core}
    out = []
    for cq in sorted({cq for m in by_tk.values() for cq in m}):
        if any(cq not in by_tk[tk] for tk in core):
            continue
        total = sum(by_tk[tk][cq] for tk in core)
        p = _prior_cq(cq)
        prior = (sum(by_tk[tk][p] for tk in core)
                 if all(p in by_tk[tk] for tk in core) else None)
        yoy = (total - prior) / prior * 100.0 if prior else None
        out.append({"cq": cq, "total_b": round(total, 2),
                    "prior_b": round(prior, 2) if prior is not None else None,
                    "yoy_pct": round(yoy, 1) if yoy is not None else None})
    return out


def pending_quarter(capex: dict) -> dict | None:
    """The newest quarter some-but-not-all core spenders have reported.

    Feeds the 'awaiting N of M spenders' copy so a half-entered earnings season
    reads as in-progress rather than silently shifting the aggregate.
    """
    core = capex["core"]
    by_tk = {tk: {r["cq"] for r in capex["series"].get(tk, [])} for tk in core}
    all_cqs = sorted({cq for s in by_tk.values() for cq in s})
    if not all_cqs:
        return None
    newest = all_cqs[-1]
    have = [tk for tk in core if newest in by_tk[tk]]
    if len(have) == len(core):
        return None
    return {"cq": newest, "have": have,
            "missing": [tk for tk in core if newest not in by_tk[tk]]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat: core capex YoY aggregate + pending-quarter status (Capex Pulse task 2)"
```

---

### Task 3: Beneficiary fundamentals history from the report corpus

**Files:**
- Modify: `lib/capex.py` (append)
- Test: `tests/test_capex.py` (append)

**Interfaces:**
- Consumes: the morning-report corpus shape — `reports: dict[date_str, report]`, where `report["watchlist"][ticker]["valuation"]` carries `revenue_growth_pct`, `fcf_yield_pct`, `forward_pe`, `peg_ratio`, `cluster_name`, and `analyst_consensus.earnings_growth_pct`.
- Produces: `fundamentals_history(reports: dict) -> pd.DataFrame` with columns exactly `["date", "ticker", "cluster", "revenue_growth_pct", "fcf_yield_pct", "forward_pe", "peg_ratio", "earnings_growth_pct"]`, one row per (report date, ticker-with-valuation), dates ascending, missing numerics as NaN.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_capex.py`)

```python
import math

from lib.capex import fundamentals_history


def _report(entries):
    return {"watchlist": entries}


SYNTH_REPORTS = {
    "2026-06-01": _report({
        "NVDA": {"valuation": {"revenue_growth_pct": 80.0, "fcf_yield_pct": 1.0,
                               "forward_pe": 30.0, "peg_ratio": 0.6,
                               "cluster_name": "Semis",
                               "analyst_consensus": {"earnings_growth_pct": 200.0}}},
        "MU": {"valuation": {"revenue_growth_pct": 40.0, "forward_pe": 12.0,
                             "cluster_name": "Semis"}},
        "D05_SI": {"no_valuation_here": True},
    }),
    "2026-07-01": _report({
        "NVDA": {"valuation": {"revenue_growth_pct": 85.2, "forward_pe": 15.5,
                               "cluster_name": "Semis"}},
    }),
}


def test_fundamentals_history_shape_and_order():
    df = fundamentals_history(SYNTH_REPORTS)
    assert list(df.columns) == ["date", "ticker", "cluster", "revenue_growth_pct",
                                "fcf_yield_pct", "forward_pe", "peg_ratio",
                                "earnings_growth_pct"]
    assert len(df) == 3  # D05_SI has no valuation dict → skipped
    assert list(df["date"]) == sorted(df["date"])


def test_fundamentals_history_values_and_nans():
    df = fundamentals_history(SYNTH_REPORTS)
    nvda_jun = df[(df["ticker"] == "NVDA") & (df["date"] == "2026-06-01")].iloc[0]
    assert nvda_jun["earnings_growth_pct"] == 200.0
    mu = df[df["ticker"] == "MU"].iloc[0]
    assert math.isnan(mu["peg_ratio"]) and math.isnan(mu["earnings_growth_pct"])
    assert mu["cluster"] == "Semis"


def test_fundamentals_history_empty_input():
    df = fundamentals_history({})
    assert df.empty and "revenue_growth_pct" in df.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 3 new failures (`ImportError: cannot import name 'fundamentals_history'`).

- [ ] **Step 3: Write the implementation** (append to `lib/capex.py`)

```python
_FUND_FIELDS = ["revenue_growth_pct", "fcf_yield_pct", "forward_pe", "peg_ratio"]
_FUND_COLUMNS = ["date", "ticker", "cluster"] + _FUND_FIELDS + ["earnings_growth_pct"]


def _num_or_nan(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else float("nan")


def fundamentals_history(reports: dict) -> pd.DataFrame:
    """One row per (report date, ticker) of valuation fundamentals.

    The daily reports snapshot ``valuation`` per ticker, so walking the corpus
    yields the beneficiary time-series for free (the Scenario-Log trick).
    Entries without a valuation dict (benchmarks-only names, pre-valuation
    reports) are skipped; missing numerics become NaN so pandas medians just
    work. Ticker keys stay in raw watchlist form (``000660_KS``).
    """
    rows = []
    for date_str in sorted(reports):
        wl = (reports[date_str] or {}).get("watchlist") or {}
        for tk, entry in wl.items():
            val = (entry or {}).get("valuation") if isinstance(entry, dict) else None
            if not isinstance(val, dict):
                continue
            row = {"date": date_str, "ticker": tk,
                   "cluster": val.get("cluster_name") or ""}
            for f in _FUND_FIELDS:
                row[f] = _num_or_nan(val.get(f))
            consensus = val.get("analyst_consensus")
            eg = consensus.get("earnings_growth_pct") if isinstance(consensus, dict) else None
            row["earnings_growth_pct"] = _num_or_nan(eg)
            rows.append(row)
    return pd.DataFrame(rows, columns=_FUND_COLUMNS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat: beneficiary fundamentals time-series from report corpus (Capex Pulse task 3)"
```

---

### Task 4: Coverage gap series + current read

**Files:**
- Modify: `lib/capex.py` (append)
- Test: `tests/test_capex.py` (append)

**Interfaces:**
- Consumes: `parse_capex`, `core_capex_yoy`, `fundamentals_history` (Tasks 1–3).
- Produces:
  - `coverage_gap_series(capex: dict, fund_df: pd.DataFrame) -> list[dict]` — ascending `{"cq": str, "capex_yoy_pct": float, "rev_growth_pct": float, "gap_pp": float, "rev_asof": str}`; `gap_pp = rev_growth − capex_yoy` (positive = healthy).
  - `current_read(capex: dict, fund_df: pd.DataFrame) -> dict | None` — `{"capex_cq", "capex_yoy_pct", "rev_asof", "rev_growth_pct", "gap_pp"}`.
  - `_median_rev_growth(fund_df, beneficiaries, on_or_after=None) -> tuple[str, float] | None` (module-private; per spec: first report on/after the anchor date, falling back to the latest available).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_capex.py`)

```python
from lib.capex import coverage_gap_series, current_read


def _capex_with_yoy(rep_2026q1="2026-05-01"):
    """core=[MSFT,GOOG]; 2026Q1 complete with YoY (2025Q1 present)."""
    return parse_capex(_raw({
        "MSFT": [{"cq": "2025Q1", "reported": "2025-04-30", "capex_usd_b": 10.0},
                 {"cq": "2026Q1", "reported": rep_2026q1, "capex_usd_b": 15.0}],
        "GOOG": [{"cq": "2025Q1", "reported": "2025-04-24", "capex_usd_b": 10.0},
                 {"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 19.0}],
    }))


GAP_REPORTS = {
    "2026-04-15": _report({"NVDA": {"valuation": {"revenue_growth_pct": 90.0}},
                           "MU": {"valuation": {"revenue_growth_pct": 50.0}}}),
    "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                           "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
    "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 70.0}},
                           "MU": {"valuation": {"revenue_growth_pct": 30.0}}}),
}


def test_gap_anchors_revenue_at_first_report_after_quarter_complete():
    fund = fundamentals_history(GAP_REPORTS)
    gaps = coverage_gap_series(_capex_with_yoy(), fund)
    assert len(gaps) == 1
    g = gaps[0]
    # quarter complete 2026-05-01 (last core report) → first report on/after = 05-02
    assert g["rev_asof"] == "2026-05-02"
    assert g["rev_growth_pct"] == 60.0          # median(80, 40)
    assert g["capex_yoy_pct"] == 70.0
    assert g["gap_pp"] == -10.0                 # 60 − 70: capex outrunning revenue


def test_gap_falls_back_to_latest_report_when_none_after_anchor():
    fund = fundamentals_history(GAP_REPORTS)
    gaps = coverage_gap_series(_capex_with_yoy(rep_2026q1="2026-08-01"), fund)
    assert gaps[0]["rev_asof"] == "2026-07-01"  # latest available


def test_gap_empty_when_no_beneficiary_data():
    gaps = coverage_gap_series(_capex_with_yoy(), fundamentals_history({}))
    assert gaps == []


def test_current_read_uses_latest_report():
    fund = fundamentals_history(GAP_REPORTS)
    cr = current_read(_capex_with_yoy(), fund)
    assert cr["rev_asof"] == "2026-07-01"
    assert cr["rev_growth_pct"] == 50.0         # median(70, 30)
    assert cr["capex_cq"] == "2026Q1" and cr["gap_pp"] == -20.0


def test_current_read_none_without_yoy():
    capex = _two_spender_capex({"2026Q1": 15.0}, {"2026Q1": 19.0})  # no prior year
    assert current_read(capex, fundamentals_history(GAP_REPORTS)) is None
```

Note: `_raw()` in these fixtures sets `beneficiaries=["NVDA", "MU"]` (Task 1) — the gap math must read the file's beneficiaries list, not clusters.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 5 new failures (`ImportError: cannot import name 'coverage_gap_series'`).

- [ ] **Step 3: Write the implementation** (append to `lib/capex.py`)

```python
def _median_rev_growth(fund_df: pd.DataFrame, beneficiaries: list,
                       on_or_after: str | None = None):
    """(report_date_used, median revenue_growth_pct across *beneficiaries*).

    Per spec: the first report on/after *on_or_after* (ISO date strings compare
    lexicographically), falling back to the latest available report; None when
    there is no usable data. Median is per-ticker across the beneficiaries
    list — deliberately NOT a cluster median.
    """
    if fund_df.empty or not beneficiaries:
        return None
    df = fund_df[fund_df["ticker"].isin(beneficiaries)].dropna(
        subset=["revenue_growth_pct"])
    if df.empty:
        return None
    dates = sorted(df["date"].unique())
    use = None
    if on_or_after is not None:
        after = [d for d in dates if d >= on_or_after]
        use = after[0] if after else None
    if use is None:
        use = dates[-1]
    med = df[df["date"] == use]["revenue_growth_pct"].median()
    return use, float(med)


def coverage_gap_series(capex: dict, fund_df: pd.DataFrame) -> list[dict]:
    """The digestion signal: beneficiary revenue growth − core capex YoY, per
    quarter. Positive = revenue outrunning capex = healthy (ideas doc §4).

    Revenue is anchored at the first report on/after the date the quarter's
    LAST core spender reported (when the aggregate became knowable). Quarters
    whose anchor predates the report corpus all fall back to the earliest
    corpus dates — the revenue side is only as old as the corpus; the band's
    caption says so.
    """
    out = []
    for r in core_capex_yoy(capex):
        if r["yoy_pct"] is None:
            continue
        reported = [row["reported"] for tk in capex["core"]
                    for row in capex["series"].get(tk, []) if row["cq"] == r["cq"]]
        anchor = max(reported).isoformat() if reported else None
        med = _median_rev_growth(fund_df, capex["beneficiaries"], on_or_after=anchor)
        if med is None:
            continue
        rev_asof, rev = med
        out.append({"cq": r["cq"], "capex_yoy_pct": r["yoy_pct"],
                    "rev_growth_pct": round(rev, 1),
                    "gap_pp": round(rev - r["yoy_pct"], 1),
                    "rev_asof": rev_asof})
    return out


def current_read(capex: dict, fund_df: pd.DataFrame) -> dict | None:
    """Today's beneficiary median vs the latest complete capex quarter."""
    yoy_rows = [r for r in core_capex_yoy(capex) if r["yoy_pct"] is not None]
    med = _median_rev_growth(fund_df, capex["beneficiaries"])
    if not yoy_rows or med is None:
        return None
    latest = yoy_rows[-1]
    rev_asof, rev = med
    return {"capex_cq": latest["cq"], "capex_yoy_pct": latest["yoy_pct"],
            "rev_asof": rev_asof, "rev_growth_pct": round(rev, 1),
            "gap_pp": round(rev - latest["yoy_pct"], 1)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat: coverage-gap series + current read (Capex Pulse task 4)"
```

---

### Task 5: Scorecard chips

**Files:**
- Modify: `lib/capex.py` (append)
- Test: `tests/test_capex.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `build_chips(capex: dict, fund_df: pd.DataFrame, today: datetime.date) -> list[dict]` — always exactly 5 chips in order (keys `"capex"`, `"gap"`, `"rev"`, `"val"`, `"fragile"`), each `{"key": str, "label": str, "state": str, "detail": str, "asof": str}` with `state ∈ {"ok", "warn", "accel", "na"}`. Degraded inputs produce `"na"` chips with explicit copy — never missing chips, never an exception.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_capex.py`)

```python
from datetime import date as _date

from lib.capex import build_chips


def _chip(chips, key):
    return next(c for c in chips if c["key"] == key)


def _capex_three_yoy(y1, y2):
    """core=[MSFT,GOOG]; two YoY points: 2025Q4 (y1%) and 2026Q1 (y2%)."""
    def q(cq, rep, v):
        return {"cq": cq, "reported": rep, "capex_usd_b": v}
    base = 10.0
    return parse_capex(_raw({
        "MSFT": [q("2024Q4", "2025-01-29", base), q("2025Q1", "2025-04-30", base),
                 q("2025Q4", "2026-01-29", base * (1 + y1 / 100)),
                 q("2026Q1", "2026-04-29", base * (1 + y2 / 100))],
        "GOOG": [q("2024Q4", "2025-02-04", base), q("2025Q1", "2025-04-24", base),
                 q("2025Q4", "2026-02-03", base * (1 + y1 / 100)),
                 q("2026Q1", "2026-04-28", base * (1 + y2 / 100))],
    }))


def test_chips_always_five_in_order_even_on_empty_inputs():
    chips = build_chips(parse_capex({}), fundamentals_history({}), _date(2026, 7, 3))
    assert [c["key"] for c in chips] == ["capex", "gap", "rev", "val", "fragile"]
    assert all(c["state"] == "na" for c in chips)
    assert _chip(chips, "gap")["detail"] == "needs capex data"


def test_capex_chip_accelerating_at_threshold():
    chips = build_chips(_capex_three_yoy(50.0, 52.0), fundamentals_history({}),
                        _date(2026, 7, 3))
    assert _chip(chips, "capex")["state"] == "accel"       # +2.0pp = ACCEL_PP


def test_capex_chip_decelerating_warns():
    chips = build_chips(_capex_three_yoy(60.0, 40.0), fundamentals_history({}),
                        _date(2026, 7, 3))
    c = _chip(chips, "capex")
    assert c["state"] == "warn" and "decelerating" in c["detail"]


def test_gap_chip_warns_when_negative():
    fund = fundamentals_history(GAP_REPORTS)          # medians 60/50 range
    chips = build_chips(_capex_three_yoy(60.0, 70.0), fund, _date(2026, 7, 3))
    assert _chip(chips, "gap")["state"] == "warn"     # rev ~60 < capex 70


def test_rev_chip_falling_warns():
    reports = {
        "2026-04-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 90.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 60.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 70.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 30.0}}}),
    }
    chips = build_chips(parse_capex(_raw()), fundamentals_history(reports),
                        _date(2026, 7, 3))
    c = _chip(chips, "rev")
    assert c["state"] == "warn" and "falling" in c["detail"]


def test_valuation_chip_needs_five_reports():
    chips = build_chips(parse_capex(_raw()), fundamentals_history(SYNTH_REPORTS),
                        _date(2026, 7, 3))
    assert _chip(chips, "val")["state"] == "na"


def test_fragile_chip_surfaces_flag_and_note():
    capex = parse_capex(_raw({"CRWV": [
        {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 6.8,
         "flag": "amber", "note": "debt-funded ramp"},
    ]}))
    c = _chip(build_chips(capex, fundamentals_history({}), _date(2026, 7, 3)),
              "fragile")
    assert c["state"] == "warn"
    assert "CRWV" in c["detail"] and "amber" in c["detail"] and "debt-funded ramp" in c["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 7 new failures (`ImportError: cannot import name 'build_chips'`).

- [ ] **Step 3: Write the implementation** (append to `lib/capex.py`)

```python
def _capex_chip(capex: dict) -> dict:
    yoy = [r for r in core_capex_yoy(capex) if r["yoy_pct"] is not None]
    if len(yoy) < 2:
        pend = pending_quarter(capex)
        detail = (f"awaiting {len(pend['missing'])} of {len(capex['core'])} spenders for {pend['cq']}"
                  if pend else "needs two quarters of complete core capex")
        return {"key": "capex", "label": "Capex", "state": "na",
                "detail": detail, "asof": yoy[-1]["cq"] if yoy else "—"}
    cur, prev = yoy[-1], yoy[-2]
    delta = cur["yoy_pct"] - prev["yoy_pct"]
    if delta >= ACCEL_PP:
        state, word = "accel", "accelerating"
    elif delta <= -ACCEL_PP:
        state, word = "warn", "decelerating"
    else:
        state, word = "ok", "steady"
    return {"key": "capex", "label": "Capex", "state": state,
            "detail": (f"core YoY {cur['yoy_pct']:+.1f}% vs "
                       f"{prev['yoy_pct']:+.1f}% prior — {word}"),
            "asof": cur["cq"]}


def _gap_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    gaps = coverage_gap_series(capex, fund_df)
    if not gaps:
        return {"key": "gap", "label": "Coverage gap", "state": "na",
                "detail": "needs capex data", "asof": "—"}
    g = gaps[-1]
    widening = len(gaps) >= 2 and (g["gap_pp"] - gaps[-2]["gap_pp"]) <= -GAP_WIDEN_PP
    if g["gap_pp"] < 0:
        state, word = "warn", ("negative and widening" if widening
                               else "capex outrunning revenue")
    elif widening:
        state, word = "warn", "narrowing fast"
    else:
        state, word = "ok", "revenue keeping pace"
    return {"key": "gap", "label": "Coverage gap", "state": state,
            "detail": (f"{g['gap_pp']:+.1f}pp (rev {g['rev_growth_pct']:+.1f}% − "
                       f"capex {g['capex_yoy_pct']:+.1f}%) — {word}"),
            "asof": g["cq"]}


def _rev_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    now = _median_rev_growth(fund_df, capex["beneficiaries"])
    if now is None:
        return {"key": "rev", "label": "Beneficiary revenue", "state": "na",
                "detail": "no revenue-growth data in reports", "asof": "—"}
    now_date, now_med = now
    cutoff = (datetime.strptime(now_date, "%Y-%m-%d").date()
              - timedelta(days=REV_TREND_WINDOW_DAYS)).isoformat()
    bdf = fund_df[fund_df["ticker"].isin(capex["beneficiaries"])].dropna(
        subset=["revenue_growth_pct"])
    older = sorted(d for d in bdf["date"].unique() if d <= cutoff)
    if not older:
        return {"key": "rev", "label": "Beneficiary revenue", "state": "ok",
                "detail": (f"median {now_med:+.1f}% — corpus younger than "
                           f"{REV_TREND_WINDOW_DAYS}d, no trend yet"),
                "asof": now_date}
    ref_date = older[-1]
    ref_med = float(bdf[bdf["date"] == ref_date]["revenue_growth_pct"].median())
    delta = now_med - ref_med
    if delta >= REV_FLAT_PP:
        state, word = "ok", "rising"
    elif delta <= -REV_FLAT_PP:
        state, word = "warn", "falling"
    else:
        state, word = "ok", "flat"
    return {"key": "rev", "label": "Beneficiary revenue", "state": state,
            "detail": f"median {now_med:+.1f}% vs {ref_med:+.1f}% on {ref_date} — {word}",
            "asof": now_date}


def _val_chip(fund_df: pd.DataFrame) -> dict:
    sem = fund_df[fund_df["cluster"] == SEMIS_CLUSTER]
    pe = sem.dropna(subset=["forward_pe"]).groupby("date")["forward_pe"].median()
    if len(pe) < 5:
        return {"key": "val", "label": "Valuation", "state": "na",
                "detail": "needs ≥5 reports with Semis valuations", "asof": "—"}
    peg = sem.dropna(subset=["peg_ratio"]).groupby("date")["peg_ratio"].median()
    pe_now, pe_hot = float(pe.iloc[-1]), float(pe.quantile(VAL_WARN_QUANTILE))
    peg_now = float(peg.iloc[-1]) if len(peg) else float("nan")
    peg_hot = float(peg.quantile(VAL_WARN_QUANTILE)) if len(peg) else float("nan")
    rich = pe_now > pe_hot or (peg_now == peg_now and peg_hot == peg_hot
                               and peg_now > peg_hot)
    peg_s = f" · PEG {peg_now:.2f}" if peg_now == peg_now else ""
    return {"key": "val", "label": "Valuation",
            "state": "warn" if rich else "ok",
            "detail": (f"Semis median fwd PE {pe_now:.1f} "
                       f"(80th pct {pe_hot:.1f}){peg_s} — "
                       f"{'rich vs own history' if rich else 'within range'}"),
            "asof": str(pe.index[-1])}


def _fragile_chip(capex: dict) -> dict:
    frows = [(tk, capex["series"][tk][-1]) for tk in capex["fragile"]
             if capex["series"].get(tk)]
    if not frows:
        return {"key": "fragile", "label": "Fragile tier", "state": "na",
                "detail": "no fragile-tier rows", "asof": "—"}
    severity = {"red": 2, "amber": 1}
    tk, row = max(frows, key=lambda p: severity.get(p[1].get("flag", ""), 0))
    flag = row.get("flag") or "unflagged"
    note = f" — {row['note']}" if row.get("note") else ""
    return {"key": "fragile", "label": "Fragile tier",
            "state": "warn" if flag in severity else "ok",
            "detail": f"{tk} {row['cq']} capex ${row['capex_usd_b']:.1f}B · {flag}{note}",
            "asof": row["cq"]}


def build_chips(capex: dict, fund_df: pd.DataFrame, today: date) -> list[dict]:
    """The five scorecard chips (spec §2), always present and in order.

    Degraded inputs yield explicit 'na' copy — a chip never silently vanishes,
    and no chip renders from data we don't hold (hence no margins chip).
    ``today`` is unused by the chips themselves (staleness renders separately
    via ``curation_age_days``) but kept in the signature so the band has one
    clock to pass.
    """
    return [_capex_chip(capex), _gap_chip(capex, fund_df),
            _rev_chip(capex, fund_df), _val_chip(fund_df),
            _fragile_chip(capex)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capex.py -q`
Expected: 25 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat: five-chip digestion scorecard states (Capex Pulse task 5)"
```

---

### Task 6: Data-file loaders + cascade seed file

**Files:**
- Modify: `lib/data_loader.py` (append two loaders at the end)
- Create: `data/earnings_cascades.json`
- Test: `tests/test_data_loader.py` (append)

**Interfaces:**
- Consumes: existing `DATA_DIR`, `_mtime`, `_load_json_cached` in `lib/data_loader.py`.
- Produces:
  - `load_capex_quarterly() -> dict` — raw parsed JSON of `data/capex_quarterly.json`, `{}` when missing/malformed.
  - `load_earnings_cascades() -> dict` — same for `data/earnings_cascades.json`.
  - Cascade config shape (consumed by Task 7): `{reporter_ticker: {"aliases": list[str], "why": str, "bull": {"read": str, "tickers": list[str], "scenario_hint": str}, "bear": {...same...}}}` — affected tickers in raw watchlist form.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_data_loader.py`)

```python
# ── Capex Pulse loaders (hand-maintained data files) ──
def test_load_capex_quarterly_returns_seeded_dict():
    d = dl.load_capex_quarterly()
    assert d.get("core_spenders") == ["MSFT", "GOOG", "AMZN", "META"]
    assert "MSFT" in d.get("series", {})


def test_load_earnings_cascades_returns_seeded_dict():
    d = dl.load_earnings_cascades()
    assert "MU" in d
    assert d["MU"]["bull"]["read"]
    assert isinstance(d["MU"]["aliases"], list)


def test_capex_loaders_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    assert dl.load_capex_quarterly() == {}
    assert dl.load_earnings_cascades() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_data_loader.py -q`
Expected: 3 new failures (`AttributeError: module 'lib.data_loader' has no attribute 'load_capex_quarterly'`).

- [ ] **Step 3: Write the loaders** (append to `lib/data_loader.py`)

```python
def load_capex_quarterly() -> dict:
    """Hand-maintained quarterly capex file for the AI Capex Pulse band.

    ``{}`` when missing/malformed (band degrades, never crashes); validation
    and row-dropping live in ``lib.capex.parse_capex``, not here.
    """
    path = DATA_DIR / "capex_quarterly.json"
    if not path.exists():
        return {}
    return _load_json_cached(str(path), _mtime(path))


def load_earnings_cascades() -> dict:
    """Hand-maintained earnings-cascade config (pre-wired bull/bear reads)."""
    path = DATA_DIR / "earnings_cascades.json"
    if not path.exists():
        return {}
    return _load_json_cached(str(path), _mtime(path))
```

- [ ] **Step 4: Create the cascade seed file**

Create `data/earnings_cascades.json` (content grounded in `CAPEX_CYCLE_IDEAS.md` §6/§7; affected tickers in raw watchlist key form):

```json
{
  "MU": {
    "aliases": ["Micron", "MU"],
    "why": "MU + SK Hynix are the memory cycle; HBM ASPs proxy AI demand intensity.",
    "bull": {"read": "Beat + HBM guide raise confirms Layer-2 demand; reinforces the NVDA/AVGO datacenter thesis.",
             "tickers": ["000660_KS", "NVDA", "AVGO", "TSM"],
             "scenario_hint": "base/optimistic firm"},
    "bear": {"read": "Guide miss or softening HBM ASPs — earliest crack in the coverage gap; pressures the whole semis cluster.",
             "tickers": ["000660_KS", "NVDA", "AVGO", "TSM"],
             "scenario_hint": "pessimistic up"}
  },
  "NVDA": {
    "aliases": ["Nvidia", "NVDA"],
    "why": "The center of the capex loop: hyperscaler capex is NVDA revenue; its gross margin is the cycle's canary.",
    "bull": {"read": "Datacenter beat with gross margin held — spend is landing as sales; cycle intact.",
             "tickers": ["AMD", "AVGO", "TSM", "MU", "LITE"],
             "scenario_hint": "base holds"},
    "bear": {"read": "Datacenter deceleration or margin compression — demand air-pocket forming; hits the entire supply chain.",
             "tickers": ["AMD", "AVGO", "TSM", "MU", "000660_KS", "LITE", "CRWV"],
             "scenario_hint": "pessimistic up"}
  },
  "TSM": {
    "aliases": ["TSMC", "Taiwan Semiconductor", "TSM"],
    "why": "The physical bottleneck: CoWoS/advanced packaging capacity gates every accelerator roadmap.",
    "bull": {"read": "AI revenue guide up and capex raised — foundry sees sustained orders; confirms chip demand.",
             "tickers": ["NVDA", "AMD", "ASML", "AVGO"],
             "scenario_hint": "base/optimistic firm"},
    "bear": {"read": "Capex trimmed or AI order digestion flagged — the most credible early-cycle-top signal there is.",
             "tickers": ["NVDA", "AMD", "ASML", "AVGO"],
             "scenario_hint": "pessimistic up"}
  },
  "ASML": {
    "aliases": ["ASML"],
    "why": "Book-to-bill is the equipment-layer leading indicator for the whole foundry chain.",
    "bull": {"read": "Bookings beat — foundry expansion demand intact one layer upstream.",
             "tickers": ["TSM", "AIXA_DE"],
             "scenario_hint": "base holds"},
    "bear": {"read": "Bookings miss / push-outs — foundries hesitating on expansion; leads TSM capex cuts.",
             "tickers": ["TSM", "NVDA", "AIXA_DE"],
             "scenario_hint": "pessimistic up"}
  },
  "AVGO": {
    "aliases": ["Broadcom", "AVGO"],
    "why": "Custom-ASIC + networking read: the non-NVDA share of AI silicon spend.",
    "bull": {"read": "AI revenue guide raised — hyperscaler custom-silicon programs expanding; capex breadth confirmed.",
             "tickers": ["NVDA", "TSM", "LITE"],
             "scenario_hint": "base/optimistic firm"},
    "bear": {"read": "AI order push-outs — a hyperscaler trimming a program; first budget-cut evidence.",
             "tickers": ["NVDA", "TSM", "LITE"],
             "scenario_hint": "pessimistic up"}
  },
  "MSFT": {
    "aliases": ["Microsoft", "MSFT"],
    "why": "Largest self-funded spender; Azure growth is the demand its capex is spent against.",
    "bull": {"read": "Azure accelerates + capex guide held/raised — Layer-1 demand real, spend durable.",
             "tickers": ["NVDA", "AMD", "AVGO", "CRWV"],
             "scenario_hint": "base/optimistic firm"},
    "bear": {"read": "Azure decelerates while capex still climbs — the coverage gap widening at the source; watch depreciation commentary.",
             "tickers": ["NVDA", "AMD", "AVGO", "CRWV"],
             "scenario_hint": "pessimistic up"}
  },
  "GOOG": {
    "aliases": ["Google", "Alphabet", "GOOG"],
    "why": "Self-funded spender; GCP growth + capex guide are the demand-vs-spend read.",
    "bull": {"read": "GCP growth holds with capex guide intact — cloud demand supporting the spend.",
             "tickers": ["NVDA", "AVGO", "TSM"],
             "scenario_hint": "base holds"},
    "bear": {"read": "Capex guide raised again while cloud growth slows — spend outrunning demand.",
             "tickers": ["NVDA", "AVGO"],
             "scenario_hint": "pessimistic up"}
  },
  "AMZN": {
    "aliases": ["Amazon", "AMZN"],
    "why": "Largest 2026 spender ($200B guide); its thesis-break condition is capex-shaped (delay/cancel).",
    "bull": {"read": "AWS reaccelerates + capex on track — the biggest budget confirmed.",
             "tickers": ["NVDA", "AVGO", "MU"],
             "scenario_hint": "base/optimistic firm"},
    "bear": {"read": "AI capex plan delayed or trimmed — AMZN's own thesis-break condition; systemic demand signal.",
             "tickers": ["NVDA", "AVGO", "MU", "CRWV"],
             "scenario_hint": "pessimistic up"}
  },
  "CRWV": {
    "aliases": ["CoreWeave", "CRWV"],
    "why": "The fragile debt-funded tier and circular-financing node (NVDA investee & customer) — first place stress shows.",
    "bull": {"read": "Backlog grows with financing costs contained — fragile tier still funding the ramp.",
             "tickers": ["NVDA"],
             "scenario_hint": "base holds"},
    "bear": {"read": "Guide cut, financing strain, or covenant noise — the late-cycle tell firing; de-risk the fragile tier first.",
             "tickers": ["NVDA", "MU"],
             "scenario_hint": "pessimistic up, wildcard watch"}
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_loader.py tests/test_capex.py -q`
Expected: all pass (3 new + existing).

- [ ] **Step 6: Commit**

```bash
git add lib/data_loader.py data/earnings_cascades.json tests/test_data_loader.py
git commit -m "feat: capex + cascade file loaders, seeded cascade config (Capex Pulse task 6)"
```

---

### Task 7: Cascade annotations in the Week-Ahead calendar (+ spec amendment)

**Files:**
- Modify: `components/briefing/calendar.py`
- Modify: `docs/superpowers/specs/2026-07-03-capex-pulse-design.md` (two sentences — see Step 5)
- Create: `tests/test_cascades.py`

**Interfaces:**
- Consumes: cascade config shape from Task 6; existing `calendar_card_html(events, lane)` and `_group_html(group, muted)`.
- Produces:
  - `calendar_card_html(events: list, lane: str = "ledger", cascades: dict | None = None) -> str` — same output as today when `cascades` is None/empty (backward compatible; existing callers unchanged until Task 9).
  - `_cascade_block_html(event_text: str, cascades: dict | None) -> str` (module-private) — bull/bear read block for an earnings event, `""` when unmatched.

**Matching rule (spec-divergence note):** the spec said cascades join `scheduled_tech_events`; in the real data, earnings dates live in `events_this_week` as free text like `"TSMC Earnings"` with no ticker field (`scheduled_tech_events` currently carries only one non-earnings entry). So the join is: event text contains the word "earnings" (case-insensitive) AND a whole-word, case-insensitive match of any curated alias. Step 5 amends the spec to record this.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cascades.py`:

```python
"""Tests for the earnings-cascade annotations in the Week-Ahead calendar."""
from components.briefing.calendar import _cascade_block_html, calendar_card_html

CASCADES = {
    "TSM": {
        "aliases": ["TSMC", "Taiwan Semiconductor", "TSM"],
        "why": "The physical bottleneck.",
        "bull": {"read": "AI revenue guide up.", "tickers": ["NVDA", "000660_KS"],
                 "scenario_hint": "base holds"},
        "bear": {"read": "Capex trimmed — cycle-top signal.", "tickers": ["NVDA"],
                 "scenario_hint": "pessimistic up"},
    },
    "MU": {"aliases": ["Micron", "MU"], "why": "Memory cycle.",
           "bull": {"read": "HBM guide raise.", "tickers": []},
           "bear": {"read": "HBM ASPs soften.", "tickers": []}},
}


def test_cascade_matches_alias_in_earnings_event():
    html = _cascade_block_html("TSMC Earnings", CASCADES)
    assert "AI revenue guide up." in html
    assert "Capex trimmed — cycle-top signal." in html
    assert "BULL" in html and "BEAR" in html
    assert "000660.KS" in html          # raw key displayed via display_ticker
    assert "The physical bottleneck." in html


def test_cascade_requires_earnings_word():
    assert _cascade_block_html("TSMC Technology Symposium", CASCADES) == ""


def test_cascade_alias_is_whole_word():
    # 'MU' must not fire inside an unrelated word
    assert _cascade_block_html("Amusement Earnings", CASCADES) == ""


def test_cascade_unmatched_or_empty_config():
    assert _cascade_block_html("Nokia Earnings", CASCADES) == ""
    assert _cascade_block_html("TSMC Earnings", None) == ""
    assert _cascade_block_html("TSMC Earnings", {}) == ""


def test_calendar_card_renders_cascade_for_matching_event():
    events = [{"date": "2026-07-16", "event": "TSMC Earnings", "impact": "MEDIUM",
               "type": "forward_catalyst"}]
    html = calendar_card_html(events, lane="strip", cascades=CASCADES)
    assert "AI revenue guide up." in html


def test_calendar_card_unchanged_without_cascades():
    events = [{"date": "2026-07-16", "event": "TSMC Earnings", "impact": "MEDIUM"}]
    assert calendar_card_html(events) == calendar_card_html(events, cascades=None)
    assert "BULL" not in calendar_card_html(events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cascades.py -q`
Expected: FAIL with `ImportError: cannot import name '_cascade_block_html'`.

- [ ] **Step 3: Implement in `components/briefing/calendar.py`**

Add imports at the top (after the existing ones):

```python
import re

from lib.charts import STATUS_NEG, STATUS_POS
from lib.formatters import display_ticker
```

Add the helper (below `_timing_line_html`):

```python
def _cascade_block_html(event_text: str, cascades: dict | None) -> str:
    """Pre-wired bull/bear reads for an earnings event ('' when unmatched).

    Match rule: the event text mentions earnings AND a whole-word,
    case-insensitive hit on a curated alias. Matching is alias-based because
    ``events_this_week`` entries are free text ("TSMC Earnings") with no ticker
    field — the aliases are part of the hand-maintained cascade config.
    """
    text = event_text or ""
    if not cascades or "earning" not in text.lower():
        return ""
    for cfg in cascades.values():
        cfg = cfg or {}
        aliases = cfg.get("aliases") or []
        if not any(re.search(rf"\b{re.escape(a)}\b", text, re.IGNORECASE)
                   for a in aliases):
            continue
        rows = ""
        for side, color, mark in (("bull", STATUS_POS, "▲"),
                                  ("bear", STATUS_NEG, "▼")):
            d = cfg.get(side) or {}
            if not d.get("read"):
                continue
            chips = "".join(
                f'<span style="font-family:var(--mono);font-size:9px;'
                f'background:var(--surface-2,{SURFACE_2_FALLBACK});'
                f'border-radius:3px;padding:1px 4px;margin-left:3px;'
                f'color:var(--ink-2);">{_escape_dollars(display_ticker(t))}</span>'
                for t in (d.get("tickers") or [])[:6]
            )
            hint = f' · {d["scenario_hint"]}' if d.get("scenario_hint") else ""
            rows += (
                f'<div style="margin-top:3px;padding-left:8px;'
                f'border-left:2px solid {color};font-size:11px;'
                f'color:var(--ink-3);line-height:1.45;">'
                f'<span style="color:{color};font-family:var(--mono);">'
                f'{mark} {side.upper()}</span> {_escape_dollars(d["read"])}'
                f'{_escape_dollars(hint)}{chips}</div>'
            )
        if not rows:
            return ""
        why = cfg.get("why") or ""
        why_html = (f'<div style="margin-top:3px;font-size:10.5px;'
                    f'color:var(--ink-3);font-style:italic;">'
                    f'{_escape_dollars(why)}</div>') if why else ""
        return f'<div style="margin-top:4px;">{why_html}{rows}</div>'
    return ""
```

Thread `cascades` through. Change `_group_html`'s signature and the `text_html` assembly:

```python
def _group_html(group: list, muted: bool = False, cascades: dict | None = None) -> str:
```

and inside it (the existing comment about `.cal-text` stays; the cascade block joins the bucket pill + timing line INSIDE the 1fr text column):

```python
            text_html = (
                f'{_escape_dollars(e.get("event", ""))}'
                f'{_bucket_pill_html(e)}'
                f'{_timing_line_html(e)}'
                f'{_cascade_block_html(e.get("event", ""), cascades)}'
            )
```

Change `calendar_card_html`'s signature and its two `_group_html` calls:

```python
def calendar_card_html(events: list, lane: str = "ledger",
                       cascades: dict | None = None) -> str:
```

```python
    body = _group_html(this_week, cascades=cascades)
```

```python
        body += _group_html(forward, muted=True, cascades=cascades)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cascades.py -q` → 6 passed.
Then: `python -m pytest -q` → everything else still green.

- [ ] **Step 5: Amend the spec to record the join-surface divergence**

In `docs/superpowers/specs/2026-07-03-capex-pulse-design.md`, make exactly two edits:

1. Replace the sentence
   `- Joined to `scheduled_tech_events` earnings entries by reporter ticker at render time. Entries with no cascade config render exactly as today.`
   with
   `- Joined to the Week-Ahead calendar's ``events_this_week`` entries at render time: an entry matches when its free text mentions earnings and hits a curated whole-word alias (the entries carry no ticker field; ``scheduled_tech_events`` turned out to hold no earnings entries). Unmatched entries render exactly as today.`
2. Replace the sentence
   `- **Cascades get no new surface**: `components/briefing/earnings.py` renders the bull/bear reads and affected-ticker chips on earnings entries that match the cascade config.`
   with
   `- **Cascades get no new surface**: `components/briefing/calendar.py` renders the bull/bear reads and affected-ticker chips under Week-Ahead earnings entries that match the cascade config.`

- [ ] **Step 6: Commit**

```bash
git add components/briefing/calendar.py tests/test_cascades.py docs/superpowers/specs/2026-07-03-capex-pulse-design.md
git commit -m "feat: pre-wired earnings-cascade reads on Week-Ahead entries (Capex Pulse task 7)"
```

---

### Task 8: The AI Capex Pulse band component

**Files:**
- Create: `components/briefing/capex_pulse.py`
- Create: `tests/test_capex_pulse.py`

**Interfaces:**
- Consumes: everything public from `lib.capex` (Tasks 1–5), `load_capex_quarterly` (Task 6), `load_all_reports`/`data_fingerprint` (existing), `lib.cards.render_section_head`, `lib.charts` constants + `style_fig`/`chart_data_table`/`PLOTLY_CONFIG`, `lib.formatters._escape_dollars`.
- Produces:
  - `render_capex_pulse() -> None` — the full band (chips → current-read caption → gap chart → trends expander). Renders nothing only when BOTH the capex file and the corpus are empty.
  - Testable helpers: `_chips_html(chips: list, overdue_days: int | None) -> str`, `_gap_chart_frame(gap_rows: list) -> pd.DataFrame` (columns `["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"]`), `_cluster_medians(fund_df, metric: str) -> pd.DataFrame` (dates × clusters pivot of medians).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_capex_pulse.py`:

```python
"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd

from components.briefing.capex_pulse import (_chips_html, _cluster_medians,
                                             _gap_chart_frame)
from lib.capex import CURATION_OVERDUE_DAYS


CHIPS = [
    {"key": "capex", "label": "Capex", "state": "accel",
     "detail": "core YoY +68.9% vs +53.5% prior — accelerating", "asof": "2026Q1"},
    {"key": "gap", "label": "Coverage gap", "state": "warn",
     "detail": "-10.0pp — capex outrunning revenue & <script>", "asof": "2026Q1"},
    {"key": "val", "label": "Valuation", "state": "na",
     "detail": "needs ≥5 reports", "asof": "—"},
]


def test_chips_html_renders_labels_states_and_asof():
    html = _chips_html(CHIPS, overdue_days=30)
    assert "Capex" in html and "2026Q1" in html
    assert "▲" in html and "⚠" in html and "—" in html
    assert "CURATION OVERDUE" not in html          # 30d is fresh


def test_chips_html_escapes_detail_text():
    html = _chips_html(CHIPS, overdue_days=None)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_chips_html_overdue_banner_past_threshold():
    html = _chips_html(CHIPS, overdue_days=CURATION_OVERDUE_DAYS + 1)
    assert "CURATION OVERDUE" in html and "capex_quarterly.json" in html


def test_gap_chart_frame_columns():
    df = _gap_chart_frame([{"cq": "2026Q1", "capex_yoy_pct": 68.9,
                            "rev_growth_pct": 58.9, "gap_pp": -10.0,
                            "rev_asof": "2026-05-02"}])
    assert list(df.columns) == ["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"]
    assert df.iloc[0]["quarter"] == "2026Q1"


def test_cluster_medians_pivots_by_cluster():
    fund = pd.DataFrame([
        {"date": "2026-06-01", "ticker": "NVDA", "cluster": "Semis",
         "revenue_growth_pct": 80.0},
        {"date": "2026-06-01", "ticker": "MU", "cluster": "Semis",
         "revenue_growth_pct": 40.0},
        {"date": "2026-06-01", "ticker": "D05_SI", "cluster": "SG Banks",
         "revenue_growth_pct": 5.0},
        {"date": "2026-06-01", "ticker": "X", "cluster": "",
         "revenue_growth_pct": 1.0},
    ])
    piv = _cluster_medians(fund, "revenue_growth_pct")
    assert piv.loc["2026-06-01", "Semis"] == 60.0
    assert piv.loc["2026-06-01", "SG Banks"] == 5.0
    assert "" not in piv.columns                    # unclustered rows excluded


def test_cluster_medians_empty_metric():
    piv = _cluster_medians(pd.DataFrame(columns=["date", "cluster", "forward_pe"]),
                           "forward_pe")
    assert piv.empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex_pulse.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'components.briefing.capex_pulse'`.

- [ ] **Step 3: Write the component**

Create `components/briefing/capex_pulse.py`:

```python
"""Briefing · AI Capex Pulse band.

Human-read digestion scorecard for the capex cycle (spec
docs/superpowers/specs/2026-07-03-capex-pulse-design.md): five chips, the
coverage-gap chart, and cluster-fundamentals trends behind an expander. By
design a cross-check the reader eyeballs against the scenario odds — nothing
here feeds the odds mechanically.
"""
from __future__ import annotations

from datetime import date as _date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.capex import (CURATION_OVERDUE_DAYS, build_chips, coverage_gap_series,
                       curation_age_days, current_read, fundamentals_history,
                       parse_capex)
from lib.cards import render_section_head
from lib.charts import (CHART_ACCENT, CHART_MUTED, CHART_PALETTE, INK_FALLBACK,
                        PLOTLY_CONFIG, STATUS_NEG, STATUS_POS, STATUS_WARN,
                        chart_data_table, style_fig)
from lib.data_loader import data_fingerprint, load_all_reports, load_capex_quarterly
from lib.formatters import _escape_dollars

_STATE_GLYPH = {"ok": "✅", "warn": "⚠", "accel": "▲", "na": "—"}
_STATE_COLOR = {"ok": STATUS_POS, "warn": STATUS_WARN, "accel": CHART_ACCENT,
                "na": INK_FALLBACK}

_TREND_METRICS = [("revenue_growth_pct", "Revenue growth %"),
                  ("earnings_growth_pct", "Earnings growth %"),
                  ("fcf_yield_pct", "FCF yield %"),
                  ("forward_pe", "Forward P/E")]


@st.cache_data(show_spinner=False, max_entries=2)
def _fundamentals_cached(cache_key: tuple, _reports: dict) -> pd.DataFrame:
    """Corpus-derived fundamentals frame, memoized on the cheap fingerprint.

    Same contract as the Signal-Tracker derives (review P7-2): ``cache_key`` is
    ``data_fingerprint()``; the heavy corpus is ``_``-prefixed so it is never
    hashed.
    """
    return fundamentals_history(_reports)


def _chips_html(chips: list, overdue_days: int | None) -> str:
    """Chip-row scorecard + optional curation-overdue banner, as one HTML string."""
    overdue = ""
    if overdue_days is not None and overdue_days > CURATION_OVERDUE_DAYS:
        overdue = (
            f'<div style="margin:0 0 8px;font-family:var(--mono);font-size:11px;'
            f'color:{STATUS_WARN};">⚠ CURATION OVERDUE — newest core capex row '
            f'is {overdue_days}d old; a newer quarter has likely been reported. '
            f'Update data/capex_quarterly.json.</div>'
        )
    cells = ""
    for c in chips:
        color = _STATE_COLOR.get(c["state"], INK_FALLBACK)
        cells += (
            f'<div style="flex:1 1 170px;min-width:160px;padding:8px 10px;'
            f'border:1px solid var(--rule);border-left:3px solid {color};">'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.08em;text-transform:uppercase;color:var(--ink-3);">'
            f'{_escape_dollars(c["label"])} · {_escape_dollars(c["asof"])}</div>'
            f'<div style="margin-top:3px;font-size:12.5px;color:var(--ink-2);'
            f'line-height:1.45;">'
            f'<span style="color:{color};font-weight:600;">'
            f'{_STATE_GLYPH.get(c["state"], "—")}</span> '
            f'{_escape_dollars(c["detail"])}</div></div>'
        )
    return f'{overdue}<div style="display:flex;flex-wrap:wrap;gap:8px;">{cells}</div>'


def _gap_chart_frame(gap_rows: list) -> pd.DataFrame:
    """The exact frame behind the gap chart (also the a11y table)."""
    return pd.DataFrame(
        [{"quarter": g["cq"], "capex_yoy_pct": g["capex_yoy_pct"],
          "rev_growth_pct": g["rev_growth_pct"], "gap_pp": g["gap_pp"]}
         for g in gap_rows],
        columns=["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"])


def _gap_fig(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_bar(x=df["quarter"], y=df["gap_pp"], name="Coverage gap (pp)",
                marker_color=[STATUS_POS if v >= 0 else STATUS_NEG
                              for v in df["gap_pp"]])
    fig.add_scatter(x=df["quarter"], y=df["capex_yoy_pct"],
                    name="Core capex YoY %", mode="lines+markers",
                    line=dict(color=CHART_MUTED))
    fig.add_scatter(x=df["quarter"], y=df["rev_growth_pct"],
                    name="Beneficiary revenue growth %", mode="lines+markers",
                    line=dict(color=CHART_ACCENT))
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_fig(fig)


def _cluster_medians(fund_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """dates × clusters pivot of per-cluster medians for *metric*."""
    if fund_df.empty:
        return pd.DataFrame()
    df = fund_df[fund_df["cluster"] != ""].dropna(subset=[metric])
    if df.empty:
        return pd.DataFrame()
    return df.groupby(["date", "cluster"])[metric].median().unstack("cluster")


def _trend_fig(pivot: pd.DataFrame):
    fig = go.Figure()
    for i, cluster in enumerate(pivot.columns):
        fig.add_scatter(x=list(pivot.index), y=pivot[cluster], mode="lines",
                        name=str(cluster),
                        line=dict(color=CHART_PALETTE[i % len(CHART_PALETTE)],
                                  width=1.6))
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_fig(fig)


def render_capex_pulse() -> None:
    """The AI Capex Pulse band (Briefing). Degrades chip-by-chip, never crashes."""
    capex = parse_capex(load_capex_quarterly())
    fund_df = _fundamentals_cached(data_fingerprint(), load_all_reports())
    if not capex["series"] and fund_df.empty:
        return
    today = _date.today()
    render_section_head(
        "AI Capex Pulse",
        "Digestion scorecard — human-read cross-check, not a wired signal")
    for w in capex["warnings"]:
        st.caption(f"⚠ capex file: {w}")
    st.markdown(_chips_html(build_chips(capex, fund_df, today),
                            curation_age_days(capex, today)),
                unsafe_allow_html=True)
    cr = current_read(capex, fund_df)
    if cr:
        st.caption(
            f"Current read: beneficiary revenue {cr['rev_growth_pct']:+.1f}% "
            f"({cr['rev_asof']}) vs core capex {cr['capex_yoy_pct']:+.1f}% YoY "
            f"({cr['capex_cq']}) → gap {cr['gap_pp']:+.1f}pp. The revenue side "
            f"is only as old as the report corpus.")
    gaps = coverage_gap_series(capex, fund_df)
    if gaps:
        df = _gap_chart_frame(gaps)
        st.plotly_chart(_gap_fig(df), use_container_width=True,
                        config=PLOTLY_CONFIG)
        chart_data_table(df)
    if not fund_df.empty:
        with st.expander("Cluster fundamentals over time"):
            for metric, label in _TREND_METRICS:
                pivot = _cluster_medians(fund_df, metric)
                if pivot.empty:
                    continue
                st.markdown(
                    f'<div style="font-family:var(--mono);font-size:10px;'
                    f'letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:var(--ink-3);margin:8px 0 2px;">{label}</div>',
                    unsafe_allow_html=True)
                st.plotly_chart(_trend_fig(pivot), use_container_width=True,
                                config=PLOTLY_CONFIG)
                chart_data_table(pivot.reset_index())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capex_pulse.py -q` → 6 passed.
Then: `python -m pytest -q` → full suite green.

- [ ] **Step 5: Commit**

```bash
git add components/briefing/capex_pulse.py tests/test_capex_pulse.py
git commit -m "feat: AI Capex Pulse band — chips, gap chart, cluster trends (Capex Pulse task 8)"
```

---

### Task 9: Wire into the Briefing + AppTest coverage

**Files:**
- Modify: `components/briefing/__init__.py`
- Modify: `dashboard.py` (three small edits)
- Test: `tests/test_app_pages.py` (append)

**Interfaces:**
- Consumes: `render_capex_pulse` (Task 8), `load_earnings_cascades` (Task 6), `calendar_card_html(..., cascades=...)` (Task 7).
- Produces: the band live on the Briefing between the Earnings Scorecard block and the Context band; cascades under Week-Ahead earnings entries.

- [ ] **Step 1: Write the failing test** (append to `tests/test_app_pages.py`)

```python
def test_briefing_renders_capex_pulse_band():
    at = _boot()
    assert not at.exception
    assert any("AI Capex Pulse" in str(m.value) for m in at.markdown)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_pages.py::test_briefing_renders_capex_pulse_band -q`
Expected: FAIL on the `any(...)` assertion (band not rendered yet).

- [ ] **Step 3: Wire it up**

In `components/briefing/__init__.py`: add the import and `__all__` entry (alphabetical position after `render_calibration`):

```python
from components.briefing.capex_pulse import render_capex_pulse
```

```python
    "render_capex_pulse",
```

In `dashboard.py`:

1. Add `render_capex_pulse` to the `from components.briefing import (...)` block (after `render_calibration,`).
2. Add `load_earnings_cascades` to the `from lib.data_loader import (...)` block (after `list_report_dates,`).
3. In `_render_briefing_body()`, insert the band call after `render_contrarian_candidates(contrarians)`:

```python
        render_contrarian_candidates(contrarians)
        render_capex_pulse()
```

4. Pass cascades into the calendar card (the Context band composition):

```python
            + calendar_card_html(events, lane="strip",
                                 cascades=load_earnings_cascades())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_pages.py -q` → all pass (the AppTest walk also re-proves no page crashes).
Then: `python -m pytest -q` → full suite green.

- [ ] **Step 5: Eyeball the real thing**

Run: `streamlit run dashboard.py` (or use the project's run skill if executing interactively) and confirm on the Briefing: the five chips render with real states, the gap chart shows the seeded quarters, the trends expander opens, and a Week-Ahead earnings entry (e.g. "TSMC Earnings" on Jul 16) carries its bull/bear block. Stop the server after checking.

- [ ] **Step 6: Commit**

```bash
git add components/briefing/__init__.py dashboard.py tests/test_app_pages.py
git commit -m "feat: wire Capex Pulse band + cascades into the Briefing (Capex Pulse task 9)"
```

---

## Post-plan notes for the reviewer

- **Provisional seed rows:** MSFT/GOOG/AMZN 2025Q4 capex are estimates pending IR verification (Task 1 Step 6); their `note` fields say so in-file. The 2026Q1 row of every name and both CRWV rows are web-verified (2026-07-03).
- **Known modeling caveat (accepted in spec):** gap points for quarters whose reporting date predates the report corpus (starts 2026-03-12) anchor their revenue side at the earliest corpus dates; the band caption discloses this. The chart becomes fully honest as the corpus accumulates quarters.
- **Curation workflow** (spec §"Curation workflow"): ~4×/yr add one row per spender to `data/capex_quarterly.json`; refresh CRWV `flag`/`note`; revisit cascade reads before major reports. The CURATION OVERDUE banner fires past 110 days.
