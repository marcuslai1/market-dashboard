"""Retrospective page: monthly "what we called / what happened" narrative digest.

Spec: docs/superpowers/specs/2026-07-20-reader-retrospective-design.md
(MarketReport capability-gap survey 2026-07-19, item #8). Derives one-sentence
verdicts from the pipeline's exported call ledger (data/signal_log.csv).
Verdicts are frozen to each call's own 5/10/20-session outcome window — never
re-marked to the latest price — so a finished month's story never changes
afterwards. Retired tickers deliberately stay in: the page is about what we
*said*, and dropping bad old calls would be survivorship bias (deliberate
divergence from the Watchlist's RETIRED_TICKERS filter).
"""
from __future__ import annotations

import pandas as pd

_DIRECTIONAL = ("BUY", "ACCUMULATE", "CAUTION", "AVOID")
_LONG = ("BUY", "ACCUMULATE")


def dedupe_calls(log_df: pd.DataFrame) -> pd.DataFrame:
    """One row per *call*: the first row of each consecutive same-signal run
    per ticker, then directional calls only.

    The log repeats a signal daily while it stands; a HOLD/WATCH day between
    two ACCUMULATE days breaks the run (two distinct calls) — the same streak
    rule ``compute_signal_accuracy`` uses on the report corpus.
    """
    if log_df is None or log_df.empty or "signal" not in log_df.columns:
        return pd.DataFrame()
    df = log_df[log_df["signal"].notna()].sort_values(["ticker", "date"])
    first_of_run = df["signal"] != df.groupby("ticker")["signal"].shift()
    calls = df[first_of_run]
    return calls[calls["signal"].isin(_DIRECTIONAL)].reset_index(drop=True)
