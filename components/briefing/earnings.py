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


def _display_ticker(tk: str) -> str:
    """Human display form of a watchlist key, e.g. ``000660_KS`` -> ``000660.KS``.

    ``TICKER_DISPLAY`` is a *sparse* override map — it only lists tickers whose
    display needs special glyphs (``CL_F`` -> ``CL=F``, ``VIX`` -> ``^VIX``). It
    does **not** carry the plain underscore-for-dot names (``000660_KS``), so the
    codebase-wide ``TICKER_DISPLAY.get(tk, tk)`` leaks the munged key into the UI
    for those. Prefer the override, then fall back to restoring the dot — giving
    the clean dotted ticker the cluster band already shows.
    """
    return TICKER_DISPLAY.get(tk) or str(tk).replace("_", ".")


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
            "ticker": _display_ticker(tk),
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
