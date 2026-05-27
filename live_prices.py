"""Live Yahoo Finance quote overlay for the MarketReport dashboard.

Maps every benchmark + watchlist key used in the morning-report JSONs to its
Yahoo Finance symbol, fetches last_price / previous_close in parallel, and
returns a {report_key: {price, chg_pct}} dict the dashboard can overlay onto
the static snapshot.

Designed to fail soft: a missing symbol, a thrown yfinance exception, or
yfinance not being installed at all returns an empty dict so the dashboard
falls back to the report-snapshot values.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import streamlit as st


# ── Yahoo symbol map ───────────────────────────────────────────────────
# Benchmarks: spot index / front-month futures where Yahoo has no spot.
# Watchlist: report-key (underscore-encoded) → Yahoo symbol (dot-encoded).
TICKER_TO_YAHOO: dict[str, str] = {
    # Benchmarks
    "SPY":   "SPY",
    "QQQ":   "QQQ",
    "DXY":   "DX-Y.NYB",
    "WTI":   "CL=F",
    "Gold":  "GC=F",
    "VIX":   "^VIX",
    "US10Y": "^TNX",
    "SOXX":  "SOXX",
    # Watchlist — US
    "NVDA":  "NVDA", "AMD": "AMD", "INTC": "INTC", "MU": "MU",
    "TSM":   "TSM",  "TSEM": "TSEM", "AVGO": "AVGO", "ASML": "ASML",
    "AMZN":  "AMZN", "GOOG": "GOOG", "MSFT": "MSFT",
    "LITE":  "LITE", "NOK":  "NOK",  "BE":   "BE",
    "PLTR":  "PLTR", "WRD":  "WRD",  "SITM": "SITM",
    "CRWV":  "CRWV", "CBRS": "CBRS",
    # Watchlist — non-US (suffix-based)
    "D05_SI":    "D05.SI",
    "O39_SI":    "O39.SI",
    "U11_SI":    "U11.SI",
    "IFX_DE":    "IFX.DE",
    "AIXA_DE":   "AIXA.DE",
    "2308_TW":   "2308.TW",
    "000660_KS": "000660.KS",
}


def _fetch_one(yahoo_sym: str) -> dict | None:
    """Pull last_price + previous_close for a single symbol. None on any error."""
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        fi = yf.Ticker(yahoo_sym).fast_info
        # yfinance FastInfo exposes attributes in snake_case but its .get()
        # uses camelCase keys — use attribute access for consistency across
        # versions.
        last = getattr(fi, "last_price", None)
        prev = getattr(fi, "previous_close", None)
        if last is None or prev is None:
            return None
        last_f = float(last)
        prev_f = float(prev)
        if prev_f == 0:
            return None
        return {
            "price":   last_f,
            "chg_pct": (last_f - prev_f) / prev_f * 100,
        }
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_live_quotes() -> dict:
    """Return {report_key: {price, chg_pct}} for every mapped ticker.

    Cached for 60s so a page rerun doesn't hammer Yahoo. Missing or failed
    symbols are simply absent from the dict (caller falls back to snapshot).
    Includes a synthetic "__meta__" entry with the fetch timestamp and the
    number of successful quotes for the freshness caption.
    """
    out: dict[str, dict] = {}
    items = list(TICKER_TO_YAHOO.items())
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(_fetch_one, sym): key for key, sym in items}
        for fut in as_completed(futures):
            key = futures[fut]
            quote = fut.result()
            if quote is not None:
                out[key] = quote
    out["__meta__"] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_ok": len(out),
        "n_total": len(items),
    }
    return out


def overlay_live(report: dict, live: dict) -> dict:
    """Return a shallow copy of `report` with live price + chg_pct overlaid.

    Mutates only the `price` and `chg_pct` fields inside each benchmark and
    watchlist entry. All other snapshot fields (sma50, rsi, 1mo_pct, …) are
    left as-is — they're computed off historical bars and would be misleading
    if we partially refreshed them.
    """
    if not live:
        return report
    out = dict(report)
    benchmarks = dict(report.get("benchmarks", {}))
    for key, b in list(benchmarks.items()):
        q = live.get(key)
        if not q:
            continue
        nb = dict(b)
        nb["price"] = q["price"]
        nb["chg_pct"] = q["chg_pct"]
        benchmarks[key] = nb
    out["benchmarks"] = benchmarks

    watchlist = dict(report.get("watchlist", {}))
    for key, d in list(watchlist.items()):
        q = live.get(key)
        if not q:
            continue
        nd = dict(d)
        nd["price"] = q["price"]
        nd["chg_pct"] = q["chg_pct"]
        watchlist[key] = nd
    out["watchlist"] = watchlist
    return out
