"""Briefing · compact Fundamentals card (verdicts only).

Design revision 2026-07-24: three rows — Capex, Valuation, Fragile node — each
a fixed-width label, a verdict word, and a note. The label column is fixed so
all three verdict words start at the same x and the eye tracks a clean vertical
line of verdicts down the card.

The three verdict colours are the clearest statement of the colour rule in the
whole design: brass (data axis), steel (structural state), terracotta (stress) —
and NOT ONE of them touches the signal palette, because none of them is a
buy/sell signal. The full measure list opens in a modal from the Briefing.
"""
from __future__ import annotations

from components.briefing.capex_pulse import capex_chips, capex_verdict
from lib.cards import card_container
from lib.formatters import _escape_dollars

# Valuation tone -> verdict word. Kept off both the signal palette and the
# health tones: valuation is a structural state, not a health verdict.
_VAL_WORD = {"good": "Within range", "watch": "Stretched", "stress": "Extended"}


def fundamentals_strip_html(watchlist: dict) -> str:
    """Return the compact Fundamentals card, or "" when there is no capex data."""
    verdict = capex_verdict()
    chips = {c["key"]: c for c in (capex_chips() or [])}
    if not verdict and not chips:
        return ""

    rows = ""

    def _row(label: str, word: str, colour: str, note: str) -> str:
        return (
            f'<div class="fx-row">'
            f'<div class="fx-label">{label}</div>'
            f'<div class="fx-verdict" style="color:{colour};">{_escape_dollars(word)}</div>'
            f'<div class="fx-note">{_escape_dollars(note)}</div>'
            f'</div>'
        )

    # Capex — the cycle read. A fundamentals/data readout, so the DATA axis.
    if verdict and verdict.get("label"):
        rows += _row("Capex", verdict["label"], "var(--brass)", verdict.get("gloss", ""))

    # Valuation — a neutral structural state, so the structural colour.
    val = chips.get("val")
    if val:
        word = _VAL_WORD.get(val.get("tone"), val.get("value") or "—")
        rows += _row("Valuation", word, "var(--accent)", val.get("remark") or "")

    # Fragile node — the one stress reading on the card. Terracotta looks like a
    # warning but is deliberately NOT signal-red, so it can never be misread as
    # a CAUTION rating on the stock itself.
    frag = chips.get("fragile")
    if frag:
        word = f'{frag.get("value") or "—"} · watch'
        rows += _row("Fragile node", word, "var(--stress)", frag.get("remark") or "")

    if not rows:
        return ""
    return card_container(
        eyebrow='Fundamentals<span class="eb-sub"> · the cycle cross-check</span>',
        headline="",
        body_html=rows,
        lane="ledger",
    )


def fundamentals_detail_html(chips: list | None = None) -> str:
    """The full numbered measure list for the drill-in modal.

    Verdict-first even at row level: a faint ordinal, the measure, its value in
    brass (the data axis), then the plain-English "what it means" line — no
    jargon. Pure markup with no Streamlit widgets, so interacting with the
    dialog can never trigger a rerun that dismisses it.
    """
    chips = chips if chips is not None else capex_chips()
    if not chips:
        return ""
    rows = ""
    for i, c in enumerate(chips, start=1):
        rows += (
            f'<div class="fxd-row">'
            f'<div class="fxd-no">{i:02d}</div>'
            f'<div class="fxd-measure">{_escape_dollars(c.get("measure") or "")}</div>'
            f'<div class="fxd-value">{_escape_dollars(str(c.get("value") or "—"))}</div>'
            f'<div class="fxd-note">{_escape_dollars(c.get("remark") or "")}</div>'
            f'</div>'
        )
    return f'<div class="fxd-list">{rows}</div>'
