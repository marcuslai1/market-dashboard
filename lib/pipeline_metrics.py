"""Derived figures for the Pipeline health page.

Design spec: docs/superpowers/specs/2026-07-25-pipeline-health-redesign-design.md

Every number the page prints is computed here. Pure pandas, no Streamlit, so the
arithmetic can be tested without booting an app — and the arithmetic is exactly
where this page has been wrong: ``cost_usd.cumsum()`` used to run across all
rows including pre-cutover ones the code's own comment says overstate spend
~10x, so the cumulative chart contradicted the "Total (post-cutover)" tile
directly above it. A running total spanning two pricing regimes is not a number.
``cost_stats`` therefore takes the cutover as a hard boundary and every total,
mean and cumulative figure lives on the post side of it.
"""
from __future__ import annotations

import json

import pandas as pd

# The pipeline moved from Sonnet+Haiku to cache-aware DeepSeek v4 Pro pricing on
# this date. Rows before it are kept for the record and excluded from every
# aggregate.
CUTOVER = pd.Timestamp("2026-05-05")

# Cached input bills at $0.07/MTok instead of $0.27/MTok.
_CACHE_SAVING_PER_MTOK = 0.27 - 0.07

# Runs per month at the current cadence (one per weekday).
_RUNS_PER_MONTH = 21.7


# ── Thresholds ───────────────────────────────────────────────────────────────
# OPERATOR BUDGET, NOT MEASUREMENT. Each is set from the observed post-cutover
# distribution (2026-07-25: 62 rows) with headroom, and each is printed next to
# its metric on the page so the reader can judge the budget as well as the
# reading. A limit tight enough to trip on a normal run trains the operator to
# ignore it, which is worse than having none.
THRESHOLDS = {
    # last-28 p90 $0.0677, observed max $0.0709
    "cost":     {"limit": 0.08,     "kind": "ceiling"},
    # p50 74%, but some runs land at 0.0% — that is the failure this catches
    "cache":    {"limit": 0.40,     "kind": "floor"},
    # last-28 p90 188k
    "input":    {"limit": 220_000,  "kind": "ceiling"},
    # last-28 p90 481s
    "gen":      {"limit": 600.0,    "kind": "ceiling"},
    # p50 24; the last 28 contain runs at 0
    "articles": {"limit": 5,        "kind": "floor"},
}


def breached(key: str, value) -> bool:
    """True when ``value`` is outside the metric's budget.

    A missing value is not a breach — absent telemetry is a gap in the record,
    not evidence of a problem, and colouring it terracotta would cry wolf.
    """
    if value is None or pd.isna(value):
        return False
    t = THRESHOLDS.get(key)
    if not t:
        return False
    return value > t["limit"] if t["kind"] == "ceiling" else value < t["limit"]


def post_cutover(df: pd.DataFrame) -> pd.DataFrame:
    """Rows at or after the pricing cutover, date-sorted."""
    if df is None or df.empty or "date" not in df.columns:
        return pd.DataFrame()
    return df[df["date"] >= CUTOVER].sort_values("date")


def cost_stats(df: pd.DataFrame) -> dict | None:
    """Cost figures, all computed on post-cutover rows only.

    ``monthly`` projects the 7-day mean to a month because a cost per run is
    meaningless to a human until projected — nobody reasons in fractions of a
    cent. ``monthly_uncached`` is the counterfactual: what the same input would
    cost billed entirely as cache miss.
    """
    post = post_cutover(df)
    if post.empty or "computed_cost_usd" not in post.columns:
        return None
    c = post.dropna(subset=["computed_cost_usd"]).copy()
    if c.empty:
        return None
    c["cost"] = c["computed_cost_usd"].astype(float)

    latest = float(c["cost"].iloc[-1])
    avg7 = float(c["cost"].tail(7).mean())
    saving = float(cache_saving_per_run(c) or 0.0)
    return {
        "latest": latest,
        "avg7": avg7,
        "mean": float(c["cost"].mean()),
        "total": float(c["cost"].sum()),
        "runs": len(c),
        "monthly": avg7 * _RUNS_PER_MONTH,
        "monthly_uncached": (avg7 + saving) * _RUNS_PER_MONTH,
        "saving_per_run": saving,
        "series": c[["date", "cost"]].reset_index(drop=True),
    }


def cache_saving_per_run(df: pd.DataFrame) -> float | None:
    """Mean $/run saved by the prefix cache over the last 7 rows."""
    if df is None or df.empty or "cache_hit_tokens" not in df.columns:
        return None
    hits = pd.to_numeric(df["cache_hit_tokens"], errors="coerce").fillna(0).tail(7)
    if hits.empty:
        return None
    return float(hits.mean() * _CACHE_SAVING_PER_MTOK / 1_000_000)


def cache_stats(df: pd.DataFrame) -> dict | None:
    """Prefix-cache hit ratio, token split and cumulative saving."""
    post = post_cutover(df)
    if post.empty or "cache_hit_tokens" not in post.columns:
        return None
    c = post.copy()
    c["hit"] = pd.to_numeric(c["cache_hit_tokens"], errors="coerce").fillna(0)
    c["miss"] = pd.to_numeric(c["cache_miss_tokens"], errors="coerce").fillna(0)
    c["total_input"] = c["hit"] + c["miss"]
    c = c[c["total_input"] > 0]
    if c.empty:
        return None
    c["ratio"] = c["hit"] / c["total_input"]
    latest = c.iloc[-1]
    return {
        "latest": float(latest["ratio"]),
        "mean": float(c["ratio"].mean()),
        "hit_tokens": int(latest["hit"]),
        "miss_tokens": int(latest["miss"]),
        "total_input": int(latest["total_input"]),
        "saved_total": float(c["hit"].sum() * _CACHE_SAVING_PER_MTOK / 1_000_000),
        "series": c[["date", "ratio"]].reset_index(drop=True),
    }


_PROMPT_BLOCKS = [
    ("system_prompt_chars", "System prompt",
     "Static — should sit in the cached prefix"),
    ("watchlist_data_chars", "Watchlist data",
     "Regenerated each run — breaks the prefix from here down"),
    ("tavily_chars", "Tavily news",
     "Varies with the day's ingest"),
    ("yfinance_chars", "yFinance news",
     "Varies with the day's ingest"),
    ("memory_chars", "Memory",
     "Grows slowly as the record accumulates"),
]


def prompt_composition(df: pd.DataFrame) -> list[dict] | None:
    """The latest run's prompt as shares of one whole, largest first.

    Shares of a run rather than five time series because the question this
    section answers is *what dominates*, not *how each moved*.
    """
    post = post_cutover(df)
    if post.empty:
        return None
    have = [c for c, _n, _n2 in _PROMPT_BLOCKS if c in post.columns]
    if not have:
        return None
    rows = post.dropna(subset=have, how="all")
    if rows.empty:
        return None
    latest = rows.iloc[-1]

    blocks = []
    for col, name, note in _PROMPT_BLOCKS:
        v = pd.to_numeric(latest.get(col), errors="coerce")
        blocks.append({"name": name, "note": note,
                       "chars": 0 if pd.isna(v) else int(v)})
    total = sum(b["chars"] for b in blocks)
    if not total:
        return None
    for b in blocks:
        b["share"] = b["chars"] / total * 100.0
    return sorted(blocks, key=lambda b: b["chars"], reverse=True)


def reliability(df: pd.DataFrame) -> dict:
    """Run completeness and validator warnings, stated honestly.

    There is no "scheduled runs" column, so the only denominator the data
    supports is weekdays in the observed span — and it is reported as that,
    rather than dressed up as a schedule the pipeline never recorded. Warning
    counts are the real totals from ``validator_warnings_json`` (a
    check-name -> count map), not a tally of runs that had any.
    """
    post = post_cutover(df)
    if post.empty:
        return {"runs": 0, "weekdays": 0, "missed": 0, "warnings": 0, "checks": 0}

    dates = set(pd.to_datetime(post["date"]).dt.date)
    weekdays = pd.bdate_range(post["date"].min(), post["date"].max()).date
    missed = sum(1 for d in weekdays if d not in dates)

    warnings = checks = 0
    if "validator_warnings_json" in post.columns:
        raw = post["validator_warnings_json"].dropna()
        if len(raw):
            try:
                parsed = json.loads(raw.iloc[-1])
                if isinstance(parsed, dict):
                    warnings = int(sum(parsed.values()))
                    checks = len(parsed)
            except (ValueError, TypeError):
                warnings = checks = 0

    return {"runs": len(post), "weekdays": len(weekdays),
            "missed": int(missed), "warnings": warnings, "checks": checks}


def overall_status(cells: list[dict]) -> tuple[str, str]:
    """(word, key) for the verdict band, from the strip's breach states.

    Three steps on the site's steel -> gold -> terracotta health axis. "Healthy"
    is steel rather than green because fine is the structural default, not an
    achievement — and because green is reserved for market direction.
    """
    if any(c.get("breach") for c in cells):
        return "Over budget", "breach"
    if any(c.get("near") for c in cells):
        return "Watch", "near"
    return "Healthy", "ok"
