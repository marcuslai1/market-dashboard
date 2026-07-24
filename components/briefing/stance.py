"""Briefing · Posture headline (the page's opening verdict).

Design revision 2026-07-24 (ref docs/briefing.jpg): the posture is a bare,
full-width verdict block — NOT a card. The page opens on the conclusion, with
ONE distribution fact folded into the sub-line (design-spec §1 block 1), which
replaces the old six-cell signal-distribution ledger card. Dropping that second
card also removes the mismatched-box alignment it caused beside the posture.
"""
from __future__ import annotations

from lib.catalog import SIGNAL_COLORS, SIGNAL_ORDER
from lib.charts import INK_FALLBACK
from lib.formatters import _escape_dollars


def _dominant_signal(counts: dict) -> tuple[str, int]:
    """The most-held signal today, ties broken best-first by SIGNAL_ORDER.

    Returns ("", 0) when nothing is counted, so the caller omits the fact.
    """
    live = {s: n for s, n in (counts or {}).items() if n}
    if not live:
        return "", 0
    order = {s: i for i, s in enumerate(SIGNAL_ORDER)}
    dominant = sorted(live, key=lambda s: (-live[s], order.get(s, 99)))[0]
    return dominant, live[dominant]


def stance_band_html(snapshot: dict, total_tracked: int,
                     extension_regime: dict | None = None) -> str:
    """Return the posture band markup — eyebrow, verdict headline, sub-line.

    The sub-line carries the distribution as prose ("21 of 32 names on
    CAUTION"), the extension breadth when the report knows it, and the desk's
    own stance line — rather than a grid of count cells.
    """
    counts = snapshot.get("signal_counts", {}) or {}
    stance = snapshot.get("overall_stance", "") or ""
    posture = snapshot.get("risk_posture", "") or stance or "—"
    total = sum(counts.values()) or total_tracked

    dominant, dom_n = _dominant_signal(counts)
    dot_color = SIGNAL_COLORS.get(dominant, INK_FALLBACK) if dominant else INK_FALLBACK

    bits = []
    if dominant and total:
        bits.append(f"{dom_n} of {total} names on {dominant}")
    blocked = (extension_regime or {}).get("blocked_tickers") or []
    if blocked:
        bits.append(f"{len(blocked)} hard-blocked on extension")
    if stance:
        bits.append(stance)
    sub = " · ".join(bits)

    return (
        '<div class="posture-band">'
        '<div class="posture-eyebrow">'
        f'<span class="posture-dot" style="background:{dot_color};"></span>'
        f"Today's posture · {total} names tracked"
        '</div>'
        f'<h1 class="posture-headline">{_escape_dollars(posture)}</h1>'
        + (f'<div class="posture-sub">{_escape_dollars(sub)}</div>' if sub else "")
        + '</div>'
    )
