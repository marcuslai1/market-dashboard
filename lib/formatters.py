"""Pure formatting helpers — no Streamlit dependency.

String/number formatters and threshold→color helpers used by the editorial
renderers. Functions here MUST NOT import ``streamlit`` (so they remain
trivially testable and reusable from non-Streamlit contexts).
"""
from __future__ import annotations

import pandas as pd


def _escape_dollars(text: str) -> str:
    """Escape $ signs so Streamlit doesn't render them as LaTeX."""
    return text.replace("$", "\\$") if text else text


def _truncate_rationale(text: str) -> str:
    """Show the first 1-2 complete sentences of the rationale."""
    if not text:
        return text
    # Find the second sentence boundary to capture 1-2 full sentences
    end = -1
    for i, ch in enumerate(text):
        if ch == '.' and i + 1 < len(text) and text[i + 1] == ' ':
            if end == -1:
                end = i + 1  # first sentence
            else:
                end = i + 1  # second sentence
                break
    # If text ends with a period (single sentence, no trailing space)
    if end == -1 and text.rstrip().endswith('.'):
        return text.rstrip()
    if end == -1:
        return text  # no sentence boundary found, show all
    return text[:end]


def _price_str(price, currency: str = "USD") -> str:
    """Format a price with currency-aware prefix, escaped for Streamlit."""
    if price is None:
        return "—"
    pfx = "S\\$" if currency == "SGD" else "\\$"
    return f"{pfx}{price:,.2f}"


# ── Metric color helpers ──
def _metric_bg(value: float | None, thresholds: list[tuple[object, str]],
               default: str = "transparent") -> str:
    """Return a muted background color for a metric value.

    *thresholds* is a list of (test, color) pairs evaluated in order.
    Each *test* is a callable ``(value) -> bool``.
    """
    if value is None:
        return default
    for test, color in thresholds:
        if test(value):
            return color
    return default


_GREEN_BG = "#1a3a2a"
_ORANGE_BG = "#3a2a1a"
_RED_BG = "#3a1a1a"

_RSI_THRESHOLDS: list[tuple[object, str]] = [
    (lambda v: v < 40, _GREEN_BG),
    (lambda v: v > 70, _RED_BG),
]

_VS_SMA50_THRESHOLDS: list[tuple[object, str]] = [
    (lambda v: v > 5, _RED_BG),
    (lambda v: 2 < v <= 5, _ORANGE_BG),
    (lambda v: -2 <= v <= 2, _GREEN_BG),
    (lambda v: v < -2, _GREEN_BG),
]

_RR_THRESHOLDS: list[tuple[object, str]] = [
    (lambda v: v >= 2.0, _GREEN_BG),
    (lambda v: 1.0 <= v < 2.0, _ORANGE_BG),
    (lambda v: v < 1.0, _RED_BG),
]


def _delta_class(chg, inverse=False) -> str:
    if chg is None or (isinstance(chg, float) and pd.isna(chg)) or chg == 0:
        return "flat"
    up = chg > 0
    if inverse:
        return "down" if up else "up"
    return "up" if up else "down"


def _fmt_num(n, decimals=2) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "—"
    return f"{float(n):,.{decimals}f}"


def _sign(n) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return ""
    return "+" if n > 0 else ""


def _writeup_for_render(d: dict) -> dict:
    """Return {headline, prior_period_delta_narrative, what_to_do, entry_block} from
    new schema, or shim from legacy.

    For old reports that only have signal_rationale: headline = first sentence,
    what_to_do = remaining sentences (or None for HOLD / CAUTION-technical), and
    entry_block reads the top-level mechanical entry_block field.
    """
    wu = d.get("writeup")
    if isinstance(wu, dict):
        return {
            "headline": wu.get("headline") or "",
            "prior_period_delta_narrative": wu.get("prior_period_delta_narrative"),
            "what_to_do": wu.get("what_to_do"),
            "entry_block": wu.get("entry_block") or d.get("entry_block"),
        }
    rat = (d.get("signal_rationale") or "").strip()
    if not rat:
        return {"headline": "", "prior_period_delta_narrative": None, "what_to_do": None, "entry_block": d.get("entry_block")}
    # Split first sentence as headline, rest as what_to_do.
    headline = rat
    rest = ""
    for i, ch in enumerate(rat):
        if ch == "." and i + 1 < len(rat) and rat[i + 1] == " ":
            headline = rat[: i + 1]
            rest = rat[i + 2 :].strip()
            break
    # Suppress what_to_do for signals where new schema mandates null.
    sig = d.get("signal", "")
    cs = d.get("caution_source", "")
    if sig == "HOLD":
        rest = ""
    elif sig == "CAUTION" and cs == "hard_block":
        # Mechanical block, treat as technical_only — entry_block carries the gate.
        rest = ""
    return {
        "headline": headline,
        "prior_period_delta_narrative": None,
        "what_to_do": rest or None,
        "entry_block": d.get("entry_block"),
    }


def _legacy_rationale_from(d: dict) -> str:
    """Flatten the writeup into one string for legacy views (Historical
    Writeup Viewer, Compare-dates Rationale column). Concatenates
    headline + prior_period_delta_narrative + what_to_do for the new schema;
    falls back to signal_rationale for old reports.
    """
    wu = d.get("writeup")
    if isinstance(wu, dict):
        h = (wu.get("headline") or "").strip()
        delta = (wu.get("prior_period_delta_narrative") or "").strip()
        wt = (wu.get("what_to_do") or "").strip()
        pieces = [p for p in (h, delta, wt) if p]
        return " ".join(pieces)
    return d.get("signal_rationale", "") or ""
