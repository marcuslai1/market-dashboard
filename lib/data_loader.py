"""Cached data loaders.

All loaders use ``@st.cache_data`` so repeat reads inside one Streamlit
session are O(1). Cache keys are the function's qualified name + arg values
+ the function's source; keep signatures stable when moving files.

Every loader is **mtime-keyed** (public wrapper stats the file/dir, cached
impl takes ``(path, mtime)``): reruns pay a cheap ``stat()``, and a rewritten
file busts its cache entry on the next rerun — so a fresh pipeline run is
visible immediately, with no TTL lag and no manual Refresh (review P2-5).
Two contract notes: the mtime param must NOT be ``_``-prefixed
(``st.cache_data`` would drop it from the key and serve stale content), and
caches carry ``max_entries`` so mtime churn can't grow memory unbounded.

Paths are resolved relative to the project root (parent of ``lib/``).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from lib.catalog import RETIRED_TICKERS

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _PROJECT_ROOT / "data"


def _mtime(path: Path) -> float:
    """The file's mtime for cache keying, or ``0.0`` when it doesn't exist.

    ``0.0`` (rather than raising) keeps missing-file handling in the cached
    impls; when the file later appears its real mtime busts the stale entry.
    """
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False, max_entries=8)
def _read_text_asset(path: str, mtime: float) -> str:
    """Read a UTF-8 text asset. Cached by (path, mtime).

    ``mtime`` is part of the cache key: editing the file changes its mtime and
    busts the entry, so an edited asset hot-reloads on the next rerun while an
    unchanged one skips the disk read entirely. (It must NOT be named with a
    leading underscore — ``st.cache_data`` excludes ``_``-prefixed params from
    the key, which would make the cache serve stale content.)
    """
    return Path(path).read_text(encoding="utf-8")


def load_text_asset(path: str | Path) -> str:
    """Return a text asset's contents, cached until the file's mtime changes.

    Used for the ~49KB ``assets/theme.css`` injected on every Streamlit rerun:
    the naive ``Path(...).read_text()`` at module scope re-read the whole file
    on each interaction. A ``stat()`` per rerun is orders of magnitude cheaper
    than decoding 49KB, and the content still reflects live edits.
    """
    p = Path(path)
    return _read_text_asset(str(p), p.stat().st_mtime)


def _safe_read_csv(csv_path: Path) -> pd.DataFrame:
    """Read a CSV, returning an empty frame (not raising) on any read failure.

    A truncated, locked, or malformed export used to crash the whole page; this
    fails soft the same way ``load_all_reports`` does for bad JSON.
    """
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(csv_path)
    except (OSError, ValueError, UnicodeDecodeError, pd.errors.ParserError,
            pd.errors.EmptyDataError):
        st.sidebar.warning(f"Skipped unreadable data file: {csv_path.name}")
        return pd.DataFrame()


@st.cache_data(max_entries=2)
def _load_all_reports_cached(fingerprint: tuple) -> dict[str, dict]:
    """Parse every report path in *fingerprint* — ((path, mtime), …).

    The fingerprint is both the cache key and the file list: any added,
    removed, or rewritten report file produces a different tuple and re-parses
    the corpus. ``max_entries=2`` because each entry holds ~9MB of parsed JSON.
    """
    reports = {}
    for path_str, _unused_mtime in fingerprint:
        f = Path(path_str)
        date_str = f.stem.replace("morning_report_", "")
        try:
            reports[date_str] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            st.sidebar.warning(f"Skipped malformed report: {f.name} — {e}")
        except OSError:
            continue
    return reports


def load_all_reports() -> dict[str, dict]:
    """Load all morning_report JSON files, keyed by date string."""
    fingerprint = tuple(
        (str(f), _mtime(f)) for f in sorted(DATA_DIR.glob("morning_report_*.json"))
    )
    return _load_all_reports_cached(fingerprint)


def data_fingerprint() -> tuple:
    """Cheap ``(path, mtime)`` fingerprint of the report corpus + price CSV.

    Changes whenever any report file or ``market_data.csv`` is added, removed,
    or rewritten. Pages use it as the ``st.cache_data`` key for expensive
    derived frames (Signal Tracker episodes/accuracy — review P7-2) so the
    heavy inputs themselves never need hashing.
    """
    prices_csv = DATA_DIR / "market_data.csv"
    return (
        *((str(f), _mtime(f)) for f in sorted(DATA_DIR.glob("morning_report_*.json"))),
        (str(prices_csv), _mtime(prices_csv)),
    )


@st.cache_data(max_entries=8)
def _list_report_dates_cached(dir_str: str, dir_mtime: float) -> list[str]:
    return sorted(
        f.stem.replace("morning_report_", "")
        for f in Path(dir_str).glob("morning_report_*.json")
    )


def list_report_dates() -> list[str]:
    """Ascending list of available report dates, from filenames only.

    Hot-path pages (masthead, Briefing, Watchlist) need the set of dates but not
    every report body. Reading directory entries avoids decoding ~9MB of JSON
    just to learn which dates exist. Keyed by the directory's mtime — creating
    or deleting a report file updates it, so a new date appears on the next
    rerun; callers then ``load_report`` the one or two they actually render.
    """
    return _list_report_dates_cached(str(DATA_DIR), _mtime(DATA_DIR))


@st.cache_data(max_entries=128)
def _load_json_cached(path_str: str, mtime: float) -> dict:
    """JSON-parse one file, ``{}`` on any failure. Cached by (path, mtime)."""
    try:
        return json.loads(Path(path_str).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_report(date_str: str) -> dict:
    """Load a single morning_report JSON by date. ``{}`` if missing/malformed.

    Cached per (date, mtime), so pages needing only the latest one or two
    reports don't pay to parse the whole corpus the way ``load_all_reports``
    does — and a regenerated file is picked up on the next rerun. Fails soft
    (returns ``{}``) exactly like the other loaders so a truncated file degrades
    to an empty view rather than crashing the page.
    """
    path = DATA_DIR / f"morning_report_{date_str}.json"
    if not path.exists():
        return {}
    return _load_json_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_sqlite_prices_cached(path_str: str, mtime: float) -> pd.DataFrame:
    df = _safe_read_csv(Path(path_str))
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        if "ticker" in df.columns:
            df = df[~df["ticker"].isin(RETIRED_TICKERS)]
    return df


def load_sqlite_prices() -> pd.DataFrame:
    """Load price history from CSV export."""
    path = DATA_DIR / "market_data.csv"
    return _load_sqlite_prices_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_paper_nav_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return _safe_read_csv(Path(path_str))


def load_paper_nav() -> pd.DataFrame:
    """Daily paper-portfolio NAV series (``data/paper_nav.csv``), or empty.

    Exported by the pipeline from its ``paper_portfolio_nav`` table (spec
    2026-07-05-paper-book-band-design): ``policy_id, date, nav_units,
    cash_units, n_positions, spy_close, soxx_close``. Raw frame — date
    parsing and policy selection live in the band's reducers. Missing file
    (every checkout until the pipeline first exports it) → empty frame.
    """
    path = DATA_DIR / "paper_nav.csv"
    return _load_paper_nav_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_paper_trades_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return _safe_read_csv(Path(path_str))


def load_paper_trades() -> pd.DataFrame:
    """Completed paper-book round-trips (``data/paper_trades.csv``), or empty.

    Exported by the pipeline (spec 2026-07-17-paper-trade-history-design):
    ``policy_id, ticker, entry_date, avg_entry_price, tranches, exit_date,
    exit_price, exit_reason, pnl_pct, pnl_units``, one row per closed
    position. Raw frame — date parsing, policy selection, and the
    units→dollars transform live in the band's reducers. Missing file (every
    checkout until the pipeline first exports it) → empty frame.
    """
    path = DATA_DIR / "paper_trades.csv"
    return _load_paper_trades_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_paper_positions_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return _safe_read_csv(Path(path_str))


def load_paper_positions() -> pd.DataFrame:
    """Open paper-book positions across every lane
    (``data/paper_positions.csv``), or empty.

    Exported by the pipeline (spec 2026-07-17-paper-trade-history-design,
    addendum 2): ``policy_id, ticker, entry_date, avg_entry_price, tranches,
    qty, invested_units, last_close, fx_rate, stop_price, max_dd_pct``, one
    row per open position. Raw frame — the pot scaling lives in the band's
    reducers. Missing file → empty frame.
    """
    path = DATA_DIR / "paper_positions.csv"
    return _load_paper_positions_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_pipeline_stats_cached(path_str: str, mtime: float) -> pd.DataFrame:
    df = _safe_read_csv(Path(path_str))
    if df.empty:
        return df
    extra_cols = ["yfinance_articles", "yfinance_chars", "tavily_articles",
                  "tavily_chars", "system_prompt_chars", "watchlist_data_chars",
                  "memory_chars", "total_prompt_chars", "computed_cost_usd",
                  "cache_hit_tokens", "cache_miss_tokens"]
    # Ensure all expected columns exist (fill missing with NaN)
    for c in extra_cols:
        if c not in df.columns:
            df[c] = float("nan")
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_pipeline_stats() -> pd.DataFrame:
    """Load pipeline article stats from CSV export."""
    path = DATA_DIR / "pipeline_stats.csv"
    return _load_pipeline_stats_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_token_usage_cached(path_str: str, mtime: float) -> pd.DataFrame:
    df = _safe_read_csv(Path(path_str))
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_token_usage() -> pd.DataFrame:
    """Load Claude API usage from CSV export."""
    path = DATA_DIR / "claude_analysis.csv"
    return _load_token_usage_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_signal_log_cached(path_str: str, mtime: float) -> pd.DataFrame:
    df = _safe_read_csv(Path(path_str))
    if df.empty or "date" not in df.columns:
        return df
    df["date"] = pd.to_datetime(df["date"])
    for col in ["price_after_5d", "price_after_10d", "price_after_20d",
                "entry_price", "invalidation", "upside_target", "rr_ratio"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for horizon in ["5d", "10d", "20d"]:
        pa = f"price_after_{horizon}"
        if pa in df.columns:
            df[f"return_{horizon}"] = (df[pa] - df["entry_price"]) / df["entry_price"] * 100
    return df


def load_signal_log() -> pd.DataFrame:
    """Load signal_evaluation_log export (paper-trade outcomes)."""
    path = DATA_DIR / "signal_log.csv"
    return _load_signal_log_cached(str(path), _mtime(path))


def load_capex_quarterly() -> dict:
    """Hand-maintained quarterly capex file for the AI Capex Pulse band.

    ``{}`` when missing/malformed (band degrades, never crashes); validation
    and row-dropping live in ``lib.capex.parse_capex``, not here.
    """
    path = DATA_DIR / "capex_quarterly.json"
    if not path.exists():
        return {}
    return _load_json_cached(str(path), _mtime(path))


def load_earnings_cascades() -> dict:
    """Hand-maintained earnings-cascade config (pre-wired bull/bear reads)."""
    path = DATA_DIR / "earnings_cascades.json"
    if not path.exists():
        return {}
    return _load_json_cached(str(path), _mtime(path))


def load_changelog() -> list:
    """Hand-maintained methodology change log for the Signal Tracker's
    'what we've changed' strip. ``[]`` when missing/malformed (section is
    simply skipped)."""
    path = DATA_DIR / "changelog.json"
    if not path.exists():
        return []
    data = _load_json_cached(str(path), _mtime(path))
    return data if isinstance(data, list) else []


def load_report_memory() -> dict:
    """Load report_memory.json for narrative tracking."""
    mem_path = DATA_DIR / "report_memory.json"
    # Also check legacy path for local development
    if not mem_path.exists():
        mem_path = _PROJECT_ROOT / "market_data" / "report_memory.json"
    if not mem_path.exists():
        return {}
    return _load_json_cached(str(mem_path), _mtime(mem_path))
