"""Static catalog constants: tone palette, ticker metadata, lookup tables.

Loaded once at import time from ``assets/catalog.json``. Contains only data —
no Streamlit calls and no functions. Renderers import these names and read
from them; no module mutates them after load.

The signal palette, verbs and ranks left on 2026-10-01 with the labels
(MarketReport spec 2026-10-01-info-only-watchlist; tag ``pre-label-removal``).
The colours themselves stay, renamed to neutral roles (``TONE_COLORS``).
"""
from __future__ import annotations

import json
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

_CATALOG = json.loads((ASSETS_DIR / "catalog.json").read_text(encoding="utf-8"))

# Tickers removed from the watchlist — filter from all dashboard views.
# Historical data is preserved in the raw JSONs/SQLite if needed.
RETIRED_TICKERS = set(_CATALOG["tickers"]["retired"])

# Neutral colour roles (pos / info / warn / muted / neg / neg_deep). The CSS
# tokens --tone-* in assets/theme.css hand-mirror these values.
TONE_COLORS = _CATALOG["tones"]["colors"]
TONE_TINTS = _CATALOG["tones"]["tints"]

# Reverse ticker_to_key: restore dots/hyphens/carets for display
TICKER_DISPLAY = _CATALOG["tickers"]["display"]

# Report key → cluster name. Mirrors MarketReport ``config.CLUSTER_MAP``; the
# Watchlist groups and orders by it until reports carry their own ``cluster``.
CLUSTER_MAP = _CATALOG["tickers"]["cluster"]

# Decision-relevant tape — 5 benchmarks (design-spec §7). WTI / Gold / DXY were
# dropped from the tape in the 2026-07 overhaul: they are macro context, carried
# narratively in the Macro note rather than as standing tiles (overhaul-plan §C6).
PULSE_ORDER = [
    ("SPY",   "S&P 500",     False),
    ("QQQ",   "Nasdaq 100",  False),
    ("VIX",   "Fear gauge",  True),
    ("US10Y", "10-yr yield", False),
    ("SOXX",  "Semis ETF",   False),
    # USD/SGD (2026-09-29, owner: USD assets, lives in SGD). inverse=None = neutral
    # ink: a currency pair has no good direction for a reader (colour is a claim).
    ("USDSGD", "S$ per US$", None),
]
