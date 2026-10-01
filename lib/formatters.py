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
