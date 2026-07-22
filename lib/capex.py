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

# Vocabulary banned from every chip `remark` (spec §2 rule 1). The remark column
# is the one place the band speaks plain English; these terms assume a
# vocabulary the reader has told us they do not have. Enforced by
# tests/test_capex.py::test_no_remark_uses_banned_vocabulary.
_BANNED_REMARK_TERMS = (r"\bPEG\b", r"\bpp\b", r"\bpct\b", r"\bpercentile\b",
                        r"\bcircularity\b", r"\bfragile tier\b", r"\bbeneficiar")

_CAPEX_REMARK = {"accelerating": "Up from {prev:+.1f}% — still building",
                 "decelerating": "Down from {prev:+.1f}% — easing off",
                 "steady": "Holding near {prev:+.1f}%"}

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
_FUND_COLUMNS = ["date", "ticker", "cluster", *_FUND_FIELDS, "earnings_growth_pct"]


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


def forward_revenue_note(capex: dict, fund_df: pd.DataFrame) -> dict | None:
    """Where beneficiary revenue has moved SINCE the quarter's anchored figure —
    a forward hint, not a gap.

    The coverage gap anchors revenue to the date the quarter's capex was reported.
    This reports the latest beneficiary median relative to that anchor, so the
    band can say "revenue has since risen/fallen — next gap may narrow/widen"
    without subtracting today's revenue from a quarter-old capex number (which is
    what produced the old, contradictory second gap). ``None`` when there is no
    fresher report or the move is within ``±REV_FLAT_PP``.
    """
    gaps = coverage_gap_series(capex, fund_df)
    if not gaps:
        return None
    anchor_pct = gaps[-1]["rev_growth_pct"]
    anchor_date = gaps[-1]["rev_asof"]
    live = _median_rev_growth(fund_df, capex["beneficiaries"])
    if live is None:
        return None
    now_date, now_med = live
    if now_date <= anchor_date:
        return None
    now_med = round(now_med, 1)
    delta = now_med - anchor_pct
    if delta >= REV_FLAT_PP:
        direction, hint = "risen", "narrow"
    elif delta <= -REV_FLAT_PP:
        direction, hint = "fallen", "widen"
    else:
        return None
    return {"now_pct": now_med, "now_asof": now_date,
            "direction": direction, "hint": hint}


def _capex_chip(capex: dict) -> dict:
    names = "/".join(capex["core"]) or "core-spender"
    sub = f"combined {names} capex, year-over-year"
    yoy = [r for r in core_capex_yoy(capex) if r["yoy_pct"] is not None]
    if len(yoy) < 2:
        pend = pending_quarter(capex)
        awaiting = (f"awaiting {len(pend['missing'])} of {len(capex['core'])} "
                    f"spenders for {pend['cq']}" if pend else "")
        if yoy:
            # Exactly one comparable quarter. The growth figure EXISTS — the
            # coverage-gap row quotes it — so this row must print it. What is
            # missing is an *earlier* quarter to compare it against, which is a
            # different statement from "cannot be computed". Saying the latter
            # made row 01 deny the number row 03 was quoting (spec §2 rule 4).
            cur = yoy[-1]
            return {"key": "capex", "label": "Capex", "sub": sub,
                    "measure": "Capex growth",
                    "value": f"{cur['yoy_pct']:+.1f}%",
                    "remark": (f"{cur['cq']} only — no earlier quarter yet to "
                               f"say if this is speeding up or slowing"),
                    "tone": "neutral", "arrow": "none",
                    "detail": (f"core YoY {cur['yoy_pct']:+.1f}% for {cur['cq']} "
                               f"— one comparable quarter only"
                               + (f"; {awaiting}" if awaiting else "")),
                    "asof": cur["cq"]}
        return {"key": "capex", "label": "Capex", "sub": sub,
                "measure": "Capex growth", "value": "—",
                "remark": (f"Waiting on {len(pend['missing'])} of "
                           f"{len(capex['core'])} big spenders to report {pend['cq']}"
                           if pend else
                           "Needs two full quarters before it can be compared"),
                "tone": "na", "arrow": "none",
                "detail": awaiting or "needs two quarters of complete core capex",
                "asof": "—"}
    cur, prev = yoy[-1], yoy[-2]
    delta = cur["yoy_pct"] - prev["yoy_pct"]
    if delta >= ACCEL_PP:
        arrow, word = "up", "accelerating"
    elif delta <= -ACCEL_PP:
        arrow, word = "down", "decelerating"
    else:
        arrow, word = "none", "steady"
    return {"key": "capex", "label": "Capex", "sub": sub,
            "measure": "Capex growth",
            "value": f"{cur['yoy_pct']:+.1f}%",
            "remark": _CAPEX_REMARK[word].format(prev=prev["yoy_pct"]),
            "tone": "neutral", "arrow": arrow,
            "detail": (f"core YoY {cur['yoy_pct']:+.1f}% vs "
                       f"{prev['yoy_pct']:+.1f}% prior — {word}"),
            "asof": cur["cq"]}


def _gap_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    sub = ("beneficiary revenue growth minus capex growth — "
           "negative = spend outrunning sales")
    gaps = coverage_gap_series(capex, fund_df)
    if not gaps:
        return {"key": "gap", "label": "Coverage gap", "sub": sub,
                "measure": "Coverage gap", "value": "—",
                "remark": "Needs at least one complete spending quarter",
                "tone": "na", "arrow": "none", "detail": "needs capex data",
                "asof": "—"}
    g = gaps[-1]
    widening = len(gaps) >= 2 and (g["gap_pp"] - gaps[-2]["gap_pp"]) <= -GAP_WIDEN_PP
    if g["gap_pp"] < 0:
        tone = "watch"
        word = "negative and widening" if widening else "capex outrunning revenue"
    elif widening:
        tone, word = "watch", "narrowing fast"
    else:
        tone, word = "good", "revenue keeping pace"
    # The reconciliation (spec §2 rule 4). The gap is anchored to the last
    # complete quarter, so its sales figure is older than the sales row's. Say
    # that in the same row as the number, at full text weight — the 2026-07-03
    # pass put this in an --ink-3 footnote and the reader never reached it.
    remark = (f"{g['cq']} only: spending grew {g['capex_yoy_pct']:+.1f}% "
              f"against sales {g['rev_growth_pct']:+.1f}%.")
    note = forward_revenue_note(capex, fund_df)
    if note is not None:
        remark += (f" Sales have since reached {note['now_pct']:+.1f}%, "
                   f"so the next reading should {note['hint']}.")
    return {"key": "gap", "label": "Coverage gap", "sub": sub,
            "measure": f"Coverage gap ({g['cq']})",
            "value": f"{g['gap_pp']:+.1f}pp",
            "remark": remark,
            "tone": tone, "arrow": "none",
            "detail": (f"{g['gap_pp']:+.1f}pp (rev {g['rev_growth_pct']:+.1f}% − "
                       f"capex {g['capex_yoy_pct']:+.1f}%) — {word}"),
            "asof": g["cq"]}


def _rev_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    sub = "median sales growth of the chip names that sell into that capex"
    now = _median_rev_growth(fund_df, capex["beneficiaries"])
    if now is None:
        return {"key": "rev", "label": "Beneficiary revenue", "sub": sub,
                "measure": "Customer sales", "value": "—",
                "remark": "No sales-growth figures in the reports yet",
                "tone": "na", "arrow": "none",
                "detail": "no revenue-growth data in reports", "asof": "—"}
    now_date, now_med = now
    cutoff = (datetime.strptime(now_date, "%Y-%m-%d").date()
              - timedelta(days=REV_TREND_WINDOW_DAYS)).isoformat()
    bdf = fund_df[fund_df["ticker"].isin(capex["beneficiaries"])].dropna(
        subset=["revenue_growth_pct"])
    older = sorted(d for d in bdf["date"].unique() if d <= cutoff)
    if not older:
        return {"key": "rev", "label": "Beneficiary revenue", "sub": sub,
                "measure": "Customer sales", "value": f"{now_med:+.1f}%",
                "remark": "Not enough history yet to show a trend",
                "tone": "neutral", "arrow": "none",
                "detail": (f"median {now_med:+.1f}% — corpus younger than "
                           f"{REV_TREND_WINDOW_DAYS}d, no trend yet"),
                "asof": now_date}
    ref_date = older[-1]
    ref_med = float(bdf[bdf["date"] == ref_date]["revenue_growth_pct"].median())
    delta = now_med - ref_med
    if delta >= REV_FLAT_PP:
        tone, arrow, word = "good", "up", "rising"
    elif delta <= -REV_FLAT_PP:
        tone, arrow, word = "watch", "down", "falling"
    else:
        tone, arrow, word = "good", "none", "flat"
    # Name the baseline to the day. Row 03 names its own measurement point
    # ("Coverage gap (2026Q1)") and anchors its sales figure there; a bare month
    # here made the two rows read as contradictory — "Unchanged since May" next
    # to "Sales have since reached +85.2%" — when they simply measure from
    # different dates. Windows-safe formatting (no %-d), as in scenario_log.
    ref_d = datetime.strptime(ref_date, "%Y-%m-%d").date()
    ref_label = f'{ref_d.strftime("%b")} {ref_d.day}, {ref_d.year}'
    _REV_REMARK = {"rising": f"Up from {ref_med:+.1f}% on {ref_label}",
                   "falling": f"Down from {ref_med:+.1f}% on {ref_label} — buyers slowing",
                   "flat": f"Unchanged since {ref_label}"}
    return {"key": "rev", "label": "Beneficiary revenue", "sub": sub,
            "measure": "Customer sales", "value": f"{now_med:+.1f}%",
            "remark": _REV_REMARK[word],
            "tone": tone, "arrow": arrow,
            "detail": f"median {now_med:+.1f}% vs {ref_med:+.1f}% on {ref_date} — {word}",
            "asof": now_date}


def _val_chip(fund_df: pd.DataFrame) -> dict:
    sub = "Semis forward P/E vs its own recent range"
    sem = fund_df[fund_df["cluster"] == SEMIS_CLUSTER]
    pe = sem.dropna(subset=["forward_pe"]).groupby("date")["forward_pe"].median()
    if len(pe) < 5:
        return {"key": "val", "label": "Valuation", "sub": sub,
                "measure": "Chip valuations", "value": "—",
                "remark": "Needs at least five reports carrying chip valuations",
                "tone": "na", "arrow": "none",
                "detail": "needs ≥5 reports with Semis valuations", "asof": "—"}
    peg = sem.dropna(subset=["peg_ratio"]).groupby("date")["peg_ratio"].median()
    pe_now, pe_hot = float(pe.iloc[-1]), float(pe.quantile(VAL_WARN_QUANTILE))
    peg_now = float(peg.iloc[-1]) if len(peg) else float("nan")
    peg_hot = float(peg.quantile(VAL_WARN_QUANTILE)) if len(peg) else float("nan")
    pe_rich = pe_now > pe_hot
    growth_rich = (peg_now == peg_now and peg_hot == peg_hot and peg_now > peg_hot)
    rich = pe_rich or growth_rich
    # `rich` is an OR of two independent tests, so the remark must narrate the
    # one that actually fired. The growth-adjusted test can trip while the price
    # sits well inside its range; narrating the price range regardless printed
    # "Above its own recent range — 28.4x is the usual high" beside a Value of
    # 21.0x — the row contradicting its own figure (spec §2 rule 4). The
    # growth-adjusted case is said in words: the reader has told us the ratio's
    # name means nothing to them, and it is banned from this column.
    if pe_rich:
        remark = f"Above its own recent range — {pe_hot:.1f}x is the usual high"
        gloss = "rich vs own history"
    elif growth_rich:
        remark = ("Inside its usual price range, but expensive next to the "
                  "growth expected")
        gloss = "price within range, rich once growth is allowed for"
    else:
        remark = f"Inside its own recent range — {pe_hot:.1f}x is the usual high"
        gloss = "within range"
    peg_s = (f" · PEG {peg_now:.2f} (80th pct {peg_hot:.2f})"
             if peg_now == peg_now else "")
    return {"key": "val", "label": "Valuation", "sub": sub,
            "measure": "Chip valuations",
            "value": f"{pe_now:.1f}x",
            "remark": remark,
            "tone": "watch" if rich else "good", "arrow": "none",
            "detail": (f"Semis median fwd PE {pe_now:.1f} "
                       f"(80th pct {pe_hot:.1f}){peg_s} — {gloss}"),
            "asof": str(pe.index[-1])}


def _fragile_chip(capex: dict) -> dict:
    sub = "the debt-funded name most likely to crack first; NVDA–CRWV circularity node"
    frows = [(tk, capex["series"][tk][-1]) for tk in capex["fragile"]
             if capex["series"].get(tk)]
    if not frows:
        return {"key": "fragile", "label": "Fragile tier", "sub": sub,
                "measure": "Weakest borrower", "value": "—",
                "remark": "No borrower rows in the spending file",
                "tone": "na", "arrow": "none", "detail": "no fragile-tier rows",
                "asof": "—"}
    severity = {"red": 2, "amber": 1}
    tk, row = max(frows, key=lambda p: severity.get(p[1].get("flag", ""), 0))
    flag = row.get("flag") or "unflagged"
    note = f" — {row['note']}" if row.get("note") else ""
    tone = {"red": "stress", "amber": "watch"}.get(flag, "good")
    _FRAGILE_REMARK = {
        "stress": (f"Under strain funding ${row['capex_usd_b']:.1f}B of spending "
                   f"— the first to struggle if money tightens"),
        "watch": (f"Borrows to fund ${row['capex_usd_b']:.1f}B of spending "
                  f"— watch this one first if money tightens"),
        "good": f"Spending ${row['capex_usd_b']:.1f}B with no strain flagged",
    }
    return {"key": "fragile", "label": "Fragile tier", "sub": sub,
            "measure": "Weakest borrower",
            "value": tk,
            "remark": _FRAGILE_REMARK[tone],
            "tone": tone, "arrow": "none",
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


_VERDICT = {
    "intact": ("INTACT", "good",
               "Revenue is keeping pace with the spending it's built on — cycle looks intact."),
    "digesting": ("DIGESTING", "watch",
                  "Spending is outrunning the revenue it produces — the cycle is still "
                  "growing, but the gap bears watching."),
    "cracking": ("CRACKING", "stress",
                 "The spend/revenue gap is opening as revenue rolls over — "
                 "treat as an early crack."),
    "insufficient": ("INSUFFICIENT DATA", "neutral",
                     "Not enough complete capex quarters yet — showing the signals we have."),
}

_CRACKING_FRAGILE_GLOSS = ("The fragile, debt-funded name is under stress — "
                           "treat as an early crack.")


def pulse_verdict(gap_available: bool, gap_pp: float,
                  rev_falling: bool, fragile_red: bool) -> dict:
    """One headline read for the band, from the digestion axis (gap + revenue +
    fragile). Valuation is narrated in the band copy but never sets the state.

    A documented presentation rule, NOT a calibrated signal — nothing here feeds
    the scenario odds.
    """
    if not gap_available:
        state = "insufficient"
    elif fragile_red or (gap_pp < 0 and rev_falling):
        state = "cracking"
    elif gap_pp >= 0 and not rev_falling:
        state = "intact"
    else:
        state = "digesting"
    label, tone, gloss = _VERDICT[state]
    # Trigger-aware CRACKING copy: only claim the gap is opening when the crack
    # is actually gap-driven; a fragile-only crack must not contradict a
    # positive/green gap hero.
    if state == "cracking" and not (gap_pp < 0 and rev_falling):
        gloss = _CRACKING_FRAGILE_GLOSS
    return {"state": state, "label": label, "tone": tone, "gloss": gloss}


def compute_verdict(capex: dict, fund_df: pd.DataFrame, chips: list) -> dict:
    """Wire the band's own chips into ``pulse_verdict`` — the single testable
    entry point. Reuses the rev/fragile chip tones so the verdict can never
    disagree with the chips it summarizes.
    """
    gaps = coverage_gap_series(capex, fund_df)
    gap_pp = gaps[-1]["gap_pp"] if gaps else 0.0
    by_key = {c["key"]: c for c in chips}
    rev_falling = by_key.get("rev", {}).get("tone") == "watch"
    fragile_red = by_key.get("fragile", {}).get("tone") == "stress"
    return pulse_verdict(bool(gaps), gap_pp, rev_falling, fragile_red)


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
