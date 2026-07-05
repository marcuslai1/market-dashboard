"""Signal Tracker · Paper-book band (page-contract tier 1c).

Renders the pipeline's mechanical paper portfolio — policy ``v1_flat10``,
replay-seeded 2026-04-19, Measurement-Gate-exempt — from two exported
sources: the report's ``paper_portfolio`` summary block and
``data/paper_nav.csv`` (daily NAV + SPY/SOXX closes). The dashboard's only
arithmetic is rebasing exported series to 100 at their first valid row;
all measurement lives upstream
(docs/superpowers/specs/2026-07-05-paper-book-band-design.md).
"""
from __future__ import annotations

import pandas as pd

# Exported column → display series name. NAV is the hero series; SPY/SOXX are
# the benchmarks the upstream summary already compares against.
_REBASE_COLS = {"nav_units": "Paper book", "spy_close": "SPY", "soxx_close": "SOXX"}


def select_policy(nav_df: pd.DataFrame | None, block: dict) -> pd.DataFrame:
    """Rows of *nav_df* for the policy the latest report block names.

    Without a block, falls back to the sole distinct ``policy_id`` — but a
    multi-policy CSV with no block to disambiguate yields an EMPTY frame:
    side-by-side policy variants must never blend into one curve.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame()
    pid = (block or {}).get("policy_id")
    if pid is None:
        ids = nav_df["policy_id"].dropna().unique()
        if len(ids) != 1:
            return pd.DataFrame()
        pid = ids[0]
    return nav_df[nav_df["policy_id"] == pid].sort_values("date")


def rebase_curves(df: pd.DataFrame | None) -> pd.DataFrame:
    """``date`` + one rebased-to-100 column per available series.

    Each series rebases to its own first valid value (the upstream summary
    computes benchmark returns first-row→last-row the same way — this is
    presentation math, not measurement). Series that are absent, all-NaN, or
    zero-based are omitted rather than plotted wrong.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], errors="coerce")})
    for col, label in _REBASE_COLS.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        valid = series.dropna()
        if valid.empty or valid.iloc[0] == 0:
            continue
        out[label] = series / valid.iloc[0] * 100.0
    if out.columns.tolist() == ["date"]:
        return pd.DataFrame()
    return out


def verdict_bits(block: dict) -> tuple[str, str]:
    """(verdict sentence, tone) for the band's lead line.

    Tone ∈ {"pos", "neg", ""} colours the "— …the benchmark" clause. A block
    whose returns are still ``None`` (seed day / no matured session) reads
    "seeded", mirroring the upstream Telegram glance line.
    """
    nav = block.get("nav_return_pct")
    spy = block.get("spy_return_pct")
    since = f" since {block['inception']}" if block.get("inception") else ""
    if nav is None or spy is None:
        return (f"Paper book seeded{since} — first fills pending.", "")
    body = f"Paper book {nav:+.1f}%{since} vs SPY {spy:+.1f}%"
    if nav > spy:
        return (f"{body} — leading the benchmark.", "pos")
    if nav < spy:
        return (f"{body} — trailing the benchmark.", "neg")
    return (f"{body} — tracking the benchmark.", "")
