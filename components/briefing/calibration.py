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
