"""Briefing · Action Card (next-step callout).

Renders the "If you only do one thing today" card — picks the single
highest-conviction BUY/ACCUMULATE/WATCH ticker and surfaces its headline,
plain-language body, optional entry block, and live price stats. Also
exposes ``render_action_summary`` for the full 7-bucket action digest
(currently not wired into the Briefing tab, but kept paired with the
action-card module for future use). Extracted from dashboard.py during
the Day-2 modularization pass.
"""
from __future__ import annotations

import streamlit as st

from lib.cards import card_container, render_section_head
from lib.catalog import (
    CLUSTER_MAP,
    RETIRED_TICKERS,
    SIGNAL_COLORS,
    SIGNAL_TINTS,
    SIGNAL_VERBS,
    TICKER_DISPLAY,
)
from lib.formatters import (
    _escape_dollars,
    _fmt_num,
    _sign,
    _writeup_for_render,
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
    color = SIGNAL_COLORS.get(sig, "#9F988B")
    display_tk = TICKER_DISPLAY.get(tk, tk)
    cluster = CLUSTER_MAP.get(tk, "")
    price = d.get("price")
    ccy = d.get("currency", "USD")
    chg = d.get("chg_pct")
    wu = _writeup_for_render(d)
    headline = wu["headline"] or ""
    body = wu["what_to_do"] or ""
    block = wu["entry_block"]
    rr_label = (d.get("risk_reward") or {}).get("ratio_label", "")

    pfx = "S$" if ccy == "SGD" else "$"
    price_str = f"{pfx}{_fmt_num(price, 2)}"
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
        f'border-left:2px solid #f59e0b80;padding-left:10px;color:#fbb454;'
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


def render_action_summary(action_summary: dict) -> None:
    """Full action bucket digest — all 7 buckets in compact rows below the action card."""
    if not action_summary:
        return

    BUCKET_ORDER = [
        ("consider_adding",       "Consider Adding",        SIGNAL_COLORS["BUY"]),
        ("accumulate",            "Accumulate",             SIGNAL_COLORS["ACCUMULATE"]),
        ("watch_for_entry",       "Watch for Entry",        SIGNAL_COLORS["WATCH"]),
        ("regime_change_pending", "Regime Change Pending",  "#f59e0b"),
        ("on_deck",               "On Deck",                "#9ca3af"),
        ("avoid",                 "Avoid",                  SIGNAL_COLORS["AVOID"]),
        ("hold_no_action",        "Hold / No Action",       SIGNAL_COLORS["HOLD"]),
    ]
    new_names = action_summary.get("new_stocks_to_watch") or []
    any_entries = any(action_summary.get(k) for k, _, _ in BUCKET_ORDER) or new_names
    if not any_entries:
        return

    render_section_head("Action Summary", "All signals by bucket — full breakdown")

    html_parts: list[str] = []
    for key, label, color in BUCKET_ORDER:
        entries = action_summary.get(key) or []
        if not entries:
            continue
        html_parts.append(
            f'<div style="margin-bottom:20px;">'
            f'<div style="font-family:var(--mono);font-size:10.5px;letter-spacing:0.13em;'
            f'text-transform:uppercase;color:{color};margin-bottom:8px;'
            f'padding-bottom:5px;border-bottom:1px solid rgba(255,255,255,0.06);">'
            f'{label} <span style="color:var(--ink-3);">({len(entries)})</span></div>'
        )
        for entry in entries:
            tk = entry.get("ticker", "")
            note = entry.get("note", "")
            entry_level = entry.get("entry_level")
            display_tk = TICKER_DISPLAY.get(tk, tk)
            level_html = (
                f'<span style="color:var(--ink-3);font-family:var(--mono);font-size:11px;'
                f'margin-left:10px;flex-shrink:0;">@ {_escape_dollars(str(entry_level))}</span>'
                if entry_level is not None else ""
            )
            html_parts.append(
                f'<div style="display:flex;gap:10px;align-items:baseline;'
                f'padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.03);">'
                f'<span style="font-family:var(--mono);font-size:11.5px;font-weight:600;'
                f'color:{color};min-width:80px;flex-shrink:0;">{display_tk}</span>'
                f'<span style="font-size:13.5px;color:var(--ink-2);line-height:1.45;flex:1;">'
                f'{_escape_dollars(note)}</span>'
                f'{level_html}'
                f'</div>'
            )
        html_parts.append('</div>')

    if new_names:
        html_parts.append(
            '<div style="margin-bottom:20px;">'
            '<div style="font-family:var(--mono);font-size:10.5px;letter-spacing:0.13em;'
            'text-transform:uppercase;color:#9ca3af;margin-bottom:8px;'
            'padding-bottom:5px;border-bottom:1px solid rgba(255,255,255,0.06);">'
            f'Names to Watch <span style="color:var(--ink-3);">({len(new_names)})</span></div>'
        )
        for entry in new_names:
            nm = entry.get("name", "")
            note = entry.get("note", "")
            html_parts.append(
                f'<div style="display:flex;gap:10px;align-items:baseline;'
                f'padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.03);">'
                f'<span style="font-family:var(--mono);font-size:11.5px;font-weight:600;'
                f'color:#9ca3af;min-width:80px;flex-shrink:0;">{_escape_dollars(nm)}</span>'
                f'<span style="font-size:13.5px;color:var(--ink-2);line-height:1.45;flex:1;">'
                f'{_escape_dollars(note)}</span>'
                f'</div>'
            )
        html_parts.append('</div>')

    st.markdown(
        '<div style="background:var(--paper-2);border:1px solid var(--rule);'
        'border-radius:4px;padding:20px 24px;margin-top:8px;">'
        + "".join(html_parts)
        + '</div>',
        unsafe_allow_html=True,
    )
