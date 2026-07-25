"""Trade levels — the shared entry / target / invalidation mapping.

Two surfaces draw the same three price levels: the Briefing's action-card triplet
and the Watchlist drill-down's levels plate (which adds a fourth R:R cell). The
*mapping* from report fields to labelled, annotated, coloured cells is identical
and lives here. Each surface renders its own markup, because the action card's
triplet and the drill-down's 20px plate sit in different containers at different
sizes — the shared thing is the device and the data, not the chrome.

Colour is assigned by role, never by sentiment: the two prices you are hoping for
and fearing take the market-direction palette, the level you are waiting on stays
neutral, and the ratio is a *measurement*, so it takes brass. Four colours, four
jobs — which is what lets the plate sit near a signal pill without competing.
"""
from __future__ import annotations

from typing import NamedTuple

from lib.formatters import _escape_dollars, _fmt_num, _price_str, _sign, rr_display


class Level(NamedTuple):
    """One render-ready cell: big value, small label above, small sub beneath."""

    label: str
    value: str
    sub: str
    color: str


def trade_levels(d: dict, ccy: str, *, entry_label: str = "Entry") -> list[Level]:
    """Entry / target / invalidation, or ``[]`` when the report has none of them.

    Levels come straight from the report: ``reentry_zone.level`` for the entry,
    ``risk_reward.upside_target`` / ``.invalidation`` for the exits.
    ``entry_label`` differs by surface — the action card calls it "Entry", the
    Watchlist plate calls it "Trigger", because on the grid you are reading the
    level that would *start* the trade rather than the trade itself.
    """
    rr = d.get("risk_reward") or {}
    rz = d.get("reentry_zone") or {}
    entry = rz.get("level")
    target = rr.get("upside_target")
    invalid = rr.get("invalidation")
    if not (entry or target is not None or invalid is not None):
        return []
    up_pct = rr.get("upside_pct")
    down_pct = rr.get("downside_pct")

    entry_val = _escape_dollars(str(entry)) if entry else "—"
    entry_sub = _escape_dollars(rz.get("source") or "on the setup")
    target_val = _price_str(target, ccy) if target is not None else "—"
    target_sub = (
        f'{_sign(up_pct)}{_fmt_num(up_pct, 0)}% · '
        f'{_escape_dollars(rr.get("upside_reason") or "")}'
        if up_pct is not None else _escape_dollars(rr.get("upside_reason") or "")
    )
    inv_val = _price_str(invalid, ccy) if invalid is not None else "—"
    inv_sub = (
        f'−{_fmt_num(down_pct, 1)}% · '
        f'{_escape_dollars(rr.get("invalidation_reason") or "")}'
        if down_pct is not None else _escape_dollars(rr.get("invalidation_reason") or "")
    )
    return [
        Level(entry_label, entry_val, entry_sub, "var(--ink)"),
        Level("Target", target_val, target_sub, "var(--up)"),
        Level("Invalidation", inv_val, inv_sub, "var(--down)"),
    ]


def rr_level(rr_obj: dict | None) -> Level | None:
    """The tight-stop-corrected ratio as a fourth cell, or ``None`` when absent.

    Brass, because a ratio is a measurement rather than a price — the one cell in
    the plate that is not a level you could put an order at. The sub-line says so
    when the figure was corrected, which is the difference between a 1.5:1 that
    clears the gate and one that does not.
    """
    label, _ratio, adjusted = rr_display(rr_obj)
    if not label:
        return None
    sub = "tight-stop adj." if adjusted else ((rr_obj or {}).get("rr_quality") or "")
    return Level("R:R", label, _escape_dollars(sub), "var(--brass)")
