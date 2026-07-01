"""Date-range filters for reports + price frames.

Pure functions (no Streamlit, no module globals) so they're unit-testable and
reusable. ``dashboard.py`` passes the sidebar-selected range explicitly.
"""
from __future__ import annotations

from datetime import date

import pandas as pd


def filter_reports(reports: dict, start: date, end: date) -> dict:
    """Return the reports whose ISO date key falls in ``[start, end]`` (inclusive).

    Non-ISO keys are skipped rather than raising.
    """
    out = {}
    for date_str, rpt in reports.items():
        try:
            d = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue
        if start <= d <= end:
            out[date_str] = rpt
    return out


def filter_prices(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Return price rows whose ``date`` falls in ``[start, end]`` (inclusive)."""
    if df.empty or "date" not in df.columns:
        return df
    d = df["date"].dt.date  # compute once
    return df[(d >= start) & (d <= end)]
