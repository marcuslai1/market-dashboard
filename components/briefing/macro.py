"""Briefing · Macro note (Context band, left column).

Renders the macro lead paragraph, optional commodities note, geopolitical
portfolio implication, scenario-odds bar, and the active-risks side column.
Extracted from dashboard.py during the Day-2 modularization pass.

Exposes ``macro_card_html`` and ``risks_card_html`` as string-returning helpers so
the Briefing band can be composed as a single ``st.markdown`` emission (from
dashboard.py) inside a lane wrapper.
"""
from __future__ import annotations

import re
from datetime import datetime as _dt

from lib.cards import card_container
from lib.formatters import _escape_dollars

# Core-5 rate-relevant prints, fixed display order. Other FRED series
# (real 10Y, breakevens, HY OAS) are intentionally omitted from this strip.
_PRINT_ORDER = [
    "CPI (YoY)",
    "Core PCE (YoY)",
    "Unemployment",
    "Nonfarm payrolls",
    "Fed funds (eff.)",
]


def _fmt_value(label: str, d: dict) -> str:
    v = d.get("value")
    if v is None:
        return "n/a"
    if label == "Nonfarm payrolls":
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:g}k"
    return f"{v:g}%"


def _fmt_delta(label: str, d: dict) -> str:
    chg = d.get("chg")
    if not isinstance(chg, (int, float)) or chg == 0:
        return "—"
    arrow = "▲" if chg > 0 else "▼"
    unit = "k" if label == "Nonfarm payrolls" else ""
    return f"{arrow}{abs(chg):g}{unit}"


# Upstream computes age_days from the FRED *observation* date (1st of the
# observation month), so a monthly print is ~40d "old" the day it's released
# and the upstream is_stale flag fires on perfectly fresh data. Per series:
# the age (days from observation date) past which the NEXT release should
# already exist — only beyond that is the row genuinely stale. Monthly rows
# also hide the raw day-count, which reads as staleness when it isn't.
_SERIES_FRESHNESS = {
    "CPIAUCSL":     ("monthly", 78),   # next CPI ~71-76d after obs date
    "PCEPILFE":     ("monthly", 95),   # PCE lags ~90d (May print → Jun 25)
    "UNRATE":       ("monthly", 68),   # jobs report ~61-67d after obs date
    "PAYEMS":       ("monthly", 68),
    "DFF":          ("daily", 7),
    "DFII10":       ("daily", 7),
    "T5YIE":        ("daily", 7),
    "BAMLH0A0HYM2": ("daily", 7),
}


def _fmt_freshness(d: dict) -> str:
    asof = d.get("asof", "")
    month = ""
    if asof:
        try:
            month = _dt.strptime(asof, "%Y-%m-%d").strftime("%b")
        except (ValueError, TypeError):
            month = asof
    age = d.get("age_days")
    meta = _SERIES_FRESHNESS.get(d.get("series_id"))
    if meta:
        cadence, supersede_days = meta
        show_age = cadence == "daily"
        is_stale = isinstance(age, int) and age > supersede_days
    else:
        show_age = True
        is_stale = bool(d.get("is_stale"))
    age_s = f"{age}d" if show_age and isinstance(age, int) else ""
    stale = " · STALE" if is_stale else ""
    bits = " · ".join(b for b in [month, age_s] if b)
    return f"{bits}{stale}"


def macro_prints_html(indicators: dict) -> str:
    """Return a compact FRED Core-5 prints table (or "" when no data).

    Valence-neutral (no green/red) — the strip reports figures, it does not
    editorialize direction as good/bad. Renders nothing when the block is empty
    (FRED key unset, or pre-FRED reports), so old reports stay clean.
    """
    indicators = indicators or {}
    cells = ""
    any_row = False
    for label in _PRINT_ORDER:
        d = indicators.get(label)
        if not isinstance(d, dict):
            continue
        any_row = True
        has_val = d.get("value") is not None
        val = _escape_dollars(_fmt_value(label, d))
        delta = _fmt_delta(label, d) if has_val else ""
        fresh = _escape_dollars(_fmt_freshness(d)) if has_val else "unavailable"
        cells += (
            f'<div class="fp-cell">'
            f'<div class="fp-label">{label}</div>'
            f'<div class="fp-value">{val}</div>'
            f'<div class="fp-meta">'
            f'<span class="fp-delta">{delta}</span>'
            f'<span class="fp-month">{fresh}</span>'
            f'</div>'
            f'</div>'
        )
    if not any_row:
        return ""
    # Caveat ABOVE the grid: the honesty ("not live") has to be read before the
    # numbers, not after them.
    return (
        '<div class="fp-wrap">'
        '<div class="fp-caveat">Macro prints · FRED · latest available, not live</div>'
        f'<div class="fp-grid">{cells}</div>'
        '</div>'
    )


def macro_card_html(macro_summary: str, geo: dict, commodities_note: str = "",
                    macro_indicators: dict | None = None) -> str:
    """Return the Macro Note card markup (lede lane).

    Body = context + portfolio implication: lede paragraph, optional commodities
    note, the FRED Core-5 prints, and the portfolio-implication block. The
    scenario-odds bar + narrative now live on the Scenario Log (scenario_odds_html).
    """
    body = ""
    if macro_summary:
        body += f'<p class="macro-lead">{_escape_dollars(macro_summary)}</p>'
    if commodities_note:
        body += (
            # --ink-2 not --ink-3: this is prose ("WTI leapt to $91.95…"), and at
            # caption weight it read dull against the lede above it (owner review).
            '<div style="margin-top:8px;font-family:var(--mono);font-size:11.5px;'
            'color:var(--ink-2);line-height:1.5;padding:8px 0 4px;'
            'border-top:1px solid var(--rule);">'
            f'{_escape_dollars(commodities_note)}</div>'
        )
    body += macro_prints_html(macro_indicators or {})
    if geo.get("portfolio_action"):
        body += (
            '<div class="macro-action">'
            '<strong>Implication.</strong> '
            f'{_escape_dollars(geo.get("portfolio_action", ""))}</div>'
        )
    # Scenario odds + per-scenario narrative moved to the Scenario Log tab
    # (overhaul 2026-07-24): they are macro *probability*, not "what's driving
    # prices". The Macro note stays context + portfolio implication. Rendered on
    # the Scenario Log via scenario_odds_html() below.

    return card_container(
        eyebrow="THE MACRO NOTE",
        headline="What's driving prices",
        body_html=body,
        lane="lede",
    )


_SCEN_COLORS = {
    "base": "var(--accent)",
    "optimistic": "var(--up)",
    "pessimistic": "var(--down)",
    "wildcard": "var(--brass)",
}
_SCEN_LABELS = {
    "base": "Base case",
    "optimistic": "Optimistic",
    "pessimistic": "Pessimistic",
    "wildcard": "Wildcard",
}
_SCEN_ORDER = ["base", "optimistic", "pessimistic", "wildcard"]


def scenario_odds_html(geo: dict) -> str:
    """Scenario-odds bar + per-scenario narrative, for the Scenario Log tab.

    Moved off the Briefing's Macro note (overhaul 2026-07-24): this is macro
    probability, so it belongs with the scenarios it describes. Returns "" when
    the report carries no probabilities/scenarios. Colours come from the DATA/
    structure palette, never signal hues (design-spec §3).
    """
    geo = geo or {}
    probs = geo.get("probabilities") or {}
    scenarios = geo.get("scenarios") or {}
    if not probs and not scenarios:
        return ""

    body = ""
    if probs:
        segs, keys = "", ""
        for k in _SCEN_ORDER:
            v = probs.get(k, 0) or 0
            if v:
                segs += (
                    f'<div class="odds-segment" data-scenario="{k}" '
                    f'style="width:{v}%;background:{_SCEN_COLORS[k]};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'color:var(--paper);font-family:var(--mono);'
                    f'font-size:11px;font-weight:600;">{v}%</div>'
                )
            keys += (
                f'<div><span style="display:inline-block;width:8px;height:8px;'
                f'background:{_SCEN_COLORS[k]};margin-right:6px;"></span>'
                f'{_SCEN_LABELS[k]}</div>'
            )
        body += (
            '<div style="display:flex;height:24px;border:1px solid var(--rule-strong);'
            f'margin-bottom:10px;">{segs}</div>'
            '<div style="display:flex;flex-wrap:wrap;gap:6px 20px;'
            'font-family:var(--mono);font-size:11px;color:var(--ink-3);'
            f'margin-bottom:16px;">{keys}</div>'
        )

    if scenarios:
        for k in _SCEN_ORDER:
            sc = scenarios.get(k)
            # Shape-drift days (2026-07-22) ship the scenario as a bare string.
            desc = (sc.get("description") if isinstance(sc, dict)
                    else sc if isinstance(sc, str) else None)
            if not desc:
                continue
            pct = probs.get(k)
            pct_s = f" · {pct}%" if pct else ""
            body += (
                f'<div style="margin-bottom:10px;padding-left:10px;'
                f'border-left:2px solid {_SCEN_COLORS[k]};">'
                f'<div style="font-family:var(--mono);font-size:10px;'
                f'letter-spacing:0.08em;text-transform:uppercase;'
                f'color:{_SCEN_COLORS[k]};margin-bottom:2px;">'
                f'{_SCEN_LABELS[k]}{pct_s}</div>'
                f'<div style="font-size:12.5px;color:var(--ink-2);'
                f'line-height:1.5;">{_escape_dollars(desc)}</div>'
                f'</div>'
            )

    if not body:
        return ""
    return card_container(
        eyebrow="SCENARIO ODDS",
        headline="How the week could break",
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


# Label-vs-prose split for active_risks (2026-07-22). The corpus names risks
# "Label: description", but the previous guard (<= 24 chars AND <= 2 spaces)
# accepted only 89 of the 206 colon-bearing strings across data/ — the other 117
# printed a bare severity badge where their name should have been. Measured
# replacement: a length ceiling plus a sentence-break test accepts 205/206,
# rejecting only a 181-char paragraph that happens to contain a colon.
#
# The ceiling is deliberately generous: the longest real label is 67 chars
# ("Apple CEO transition (Tim Cook -> John Ternus effective September 1)") and
# the next-longest string is that 181-char paragraph, so anything in between
# separates them cleanly.
_RISK_LABEL_MAX = 72
# A sentence break is period-or-semicolon + space + capital. Matching a bare
# period would wrongly reject "U.S. tariff uncertainty persists", which is a
# real label in the corpus — the abbreviation's period is followed by lowercase.
_RISK_SENTENCE_RE = re.compile(r"[.;]\s+[A-Z]|;")


def _split_risk_label(text: str) -> tuple[str, str]:
    """Split ``"Label: description"`` into ``(label, description)``.

    Returns ``("", text)`` when the pre-colon text reads as prose rather than a
    label, so the caller falls back to the severity badge. Never truncates —
    the bug this guard originally existed for produced mid-word fragments like
    ``"US-China tech tensions p"``.
    """
    if ":" not in text:
        return "", text
    label, _, rest = text.partition(":")
    label, rest = label.strip(), rest.strip()
    if not label or not rest or len(label) > _RISK_LABEL_MAX:
        return "", text
    if _RISK_SENTENCE_RE.search(label):
        return "", text
    return label, rest


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
        # Prefer the row's own "Label: …" name as the tag; fall back to the
        # severity (HIGH/MED/LOW) only when the pre-colon text is prose. The tag
        # colour is keyed off data-severity in CSS.
        #
        # The label is also stripped from the body: it is the tag now, and
        # printing it twice was the visible cost of the old guard accepting so
        # few labels that the duplication stayed rare enough to miss.
        label, detail = _split_risk_label(text)
        tag = label or sev
        body += (
            f'<div class="risk-card" data-severity="{sev}">'
            f'<div class="tag">{_escape_dollars(tag)}</div>'
            f'<div class="text">{_escape_dollars(detail)}</div>'
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
