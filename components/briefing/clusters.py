"""Briefing · Cluster band.

Surfaces the per-cluster analysis the pipeline writes into every report under
the top-level ``clusters`` key (summary / thesis_status / key_development /
data_anchors) — previously computed daily and rendered nowhere (review finding
P1-2). Each cluster is a collapsible row: the pipeline's prose paired with a
computed at-a-glance (signal mix + extension breadth) derived from the cluster's
own watchlist names.
"""
from __future__ import annotations

from collections import Counter

from lib.catalog import SIGNAL_ORDER


def _norm(ticker: str) -> str:
    """Anchor / blocked-ticker key form: dotted ticker -> underscore form."""
    return str(ticker).replace(".", "_")


def _signal_mix(tickers: list, watchlist: dict) -> list:
    """Signal -> count across *tickers*, ordered best->worst per SIGNAL_ORDER.

    Null/absent signals (and tickers missing from *watchlist*) fall into a
    ``"—"`` bucket that sorts last.
    """
    counts: Counter = Counter()
    for tk in tickers:
        sig = (watchlist.get(tk) or {}).get("signal")
        counts[sig if sig else "—"] += 1
    ordered = [(s, counts[s]) for s in SIGNAL_ORDER if counts.get(s)]
    if counts.get("—"):
        ordered.append(("—", counts["—"]))
    return ordered


def _extension_breadth(tickers: list, extension_regime) -> tuple | None:
    """(#hard-blocked-for-extension, #members), or None when no regime data.

    Uses ``extension_regime['blocked_tickers']`` (underscore key form) as the
    precise source. Returns None when the regime block is absent so the caller
    omits the chip rather than guessing.
    """
    if not extension_regime:
        return None
    blocked = {str(t) for t in (extension_regime.get("blocked_tickers") or [])}
    n = sum(1 for tk in tickers if _norm(tk) in blocked)
    return (n, len(tickers))
