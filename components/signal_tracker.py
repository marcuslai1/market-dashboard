"""Signal Tracker page: episode history, aggregate calibration, paper-trade outcomes.

Also home to the signal-history helpers (`extract_signal_history`,
`build_signal_episodes`, `_classify_episode_verdict`) and the accuracy helper
(`compute_signal_accuracy`) — the Signal Tracker is their primary consumer.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.catalog import RETIRED_TICKERS, TICKER_DISPLAY
from lib.data_loader import load_signal_log
from lib.formatters import _legacy_rationale_from


def _classify_episode_verdict(signal: str, ret: float | None,
                              run_during: float | None, is_active: bool) -> str:
    """Label an episode based on signal type and realised return.

    Active episodes (no closing signal fired yet) get the ⏳ prefix so
    resolved wins/losses read differently from still-open ones.
    """
    if signal == "HOLD":
        return "— non-directional"
    if signal == "WATCH":
        if run_during is not None and run_during >= 5:
            return "⚠ missed"
        return "— quiet"
    if ret is None:
        return "—"
    prefix = "⏳ " if is_active else ""
    if signal in ("BUY", "ACCUMULATE"):
        return f"{prefix}✓ profit" if ret > 0 else f"{prefix}✗ loss"
    if signal == "CAUTION":
        return f"{prefix}✓ avoided" if ret < 0 else f"{prefix}✗ wrong"
    return "—"


def build_signal_episodes(sig_df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse consecutive-same-signal rows per ticker into episodes, then
    compute trade-economics returns.

    Episode = one contiguous run of the same signal. Entry price = first-day
    price of the episode. Exit price depends on signal semantics:

    - BUY / ACCUMULATE: position opens on entry; held through subsequent
      HOLD/WATCH (non-directional). Closes when the next CAUTION fires
      for this ticker. If no CAUTION has fired yet, position is still open
      and exit = latest available price.
    - CAUTION: the "avoid / trim" call. Measured until the next
      BUY/ACCUMULATE (signal to re-enter) or latest price if none.
      Negative return = the call was right (you avoided a drop).
    - WATCH / HOLD: non-actionable; exit price is the episode's last-day
      price (only used to display something; verdict ignores return).

    Because of this, a 1-day ACCUMULATE that flipped to HOLD tomorrow
    does NOT return 0% — the position stays open until a CAUTION or
    measures to current price.
    """
    if sig_df.empty:
        return pd.DataFrame()

    latest_by_ticker: dict[str, float] = {}
    if not prices_df.empty and "ticker" in prices_df.columns:
        for tk, g in prices_df.sort_values("date").groupby("ticker"):
            last = g.iloc[-1].get("last_price")
            if pd.notna(last):
                latest_by_ticker[tk] = float(last)

    out = []
    for ticker, group in sig_df.sort_values("date").groupby("ticker"):
        group = group.reset_index(drop=True)
        sig = group["signal"].fillna("")
        episode_id = (sig != sig.shift()).cumsum()

        ticker_eps = []
        for _, ep in group.groupby(episode_id):
            signal = ep["signal"].iloc[0]
            if not signal:
                continue
            prices = pd.to_numeric(ep["price"], errors="coerce").dropna()
            ticker_eps.append({
                "signal": signal,
                "start": ep["date"].iloc[0],
                "end": ep["date"].iloc[-1],
                "entry_price": float(prices.iloc[0]) if len(prices) else None,
                "peak": float(prices.max()) if len(prices) else None,
                "last_in_ep": float(prices.iloc[-1]) if len(prices) else None,
            })

        for i, ep in enumerate(ticker_eps):
            signal = ep["signal"]
            entry_price = ep["entry_price"]
            exit_price = None
            exit_date = None
            is_active = False

            if signal in ("BUY", "ACCUMULATE"):
                for j in range(i + 1, len(ticker_eps)):
                    if ticker_eps[j]["signal"] == "CAUTION":
                        exit_price = ticker_eps[j]["entry_price"]
                        exit_date = ticker_eps[j]["start"]
                        break
                if exit_price is None:
                    exit_price = latest_by_ticker.get(ticker) or ep["last_in_ep"]
                    is_active = True
            elif signal == "CAUTION":
                for j in range(i + 1, len(ticker_eps)):
                    if ticker_eps[j]["signal"] in ("BUY", "ACCUMULATE"):
                        exit_price = ticker_eps[j]["entry_price"]
                        exit_date = ticker_eps[j]["start"]
                        break
                if exit_price is None:
                    exit_price = latest_by_ticker.get(ticker) or ep["last_in_ep"]
                    is_active = True
            else:
                exit_price = ep["last_in_ep"]

            ret = None
            if entry_price and exit_price:
                ret = (exit_price - entry_price) / entry_price * 100
            run_during = None
            if entry_price and ep["peak"]:
                run_during = (ep["peak"] - entry_price) / entry_price * 100

            out.append({
                "ticker": ticker,
                "signal": signal,
                "start": ep["start"],
                "end": ep["end"],
                "duration_days": int((ep["end"] - ep["start"]).days) + 1,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_date": exit_date,
                "return_pct": ret,
                "run_during_pct": run_during,
                "is_active": is_active,
                "verdict": _classify_episode_verdict(signal, ret, run_during, is_active),
            })
    return pd.DataFrame(out)


def extract_signal_history(reports: dict) -> pd.DataFrame:
    """Build a signal history DataFrame from all reports."""
    rows = []
    for date_str, report in reports.items():
        watchlist = report.get("watchlist", {})
        for ticker, data in watchlist.items():
            if ticker in RETIRED_TICKERS:
                continue
            rows.append({
                "date": pd.to_datetime(date_str),
                "ticker": ticker,
                "signal": data.get("signal", ""),
                "price": data.get("price"),
                "rsi": data.get("rsi_14"),
                "vs_sma50_pct": data.get("vs_sma50_pct"),
                "rationale": _legacy_rationale_from(data),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _report_ticker_to_db(ticker: str) -> str:
    """Convert report-style ticker (D05_SI) to DB-style (D05.SI)."""
    # Replace the last '_' with '.' if the suffix looks like an exchange code
    # (1-3 uppercase letters). US tickers don't have dots so pass through.
    last_us = ticker.rfind("_")
    if last_us > 0:
        suffix = ticker[last_us + 1:]
        if suffix.isalpha() and suffix.isupper() and 1 <= len(suffix) <= 3:
            return ticker[:last_us] + "." + suffix
    return ticker


def _is_sgx_ticker(ticker: str) -> bool:
    """Check if a report-style ticker is SGX-listed."""
    return ticker.endswith("_SI")


def compute_signal_accuracy(
    sig_df: pd.DataFrame, prices_df: pd.DataFrame
) -> pd.DataFrame:
    """Compute forward returns for directional signal types.

    For each signal, looks up the actual closing price 5/10/20 trading days
    later (by row position in the sorted price table, not calendar days).
    BUY/WATCH: positive returns = signal was correct.
    CAUTION: negative returns = signal was correct (avoided a loss).
    Also computes SPY benchmark return over the same window (N/A for SGX tickers).
    """
    if sig_df.empty or prices_df.empty:
        return pd.DataFrame()

    actionable = sig_df[sig_df["signal"].isin(["BUY", "ACCUMULATE", "WATCH", "CAUTION"])].copy()
    if actionable.empty:
        return pd.DataFrame()

    # Deduplicate: only keep the FIRST day of each consecutive signal streak
    actionable = actionable.sort_values(["ticker", "date"])
    keep = []
    for _ticker, grp in actionable.groupby("ticker"):
        prev_signal = None
        for idx, row in grp.iterrows():
            if row["signal"] != prev_signal:
                keep.append(idx)
            prev_signal = row["signal"]
    actionable = actionable.loc[keep]

    # Pre-filter SPY prices for benchmark comparison
    spy_prices = prices_df[prices_df["ticker"] == "SPY"].sort_values("date")

    results = []
    for _, row in actionable.iterrows():
        db_ticker = _report_ticker_to_db(row["ticker"])
        signal_date = row["date"]
        signal_price = row["price"]
        is_sgx = _is_sgx_ticker(row["ticker"])

        if signal_price is None or pd.isna(signal_price):
            continue

        # Get all future prices for this ticker sorted by date
        tk_prices = prices_df[
            (prices_df["ticker"] == db_ticker) & (prices_df["date"] > signal_date)
        ].sort_values("date")

        # SPY prices from same start date
        spy_future = spy_prices[spy_prices["date"] > signal_date].sort_values("date")
        spy_base = spy_prices[spy_prices["date"] <= signal_date]
        spy_base_price = spy_base.iloc[-1]["last_price"] if not spy_base.empty else None

        entry = {
            "date": signal_date,
            "ticker": row["ticker"],
            "signal": row["signal"],
            "price": signal_price,
        }

        for offset, label in [(5, "5d"), (10, "10d"), (20, "20d")]:
            if len(tk_prices) >= offset:
                future_price = tk_prices.iloc[offset - 1]["last_price"]
                if future_price is not None and not pd.isna(future_price):
                    ret = (future_price - signal_price) / signal_price * 100
                    entry[f"price_{label}"] = future_price
                    entry[f"return_{label}"] = round(ret, 2)
                else:
                    entry[f"price_{label}"] = None
                    entry[f"return_{label}"] = None
            else:
                entry[f"price_{label}"] = None
                entry[f"return_{label}"] = None

            # SPY benchmark return over same window
            if is_sgx or spy_base_price is None:
                entry[f"spy_{label}"] = None
                entry[f"excess_{label}"] = None
            elif len(spy_future) >= offset:
                spy_fp = spy_future.iloc[offset - 1]["last_price"]
                if spy_fp is not None and not pd.isna(spy_fp):
                    spy_ret = (spy_fp - spy_base_price) / spy_base_price * 100
                    entry[f"spy_{label}"] = round(spy_ret, 2)
                    tk_ret = entry.get(f"return_{label}")
                    if tk_ret is not None:
                        entry[f"excess_{label}"] = round(tk_ret - spy_ret, 2)
                    else:
                        entry[f"excess_{label}"] = None
                else:
                    entry[f"spy_{label}"] = None
                    entry[f"excess_{label}"] = None
            else:
                entry[f"spy_{label}"] = None
                entry[f"excess_{label}"] = None

        results.append(entry)

    df = pd.DataFrame(results) if results else pd.DataFrame()
    # Normalize None → NaN for consistent handling
    for prefix in ["return", "price", "spy", "excess"]:
        for label in ["5d", "10d", "20d"]:
            col = f"{prefix}_{label}"
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def render_signal_tracker_page(reports: dict, prices_df: pd.DataFrame) -> None:
    """Render the Signal Tracker page.

    Args:
        reports: filtered reports dict (date-keyed).
        prices_df: filtered SQLite prices DataFrame.
    """
    st.title("Signal Tracker")
    sig_df = extract_signal_history(reports)

    if sig_df.empty:
        st.warning("No signal data available yet.")
        st.stop()

    # Ticker selector
    tickers = sorted(sig_df["ticker"].unique())
    selected_tickers = st.multiselect(
        "Select tickers", tickers, default=tickers
    )

    if not selected_tickers:
        st.info("Select at least one ticker.")
        st.stop()

    signal_map = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    filtered = sig_df[sig_df["ticker"].isin(selected_tickers)].copy()
    filtered["signal_num"] = filtered["signal"].map(signal_map)

    # ── Signal Changes (top — what shifted, when) ──
    st.subheader("Signal Changes")
    changes = []
    for ticker in selected_tickers:
        tk = filtered[filtered["ticker"] == ticker].sort_values("date")
        if len(tk) < 2:
            continue
        for i in range(1, len(tk)):
            prev = tk.iloc[i - 1]
            curr = tk.iloc[i]
            if prev["signal"] != curr["signal"]:
                changes.append({
                    "Date": curr["date"].strftime("%Y-%m-%d"),
                    "Ticker": ticker,
                    "From": prev["signal"],
                    "To": curr["signal"],
                    "Rationale": curr["rationale"][:200] if curr["rationale"] else "",
                })
    if changes:
        st.dataframe(pd.DataFrame(changes), width="stretch", hide_index=True)
    else:
        st.caption("No signal changes detected in the selected tickers/date range.")

    st.divider()

    # ── Signal Outcome History (per-ticker episode view) ──
    st.subheader("Signal Outcome History")
    st.caption(
        "Each row = one *episode* (consecutive days with the same signal, collapsed). "
        "Return uses trade-economics, not signal-window boundaries: "
        "BUY/ACCUMULATE is held through HOLD/WATCH and only closes on the next **CAUTION** "
        "(or stays open vs. current price if no CAUTION has fired). CAUTION is measured "
        "until the next BUY/ACCUMULATE. ⏳ = trade still open. "
        "BUY/ACCUMULATE: ✓ if up. CAUTION: ✓ if down (loss avoided). "
        "WATCH: ⚠ missed if price ran ≥5% during the episode."
    )

    show_all = st.checkbox(
        "Show all episodes (include HOLD and quiet WATCH)",
        value=False,
        help="By default only actionable episodes are shown: BUY, ACCUMULATE, CAUTION, and WATCH episodes where price moved ≥5%.",
    )

    episodes = build_signal_episodes(
        sig_df[sig_df["ticker"].isin(selected_tickers)], prices_df
    )

    if episodes.empty:
        st.info("No episode data available yet.")
    else:
        if not show_all:
            actionable_mask = episodes["signal"].isin(["BUY", "ACCUMULATE", "CAUTION"])
            watch_triggered = (episodes["signal"] == "WATCH") & (
                episodes["run_during_pct"].fillna(0) >= 5
            )
            episodes = episodes[actionable_mask | watch_triggered]

        if episodes.empty:
            st.caption("No actionable episodes for the selected tickers — toggle 'Show all' to see HOLD/quiet WATCH.")
        else:
            for ticker in selected_tickers:
                tk_eps = episodes[episodes["ticker"] == ticker].sort_values("start", ascending=False)
                if tk_eps.empty:
                    continue
                display_tk = TICKER_DISPLAY.get(ticker, ticker)

                scored = tk_eps[tk_eps["signal"].isin(["BUY", "ACCUMULATE", "CAUTION"]) &
                                ~tk_eps["is_active"]]
                wins = scored["verdict"].isin(["✓ profit", "✓ avoided"]).sum()
                total_scored = len(scored)
                active = tk_eps["is_active"].sum()
                summary = f"**{display_tk}** — {len(tk_eps)} episodes"
                if total_scored:
                    summary += f", {wins}/{total_scored} closed trades worked out ({wins / total_scored * 100:.0f}%)"
                if active:
                    summary += f" · {active} still open"
                st.markdown(summary)

                display_df = tk_eps[[
                    "signal", "start", "exit_date", "duration_days",
                    "entry_price", "exit_price", "return_pct",
                    "run_during_pct", "is_active", "verdict",
                ]].copy()
                display_df["start"] = display_df["start"].dt.strftime("%Y-%m-%d")
                display_df["exit_date"] = display_df.apply(
                    lambda r: (
                        "open" if r["is_active"]
                        else (r["exit_date"].strftime("%Y-%m-%d") if pd.notna(r["exit_date"]) else "—")
                    ),
                    axis=1,
                )
                display_df["entry_price"] = display_df["entry_price"].map(
                    lambda v: f"{v:.2f}" if pd.notna(v) else "—"
                )
                display_df["exit_price"] = display_df["exit_price"].map(
                    lambda v: f"{v:.2f}" if pd.notna(v) else "—"
                )
                display_df["return_pct"] = display_df["return_pct"].map(
                    lambda v: f"{v:+.1f}%" if pd.notna(v) else "—"
                )
                display_df["run_during_pct"] = display_df["run_during_pct"].map(
                    lambda v: f"{v:+.1f}%" if pd.notna(v) else "—"
                )
                display_df = display_df.drop(columns=["is_active"])
                display_df.columns = [
                    "Signal", "Entry date", "Exit date", "Signal days",
                    "Entry", "Exit/Now", "Return", "Peak run", "Verdict",
                ]
                st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()

    # ── Aggregate Calibration (one-number-across-the-watchlist sanity check) ──
    st.subheader("Aggregate Calibration")
    st.caption(
        "Win rates across **all tickers** at 5d / 10d horizons — answers "
        "\"is the pipeline systematically good at calling BUYs / avoiding CAUTIONs?\""
    )
    acc_df = compute_signal_accuracy(sig_df, prices_df)  # uses ALL tickers

    if acc_df.empty:
        st.caption("No signals tracked yet — scorecard will populate as signals accumulate.")
    else:
        # A) Summary metrics row — bullish signals
        min_samples = 3
        st.markdown("**Bullish Signals** — *should we have bought?*")
        bull_cols = st.columns(9)
        for i, sig_type in enumerate(["BUY", "ACCUMULATE", "WATCH"]):
            sig_data = acc_df[acc_df["signal"] == sig_type]
            count = len(sig_data)
            offset = i * 3

            bull_cols[offset].metric(f"{sig_type} Signals", count)

            valid_5d = sig_data["return_5d"].dropna()
            if len(valid_5d) >= min_samples:
                win_rate = (valid_5d > 0).mean() * 100
                bull_cols[offset + 1].metric(
                    f"{sig_type} 5d Win Rate", f"{win_rate:.1f}%"
                )
            else:
                bull_cols[offset + 1].metric(
                    f"{sig_type} 5d Win Rate", "Pending" if count > 0 else "—"
                )

            valid_10d = sig_data["return_10d"].dropna()
            if len(valid_10d) >= min_samples:
                avg_ret = valid_10d.mean()
                bull_cols[offset + 2].metric(
                    f"{sig_type} 10d Avg", f"{avg_ret:+.1f}%"
                )
            else:
                bull_cols[offset + 2].metric(
                    f"{sig_type} 10d Avg", "Pending" if count > 0 else "—"
                )

        # A2) Summary metrics row — defensive signals (CAUTION only)
        st.markdown("**Defensive Signals** — *were we right to stay away?*")
        def_cols = st.columns(3)
        caution_data = acc_df[acc_df["signal"] == "CAUTION"]
        caution_count = len(caution_data)
        def_cols[0].metric("CAUTION Signals", caution_count)

        valid_5d = caution_data["return_5d"].dropna()
        if len(valid_5d) >= min_samples:
            avoid_rate = (valid_5d <= 0).mean() * 100
            def_cols[1].metric("CAUTION 5d Avoid Rate", f"{avoid_rate:.1f}%")
        else:
            def_cols[1].metric("CAUTION 5d Avoid Rate", "Pending" if caution_count > 0 else "—")

        valid_10d = caution_data["return_10d"].dropna()
        if len(valid_10d) >= min_samples:
            avg_ret = valid_10d.mean()
            def_cols[2].metric("CAUTION 10d Avg", f"{avg_ret:+.1f}%")
        else:
            def_cols[2].metric("CAUTION 10d Avg", "Pending" if caution_count > 0 else "—")

        # HOLD — informational only (not a directional signal)
        hold_count = len(sig_df[sig_df["signal"] == "HOLD"])
        if hold_count > 0:
            st.caption(f"HOLD signals: {hold_count} days across all tickers (not scored — HOLD is non-directional)")

    # ── Paper Trade Outcomes (from pipeline signal_evaluation_log) ──
    st.divider()
    st.subheader("Paper Trade Outcomes")
    st.caption(
        "Realised returns from the pipeline's own log — `entry_price` and "
        "`invalidation` are what the pipeline saw at signal time, not "
        "reconstructed after the fact. Outcomes fill in as trading days elapse."
    )

    sig_log = load_signal_log()
    if sig_log.empty:
        st.info("No signal log data yet — `signal_log.csv` will appear after the next pipeline run.")
    else:
        post_cutover_only = st.checkbox(
            "Post-cutover only (≥ 2026-04-19)",
            value=True,
            help="Pre-cutover rows are too sparse to drive behavior. Uncheck to include them.",
            key="paper_trade_post_cutover",
        )
        if post_cutover_only:
            sig_log = sig_log[sig_log["date"] >= pd.Timestamp("2026-04-19")].copy()
        if sig_log.empty:
            st.info("No post-cutover signals logged yet.")
            st.stop()
        # Summary metrics
        total_rows = len(sig_log)
        by_type = sig_log["entry_type"].value_counts().to_dict()
        # "Catalyst Entries" KPI removed 2026-05-30 — the catalyst entry_type is
        # retired (path is narrative-only; no new catalyst rows are produced).
        summary_cols = st.columns(3)
        summary_cols[0].metric("Total Signals Logged", total_rows)
        summary_cols[1].metric("Standard Entries", by_type.get("standard", 0))
        summary_cols[2].metric("Monitor (non-entry)", by_type.get("monitor", 0))

        # Hit-rate on invalidation vs upside target (rows with final outcomes)
        finalised = sig_log.dropna(subset=["price_after_20d"])
        if not finalised.empty:
            hit_inv = int(finalised["hit_invalidation"].fillna(0).sum())
            hit_up = int(finalised["hit_upside_target"].fillna(0).sum())
            hr_cols = st.columns(3)
            hr_cols[0].metric("Rows with 20d Outcome", len(finalised))
            hr_cols[1].metric(
                "Hit Invalidation", f"{hit_inv} ({hit_inv / len(finalised) * 100:.0f}%)"
            )
            hr_cols[2].metric(
                "Hit Upside Target", f"{hit_up} ({hit_up / len(finalised) * 100:.0f}%)"
            )
        else:
            st.caption("No signals have aged 20 trading sessions yet — hit-rate stats pending.")

        # Per-signal, per-entry-type realised return breakdown
        st.markdown("**Realised Return by Signal × Entry Type**")
        breakdown_rows = []
        for (sig_type, etype), group in sig_log.groupby(["signal", "entry_type"]):
            row = {"Signal": sig_type, "Entry Type": etype, "Count": len(group)}
            for h in ["5d", "10d", "20d"]:
                valid = group[f"return_{h}"].dropna()
                if len(valid) >= 1:
                    row[f"{h} Avg"] = f"{valid.mean():+.1f}%"
                    row[f"{h} N"] = len(valid)
                else:
                    row[f"{h} Avg"] = "—"
                    row[f"{h} N"] = 0
            breakdown_rows.append(row)
        if breakdown_rows:
            bd_df = pd.DataFrame(breakdown_rows).sort_values(
                ["Entry Type", "Signal"]
            ).reset_index(drop=True)
            st.dataframe(bd_df, width="stretch", hide_index=True)

        # Open positions — logged but still within the 20-session window
        open_rows = sig_log[sig_log["price_after_20d"].isna()].copy()
        if not open_rows.empty:
            with st.expander(f"Open positions ({len(open_rows)}) — outcomes still resolving"):
                open_display = open_rows[[
                    "date", "ticker", "signal", "entry_type",
                    "entry_price", "invalidation", "upside_target",
                    "price_after_5d", "price_after_10d",
                ]].copy()
                open_display["ticker"] = open_display["ticker"].map(
                    lambda t: TICKER_DISPLAY.get(t, t)
                )
                open_display["date"] = open_display["date"].dt.strftime("%Y-%m-%d")
                st.dataframe(open_display, width="stretch", hide_index=True)
