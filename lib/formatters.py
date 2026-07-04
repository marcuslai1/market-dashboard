"""Pure formatting helpers — no Streamlit dependency.

String/number formatters and threshold→color helpers used by the editorial
renderers. Functions here MUST NOT import ``streamlit`` (so they remain
trivially testable and reusable from non-Streamlit contexts).
"""
from __future__ import annotations

import html

import pandas as pd

from lib.catalog import TICKER_DISPLAY


def display_ticker(tk: str) -> str:
    """Human display form of a watchlist key, e.g. ``000660_KS`` -> ``000660.KS``.

    ``TICKER_DISPLAY`` is a *sparse* override map — it only lists tickers whose
    display needs special glyphs (``CL_F`` -> ``CL=F``, ``VIX`` -> ``^VIX``). It
    does **not** carry the plain underscore-for-dot names, so a raw
    ``TICKER_DISPLAY.get(tk, tk)`` leaks the munged key into the UI for those.
    Prefer the override, then fall back to restoring the dot.
    """
    return TICKER_DISPLAY.get(tk) or str(tk).replace("_", ".")


def rr_display(rr_obj: dict | None) -> tuple[str, float, bool]:
    """Risk:reward for display + ranking, correcting a distorted headline.

    When the report flags the headline R:R as ``rr_distorted`` (a too-tight
    invalidation inflates it — e.g. a 0.2% stop yielding 46.5:1), prefer the
    deeper-stop ``sizing_rr`` — the ratio the writeup itself cites (4.4:1) — and
    report it as adjusted. Falls back to the plain headline otherwise.

    Returns ``(label, ratio, adjusted)`` so callers can render the label *and*
    rank by a ratio that isn't inflated by a tight stop.
    """
    rr_obj = rr_obj or {}
    if rr_obj.get("rr_distorted"):
        sz = rr_obj.get("sizing_rr") or {}
        ratio = sz.get("ratio")
        if ratio is not None:
            label = sz.get("ratio_label") or f"{ratio:.1f}:1"
            return label, float(ratio), True
    return rr_obj.get("ratio_label", ""), float(rr_obj.get("ratio") or 0), False


def _escape_attr(text) -> str:
    """Escape a value destined for an HTML *attribute* value.

    Unlike :func:`_escape_dollars` (text-node only, ``quote=False``), this
    escapes quotes too so a value like ``a" onmouseover="x`` cannot break out of
    ``attr="..."`` and inject new attributes. Use for every dynamic value that
    lands inside ``foo="{...}"``.
    """
    if not text:
        return ""
    return html.escape(str(text), quote=True)


def _safe_href(url) -> str:
    """Sanitise a URL for use inside ``href="..."``.

    Only ``http``/``https`` URLs are allowed through (blocks ``javascript:`` /
    ``data:`` script vectors); the result is attribute-escaped so a stray quote
    or angle bracket cannot break out of the attribute. Anything else → ``""``
    (caller should then omit the link).
    """
    if not url:
        return ""
    s = str(url).strip()
    lowered = s.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return ""
    return html.escape(s, quote=True)


# ── Currency-aware price formatting ──
# HTML-safe prefixes: ``$`` is emitted as ``&#36;`` so Streamlit never parses a
# price as LaTeX math (same reasoning as ``_escape_dollars``). Non-``$`` symbols
# (€ ₩ £ ¥) are literal — they never trigger LaTeX.
_CCY_PREFIX = {
    "USD": "&#36;",
    "SGD": "S&#36;",
    "EUR": "€",
    "KRW": "₩",
    "TWD": "NT&#36;",
    "JPY": "¥",
    "GBP": "£",
    "HKD": "HK&#36;",
}

# Zero-decimal currencies: prices carry no minor unit, so ``,.2f`` invents cents.
_CCY_ZERO_DECIMAL = {"KRW", "JPY"}


def _ccy_prefix(currency) -> str:
    """HTML-safe currency prefix for a price. Unknown/None → ``$``."""
    return _CCY_PREFIX.get(currency or "USD", "&#36;")


def _ccy_decimals(currency) -> int:
    """Decimal places for a price in *currency* (0 for zero-decimal units)."""
    return 0 if currency in _CCY_ZERO_DECIMAL else 2


def _escape_dollars(text: str) -> str:
    """Make report-derived text safe to inject through ``unsafe_allow_html``.

    Two passes, order matters:

    1. **HTML-escape** ``& < >`` so LLM prose like ``"P/E < 15"`` or ``"R&D"``
       can't break the surrounding markup or be swallowed by the browser as a
       bogus tag. ``quote=False`` keeps apostrophes/quotes literal — every call
       site injects into element text, never into an attribute value.
    2. **Neutralize ``$``** so Streamlit never renders it as LaTeX math. Uses
       the HTML numeric entity ``&#36;`` rather than a markdown backslash escape
       (``\\$``): the backslash form only works in pure-markdown text, but inside
       the raw HTML we inject the markdown processor is bypassed, so ``\\$``
       would leak a literal backslash. ``&#36;`` renders as ``$`` in both
       contexts and is never parsed as math.

    The ``$`` step runs *after* HTML-escaping so the ``&`` it introduces is not
    itself turned into ``&amp;``. (Name kept for the many existing call sites.)
    """
    if not text:
        return text
    return html.escape(str(text), quote=False).replace("$", "&#36;")


def _price_str(price, currency: str = "USD") -> str:
    """Format a price with currency-aware prefix + decimals, HTML-safe.

    Uses the currency map so KRW renders ``₩2,560,000`` (right symbol, no bogus
    cents) and EUR/TWD get their own symbols rather than a hard-coded ``$``.
    """
    if price is None or (isinstance(price, float) and pd.isna(price)):
        return "—"
    return f"{_ccy_prefix(currency)}{price:,.{_ccy_decimals(currency)}f}"


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
