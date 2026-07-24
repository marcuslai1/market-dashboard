"""Briefing · compact Fundamentals strip (verdicts only).

Design revision 2026-07-24: the AI Capex Pulse verdict and the Earnings
Scorecard headline as two scannable lines on the Briefing — the glance. The
full datasheet, coverage-gap chart, and per-ticker earnings trend stay on the
Fundamentals tab (progressive disclosure).
"""
from __future__ import annotations

from components.briefing.capex_pulse import capex_verdict
from components.briefing.earnings import earnings_headline
from lib.cards import card_container
from lib.formatters import _escape_dollars

# Capex health tone -> DATA palette (steel/accent -> brass -> terracotta),
# never the signal palette (design-spec §3b: the health axis is its own system).
_TONE_VAR = {
    "good": "var(--accent)",
    "watch": "var(--brass)",
    "stress": "var(--stress)",
    "neutral": "var(--color-text-3)",
    "na": "var(--color-text-3)",
}


def fundamentals_strip_html(watchlist: dict) -> str:
    """Return the compact Fundamentals card, or "" when neither verdict is
    available (older reports without capex/earnings data)."""
    rows = ""

    verdict = capex_verdict()
    if verdict and verdict.get("label"):
        color = _TONE_VAR.get(verdict.get("tone"), "var(--color-text-3)")
        rows += (
            f'<div class="fx-row">'
            f'<span class="fx-label">Capex</span>'
            f'<span class="fx-verdict" style="color:{color};">'
            f'{_escape_dollars(verdict["label"])}</span>'
            f'<span class="fx-gloss">{_escape_dollars(verdict.get("gloss", ""))}</span>'
            f'</div>'
        )

    headline = earnings_headline(watchlist)
    if headline:
        rows += (
            f'<div class="fx-row">'
            f'<span class="fx-label">Earnings</span>'
            f'<span class="fx-verdict">{_escape_dollars(headline)}</span>'
            f'</div>'
        )

    if not rows:
        return ""
    body = f'{rows}<div class="strip-more">Detail on the <b>Fundamentals</b> tab</div>'
    return card_container(
        eyebrow="FUNDAMENTALS",
        headline="",
        body_html=body,
        lane="ledger",
    )
