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

from lib.symbols import RETIRED_ANY_SPELLING

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
            # Provider symbols are dotted (2308.TW); the catalog's retired
            # list is sanitized (2308_TW). Filter on both spellings — the
            # sanitized-only test dropped COHR/XLE and leaked four foreign
            # retired names (R12 F11, 2026-09-15).
            df = df[~df["ticker"].isin(RETIRED_ANY_SPELLING)]
    return df


def load_sqlite_prices() -> pd.DataFrame:
    """Load price history from CSV export."""
    path = DATA_DIR / "market_data.csv"
    return _load_sqlite_prices_cached(str(path), _mtime(path))


@st.cache_data(max_entries=4)
def _load_earnings_history_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return _safe_read_csv(Path(path_str))


def load_earnings_history() -> pd.DataFrame:
    """Quarter-on-quarter earnings archive (``data/earnings_history.csv``), or empty.

    Exported by the pipeline from its ``earnings_history`` table (spec
    2026-07-24-earnings-history-archive): per (ticker, quarter) EPS
    estimate/actual/surprise, revenue actual/estimate/YoY, margins. Raw frame —
    the watchlist page groups it per ticker for the drill-down table. Missing
    file (every checkout until the pipeline first exports it) → empty frame, and
    the drill-down section stays silent.
    """
    path = DATA_DIR / "earnings_history.csv"
    return _load_earnings_history_cached(str(path), _mtime(path))


def load_revenue_estimates() -> dict:
    """Web-sourced past revenue estimates + a few missing actuals (``data/revenue_estimates.json``,
    hand-curated 2026-09-29, every value with its provider and source). ``{}`` when absent."""
    path = DATA_DIR / "revenue_estimates.json"
    if not path.exists():
        return {}
    return _load_json_cached(str(path), _mtime(path))


def load_earnings_map() -> dict:
    """``{ticker: records newest-first}`` — the earnings CSV with the revenue backfill folded in
    (``components.earnings_chart.merge_backfill``). The Watchlist drawer and the briefing read this
    one map, so both show the same numbers."""
    from components.earnings_chart import merge_backfill

    df = load_earnings_history()
    backfill = load_revenue_estimates()
    out: dict = {}
    if not df.empty and "ticker" in df.columns:
        for tkey, grp in df.groupby("ticker", sort=False):
            out[tkey] = grp.to_dict("records")
    for tkey in set(out) | {k for k in backfill if not k.startswith("_")}:
        out[tkey] = merge_backfill(out.get(tkey, []), backfill.get(tkey))
    return out


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
    """Load signal_evaluation_log export (the pipeline's call ledger: signals and their matured outcomes)."""
    path = DATA_DIR / "signal_log.csv"
    return _load_signal_log_cached(str(path), _mtime(path))


def load_changelog() -> list:
    """Hand-maintained methodology change log for the Signal Tracker's
    'what we've changed' strip. ``[]`` when missing/malformed (section is
    simply skipped)."""
    path = DATA_DIR / "changelog.json"
    if not path.exists():
        return []
    data = _load_json_cached(str(path), _mtime(path))
    return data if isinstance(data, list) else []


def load_market_reads() -> dict:
    """Experimental market-read card payload (`market_read.py publish` upstream).

    ``{}`` when absent — the read is on-demand, so "never published" is a normal
    state on a fresh clone and the card is simply skipped.
    """
    path = DATA_DIR / "market_reads.json"
    if not path.exists():
        return {}
    data = _load_json_cached(str(path), _mtime(path))
    return data if isinstance(data, dict) else {}


def load_briefings() -> dict:
    """Daily briefing card payload (MarketReport `scripts/briefing.py publish`).

    ``{}`` when absent — the briefing is written by hand in the terminal, so "never
    published" is a normal state and the card is simply skipped.
    """
    path = DATA_DIR / "briefings.json"
    if not path.exists():
        return {}
    data = _load_json_cached(str(path), _mtime(path))
    return data if isinstance(data, dict) else {}


def load_report_memory() -> dict:
    """Load report_memory.json for narrative tracking."""
    mem_path = DATA_DIR / "report_memory.json"
    # Also check legacy path for local development
    if not mem_path.exists():
        mem_path = _PROJECT_ROOT / "market_data" / "report_memory.json"
    if not mem_path.exists():
        return {}
    return _load_json_cached(str(mem_path), _mtime(mem_path))
