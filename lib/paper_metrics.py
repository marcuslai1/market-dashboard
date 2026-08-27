"""Strategy scorecard metrics for the paper-book band (2026-08-27).

Pure functions over the three exported CSV frames (``paper_nav.csv``,
``paper_trades.csv``, ``paper_positions.csv``) — no Streamlit, no I/O — so
the numbers the Tracker shows are the same numbers the pipeline's read-only
instruments (``scripts/paper_exit_quality.py`` / ``paper_risk.py``) print:

- NAV return, annualised vol, Sharpe/Sortino (rf = 0, daily, sqrt(252)), max
  drawdown on the close-marked NAV series, and the same for SPY over the
  identical window (``spy_close`` rides on every nav row);
- closed round-trips: n, win rate, mean P&L, exit-rule vs stop-loss split,
  **stop drag** (stop exits' net units as % of the inception pot);
- **R-multiples**: (exit − avg cost) ÷ (avg cost − entry stop) per closed
  trade — expectancy overall, and per exit reason. Needs the ``entry_stop``
  column the pipeline exports since 2026-08-27; rows without it are skipped
  (older CSVs simply show no R);
- cash not in positions (cash + any vehicle sleeve) averaged over the window;
- explicit fees (``fees_units``) as % of the pot, when a lane models them.

Capture ratio / MFE are deliberately NOT here — they need intraday bars the
CSVs do not carry; the pipeline instrument owns them.
"""
from __future__ import annotations

import math

import pandas as pd

INCEPTION_UNITS = 1_000_000
ANN = math.sqrt(252)


def _series_stats(vals: list[float]) -> dict:
    vals = [float(v) for v in vals if v is not None and not pd.isna(v)]
    if len(vals) < 3 or vals[0] == 0:
        return {}
    rets = [b / a - 1 for a, b in zip(vals, vals[1:]) if a]
    n = len(rets)
    mu = sum(rets) / n
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    dsd = math.sqrt(sum(min(r, 0.0) ** 2 for r in rets) / n)
    peak, mdd = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return {
        "ret_pct": (vals[-1] / vals[0] - 1) * 100.0,
        "vol_pct": sd * ANN * 100.0,
        "sharpe": (mu / sd * ANN) if sd else None,
        "sortino": (mu / dsd * ANN) if dsd else None,
        "max_dd_pct": mdd * 100.0,
        "n_sessions": len(vals),
    }


def lane_nav_stats(nav_df: pd.DataFrame | None, policy_id: str) -> dict:
    """NAV-series metrics for one lane + SPY over the lane's own window."""
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return {}
    rows = nav_df[nav_df["policy_id"] == policy_id].sort_values("date")
    if rows.empty:
        return {}
    nav = pd.to_numeric(rows["nav_units"], errors="coerce").tolist()
    out = _series_stats(nav)
    if not out:
        return {}
    if "spy_close" in rows.columns:
        spy = _series_stats(pd.to_numeric(rows["spy_close"], errors="coerce").tolist())
        out["spy"] = spy
    cash = pd.to_numeric(rows["cash_units"], errors="coerce")
    if "sleeve_units" in rows.columns:
        cash = cash + pd.to_numeric(rows["sleeve_units"], errors="coerce").fillna(0)
    navs = pd.to_numeric(rows["nav_units"], errors="coerce")
    frac = (cash / navs).replace([math.inf, -math.inf], math.nan).dropna()
    out["avg_cash_pct"] = float(frac.mean() * 100.0) if not frac.empty else None
    out["as_of"] = str(rows["date"].iloc[-1])
    out["since"] = str(rows["date"].iloc[0])
    return out


def _r_multiple(row) -> float | None:
    cost = _f(row.get("avg_entry_price"))
    stop = _f(row.get("entry_stop"))
    exit_px = _f(row.get("exit_price"))
    if cost is None or stop is None or exit_px is None:
        return None
    risk = cost - stop
    if risk <= 0:
        return None
    return (exit_px - cost) / risk


def _f(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(x) else x


def lane_trade_stats(trades_df: pd.DataFrame | None, policy_id: str) -> dict:
    """Closed-trade metrics for one lane. Reasons: ``stop`` = stop-loss;
    ``caution_exit`` = the lane's exit rule; everything else (avoid/delist)
    grouped as ``other``."""
    if trades_df is None or trades_df.empty or "policy_id" not in trades_df.columns:
        return {}
    rows = trades_df[trades_df["policy_id"] == policy_id]
    if rows.empty:
        return {}
    recs = rows.to_dict("records")
    pnl = [_f(r.get("pnl_pct")) for r in recs]
    pnl = [p for p in pnl if p is not None]
    out = {
        "n_trades": len(recs),
        "win_rate_pct": (100.0 * sum(p > 0 for p in pnl) / len(pnl)) if pnl else None,
        "mean_pnl_pct": (sum(pnl) / len(pnl)) if pnl else None,
    }
    rs = [_r_multiple(r) for r in recs]
    rs_ok = [r for r in rs if r is not None]
    out["expectancy_r"] = (sum(rs_ok) / len(rs_ok)) if rs_ok else None
    out["n_r"] = len(rs_ok)
    by = {}
    for r, rm in zip(recs, rs):
        reason = r.get("exit_reason")
        key = "stop" if reason == "stop" else ("exit_rule" if reason == "caution_exit" else "other")
        b = by.setdefault(key, {"n": 0, "wins": 0, "pnl_units": 0, "r": []})
        b["n"] += 1
        p = _f(r.get("pnl_pct"))
        if p is not None and p > 0:
            b["wins"] += 1
        u = _f(r.get("pnl_units"))
        if u is not None:
            b["pnl_units"] += int(u)
        if rm is not None:
            b["r"].append(rm)
    out["by_reason"] = {
        k: {
            "n": v["n"],
            "win_rate_pct": 100.0 * v["wins"] / v["n"] if v["n"] else None,
            "net_nav_pct": 100.0 * v["pnl_units"] / INCEPTION_UNITS,
            "mean_r": (sum(v["r"]) / len(v["r"])) if v["r"] else None,
        }
        for k, v in by.items()
    }
    stop = out["by_reason"].get("stop")
    out["stop_drag_pct"] = stop["net_nav_pct"] if stop else 0.0
    if "fees_units" in rows.columns:
        fees = pd.to_numeric(rows["fees_units"], errors="coerce")
        out["fees_pct"] = (float(fees.sum()) / INCEPTION_UNITS * 100.0
                           if fees.notna().any() else None)
    else:
        out["fees_pct"] = None
    return out


def lane_scorecard(nav_df, trades_df, positions_df, policy_id: str) -> dict:
    """One lane's full row: NAV stats + trade stats + open-position count."""
    out = {"policy_id": policy_id}
    out.update(lane_nav_stats(nav_df, policy_id))
    out.update(lane_trade_stats(trades_df, policy_id))
    n_pos = None
    if positions_df is not None and not positions_df.empty and "policy_id" in positions_df.columns:
        n_pos = int((positions_df["policy_id"] == policy_id).sum())
    out["n_positions"] = n_pos
    return out


def scorecard(nav_df, trades_df, positions_df, policy_ids: list[str]) -> list[dict]:
    """Rows for every requested lane that has nav data, in the given order."""
    rows = []
    for pid in policy_ids:
        row = lane_scorecard(nav_df, trades_df, positions_df, pid)
        if "ret_pct" in row:
            rows.append(row)
    return rows
