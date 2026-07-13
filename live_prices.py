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

import concurrent.futures
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

_ET = ZoneInfo("America/New_York")

# US extended-hours windows (ET). Clock-based rather than asking Yahoo for
# marketState: no extra network call, and holidays self-correct because the
# prepost download simply has no bars inside today's window.
_PRE_START, _PRE_END = dtime(4, 0), dtime(9, 30)
_POST_START, _POST_END = dtime(16, 0), dtime(20, 0)


def _live_quotes_disabled() -> bool:
    """Test hook (mirrors lib/clock.py's TEST_DATE): LIVE_QUOTES_DISABLED=1
    skips the batch entirely. The visual harness needs this because its dead
    proxy only makes each fetch FAIL fast — yfinance's per-ticker fallback
    chain keeps the 12 worker threads hot-looping curl retries after the 4s
    deadline returns, starving the script thread and stalling first render
    past the harness's settle timeout."""
    return os.environ.get("LIVE_QUOTES_DISABLED", "").strip() not in ("", "0")

# Overall wall-clock budget for one live-quote batch. Live prices are on by
# default and fetched on first render, so an unreachable/slow Yahoo must never
# stall the page longer than this — we return whatever completed and fall back to
# the frozen snapshot for the rest. Kept tight (a healthy batch finishes in
# ~1-1.5s) so a struggling Yahoo can't hold the briefing hostage; the Briefing
# also fetches inside a fragment so even this bounded wait is off the main run.
_FETCH_DEADLINE_S = 4

# ── Yahoo symbol map ───────────────────────────────────────────────────
# Loaded from assets/catalog.json so dashboard.py and this module stay in sync.
# Benchmarks: spot index / front-month futures where Yahoo has no spot.
# Watchlist: report-key (underscore-encoded) → Yahoo symbol (dot-encoded).
_CATALOG_PATH = Path(__file__).parent / "assets" / "catalog.json"
TICKER_TO_YAHOO: dict[str, str] = json.loads(
    _CATALOG_PATH.read_text(encoding="utf-8")
)["tickers"]["yahoo"]


def _us_session_now(now: datetime | None = None) -> str | None:
    """"PRE" / "POST" when the US market is in an extended session, else None."""
    now = (now or datetime.now(_ET)).astimezone(_ET)
    if now.weekday() >= 5:
        return None
    t = now.time()
    if _PRE_START <= t < _PRE_END:
        return "PRE"
    if _POST_START <= t < _POST_END:
        return "POST"
    return None


def _us_symbols(mapping: dict[str, str]) -> dict[str, str]:
    """Subset of the catalog map that trades US extended hours.

    Plain Nasdaq/NYSE symbols only: a '.' means a foreign listing (D05.SI,
    IFX.DE), '=' a future (CL=F), '^' an index (^VIX), '-' Yahoo's composite
    symbols (DX-Y.NYB). SPY/QQQ/SOXX pass.
    """
    return {
        key: sym for key, sym in mapping.items()
        if not any(c in sym for c in ".=^-")
    }


def _session_window(session: str, now: datetime) -> tuple[datetime, datetime]:
    start, end = (_PRE_START, _PRE_END) if session == "PRE" else (_POST_START, _POST_END)
    day = now.astimezone(_ET).date()
    return (datetime.combine(day, start, tzinfo=_ET),
            datetime.combine(day, end, tzinfo=_ET))


def _fetch_ext_bars(symbols: list[str]):
    """Batched 1-minute prepost bars for the US names. None on any failure.

    One yf.download call (~0.9s for 26 symbols, measured 2026-07-13) instead of
    per-ticker .info (~0.6s each): the whole thing hides inside the fast_info
    batch's wall-clock, keeping the 4s deadline honest.
    """
    try:
        import yfinance as yf
        return yf.download(
            symbols, period="1d", interval="1m", prepost=True,
            progress=False, threads=True,
        )
    except Exception:
        return None


def _ext_quotes_from_bars(
    bars, session: str, now: datetime, sym_to_key: dict[str, str]
) -> dict[str, float]:
    """{report_key: extended-hours price} from a prepost download frame.

    Only bars stamped inside TODAY's current session window count — Friday's
    regular-session tail (or a holiday's stale bars) never leaks in as a fake
    pre-market print. Symbols with no in-window trade are simply absent.
    """
    out: dict[str, float] = {}
    if bars is None or getattr(bars, "empty", True):
        return out
    try:
        closes = bars["Close"]
    except Exception:
        return out
    win_start, win_end = _session_window(session, now)
    try:
        in_window = closes.loc[(closes.index >= win_start) & (closes.index < win_end)]
    except TypeError:
        return out  # tz-naive index — can't trust it against an ET window
    if in_window.empty:
        return out
    for sym, key in sym_to_key.items():
        if sym not in in_window.columns:
            continue
        col = in_window[sym].dropna()
        if col.empty:
            continue
        out[key] = float(col.iloc[-1])
    return out


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
        if last is None:
            return None
        last_f = float(last)
        if prev is None or float(prev) == 0:
            # Days-old listing (e.g. SKHYV the week of its IPO): Yahoo has a
            # live print but no previous_close yet. A live price with an
            # unknown Δ beats silently freezing the row at the snapshot.
            return {"price": last_f, "chg_pct": None}
        prev_f = float(prev)
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
    if _live_quotes_disabled():
        out["__meta__"] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_ok": 0,
            "n_total": len(items),
            "session": None,
        }
        return out
    session = _us_session_now()
    us = _us_symbols(TICKER_TO_YAHOO) if session else {}
    now_et = datetime.now(_ET)
    t0 = time.monotonic()
    # Not using the context manager: its __exit__ calls shutdown(wait=True), which
    # would block on stragglers and defeat the deadline. We cancel/return instead.
    pool = ThreadPoolExecutor(max_workers=12)
    try:
        # The prepost download rides the same pool and deadline as the
        # fast_info batch; measured ~0.9s, it finishes well inside the batch.
        ext_fut = pool.submit(_fetch_ext_bars, list(us.values())) if us else None
        futures = {pool.submit(_fetch_one, sym): key for key, sym in items}
        try:
            for fut in as_completed(futures, timeout=_FETCH_DEADLINE_S):
                quote = fut.result()
                if quote is not None:
                    out[futures[fut]] = quote
        except concurrent.futures.TimeoutError:
            pass  # Yahoo slow/unreachable — keep what completed, fall back for the rest.
        if ext_fut is not None:
            try:
                remaining = max(0.05, _FETCH_DEADLINE_S - (time.monotonic() - t0))
                bars = ext_fut.result(timeout=remaining)
                ext = _ext_quotes_from_bars(
                    bars, session, now_et, {sym: key for key, sym in us.items()}
                )
            except Exception:
                ext = {}  # ext quotes are garnish — never fail the batch over them
            for key, ext_price in ext.items():
                q = out.get(key)
                base = (q or {}).get("price")
                if not q or not base:
                    continue  # no regular quote → no Δ base → skip
                q["ext_price"] = ext_price
                q["ext_chg_pct"] = (ext_price - base) / base * 100
                q["ext_session"] = session
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    out["__meta__"] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_ok": len(out),
        "n_total": len(items),
        "session": session,
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

    def _apply(entry: dict, q: dict) -> dict:
        ne = dict(entry)
        if q.get("ext_price"):
            # Extended session: show the pre/post print, Δ vs last regular
            # close (matches IBKR / Yahoo's own pre-market %), and tag the
            # entry so renderers can mark it PRE/POST.
            ne["price"] = q["ext_price"]
            ne["chg_pct"] = q["ext_chg_pct"]
            ne["live_session"] = q.get("ext_session")
        else:
            ne["price"] = q["price"]
            ne["chg_pct"] = q["chg_pct"]
        return ne

    out = dict(report)
    benchmarks = dict(report.get("benchmarks", {}))
    for key, b in list(benchmarks.items()):
        q = live.get(key)
        if not q:
            continue
        benchmarks[key] = _apply(b, q)
    out["benchmarks"] = benchmarks

    watchlist = dict(report.get("watchlist", {}))
    for key, d in list(watchlist.items()):
        q = live.get(key)
        if not q:
            continue
        watchlist[key] = _apply(d, q)
    out["watchlist"] = watchlist
    return out
