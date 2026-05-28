"""Briefing · Macro note (Context band, left column).

Renders the macro lead paragraph, optional commodities note, geopolitical
portfolio implication, scenario-odds bar, and the active-risks side column.
Extracted from dashboard.py during the Day-2 modularization pass.

Visual Step 5 (ContextBand split): exposes ``macro_card_html`` and
``risks_card_html`` as string-returning helpers so the Briefing band can
be composed as a single ``st.markdown`` emission inside a lane wrapper.
The ``render_macro`` wrapper preserves the original sequential-render API
for ``render_briefing`` and any direct callers.
"""
from __future__ import annotations

import streamlit as st

from lib.cards import card_container
from lib.catalog import SIGNAL_COLORS
from lib.formatters import _escape_dollars


def macro_card_html(macro_summary: str, geo: dict, commodities_note: str = "") -> str:
    """Return the Macro Note card markup (lede lane).

    Body contains: lede paragraph, optional commodities note rule, optional
    portfolio-implication block, and the scenario-odds bar + legend.
    """
    body = ""
    if macro_summary:
        body += f'<p class="macro-lead">{_escape_dollars(macro_summary)}</p>'
    if commodities_note:
        body += (
            '<div style="margin-top:8px;font-family:var(--mono);font-size:11.5px;'
            'color:var(--ink-3);line-height:1.5;padding:8px 0 4px;'
            'border-top:1px solid var(--rule);">'
            f'{_escape_dollars(commodities_note)}</div>'
        )
    if geo.get("portfolio_action"):
        body += (
            '<div class="macro-action">'
            '<strong style="color:var(--ink);">Portfolio implication.</strong> '
            f'{_escape_dollars(geo.get("portfolio_action", ""))}</div>'
        )
    probs = geo.get("probabilities") or {}
    if probs:
        colors = {
            "base":        SIGNAL_COLORS["ACCUMULATE"],
            "optimistic":  SIGNAL_COLORS["BUY"],
            "pessimistic": SIGNAL_COLORS["CAUTION"],
            "wildcard":    SIGNAL_COLORS["WATCH"],
        }
        labels = {"base": "Base case", "optimistic": "Optimistic",
                  "pessimistic": "Pessimistic", "wildcard": "Wildcard"}
        segs, keys = "", ""
        for k in ["base", "optimistic", "pessimistic", "wildcard"]:
            v = probs.get(k, 0) or 0
            if v:
                segs += (
                    f'<div class="odds-segment" data-scenario="{k}" '
                    f'style="width:{v}%;background:{colors[k]};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'color:var(--paper);font-family:var(--mono);'
                    f'font-size:11px;font-weight:600;">{v}%</div>'
                )
            keys += (
                f'<div><span style="display:inline-block;width:8px;height:8px;'
                f'background:{colors[k]};margin-right:6px;"></span>'
                f'{labels[k]}</div>'
            )
        body += (
            '<div style="margin-top:18px;">'
            '<div style="font-family:var(--mono);font-size:10px;'
            'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
            'margin-bottom:8px;">Scenario odds</div>'
            '<div style="display:flex;height:24px;border:1px solid var(--rule-strong);'
            f'margin-bottom:8px;">{segs}</div>'
            '<div style="display:grid;grid-template-columns:repeat(2,1fr);'
            'gap:4px 18px;font-family:var(--mono);font-size:11px;'
            f'color:var(--ink-3);">{keys}</div>'
            '</div>'
        )

    return card_container(
        eyebrow="THE MACRO NOTE",
        headline="What's driving prices",
        body_html=body,
        lane="lede",
    )


def _infer_severity(risk_str: str) -> str:
    """Infer risk severity from string-shaped active_risks entries.

    Schema does not yet carry a ``severity`` field (see REDESIGN_PLAN §2.5
    Open Question 5). Tag-pattern inference: HIGH/MED/MEDIUM prefix or
    inline tag wins; everything else defaults to LOW.
    """
    up = risk_str.upper()
    if up.startswith("HIGH") or "HIGH:" in up:
        return "HIGH"
    if up.startswith(("MED", "MEDIUM")) or "MED:" in up or "MEDIUM:" in up:
        return "MED"
    return "LOW"


def risks_card_html(geo: dict) -> str:
    """Return the Active Risks card markup (ledger lane).

    Lists up to 5 risks from ``geo['active_risks']`` using the existing
    ``.risk-card`` markup. Each card carries ``data-severity`` so the CSS
    severity dot (§2.5) keys off it. When/if an entry is a dict with
    ``severity``, that value is preferred over inference.
    """
    risks = (geo.get("active_risks") or [])[:5]
    body = ""
    for r in risks:
        if isinstance(r, dict):
            text = r.get("text") or r.get("risk") or ""
            sev = (r.get("severity") or _infer_severity(text)).upper()
        else:
            text = r
            sev = _infer_severity(r)
        tag = text.split(":", 1)[0][:24] if ":" in text else "Risk"
        body += (
            f'<div class="risk-card" data-severity="{sev}">'
            f'<div class="tag">{_escape_dollars(tag)}</div>'
            f'<div class="text">{_escape_dollars(text)}</div>'
            '</div>'
        )
    if not body:
        body = '<p style="color:var(--ink-3);font-size:13px;">No active risks logged.</p>'

    return card_container(
        eyebrow="ACTIVE RISKS",
        headline="",
        body_html=body,
        lane="ledger",
    )


def render_macro(macro_summary: str, geo: dict, commodities_note: str = "") -> None:
    """Thin wrapper that emits both Macro Note + Risks cards sequentially.

    Used by ``render_briefing`` and any caller that doesn't compose the
    lane-wrapper itself. The cards' ``data-lane`` attributes are inert
    outside a ``.lane-wrapper`` parent.
    """
    st.markdown(
        macro_card_html(macro_summary, geo, commodities_note),
        unsafe_allow_html=True,
    )
    st.markdown(risks_card_html(geo), unsafe_allow_html=True)
