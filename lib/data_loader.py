"""Cached data loaders.

All loaders use ``@st.cache_data`` so repeat reads inside one Streamlit
session are O(1). Cache keys are the function's qualified name + arg values
+ the function's source; keep signatures stable when moving files.

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


@st.cache_data(ttl=300)
def load_all_reports() -> dict[str, dict]:
    """Load all morning_report JSON files, keyed by date string."""
    reports = {}
    for f in sorted(DATA_DIR.glob("morning_report_*.json")):
        date_str = f.stem.replace("morning_report_", "")
        try:
            reports[date_str] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            st.sidebar.warning(f"Skipped malformed report: {f.name} — {e}")
        except OSError:
            continue
    return reports


@st.cache_data(ttl=300)
def load_sqlite_prices() -> pd.DataFrame:
    """Load price history from CSV export."""
    df = _safe_read_csv(DATA_DIR / "market_data.csv")
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        if "ticker" in df.columns:
            df = df[~df["ticker"].isin(RETIRED_TICKERS)]
    return df


@st.cache_data(ttl=300)
def load_pipeline_stats() -> pd.DataFrame:
    """Load pipeline article stats from CSV export."""
    df = _safe_read_csv(DATA_DIR / "pipeline_stats.csv")
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


@st.cache_data(ttl=300)
def load_token_usage() -> pd.DataFrame:
    """Load Claude API usage from CSV export."""
    df = _safe_read_csv(DATA_DIR / "claude_analysis.csv")
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=300)
def load_signal_log() -> pd.DataFrame:
    """Load signal_evaluation_log export (paper-trade outcomes)."""
    df = _safe_read_csv(DATA_DIR / "signal_log.csv")
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


@st.cache_data(ttl=300)
def load_report_memory() -> dict:
    """Load report_memory.json for narrative tracking."""
    mem_path = DATA_DIR / "report_memory.json"
    # Also check legacy path for local development
    if not mem_path.exists():
        mem_path = _PROJECT_ROOT / "market_data" / "report_memory.json"
    if not mem_path.exists():
        return {}
    try:
        return json.loads(mem_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
