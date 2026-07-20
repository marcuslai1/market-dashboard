"""Retrospective page: monthly "what we called / what happened" narrative digest.

Spec: docs/superpowers/specs/2026-07-20-reader-retrospective-design.md
(MarketReport capability-gap survey 2026-07-19, item #8). Derives one-sentence
verdicts from the pipeline's exported call ledger (data/signal_log.csv).
Verdicts are frozen to each call's own 5/10/20-session outcome window — never
re-marked to the latest price — so a finished month's story never changes
afterwards. Retired tickers deliberately stay in: the page is about what we
*said*, and dropping bad old calls would be survivorship bias (deliberate
divergence from the Watchlist's RETIRED_TICKERS filter).
"""
from __future__ import annotations

import pandas as pd

from components.paper_book import select_policy

_FALLBACK_BANNER = (
    "Track record spans mostly a single market regime — read these verdicts "
    "as provisional, not proven."
)

_DIRECTIONAL = ("BUY", "ACCUMULATE", "CAUTION", "AVOID")
_LONG = ("BUY", "ACCUMULATE")


def dedupe_calls(log_df: pd.DataFrame) -> pd.DataFrame:
    """One row per *call*: the first row of each consecutive same-signal run
    per ticker, then directional calls only.

    The log repeats a signal daily while it stands; a HOLD/WATCH day between
    two ACCUMULATE days breaks the run (two distinct calls) — the same streak
    rule ``compute_signal_accuracy`` uses on the report corpus.
    """
    if log_df is None or log_df.empty or "signal" not in log_df.columns:
        return pd.DataFrame()
    df = log_df[log_df["signal"].notna()].sort_values(["ticker", "date"])
    first_of_run = df["signal"] != df.groupby("ticker")["signal"].shift()
    calls = df[first_of_run]
    return calls[calls["signal"].isin(_DIRECTIONAL)].reset_index(drop=True)


def _flag(row, col: str) -> bool:
    """True when a 0/1/NaN hit-flag cell is exactly 1."""
    v = row.get(col)
    try:
        return pd.notna(v) and float(v) == 1.0
    except (TypeError, ValueError):
        return False


def _pct_sfx(ret) -> str:
    return f" ({ret:+.1f}%)" if ret is not None else ""


def classify_call(row) -> tuple[str, str]:
    """(bucket, plain-text outcome) for one deduped call row.

    bucket: "worked" | "failed" | "pending". Right/wrong mirrors the Signal
    Tracker scorecard exactly — long calls are right when price rose (>0),
    CAUTION/AVOID right when it fell or went nowhere (<=0) — so the two pages
    can never disagree on a verdict. Only the call's own window is consulted
    (hit flags + 20-session return); no re-marking to the latest price.
    """
    ret = row.get("return_20d")
    ret = None if ret is None or pd.isna(ret) else float(ret)

    if row["signal"] in _LONG:
        hit_up = _flag(row, "hit_upside_target")
        hit_stop = _flag(row, "hit_invalidation")
        if hit_up and hit_stop:
            if ret is None:
                return "pending", ("hit both its target and its stop — verdict pending "
                                   "the 20-session mark")
            bucket = "worked" if ret > 0 else "failed"
            return bucket, (f"hit both its target and its stop inside the window — "
                            f"finished {ret:+.1f}% after 20 sessions")
        if hit_up:
            return "worked", f"hit its target inside 20 sessions{_pct_sfx(ret)}"
        if hit_stop:
            return "failed", f"stopped out{_pct_sfx(ret)}"
        if ret is None:
            return "pending", "too early to judge"
        if ret > 0:
            return "worked", f"up {ret:+.1f}% after 20 sessions"
        return "failed", f"down {ret:+.1f}% after 20 sessions"

    # CAUTION / AVOID — a drop (or nothing) proves the call right
    if ret is None:
        return "pending", "too early to judge"
    if ret == 0:
        return "worked", "went nowhere — staying out cost nothing"
    if ret < 0:
        return "worked", f"fell {abs(ret):.1f}% — staying out was right"
    return "failed", f"rallied {ret:+.1f}% instead"


def month_label(key: str) -> str:
    """'2026-07' -> 'July 2026'."""
    return pd.Timestamp(f"{key}-01").strftime("%B %Y")


def build_month_digest(calls: pd.DataFrame, month: str) -> dict:
    """Classified calls + headline stats for one 'YYYY-MM' month."""
    rows = calls[calls["date"].dt.strftime("%Y-%m") == month].sort_values("date")
    groups: dict[str, list] = {"worked": [], "failed": [], "pending": []}
    for _, row in rows.iterrows():
        bucket, outcome = classify_call(row)
        groups[bucket].append((row, outcome))
    resolved = len(groups["worked"]) + len(groups["failed"])
    return {"month": month, "n_calls": len(rows), "n_resolved": resolved,
            "n_worked": len(groups["worked"]), "groups": groups}


def banner_text(calibration_insights: dict | None) -> str:
    """The honesty banner: the pipeline's own confidence_banner verbatim when
    present, else a fixed single-regime caution. Never empty — the spec
    requires every month to render under it."""
    banner = ((calibration_insights or {}).get("confidence_banner") or "").strip()
    return banner or _FALLBACK_BANNER


def paper_month_line(nav_df: pd.DataFrame, block: dict, month: str) -> str:
    """One-line paper-book month read, or '' when the month has no NAV rows.

    Baseline = last NAV at-or-before month start (the seed month, with no
    prior row, measures from its first in-month observation). Uses the same
    ``select_policy`` rule as the Paper Book band so both surfaces always
    describe the same headline lane.
    """
    rows = select_policy(nav_df if nav_df is not None else pd.DataFrame(), block or {})
    if rows.empty:
        return ""
    rows = rows.assign(_d=pd.to_datetime(rows["date"], errors="coerce")).dropna(subset=["_d"])
    keys = rows["_d"].dt.strftime("%Y-%m")
    in_month = rows[keys == month]
    if in_month.empty:
        return ""
    before = rows[keys < month]
    base = before.iloc[-1] if not before.empty else in_month.iloc[0]
    end = in_month.iloc[-1]

    mon_name = pd.Timestamp(f"{month}-01").strftime("%B")
    bits = []
    for col, label in [("nav_units", None), ("spy_close", "SPY"), ("soxx_close", "SOXX")]:
        b = pd.to_numeric(base.get(col), errors="coerce")
        e = pd.to_numeric(end.get(col), errors="coerce")
        if pd.isna(b) or pd.isna(e) or b == 0:
            if label is None:
                return ""  # no NAV read -> no line at all
            continue
        pct = (e - b) / b * 100
        bits.append(f"{pct:+.1f}% in {mon_name}" if label is None else f"{label} {pct:+.1f}%")
    line = f"Paper book: {bits[0]}"
    if len(bits) > 1:
        line += " vs " + " · ".join(bits[1:])
    return line
