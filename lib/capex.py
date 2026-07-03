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
