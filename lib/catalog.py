"""Static catalog constants: signal palette, ticker metadata, lookup tables.

Loaded once at import time from ``assets/catalog.json``. Contains only data —
no Streamlit calls and no functions. Renderers import these names and read
from them; no module mutates them after load.
"""
from __future__ import annotations

import json
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

_CATALOG = json.loads((ASSETS_DIR / "catalog.json").read_text(encoding="utf-8"))

# Tickers removed from the watchlist — filter from all dashboard views.
# Historical data is preserved in the raw JSONs/SQLite if needed.
RETIRED_TICKERS = set(_CATALOG["tickers"]["retired"])

SIGNAL_COLORS = _CATALOG["signals"]["colors"]

# Streamlit markdown only supports named colors (:red[text], :green[text], etc.)
SIGNAL_ST_COLORS = _CATALOG["signals"]["st_colors"]

SIGNAL_VERBS = _CATALOG["signals"]["verbs"]

# Reverse ticker_to_key: restore dots/hyphens/carets for display
TICKER_DISPLAY = _CATALOG["tickers"]["display"]

CLUSTER_MAP = _CATALOG["tickers"]["cluster"]

SIGNAL_ORDER = _CATALOG["signals"]["order"]
WRITEUP_SIGNALS = set(_CATALOG["signals"]["writeup"])
ACTIONABLE_SIGNALS = set(_CATALOG["signals"]["actionable"])

# Single-source signal ranking, derived from SIGNAL_ORDER so nothing hand-maintains
# a parallel {"BUY": 5, ...} map (they had already drifted on AVOID). SIGNAL_ORDER
# is best→worst, so:
#   SIGNAL_SORT_RANK  — 0-based, lower = more bullish (watchlist/list sort order)
#   SIGNAL_BULLISHNESS — higher = more bullish (upgrade/downgrade direction)
SIGNAL_SORT_RANK = {sig: i for i, sig in enumerate(SIGNAL_ORDER)}
SIGNAL_BULLISHNESS = {sig: len(SIGNAL_ORDER) - i for i, sig in enumerate(SIGNAL_ORDER)}

# Signal palette tints (used by sig_pill_html for backgrounds)
SIGNAL_TINTS = _CATALOG["signals"]["tints"]

PULSE_ORDER = [
    ("SPY",   "S&P 500",     False),
    ("QQQ",   "Nasdaq 100",  False),
    ("VIX",   "Fear gauge",  True),
    ("WTI",   "Crude oil",   False),
    ("Gold",  "Gold",        False),
    ("DXY",   "Dollar idx",  False),
    ("US10Y", "10-yr yield", False),
    ("SOXX",  "Semis ETF",   False),
]
