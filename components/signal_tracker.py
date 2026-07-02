"""Signal Tracker page: episode history, aggregate calibration, paper-trade outcomes.

Also home to the signal-history helpers (`extract_signal_history`,
`build_signal_episodes`, `_classify_episode_verdict`) and the accuracy helper
(`compute_signal_accuracy`) — the Signal Tracker is their primary consumer.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.catalog import CLUSTER_MAP, RETIRED_TICKERS, SIGNAL_COLORS
from lib.charts import STATUS_NEG, STATUS_POS, STATUS_WARN
from lib.data_loader import load_signal_log
from lib.formatters import (
    _escape_attr,
    _escape_dollars,
    _legacy_rationale_from,
    display_ticker,
)
from lib.pills import _signal_pill_html


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
    if signal in ("CAUTION", "AVOID"):
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

            # latest_by_ticker is keyed by DB-style (dot) tickers; the loop key is
            # report-style (underscore). Convert before lookup or every non-US
            # name silently misses and freezes an open position at its stale
            # in-episode price instead of the latest close.
            db_ticker = _report_ticker_to_db(ticker)

            if signal in ("BUY", "ACCUMULATE"):
                for j in range(i + 1, len(ticker_eps)):
                    if ticker_eps[j]["signal"] in ("CAUTION", "AVOID"):
                        exit_price = ticker_eps[j]["entry_price"]
                        exit_date = ticker_eps[j]["start"]
                        break
                if exit_price is None:
                    exit_price = latest_by_ticker.get(db_ticker) or ep["last_in_ep"]
                    is_active = True
            elif signal in ("CAUTION", "AVOID"):
                for j in range(i + 1, len(ticker_eps)):
                    if ticker_eps[j]["signal"] in ("BUY", "ACCUMULATE"):
                        exit_price = ticker_eps[j]["entry_price"]
                        exit_date = ticker_eps[j]["start"]
                        break
                if exit_price is None:
                    exit_price = latest_by_ticker.get(db_ticker) or ep["last_in_ep"]
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


def _is_foreign_ticker(ticker: str) -> bool:
    """True for any non-US listing (has an exchange suffix: .SI/.KS/.TW/.DE/…).

    US tickers pass through ``_report_ticker_to_db`` unchanged; foreign ones gain
    a dot. The SPY benchmark is only meaningful for US names — a foreign name's
    Nth trading row lands on a different calendar date than SPY's Nth row, so the
    'excess vs SPY' comparison is apples-to-oranges for them.
    """
    return _report_ticker_to_db(ticker) != ticker


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

    actionable = sig_df[
        sig_df["signal"].isin(["BUY", "ACCUMULATE", "WATCH", "CAUTION", "AVOID"])
    ].copy()
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
        is_foreign = _is_foreign_ticker(row["ticker"])

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
            if is_foreign or spy_base_price is None:
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


# ── Performance-ledger HTML helpers (Signal Tracker redesign) ──

def _rate_color(rate: float | None) -> str:
    """Win/avoid-rate → traffic-light colour. Higher is always better here."""
    if rate is None:
        return "var(--ink-3)"
    if rate >= 55:
        return STATUS_POS
    if rate < 45:
        return STATUS_NEG
    return "var(--ink-2)"


def _ret_color(v: float | None) -> str:
    if v is None or pd.isna(v) or v == 0:
        return "var(--ink-3)"
    return STATUS_POS if v > 0 else STATUS_NEG


def _calibration_band_html(acc_df: pd.DataFrame) -> str:
    """The hero strip: one calibration cell per signal type.

    BUY/ACCUMULATE/WATCH show 5d win rate; CAUTION shows 5d avoid rate.
    Sub-line carries sample size and the 10d average move.
    """
    min_samples = 3
    specs = [
        ("BUY", "win", "should we have bought"),
        ("ACCUMULATE", "win", "did adds pay off"),
        ("WATCH", "win", "did the setups fire"),
        ("CAUTION", "avoid", "right to stay away"),
        ("AVOID", "avoid", "right to stay out"),
    ]
    cells = ""
    for sig, mode, _gloss in specs:
        data = acc_df[acc_df["signal"] == sig] if not acc_df.empty else pd.DataFrame()
        count = len(data)
        valid5 = data["return_5d"].dropna() if "return_5d" in data.columns else pd.Series(dtype=float)
        valid10 = data["return_10d"].dropna() if "return_10d" in data.columns else pd.Series(dtype=float)
        label = "5d avoid rate" if mode == "avoid" else "5d win rate"

        if len(valid5) >= min_samples:
            rate = (valid5 <= 0).mean() * 100 if mode == "avoid" else (valid5 > 0).mean() * 100
            col = _rate_color(rate)
            # Numeral stays --ink (neutral). Performance (good/weak) rides a thin
            # meter below it — so a low ACCUMULATE win-rate no longer renders in
            # CAUTION-red and read as a signal. The meter matches the by-name
            # winbars, keeping "rate = a bar" consistent across the page.
            val_html = (
                f'<div class="cval">{rate:.0f}%</div>'
                f'<div class="cbar"><i style="width:{rate:.0f}%;background:{col};"></i></div>'
            )
        else:
            val_html = f'<div class="cval muted">{"Pending" if count else "—"}</div>'

        sub = f"{label} · n={count}"
        if len(valid10) >= min_samples:
            sub += f" · 10d {valid10.mean():+.1f}%"
        color = SIGNAL_COLORS.get(sig, "#9F988B")
        cells += (
            f'<div class="calib-cell">'
            f'<div class="clabel"><span class="cdot" style="background:{color};"></span>{sig}</div>'
            f'{val_html}<div class="csub">{sub}</div>'
            f'</div>'
        )
    return f'<div class="calib-grid">{cells}</div>'


def _winbar_html(rate: float | None) -> str:
    if rate is None:
        return ('<div class="winbar-wrap"><div class="winbar"></div>'
                '<span class="winbar-pct led-empty">—</span></div>')
    col = _rate_color(rate)
    return (
        f'<div class="winbar-wrap"><div class="winbar">'
        f'<div class="winbar-fill" style="width:{rate:.0f}%;background:{col};"></div></div>'
        f'<span class="winbar-pct" style="color:{col};">{rate:.0f}%</span></div>'
    )


def _ret_num_cell(v: float | None) -> str:
    if v is None or pd.isna(v):
        return '<div class="led-num led-empty">—</div>'
    return f'<div class="led-num" style="color:{_ret_color(v)};">{v:+.1f}%</div>'


def _episode_table_html(eps: pd.DataFrame) -> str:
    """Compact per-name episode table — lives inside the row's drill-down."""
    eps = eps.sort_values("start", ascending=False)
    rows = ""
    for _, e in eps.iterrows():
        ret = e["return_pct"]
        peak = e["run_during_pct"]
        verdict = e["verdict"] or "—"
        vcol = "var(--ink-3)"
        if "✓" in verdict:
            vcol = STATUS_POS
        elif "✗" in verdict:
            vcol = STATUS_NEG
        elif "⚠" in verdict:
            vcol = STATUS_WARN
        exit_lbl = "open" if e["is_active"] else (
            e["exit_date"].strftime("%Y-%m-%d") if pd.notna(e["exit_date"]) else "—"
        )
        entry_p = f'{e["entry_price"]:.2f}' if pd.notna(e["entry_price"]) else "—"
        exit_p = f'{e["exit_price"]:.2f}' if pd.notna(e["exit_price"]) else "—"
        ret_s = f'{ret:+.1f}%' if pd.notna(ret) else "—"
        peak_s = f'{peak:+.1f}%' if pd.notna(peak) else "—"
        rows += (
            f'<tr>'
            f'<td>{_signal_pill_html(e["signal"], small=True)}</td>'
            f'<td>{e["start"].strftime("%Y-%m-%d")} → {exit_lbl}</td>'
            f'<td class="num">{int(e["duration_days"])}d</td>'
            f'<td class="num">{entry_p} → {exit_p}</td>'
            f'<td class="num" style="color:{_ret_color(ret)};">{ret_s}</td>'
            f'<td class="num">{peak_s}</td>'
            f'<td style="color:{vcol};">{verdict}</td>'
            f'</tr>'
        )
    return (
        '<table class="ep-table"><thead><tr>'
        '<th scope="col">Signal</th><th scope="col">Window</th>'
        '<th scope="col" class="num">Held</th>'
        '<th scope="col" class="num">Entry → Exit/Now</th>'
        '<th scope="col" class="num">Return</th>'
        '<th scope="col" class="num">Peak run</th><th scope="col">Verdict</th>'
        '</tr></thead><tbody>'
        f'{rows}</tbody></table>'
    )


def _name_ledger_html(episodes: pd.DataFrame, current_signal: dict) -> str:
    """One <details> block per name: summary scorecard row + episode drill-down.

    Sorted scored-names-first (by win rate, then avg return); names with no
    closed trades sink to the bottom.
    """
    rows: list[tuple] = []
    for ticker, tk_eps in episodes.groupby("ticker"):
        if tk_eps.empty:
            continue
        scored = tk_eps[tk_eps["signal"].isin(["BUY", "ACCUMULATE", "CAUTION", "AVOID"]) & ~tk_eps["is_active"]]
        n_scored = len(scored)
        wins = int(scored["verdict"].isin(["✓ profit", "✓ avoided"]).sum())
        win_rate = (wins / n_scored * 100) if n_scored else None
        rets = tk_eps["return_pct"].dropna()
        avg = rets.mean() if len(rets) else None
        best = rets.max() if len(rets) else None
        worst = rets.min() if len(rets) else None
        open_n = int(tk_eps["is_active"].sum())

        display_tk = _escape_dollars(display_ticker(ticker))
        cur_sig = current_signal.get(ticker, "HOLD")
        cluster = _escape_dollars(CLUSTER_MAP.get(ticker, ""))

        eps_cell = f'{len(tk_eps)}'
        if open_n:
            eps_cell += f'<span class="led-open"> · {open_n} open</span>'

        summary = (
            '<summary>'
            f'<div class="led-tk">{display_tk}</div>'
            f'<div class="led-name">{cluster}</div>'
            f'<div>{_signal_pill_html(cur_sig, small=True)}</div>'
            f'<div class="led-num">{eps_cell}</div>'
            f'{_winbar_html(win_rate)}'
            f'{_ret_num_cell(avg)}'
            f'{_ret_num_cell(best)}'
            f'{_ret_num_cell(worst)}'
            '</summary>'
        )
        body = f'<div class="tk-drilldown">{_episode_table_html(tk_eps)}</div>'
        block = f'<details class="led-details" data-signal="{_escape_attr(cur_sig)}">{summary}{body}</details>'

        # sort: scored names first (group 0) by -win_rate, -avg; then the rest
        if win_rate is not None:
            key = (0, -win_rate, -(avg if avg is not None else -999))
        else:
            key = (1, 0, -(avg if avg is not None else -999))
        rows.append((key, block))

    rows.sort(key=lambda r: r[0])
    head = (
        '<div class="led-head" role="row">'
        '<div role="columnheader">Name</div>'
        '<div role="columnheader">Sector</div>'
        '<div role="columnheader">Now</div>'
        '<div role="columnheader" class="led-num">Episodes</div>'
        '<div role="columnheader">Trades won</div>'
        '<div role="columnheader" class="led-num">Avg</div>'
        '<div role="columnheader" class="led-num">Best</div>'
        '<div role="columnheader" class="led-num">Worst</div>'
        '</div>'
    )
    # Wrapped in .tk-scroll so the fixed-column ledger swipes horizontally on
    # phones rather than clipping the Avg/Best/Worst columns off the edge.
    body = head + "".join(b for _, b in rows)
    return f'<div class="tk-scroll" role="table" aria-label="Per-name track record">{body}</div>'


def render_signal_tracker_page(reports: dict, prices_df: pd.DataFrame) -> None:
    """Render the Signal Tracker page — the Performance Ledger.

    Three tiers, verdict-first:
      1. Calibration band  — is the pipeline systematically any good?
      2. By-name ledger    — which names' calls work, click to see episodes.
      3. Secondary detail  — signal changes + paper-trade log (collapsed).

    Args:
        reports: filtered reports dict (date-keyed).
        prices_df: filtered SQLite prices DataFrame.
    """
    st.markdown(
        '<div class="section-head"><h2>Signal Tracker</h2>'
        '<span class="sub">Track record · calibration</span></div>',
        unsafe_allow_html=True,
    )
    sig_df = extract_signal_history(reports)

    if sig_df.empty:
        st.warning("No signal data available yet.")
        st.stop()

    tickers = sorted(sig_df["ticker"].unique())

    # Filter lives in a popover so the page no longer opens on a wall of chips.
    with st.popover(f"Filter names · {len(tickers)} selected", use_container_width=False):
        selected_tickers = st.multiselect(
            "Names to include", tickers, default=tickers, label_visibility="collapsed",
        )
    if not selected_tickers:
        st.info("Select at least one name in the filter.")
        st.stop()

    # ── 1. Calibration band (across ALL tickers — the headline sanity check) ──
    acc_df = compute_signal_accuracy(sig_df, prices_df)
    st.caption(
        "Forward-return calibration across **all** tracked names, deduped to the "
        "first day of each signal streak. BUY/ACCUMULATE/WATCH: % that rose 5 "
        "sessions later. CAUTION: % that fell (loss avoided)."
    )
    if acc_df.empty:
        st.caption("No signals tracked yet — calibration populates as signals accumulate.")
    else:
        st.markdown(_calibration_band_html(acc_df), unsafe_allow_html=True)
        hold_count = len(sig_df[sig_df["signal"] == "HOLD"])
        if hold_count:
            st.caption(f"HOLD: {hold_count} ticker-days, not scored (non-directional).")

    # ── 2. By-name performance ledger (replaces 27 stacked tables) ──
    st.markdown(
        '<div class="section-head" style="margin-top:26px;"><h2>By Name</h2>'
        '<span class="sub">Click a row for its episodes</span></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "One row per name. *Trades won* = share of closed BUY/ACCUMULATE/CAUTION "
        "episodes that worked out (profit, or loss avoided). Return uses trade-"
        "economics: BUY/ACCUMULATE is held through HOLD/WATCH and closes on the "
        "next CAUTION; CAUTION runs until the next BUY/ACCUMULATE. Names with no "
        "closed trades sort last."
    )

    episodes = build_signal_episodes(
        sig_df[sig_df["ticker"].isin(selected_tickers)], prices_df
    )
    if not episodes.empty:
        actionable_mask = episodes["signal"].isin(["BUY", "ACCUMULATE", "CAUTION", "AVOID"])
        watch_triggered = (episodes["signal"] == "WATCH") & (
            episodes["run_during_pct"].fillna(0) >= 5
        )
        episodes = episodes[actionable_mask | watch_triggered]

    if episodes.empty:
        st.info("No actionable episodes for the selected names yet.")
    else:
        latest = sig_df.sort_values("date").groupby("ticker")["signal"].last().to_dict()
        st.markdown(_name_ledger_html(episodes, latest), unsafe_allow_html=True)

    # ── 3. Secondary detail (collapsed by default) ──
    filtered = sig_df[sig_df["ticker"].isin(selected_tickers)]
    changes = []
    for ticker in selected_tickers:
        tk = filtered[filtered["ticker"] == ticker].sort_values("date")
        for i in range(1, len(tk)):
            prev, curr = tk.iloc[i - 1], tk.iloc[i]
            if prev["signal"] != curr["signal"]:
                changes.append({
                    "Date": curr["date"].strftime("%Y-%m-%d"),
                    "Ticker": display_ticker(ticker),
                    "From": prev["signal"],
                    "To": curr["signal"],
                    "Rationale": curr["rationale"][:200] if curr["rationale"] else "",
                })

    with st.expander(f"Signal changes ({len(changes)}) — what flipped, and why", expanded=False):
        if changes:
            st.dataframe(pd.DataFrame(changes), width="stretch", hide_index=True)
        else:
            st.caption("No signal changes in the selected names / date range.")

    _render_paper_trade_outcomes()


def _render_paper_trade_outcomes() -> None:
    """Pipeline paper-trade log — a separate data source, kept collapsed."""
    sig_log = load_signal_log()
    title = "Paper trade outcomes — realised returns from the pipeline log"
    with st.expander(title, expanded=False):
        st.caption(
            "Realised returns from the pipeline's own log — `entry_price` and "
            "`invalidation` are what the pipeline saw at signal time, not "
            "reconstructed after the fact. Outcomes fill in as trading days elapse."
        )
        if sig_log.empty:
            st.info("No signal log data yet — `signal_log.csv` appears after the next pipeline run.")
            return

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
            return

        total_rows = len(sig_log)
        by_type = sig_log["entry_type"].value_counts().to_dict()
        summary_cols = st.columns(3)
        summary_cols[0].metric("Total Signals Logged", total_rows)
        summary_cols[1].metric("Standard Entries", by_type.get("standard", 0))
        summary_cols[2].metric("Monitor (non-entry)", by_type.get("monitor", 0))

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

        open_rows = sig_log[sig_log["price_after_20d"].isna()].copy()
        if not open_rows.empty:
            with st.expander(f"Open positions ({len(open_rows)}) — outcomes still resolving"):
                open_display = open_rows[[
                    "date", "ticker", "signal", "entry_type",
                    "entry_price", "invalidation", "upside_target",
                    "price_after_5d", "price_after_10d",
                ]].copy()
                open_display["ticker"] = open_display["ticker"].map(display_ticker)
                open_display["date"] = open_display["date"].dt.strftime("%Y-%m-%d")
                st.dataframe(open_display, width="stretch", hide_index=True)
