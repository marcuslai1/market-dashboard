"""Briefing · Action Card (next-step callout).

Renders the "If you only do one thing today" card — picks the single
highest-conviction BUY/ACCUMULATE/WATCH ticker and surfaces its headline,
plain-language body, optional entry block, and live price stats. Extracted
from dashboard.py during the Day-2 modularization pass.
"""
from __future__ import annotations

import streamlit as st

from lib.cards import card_container
from lib.catalog import (
    CLUSTER_MAP,
    RETIRED_TICKERS,
    SIGNAL_COLORS,
    SIGNAL_TINTS,
    SIGNAL_VERBS,
)
from lib.charts import INK_FALLBACK, STATUS_WARN, STATUS_WARN_SOFT
from lib.formatters import (
    _escape_dollars,
    _fmt_num,
    _price_str,
    _sign,
    _writeup_for_render,
    display_ticker,
)


def _pick_action_ticker(wl: dict) -> tuple[str | None, dict | None]:
    """Pick the single most actionable BUY/ACCUMULATE/WATCH name.

    Returns (None, None) when nothing is actionable — caller should skip the callout.
    """
    priority = {"BUY": 0, "ACCUMULATE": 1, "WATCH": 2}
    candidates = [
        (tk, d) for tk, d in wl.items()
        if d.get("signal") in priority and tk not in RETIRED_TICKERS
    ]
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: (
        priority.get(x[1].get("signal"), 99),
        -((x[1].get("risk_reward") or {}).get("ratio") or 0),
    ))
    return candidates[0]


def render_action_card(wl: dict, events: list) -> None:
    tk, d = _pick_action_ticker(wl)
    if not tk:
        # Nothing actionable today — render nothing per design.
        return
    sig = d.get("signal", "WATCH")
    color = SIGNAL_COLORS.get(sig, INK_FALLBACK)
    display_tk = _escape_dollars(display_ticker(tk))
    cluster = _escape_dollars(CLUSTER_MAP.get(tk, ""))
    price = d.get("price")
    ccy = d.get("currency", "USD")
    chg = d.get("chg_pct")
    wu = _writeup_for_render(d)
    headline = wu["headline"] or ""
    body = wu["what_to_do"] or ""
    block = wu["entry_block"]
    rr_label = (d.get("risk_reward") or {}).get("ratio_label", "")

    price_str = _price_str(price, ccy)
    delta_color = SIGNAL_COLORS["BUY"] if (chg or 0) >= 0 else SIGNAL_COLORS["CAUTION"]
    delta_str = f"{_sign(chg)}{_fmt_num(chg, 2)}%" if chg is not None else ""
    verb_pill = (
        f'<span style="display:inline-block;font-family:var(--mono);font-size:10px;'
        f'font-weight:600;letter-spacing:0.04em;padding:3px 9px;'
        f'border-radius:var(--radius-pill);background:{SIGNAL_TINTS.get(sig, "var(--paper-3)")};'
        f'color:{color};">{SIGNAL_VERBS.get(sig, sig)}</span>'
    )

    block_html = (
        f'<div style="margin-top:10px;font-family:var(--mono);font-size:11.5px;'
        f'border-left:2px solid {STATUS_WARN}80;padding-left:10px;color:{STATUS_WARN_SOFT};'
        f'line-height:1.5;">{_escape_dollars(block)}</div>'
        if block else ""
    )

    rr_html = (
        f'<div style="margin-top:8px;">R:R {rr_label}</div>'
        if rr_label else ""
    )

    # Two-column body: signal-railed content on the left, price stats on the right.
    # The card's eyebrow + headline (in .card-head) already render the
    # ticker headline above, so the body opens with the ticker line + plain body.
    body_html = (
        f'<div style="display:grid;grid-template-columns:1fr auto;gap:24px;align-items:start;">'
        # Left column — signal-coloured rail preserves the old .action-card look.
        f'<div style="border-left:3px solid {color};padding-left:16px;">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">'
        f'<span style="font-family:var(--mono);font-size:12.5px;font-weight:600;'
        f'letter-spacing:0.04em;color:var(--ink-3);">'
        f'{display_tk}{" · " + cluster if cluster else ""}</span>'
        f'{verb_pill}'
        f'</div>'
        f'<div style="color:var(--ink-2);font-size:14px;line-height:1.55;max-width:60ch;">'
        f'{_escape_dollars(body)}</div>'
        f'{block_html}'
        f'</div>'
        # Right column — price stats (Last / level / delta / R:R).
        f'<div style="font-family:var(--mono);font-size:11px;text-align:right;'
        f'color:var(--ink-3);line-height:1.6;min-width:120px;">'
        f'<div>Last</div>'
        f'<div style="font-family:var(--serif);font-size:1.4rem;color:var(--ink);'
        f'font-weight:500;letter-spacing:-0.01em;">{price_str}</div>'
        f'<div style="margin-top:6px;color:{delta_color};">{delta_str} today</div>'
        f'{rr_html}'
        f'</div>'
        f'</div>'
    )

    st.markdown(
        card_container(
            eyebrow="IF YOU ONLY DO ONE THING TODAY",
            headline=_escape_dollars(headline),
            body_html=body_html,
            lane="lede",
        ),
        unsafe_allow_html=True,
    )
