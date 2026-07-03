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
