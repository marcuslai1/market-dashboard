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
- cash not in positions (cash + a T-bill sleeve) averaged over the window; an
  ETF sleeve (``INDEX_SLEEVE_LANES``) is market exposure and rides separately;
- explicit fees (``fees_units``) as % of the pot, when a lane models them.

Capture ratio / MFE are deliberately NOT here — they need intraday bars the
CSVs do not carry; the pipeline instrument owns them.
"""
from __future__ import annotations

import math

import pandas as pd

INCEPTION_UNITS = 1_000_000
ANN = math.sqrt(252)

# Books whose cash sleeve is an INDEX position (2026-09-02, colour-is-a-claim
# follow-up). The CSV carries the sleeve's balance and income, not its
# vehicle; the pipeline registry names these four. For them the parked
# balance is market exposure, not idle cash: ``avg_cash_pct`` counts only
# ``cash_units`` and the sleeve share rides separately as
# ``avg_index_sleeve_pct`` (+ ``sleeve_vehicle``). T-bill books keep
# counting the sleeve as cash — that is what it is.
INDEX_SLEEVE_LANES = {
    "v2_starter_b15_regime_fees": "SOXX while the trend is up, T-bills otherwise",
    "v2_starter_b15_spy_fees": "SPY",
    "v1_wide_extthesis_100_b15_spy": "SPY",
    "v1_wide_extthesis_100_b15_spy_fees": "SPY",
}


def sleeve_short(vehicle):
    """'SOXX / T-bills', 'SPY' … for the scorecard cell; None for a T-bill or
    no sleeve. The regime book's sleeve is SOXX only while the trend is up,
    so its label says so — the CSV cannot split the two legs."""
    if not vehicle:
        return None
    return "SOXX / T-bills" if "SOXX" in vehicle else "SPY"


def sleeve_exposure_note(vehicle):
    """The parenthetical after a parked-ETF figure."""
    if vehicle and "SOXX" in vehicle:
        return "market exposure while in SOXX, not idle cash"
    return "market exposure, not idle cash"


def _series_stats(vals: list[float]) -> dict:
    vals = [float(v) for v in vals if v is not None and not pd.isna(v)]
    if len(vals) < 3 or vals[0] == 0:
        return {}
    rets = [b / a - 1 for a, b in zip(vals, vals[1:], strict=False) if a]
    n = len(rets)
    mu = sum(rets) / n
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    dsd = math.sqrt(sum(min(r, 0.0) ** 2 for r in rets) / n)
    peak, mdd = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    total = vals[-1] / vals[0]
    # Calmar (2026-08-29): annualised return over the worst peak-to-trough
    # fall — return per unit of the pain actually sat through.
    ann_ret = total ** (252.0 / n) - 1.0 if n and total > 0 else None
    calmar = (ann_ret / abs(mdd)) if (ann_ret is not None and mdd < 0) else None
    return {
        "ret_pct": (total - 1) * 100.0,
        "vol_pct": sd * ANN * 100.0,
        "sharpe": (mu / sd * ANN) if sd else None,
        "sortino": (mu / dsd * ANN) if dsd else None,
        "calmar": calmar,
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
    navs = pd.to_numeric(rows["nav_units"], errors="coerce")
    index_vehicle = INDEX_SLEEVE_LANES.get(policy_id)
    sleeve = None
    if "sleeve_units" in rows.columns:
        sleeve = pd.to_numeric(rows["sleeve_units"], errors="coerce").fillna(0)
        if not index_vehicle:
            cash = cash + sleeve       # T-bills are cash; an ETF sleeve is not
    if "soxx_close" in rows.columns:
        soxx = pd.to_numeric(rows["soxx_close"], errors="coerce")
        out["soxx"] = _series_stats(soxx.tolist())
        # Factor read (audit 2026-08-27): beta of the lane's daily NAV return
        # to SOXX (whole portfolio, cash included) and per invested dollar
        # (return / exposure entering the day, days >20% invested only), plus
        # the annualised intercept. One window's exit timing + cash can make
        # both low — a descriptive number, not a significance claim.
        out.update(_soxx_beta(navs, soxx, cash))
        if "spy_close" in rows.columns:
            out.update(factor_residual(
                navs, pd.to_numeric(rows["spy_close"], errors="coerce"), soxx))
    frac = (cash / navs).replace([math.inf, -math.inf], math.nan).dropna()
    out["avg_cash_pct"] = float(frac.mean() * 100.0) if not frac.empty else None
    if index_vehicle and sleeve is not None:
        sfrac = (sleeve / navs).replace([math.inf, -math.inf], math.nan).dropna()
        out["avg_index_sleeve_pct"] = float(sfrac.mean() * 100.0) if not sfrac.empty else None
        out["sleeve_vehicle"] = index_vehicle
    out.update(_sleeve_income_stats(rows, navs))
    out.update(_invested_basis(rows, navs))
    out["as_of"] = str(rows["date"].iloc[-1])
    out["since"] = str(rows["date"].iloc[0])
    return out


def _invested_basis(rows: pd.DataFrame, navs: pd.Series) -> dict:
    """Equity-leg return per invested dollar (critique 2026-09-02).

    NAV Sharpe and Max DD reward a book for holding cash: on the same trades
    a 58%-idle twin prints a shallower drawdown than a 52%-idle one. This
    restates each day's P&L with the sleeve's mark change (``sleeve_income_
    units`` is cumulative, so its day-over-day difference) stripped out,
    divided by the prior day's invested value (nav − cash − sleeve). Days
    under 2% invested contribute 0. Pinned to ``scripts/paper_factor_
    attribution.py::invested_basis``. NOT a portfolio return — a yardstick
    for comparing exit rules across books with different cash shares.
    Keys: ``inv_sharpe``, ``inv_sortino``, ``inv_max_dd_pct``, ``inv_ret_pct``,
    ``avg_invested_pct``. Empty when the series is short."""
    cash = pd.to_numeric(rows["cash_units"], errors="coerce").fillna(0)
    sleeve = (pd.to_numeric(rows["sleeve_units"], errors="coerce").fillna(0)
              if "sleeve_units" in rows.columns else pd.Series(0.0, index=rows.index))
    income = (pd.to_numeric(rows["sleeve_income_units"], errors="coerce").fillna(0)
              if "sleeve_income_units" in rows.columns else pd.Series(0.0, index=rows.index))
    invested_prev = (navs - cash - sleeve).shift(1)
    eq_pnl = navs.diff() - income.diff()
    ok = invested_prev > 0.02 * navs.shift(1)
    rets = (eq_pnl / invested_prev).where(ok, 0.0).iloc[1:]
    if len(rets) < 2:          # _series_stats needs three marks
        return {}
    cum = [INCEPTION_UNITS]
    for r in rets.tolist():
        cum.append(cum[-1] * (1.0 + (0.0 if pd.isna(r) else r)))
    st = _series_stats(cum)
    if not st:
        return {}
    share = ((navs - cash - sleeve) / navs).replace([math.inf, -math.inf], math.nan).dropna()
    return {"inv_sharpe": st["sharpe"], "inv_sortino": st["sortino"],
            "inv_max_dd_pct": st["max_dd_pct"], "inv_ret_pct": st["ret_pct"],
            "avg_invested_pct": float(share.mean() * 100.0) if not share.empty else None}


def _sleeve_income_stats(rows: pd.DataFrame, navs: pd.Series) -> dict:
    """What the parked cash earned (2026-09-01, owner ask "how much is the
    idle cash generating?"). The pipeline exports ``sleeve_income_units`` —
    cumulative mark-to-market income of the cash sleeve, derived exactly
    from the sweep / release ledger (T-bill interest; for a SPY/SOXX sleeve
    its market P&L). Returns:
      cash_income_units  — cumulative income at the last row (units)
      cash_income_pct    — as % of the starting pot
      cash_yield_ann_pct — annualised rate on the average PARKED balance
                           (income / mean sleeve balance × 365 / days held)
    Empty dict for books without a sleeve or before the export carries it."""
    if "sleeve_income_units" not in rows.columns or "sleeve_units" not in rows.columns:
        return {}
    inc = pd.to_numeric(rows["sleeve_income_units"], errors="coerce")
    sleeve = pd.to_numeric(rows["sleeve_units"], errors="coerce")
    if inc.dropna().empty:
        return {}
    last = float(inc.dropna().iloc[-1])
    start = float(navs.dropna().iloc[0]) if not navs.dropna().empty else None
    out = {"cash_income_units": last,
           "cash_income_pct": (last / start * 100.0) if start else None}
    held = sleeve.dropna()
    held = held[held > 0]
    try:
        d0 = pd.to_datetime(rows["date"].iloc[0])
        d1 = pd.to_datetime(rows["date"].iloc[-1])
        days = max((d1 - d0).days, 1)
    except Exception:            # unparseable dates: no yield figure
        days = None
    if days and not held.empty and held.mean() > 0:
        out["cash_yield_ann_pct"] = last / float(held.mean()) * 365.0 / days * 100.0
    else:
        out["cash_yield_ann_pct"] = None
    return out


def _soxx_beta(navs: pd.Series, soxx: pd.Series, cash: pd.Series) -> dict:
    nav_r = navs.pct_change()
    sx_r = soxx.pct_change()
    exposure = (1 - cash / navs).shift(1)          # entering the day
    ok = nav_r.notna() & sx_r.notna() & (sx_r.abs() < 1)
    if ok.sum() < 10:
        return {}
    x, y = sx_r[ok], nav_r[ok]
    vx = ((x - x.mean()) ** 2).sum()
    if vx <= 0:
        return {}
    beta = ((x - x.mean()) * (y - y.mean())).sum() / vx
    alpha = (y.mean() - beta * x.mean()) * 252 * 100.0
    out = {"beta_soxx": float(beta), "alpha_soxx_ann_pct": float(alpha)}
    inv = ok & (exposure > 0.2)
    if inv.sum() >= 10:
        xi, yi = sx_r[inv], nav_r[inv] / exposure[inv]
        vxi = ((xi - xi.mean()) ** 2).sum()
        if vxi > 0:
            out["beta_soxx_invested"] = float(
                ((xi - xi.mean()) * (yi - yi.mean())).sum() / vxi)
    return out


# ── two-factor residual (2026-08-29, pipeline §66) ────────────────────────
# Most names load on SOXX and the seeded window is a semis rally, so the raw
# NAV cannot separate "picks well" from "was long the factor". Regress the
# lane's daily return on SPY + SOXX, strip the factor moves (the intercept
# stays IN the residual so cumulative residual = the book's own P&L), and
# score the residual the way the raw series is scored. Pure-python OLS,
# pinned to scripts/paper_factor_attribution.py. Descriptive, display-only.
def _ols2(y: list[float], x1: list[float], x2: list[float]) -> dict:
    n = len(y)
    if n < 20:
        return {}
    idx = range(n)
    s11 = sum(x1[i] * x1[i] for i in idx)
    s12 = sum(x1[i] * x2[i] for i in idx)
    s22 = sum(x2[i] * x2[i] for i in idx)
    m = [[float(n), sum(x1), sum(x2)], [sum(x1), s11, s12], [sum(x2), s12, s22]]
    v = [sum(y), sum(x1[i] * y[i] for i in idx), sum(x2[i] * y[i] for i in idx)]
    # 3x3 solve by Cramer's rule.
    def det(a):
        return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
                - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    d = det(m)
    if abs(d) < 1e-18:
        return {}
    coef = []
    for c in range(3):
        mc = [row[:] for row in m]
        for r in range(3):
            mc[r][c] = v[r]
        coef.append(det(mc) / d)
    fitted = [coef[0] + coef[1] * x1[i] + coef[2] * x2[i] for i in idx]
    sse = sum((y[i] - fitted[i]) ** 2 for i in idx)
    ybar = sum(y) / n
    sst = sum((yy - ybar) ** 2 for yy in y)
    return {"alpha": coef[0], "beta1": coef[1], "beta2": coef[2],
            "r2": (1 - sse / sst) if sst > 0 else None}


def factor_residual(navs: pd.Series, spy: pd.Series, soxx: pd.Series) -> dict:
    """{beta_spy, beta_soxx_2f, r2_2f, alpha_2f_ann_pct, resid_ret_pct,
    resid_sharpe, resid_max_dd_pct, resid_vol_pct} or {} when too short."""
    df = pd.DataFrame({"n": navs.pct_change(), "s": spy.pct_change(),
                       "x": soxx.pct_change()}).dropna()
    df = df[(df["s"].abs() < 1) & (df["x"].abs() < 1)]
    fit = _ols2(df["n"].tolist(), df["s"].tolist(), df["x"].tolist())
    if not fit:
        return {}
    resid = (df["n"] - fit["beta1"] * df["s"] - fit["beta2"] * df["x"]).tolist()
    cum, path = 1.0, [1.0]
    for r in resid:
        cum *= 1 + r
        path.append(cum)
    st = _series_stats(path)
    return {
        "beta_spy": fit["beta1"], "beta_soxx_2f": fit["beta2"], "r2_2f": fit["r2"],
        "alpha_2f_ann_pct": fit["alpha"] * 252 * 100.0,
        "resid_ret_pct": st.get("ret_pct"), "resid_sharpe": st.get("sharpe"),
        "resid_sortino": st.get("sortino"), "resid_calmar": st.get("calmar"),
        "resid_max_dd_pct": st.get("max_dd_pct"), "resid_vol_pct": st.get("vol_pct"),
    }


def _residual_returns(nav_df: pd.DataFrame, policy_id: str) -> list[float]:
    rows = nav_df[nav_df["policy_id"] == policy_id].sort_values("date")
    if rows.empty or "spy_close" not in rows.columns or "soxx_close" not in rows.columns:
        return []
    df = pd.DataFrame({
        "n": pd.to_numeric(rows["nav_units"], errors="coerce").pct_change(),
        "s": pd.to_numeric(rows["spy_close"], errors="coerce").pct_change(),
        "x": pd.to_numeric(rows["soxx_close"], errors="coerce").pct_change(),
    }).dropna()
    fit = _ols2(df["n"].tolist(), df["s"].tolist(), df["x"].tolist())
    if not fit:
        return []
    return (df["n"] - fit["beta1"] * df["s"] - fit["beta2"] * df["x"]).tolist()


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
    for r, rm in zip(recs, rs, strict=False):
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
    worst = None
    if positions_df is not None and not positions_df.empty and "policy_id" in positions_df.columns:
        mine = positions_df[positions_df["policy_id"] == policy_id]
        n_pos = len(mine)
        if "max_dd_pct" in mine.columns and n_pos:
            # Worst peak-to-trough fall of any OPEN position while held —
            # the pain a portfolio-level drawdown hides (audit 2026-08-27).
            dd = pd.to_numeric(mine["max_dd_pct"], errors="coerce").dropna()
            worst = float(-abs(dd.max())) if not dd.empty else None
    out["n_positions"] = n_pos
    out["worst_open_dd_pct"] = worst
    return out


def scorecard(nav_df, trades_df, positions_df, policy_ids: list[str]) -> list[dict]:
    """Rows for every requested lane that has nav data, in the given order."""
    rows = []
    for pid in policy_ids:
        row = lane_scorecard(nav_df, trades_df, positions_df, pid)
        if "ret_pct" in row:
            rows.append(row)
    return rows


# ── selection haircut (deflated Sharpe, Bailey & López de Prado 2014) ──────
# The scorecard's Sharpe is the best of many variants tried on ONE window;
# some of that is luck. Given N trials whose Sharpes vary by V, the expected
# best-of-N Sharpe of strategies with NO edge is SR0; the deflated Sharpe is
# the probability the observed SR exceeds SR0 after the sample's skew /
# kurtosis and length T. Display-only honesty — never a gate input.
_EULER = 0.5772156649015329


def _norm_ppf(p: float) -> float:
    from statistics import NormalDist
    return NormalDist().inv_cdf(min(max(p, 1e-12), 1 - 1e-12))


def _norm_cdf(x: float) -> float:
    from statistics import NormalDist
    return NormalDist().cdf(x)


def _daily_returns(nav_df: pd.DataFrame, policy_id: str) -> list[float]:
    rows = nav_df[nav_df["policy_id"] == policy_id].sort_values("date")
    vals = [float(v) for v in pd.to_numeric(rows["nav_units"], errors="coerce").tolist()
            if v is not None and not pd.isna(v)]
    return [b / a - 1 for a, b in zip(vals, vals[1:], strict=False) if a]


def selection_haircut(nav_df: pd.DataFrame | None, policy_id: str,
                      trial_ids: list[str] | None = None,
                      min_sessions: int = 30, residual: bool = False) -> dict:
    """Deflated-Sharpe read for one lane against every lane tried.

    Returns {} unless the lane has >= min_sessions returns and at least two
    trials exist. ``sharpe_ann`` / ``lucky_best_sharpe_ann`` are annualised
    (same ANN as the scorecard); ``dsr`` is the probability the lane's Sharpe
    beats the best-of-N-by-luck benchmark; ``n_trials`` counts every lane
    with >= min_sessions returns (the benchmarks are not lanes).
    ``residual=True`` runs the same read on every lane's two-factor RESIDUAL
    series (SPY + SOXX stripped) — the luck question asked after the factor
    tide is removed.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return {}
    _rets = _residual_returns if residual else _daily_returns
    r = _rets(nav_df, policy_id)
    T = len(r)
    if min_sessions > T:
        return {}
    mu = sum(r) / T
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (T - 1))
    if sd <= 0:
        return {}
    sr = mu / sd
    m3 = sum((x - mu) ** 3 for x in r) / T / sd ** 3
    m4 = sum((x - mu) ** 4 for x in r) / T / sd ** 4
    ids = trial_ids if trial_ids is not None else sorted(
        set(nav_df["policy_id"].dropna().unique()))
    srs = []
    for pid in ids:
        rr = _rets(nav_df, pid)
        if len(rr) < min_sessions:
            continue
        m = sum(rr) / len(rr)
        s_ = math.sqrt(sum((x - m) ** 2 for x in rr) / (len(rr) - 1))
        if s_ > 0:
            srs.append(m / s_)
    n = len(srs)
    if n < 2:
        return {}
    mean_sr = sum(srs) / n
    var_sr = sum((x - mean_sr) ** 2 for x in srs) / (n - 1)
    sr0 = math.sqrt(var_sr) * ((1 - _EULER) * _norm_ppf(1 - 1 / n)
                               + _EULER * _norm_ppf(1 - 1 / (n * math.e)))
    denom = 1 - m3 * sr + (m4 - 1) / 4 * sr ** 2
    if denom <= 0:
        return {}
    dsr = _norm_cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(denom))
    return {
        "n_trials": n,
        "n_sessions": T,
        "sharpe_ann": sr * ANN,
        "lucky_best_sharpe_ann": sr0 * ANN,
        "dsr": dsr,
    }



# ── rolling residual Sharpe + stress line (2026-08-29, pipeline §66 addendum) ─
# The residual Sharpe above is ONE number over the whole window. A rolling
# view shows whether the signals' own contribution is steady, fading or
# lumpy — the early-warning form of the luck question. Residual uses the
# whole-window two-factor betas (stable); the Sharpe is rolled over
# ``window`` sessions. Raw rolling Sharpe rides beside it as the comparator.
def rolling_sharpes(nav_df: pd.DataFrame | None, policy_id: str,
                    window: int = 30) -> pd.DataFrame:
    """Columns: date, resid_sharpe, raw_sharpe (annualised). Empty frame when
    the lane is shorter than ``window`` + 1 sessions or the fit is singular."""
    cols = ["date", "resid_sharpe", "raw_sharpe"]
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame(columns=cols)
    rows = nav_df[nav_df["policy_id"] == policy_id].sort_values("date")
    if rows.empty or not {"spy_close", "soxx_close"} <= set(rows.columns):
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame({
        "date": rows["date"].values,
        "n": pd.to_numeric(rows["nav_units"], errors="coerce").pct_change().values,
        "s": pd.to_numeric(rows["spy_close"], errors="coerce").pct_change().values,
        "x": pd.to_numeric(rows["soxx_close"], errors="coerce").pct_change().values,
    }).dropna()
    if len(df) < window + 1:
        return pd.DataFrame(columns=cols)
    fit = _ols2(df["n"].tolist(), df["s"].tolist(), df["x"].tolist())
    if not fit:
        return pd.DataFrame(columns=cols)
    df["e"] = df["n"] - fit["beta1"] * df["s"] - fit["beta2"] * df["x"]

    def _sh(col):
        mu = df[col].rolling(window).mean()
        sd = df[col].rolling(window).std(ddof=1)
        return (mu / sd * ANN).where(sd > 0)
    out = pd.DataFrame({"date": pd.to_datetime(df["date"]),
                        "resid_sharpe": _sh("e"), "raw_sharpe": _sh("n")}).dropna()
    return out.reset_index(drop=True)


STRESS_SHOCK_PCT = -10.0


def stress_read(nav_stats: dict) -> dict:
    """What a SOXX −10% day would do to the book, from the whole-pot single-
    factor beta the scorecard already carries (same number paper_risk.py
    prints). {} when the beta is unavailable."""
    b = nav_stats.get("beta_soxx")
    if b is None:
        return {}
    return {"shock_pct": STRESS_SHOCK_PCT, "beta_soxx": b,
            "book_move_pct": b * STRESS_SHOCK_PCT}
