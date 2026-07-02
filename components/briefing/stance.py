"""Briefing · Stance / Verdict hero band.

Renders the day's overall portfolio posture as an editorial deck headline
plus a row of signal-count cells. Extracted from dashboard.py during the
Day-2 modularization pass.
"""
from __future__ import annotations

from lib.cards import card_container
from lib.catalog import SIGNAL_COLORS, SIGNAL_ORDER
from lib.charts import INK_FALLBACK, STATUS_NEG
from lib.formatters import _escape_dollars


def stance_band_html(snapshot: dict, total_tracked: int) -> str:
    """Compose the Stance band (deck + signal-distribution ledger) as one HTML
    string wrapped in a ``.lane-wrapper`` so both cards become real grid children.

    Streamlit's ``unsafe_allow_html`` injects each ``st.markdown`` call inside
    its own ``stMarkdownContainer`` wrapper — multiple ``st.markdown`` calls
    cannot share a single ``<div class="lane-wrapper">`` parent reliably. This
    helper sidesteps that by composing both cards in one string emitted via a
    single ``st.markdown`` call at the call site (dashboard.py).
    """
    stance = snapshot.get("overall_stance", "—")
    posture = snapshot.get("risk_posture", "")
    counts = snapshot.get("signal_counts", {})
    deck_color = SIGNAL_COLORS.get("CAUTION", STATUS_NEG)

    # Card 1 — Stance deck (lede lane).
    stance_body = (
        f'<div style="display:flex;align-items:center;gap:8px;'
        f'font-family:var(--mono);font-size:10.5px;letter-spacing:0.06em;color:var(--ink-3);">'
        f'<span style="width:8px;height:8px;border-radius:50%;display:inline-block;'
        f'background:{deck_color};"></span>'
        f'<span>{_escape_dollars(stance.upper())} · BY THE SIGNAL DESK</span>'
        f'</div>'
    )
    lede_card = card_container(
        eyebrow=f"TODAY'S POSTURE · {total_tracked} NAMES TRACKED",
        headline=_escape_dollars(posture or stance),
        body_html=stance_body,
        lane="lede",
    )

    # Card 2 — Signal distribution ledger (ledger lane).
    cells = ""
    for sig in SIGNAL_ORDER:
        n = counts.get(sig, 0)
        color = SIGNAL_COLORS.get(sig, INK_FALLBACK)
        zero_class = "zero" if n == 0 else ""
        num_color = f"color:{color};" if n > 0 else ""
        cells += (
            f'<div class="count-cell {zero_class}">'
            f'<div class="clabel"><span class="cdot" style="background:{color};"></span>{sig}</div>'
            f'<div class="cnum" style="{num_color}">{n}</div></div>'
        )
    counts_body = f'<div class="count-grid" style="margin-top:0;">{cells}</div>'
    ledger_card = card_container(
        eyebrow="SIGNAL DISTRIBUTION",
        headline="",
        body_html=counts_body,
        lane="ledger",
    )

    return f'<div class="lane-wrapper">{lede_card}{ledger_card}</div>'
