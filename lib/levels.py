"""Price levels as facts — the Watchlist drill-down's levels plate.

The nearest two supports below and two resistances above, the 50- and 200-day
averages and the last price, sorted high → low, each with the % move from the last
price to that level. No ratio, stop, target, trigger or fall-through: those were
the label machinery (MarketReport spec 2026-10-01-info-only-watchlist §3, O2). The
old entry / target / invalidation mapping went with it (tag ``pre-label-removal``).

**Synthetic levels are dropped.** When the pipeline finds no swing-point zone on a
side, ``attach_risk_reward`` back-fills it (``pipeline/indicators.py``
``ensure_support_zones`` / ``ensure_resistance_zones``) so its R:R had something to
divide by: with the SMA50 / SMA200 when one sits on that side, otherwise with
price × 0.8 and × 0.9 (supports) or × 1.05 and × 1.15 (resistances). Nobody traded
at those prices, so printing them as a support or resistance would state a fact
that is not one (10-01: AMD's two "resistances" are 611.76 × 1.05 / × 1.15). A
level equal to an SMA to the cent is the SMA, already on the ladder; a pair in the
synthetic ratio to the cent is the fallback.
"""
from __future__ import annotations

from typing import NamedTuple

#: Rounding slack, in price units: both members of a fallback pair are rounded to
#: 2 dp from the same price, so their ratio misses the exact multiple by < 1 cent.
_PAIR_SLACK = 0.011


class Rung(NamedTuple):
    """One ladder row. ``pct`` is the move from the last price to ``price``
    (``None`` on the last-price row itself, or when no last price is known)."""

    kind: str          # "resistance" | "support" | "sma50" | "sma200" | "last"
    label: str
    price: float
    pct: float | None


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _is_fallback_pair(levels: list[float], lo_mult: float, hi_mult: float) -> bool:
    """True when two levels are the pipeline's price-multiple fallback."""
    if len(levels) != 2:
        return False
    lo, hi = sorted(levels)
    return abs(lo - hi * lo_mult / hi_mult) <= _PAIR_SLACK


def observed_zones(d: dict) -> tuple[list[float], list[float]]:
    """``(supports, resistances)`` the report carries, minus the back-fills.

    Supports are returned nearest-first (descending), resistances nearest-first
    (ascending), at most two each — the pipeline already ships at most two.
    """
    sup = [x for x in (_num(v) for v in d.get("support_zones") or []) if x is not None]
    res = [x for x in (_num(v) for v in d.get("resistance_zones") or []) if x is not None]
    if _is_fallback_pair(sup, 0.8, 0.9):
        sup = []
    if _is_fallback_pair(res, 1.05, 1.15):
        res = []
    smas = {round(x, 2) for x in (_num(d.get("sma50")), _num(d.get("sma200"))) if x}
    sup = [x for x in sup if round(x, 2) not in smas]
    res = [x for x in res if round(x, 2) not in smas]
    return sorted(sup, reverse=True)[:2], sorted(res)[:2]


def level_ladder(d: dict) -> list[Rung]:
    """Every level the report states for this name, high → low, with the last
    price as its own rung. ``[]`` when there is no level at all."""
    last = _num(d.get("price"))
    sup, res = observed_zones(d)
    rows: list[tuple[str, str, float]] = (
        [("resistance", "Resistance", x) for x in res]
        + [("support", "Support", x) for x in sup]
    )
    for key, kind, label in (("sma50", "sma50", "50-day avg"),
                             ("sma200", "sma200", "200-day avg")):
        v = _num(d.get(key))
        if v:
            rows.append((kind, label, v))
    if not rows:
        return []

    def pct(level: float) -> float | None:
        return (level / last - 1.0) * 100.0 if last else None

    rungs = [Rung(kind, label, price, pct(price)) for kind, label, price in rows]
    if last:
        rungs.append(Rung("last", "Last", last, None))
    # Ties keep the last price above an equal level, so it never sinks below
    # a support printed at the same value.
    return sorted(rungs, key=lambda r: (-r.price, r.kind != "last"))
