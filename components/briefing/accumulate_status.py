"""Briefing · ACCUMULATE Gate status banner.

The pipeline's ``accumulate_paper_status`` block carries the Gate readout.
Its paper-phase ``line`` names what blocks graduation and renders as is. A
CLEARED Gate used to render the pipeline's "gate cleared … Live-eligible."
line in the green "ok" tone with a check mark. That reads as proof, and it is
not: the Gate tests the sign of one pooled mean, so a cleared Gate can hide a
negative regime (clean-sheet review 2026-09-24, §0 item 2, §10 R5).

Since the §12.10 step 1 follow-up (owner go 2026-09-24) a cleared Gate is
worded exactly as the Telegram glance words it (``pipeline/output.py``
``_accumulate_line``): pooled alpha, each regime's alpha, and "Not shown in
every regime" when one is negative. It uses the neutral amber "test" tone,
never green (colour is a claim: green only on proven-good).
"""
from __future__ import annotations

import html


def accumulate_banner_text(aps: dict | None) -> tuple[str, str] | None:
    """(text, tone) for the banner, or None when the report carries no line."""
    if not isinstance(aps, dict) or not aps.get("line"):
        return None
    if not aps.get("graduated"):
        return f"🧪 {aps['line']}", "test"
    alpha, n = aps.get("alpha_10d"), aps.get("n_matured")
    head = "ACCUMULATE: Gate floors met, pooled " + (
        f"{alpha:+.1f}%" if isinstance(alpha, (int, float)) else "n/a")
    head += f" over {n} rows" if n is not None else ""
    by_regime = {r: v for r, v in (aps.get("by_regime_alpha") or {}).items()
                 if isinstance(v, (int, float))}
    if not by_regime:
        # reports before 2026-09-24 carry no per-regime split
        return head + ". Not proof of edge.", "test"
    head += "; by regime " + " / ".join(
        f"{r} {v:+.1f}%" for r, v in sorted(by_regime.items()))
    if any(v < 0 for v in by_regime.values()):
        return head + ". Not shown in every regime.", "test"
    return head + ". Non-negative in every regime so far, not proof of edge.", "test"


def accumulate_banner_html(aps: dict | None) -> str:
    """The banner markup, or "" when there is nothing to show."""
    bits = accumulate_banner_text(aps)
    if bits is None:
        return ""
    text, tone = bits
    return (f'<div class="briefing-banner" data-tone="{tone}">'
            f'{html.escape(text)}</div>')
