"""Briefing · Macro note (Context band, left column).

Renders the macro lead paragraph, optional commodities note, geopolitical
portfolio implication, scenario-odds bar, and the active-risks side column.
Extracted from dashboard.py during the Day-2 modularization pass.

Exposes ``macro_card_html`` and ``risks_card_html`` as string-returning helpers so
the Briefing band can be composed as a single ``st.markdown`` emission (from
dashboard.py) inside a lane wrapper.
"""
from __future__ import annotations

from datetime import datetime as _dt

from lib.cards import card_container
from lib.catalog import SIGNAL_COLORS
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
    rows = ""
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
        rows += (
            '<div style="display:flex;justify-content:space-between;'
            'align-items:baseline;gap:8px;padding:3px 0;font-family:var(--mono);'
            'font-size:11px;color:var(--ink-2);">'
            f'<span style="color:var(--ink-3);min-width:96px;">{label}</span>'
            f'<span style="color:var(--ink);font-weight:600;">{val}</span>'
            f'<span style="color:var(--ink-3);min-width:42px;text-align:right;">{delta}</span>'
            f'<span style="color:var(--ink-3);flex:1;text-align:right;">{fresh}</span>'
            '</div>'
        )
    if not any_row:
        return ""
    return (
        '<div style="margin-top:14px;padding-top:8px;'
        'border-top:1px solid var(--rule);">'
        '<div style="font-family:var(--mono);font-size:10px;letter-spacing:0.1em;'
        'text-transform:uppercase;color:var(--ink-3);margin-bottom:6px;">'
        'Macro prints · FRED · latest available, not live</div>'
        f'{rows}</div>'
    )


def macro_card_html(macro_summary: str, geo: dict, commodities_note: str = "",
                    macro_indicators: dict | None = None) -> str:
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
    body += macro_prints_html(macro_indicators or {})
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
            # Flex row (not a 2x2 grid) so the legend reads left-to-right in the
            # same order as the bar segments above it.
            '<div style="display:flex;flex-wrap:wrap;'
            'gap:6px 20px;font-family:var(--mono);font-size:11px;'
            f'color:var(--ink-3);">{keys}</div>'
            '</div>'
        )

    # Scenario descriptions — what each odds segment actually means for the
    # portfolio. The odds bar above carries the probabilities; this carries the
    # narrative. Keyed in the same order/colour as the bar. Hidden when absent.
    scenarios = geo.get("scenarios") or {}
    if scenarios:
        sc_colors = {
            "base":        SIGNAL_COLORS["ACCUMULATE"],
            "optimistic":  SIGNAL_COLORS["BUY"],
            "pessimistic": SIGNAL_COLORS["CAUTION"],
            "wildcard":    SIGNAL_COLORS["WATCH"],
        }
        sc_labels = {"base": "Base case", "optimistic": "Optimistic",
                     "pessimistic": "Pessimistic", "wildcard": "Wildcard"}
        sc_rows = ""
        for k in ["base", "optimistic", "pessimistic", "wildcard"]:
            sc = scenarios.get(k)
            desc = sc.get("description") if isinstance(sc, dict) else None
            if not desc:
                continue
            pct = probs.get(k)
            pct_s = f" · {pct}%" if pct else ""
            sc_rows += (
                f'<div style="margin-bottom:8px;padding-left:10px;'
                f'border-left:2px solid {sc_colors[k]};">'
                f'<div style="font-family:var(--mono);font-size:10px;'
                f'letter-spacing:0.08em;text-transform:uppercase;'
                f'color:{sc_colors[k]};margin-bottom:2px;">'
                f'{sc_labels[k]}{pct_s}</div>'
                f'<div style="font-size:12.5px;color:var(--ink-2);'
                f'line-height:1.5;">{_escape_dollars(desc)}</div>'
                f'</div>'
            )
        if sc_rows:
            body += (
                '<div style="margin-top:16px;">'
                '<div style="font-family:var(--mono);font-size:10px;'
                'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
                'margin-bottom:8px;">What each scenario means</div>'
                f'{sc_rows}</div>'
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
        # Prefer a real "Category: …" prefix as the tag; otherwise fall back to
        # the severity itself (HIGH/MED/LOW) rather than a redundant "Risk"
        # label on every row. The tag colour is keyed off data-severity in CSS.
        # Only treat the pre-colon text as a category when it is genuinely
        # tag-like (short, a few words). Ordinary prose that merely contains a
        # colon — e.g. "US-China tech tensions persist: …" — must fall back to
        # the severity badge, not be sliced into a truncated fragment.
        prefix = text.split(":", 1)[0] if ":" in text else ""
        tag = prefix if (0 < len(prefix) <= 24 and prefix.count(" ") <= 2) else sev
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
