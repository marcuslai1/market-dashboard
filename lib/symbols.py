"""Report-key ↔ provider-symbol mapping, shared by every frame that joins them.

Report JSONs and ``signal_log.csv`` / ``paper_*.csv`` use sanitized keys
(``000660_KS``); ``market_data.csv`` carries the provider's dotted symbols
(``000660.KS``). The Tracker always converted; the price loader's retired-
ticker filter compared sanitized keys to dotted symbols and so only dropped
the two unsuffixed US names (external review R12 F11, 2026-09-15).
"""
from __future__ import annotations

from lib.catalog import RETIRED_TICKERS


def provider_symbol(key: str) -> str:
    """``D05_SI`` → ``D05.SI``; US keys (no exchange suffix) pass through."""
    last_us = key.rfind("_")
    if last_us > 0:
        suffix = key[last_us + 1:]
        if suffix.isalpha() and suffix.isupper() and 1 <= len(suffix) <= 3:
            return key[:last_us] + "." + suffix
    return key


# Both spellings, so a frame in either key space filters correctly.
RETIRED_ANY_SPELLING = RETIRED_TICKERS | {provider_symbol(k) for k in RETIRED_TICKERS}
