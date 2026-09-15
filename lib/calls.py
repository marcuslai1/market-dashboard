"""One definition of a *call* for every page that scores the signal ledger.

The pipeline repeats a signal daily while it stands. A call is the FIRST row
of each consecutive same-signal run per ticker, computed over every non-null
signal — so a HOLD or WATCH day between two CAUTION days ends one call and
starts another. The Review page and the Tracker popover used to implement
this separately and disagreed on exactly that HOLD case (external review R12
F05, 2026-09-15: 287 vs 224 calls on the same 2,960-row log). Callers filter
to the signal set they score AFTER this function, never before.
"""
from __future__ import annotations

import pandas as pd


def first_of_run(df: pd.DataFrame, *, signal_col: str = "signal",
                 ticker_col: str = "ticker", date_col: str = "date") -> pd.DataFrame:
    """Rows that start a consecutive same-signal run per ticker (null signals
    dropped first). Returns a copy sorted by (ticker, date)."""
    if df is None or df.empty or signal_col not in df.columns:
        return pd.DataFrame()
    d = df[df[signal_col].notna()].sort_values([ticker_col, date_col])
    starts = d[signal_col] != d.groupby(ticker_col)[signal_col].shift()
    return d[starts].copy()
