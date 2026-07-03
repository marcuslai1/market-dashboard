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
