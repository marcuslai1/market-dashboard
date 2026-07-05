"""Signal Tracker page: episode history, aggregate calibration, paper-trade outcomes.

Also home to the signal-history helpers (`extract_signal_history`,
`build_signal_episodes`, `_classify_episode_verdict`) and the accuracy helper
(`compute_signal_accuracy`) — the Signal Tracker is their primary consumer.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.paper_book import render_paper_book
from lib.catalog import CLUSTER_MAP, RETIRED_TICKERS, SIGNAL_COLORS
from lib.charts import INK_FALLBACK, STATUS_NEG, STATUS_POS, STATUS_WARN
from lib.data_loader import load_changelog, load_paper_nav
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


# Matured samples below this floor -> flag the cell "thin" (mirrors the
# pipeline's DECISION_GRADE_MIN_ALPHA_N). Below MIN_SAMPLES a rate is noise.
DECISION_GRADE_MIN = 10
MIN_SAMPLES = 3

_SCORECARD_SPECS = [
    ("BUY", "win", "Enter now"),
    ("ACCUMULATE", "win", "Starter position"),
    ("WATCH", "win", "Wait for the trigger"),
    ("CAUTION", "avoid", "Wait weeks · price wrong"),
    ("AVOID", "avoid", "Wait quarters · story broken"),
]


def _scorecard_html(acc_df: pd.DataFrame) -> str:
    """Plain-language signal scorecard: one cell per signal, showing how often
    the call went the right way 5 sessions out, with an honest small-sample
    flag.

    BUY/ACCUMULATE/WATCH score a rise as right; CAUTION/AVOID score a drop as
    right (you avoided it). `thin` mirrors the pipeline's decision-grade floor —
    a rate resting on fewer than DECISION_GRADE_MIN calls is not to be trusted,
    however tidy it looks.
    """
    cells = ""
    for sig, mode, verb in _SCORECARD_SPECS:
        data = acc_df[acc_df["signal"] == sig] if not acc_df.empty else pd.DataFrame()
        valid5 = (data["return_5d"].dropna()
                  if "return_5d" in data.columns else pd.Series(dtype=float))
        n = len(valid5)
        color = SIGNAL_COLORS.get(sig, INK_FALLBACK)
        # A shown rate below the decision-grade floor ghosts the whole cell (see
        # .calib-cell.thin) so a thin sample can't read as confidently as a solid
        # one — the small ⚠ flag alone is too easy to skim past.
        cell_thin = False

        if n >= MIN_SAMPLES:
            right = int((valid5 <= 0).sum() if mode == "avoid" else (valid5 > 0).sum())
            rate = right / n * 100
            col = _rate_color(rate)
            val_html = (
                f'<div class="cval">{rate:.0f}%</div>'
                f'<div class="cbar"><i style="width:{rate:.0f}%;background:{col};"></i></div>'
            )
            sub = f"right {right} of {n} · 5d"
            if n < DECISION_GRADE_MIN:
                cell_thin = True
                flag = f'<div class="sc-flag thin">⚠ thin — only {n} calls</div>'
            else:
                flag = f'<div class="sc-flag">n={n} · holding up</div>'
        else:
            val_html = f'<div class="cval muted">{"Pending" if n else "—"}</div>'
            sub = f"{n} of {MIN_SAMPLES}+ needed"
            flag = '<div class="sc-flag">not enough yet</div>'

        cells += (
            f'<div class="calib-cell{" thin" if cell_thin else ""}">'
            f'<div class="clabel"><span class="cdot" style="background:{color};"></span>{sig}</div>'
            f'<div class="sc-verb">{verb}</div>'
            f'{val_html}'
            f'<div class="csub">{sub}</div>'
            f'{flag}'
            f'</div>'
        )
    return f'<div class="calib-grid">{cells}</div>'


def _changelog_sub(entries: list) -> str:
    """Section-head sub for the change log, carrying the newest entry's date.

    data/changelog.json is hand-maintained; surfacing "latest YYYY-MM-DD" makes
    a rotting log visibly stale instead of silently posing as current.
    Order-independent (takes the max date, ISO strings sort correctly).
    """
    base = "Recent updates to how these signals are built"
    dates = [str(e.get("date")) for e in entries
             if isinstance(e, dict) and e.get("date")]
    if not dates:
        return base
    return f"{base} · latest {_escape_dollars(max(dates))}"


def _changelog_strip_html(entries: list) -> str:
    """Compact dated strip of recent methodology changes — the 'what we've
    changed' view. Empty list -> '' so the caller can skip the whole section.
    """
    if not entries:
        return ""
    items = ""
    for e in entries[:10]:
        if not isinstance(e, dict):
            continue
        date = _escape_dollars(str(e.get("date", "")))
        title = _escape_dollars(str(e.get("title", "")))
        note = _escape_dollars(str(e.get("note", "")))
        items += (
            f'<div class="chg-item">'
            f'<div class="chg-date">{date}</div>'
            f'<div class="chg-body">'
            f'<span class="chg-title">{title}</span>'
            f'<span class="chg-note">{note}</span>'
            f'</div></div>'
        )
    return f'<div class="chg-log">{items}</div>' if items else ""


_REGIME_UNIVERSE = 3  # trend_up / chop / trend_down — the weather we need to see


def _readiness_html(calibration_insights) -> str:
    """The trust meter: how close the track record is to being decision-grade,
    read from the pipeline's own calibration_insights (regimes seen, matured
    calls, and how many signals clear the >=10-matured / >=2-regime bar). Frames
    the scorecard so a single-regime record can't be mistaken for proof. Returns
    '' when there is nothing scored yet."""
    perf = (calibration_insights or {}).get("signal_performance") or {}
    if not perf:
        return ""
    regimes: set = set()
    total_matured = 0
    decision_grade = 0
    scored = 0
    for cell in perf.values():
        if not isinstance(cell, dict):
            continue
        scored += 1
        regimes.update(cell.get("regimes_present") or [])
        total_matured += int(cell.get("n_matured_10d") or 0)
        if (int(cell.get("n_alpha_10d") or 0) >= DECISION_GRADE_MIN
                and not cell.get("single_regime")):
            decision_grade += 1
    n_regimes = len(regimes)
    if decision_grade > 0 and n_regimes >= 2:
        verdict = ("Some signals now have cross-regime evidence — still read the "
                   "per-signal sample sizes below before leaning on any one.")
        tone = ""
    else:
        verdict = ("Read the scorecard as directional, not proven. A second market "
                   "regime — a downturn or a choppy stretch — is what turns this "
                   "into a real verdict.")
        tone = " warn"
    stats = (
        f'<div class="rd-stat"><b>{n_regimes} of {_REGIME_UNIVERSE}</b>'
        f"<span>market regimes seen</span></div>"
        f'<div class="rd-stat"><b>{total_matured}</b>'
        f"<span>matured calls</span></div>"
        f'<div class="rd-stat"><b>{decision_grade} of {scored}</b>'
        f"<span>signals decision-grade</span></div>"
    )
    return (f'<div class="rd-meter{tone}">'
            f'<div class="rd-stats">{stats}</div>'
            f'<div class="rd-verdict">{verdict}</div></div>')


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
    # Neutral numeral (no sign colour), matching the Episodes cell and the
    # calibration cards. For CAUTION names — most of the ledger — a negative
    # return is a *correct* call (loss avoided), so red/green by raw sign inverts
    # the meaning. The direction-aware "Trades won" winbar carries performance;
    # the +/- sign still shows direction. (UX-ST-1)
    if v is None or pd.isna(v):
        return '<div class="led-num led-empty">—</div>'
    return f'<div class="led-num">{v:+.1f}%</div>'


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
            f'<td class="num">{ret_s}</td>'
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


@st.cache_data(max_entries=4)
def _history_and_accuracy_cached(
    cache_key: tuple, _reports: dict, _prices: pd.DataFrame,
) -> tuple:
    """History + accuracy frames, memoized on the cheap corpus fingerprint.

    The transforms are O(reports × tickers) and used to rerun on every
    filter/toggle interaction (review P7-2). ``cache_key`` is
    ``(data_fingerprint(), date_start, date_end)`` from the caller; the heavy
    inputs are ``_``-prefixed so ``st.cache_data`` never hashes them.
    """
    sig_df = extract_signal_history(_reports)
    acc_df = compute_signal_accuracy(sig_df, _prices)
    return sig_df, acc_df


@st.cache_data(max_entries=8)
def _episodes_cached(
    cache_key: tuple, selected: tuple, _sig_df: pd.DataFrame, _prices: pd.DataFrame,
) -> pd.DataFrame:
    """Episode economics for the selected names, memoized per (key, selection)."""
    return build_signal_episodes(
        _sig_df[_sig_df["ticker"].isin(selected)], _prices
    )


def render_signal_tracker_page(
    reports: dict, prices_df: pd.DataFrame, cache_key: tuple | None = None,
) -> None:
    """Render the Signal Tracker page — the Performance Ledger.

    Four tiers, verdict-first:
      1. Readiness meter + scorecard — is the pipeline systematically any good?
         Corpus-wide by design: per-signal calibration is a property of the
         system, so the name filter deliberately does not touch it.
      1c. Paper book — the pipeline's mechanical paper portfolio (NAV vs
         SPY/SOXX), rendered from exports only; also corpus-wide.
      2. What we've changed — dated methodology strip.
      3. Detail drawers (collapsed) — by-name ledger + signal changes; the
         name filter lives here and scopes only these.

    Args:
        reports: filtered reports dict (date-keyed).
        prices_df: filtered SQLite prices DataFrame.
        cache_key: cheap hashable signature of (corpus, date range). When given,
            the derived frames are memoized on it; when None (tests, ad-hoc
            callers) the transforms run uncached.
    """
    st.markdown(
        '<div class="section-head"><h2>Signal Tracker</h2>'
        '<span class="sub">Track record · calibration</span></div>',
        unsafe_allow_html=True,
    )
    if cache_key is not None:
        sig_df, _acc_df_pre = _history_and_accuracy_cached(cache_key, reports, prices_df)
    else:
        sig_df = extract_signal_history(reports)
        _acc_df_pre = None

    if sig_df.empty:
        st.warning("No signal data available yet.")
        st.stop()

    # ── 1. Readiness meter + scorecard — the one clear read, framed by trust ──
    latest_report = reports.get(max(reports)) if reports else {}
    readiness = _readiness_html(latest_report.get("calibration_insights"))
    if readiness:
        st.markdown(readiness, unsafe_allow_html=True)

    acc_df = _acc_df_pre if _acc_df_pre is not None else compute_signal_accuracy(sig_df, prices_df)
    st.caption(
        "How often each signal went the right way, 5 sessions later. "
        "BUY / ACCUMULATE / WATCH count a **rise** as right; CAUTION / AVOID "
        "count a **drop** as right (you avoided it). This is **raw price "
        "direction** — the benchmark-relative view (alpha vs the market) is on "
        "the Briefing's calibration band."
    )
    if acc_df.empty:
        st.caption("No signals tracked yet — the scorecard fills in as calls accumulate.")
    else:
        st.markdown(_scorecard_html(acc_df), unsafe_allow_html=True)
        hold_count = len(sig_df[sig_df["signal"] == "HOLD"])
        if hold_count:
            st.caption(f"HOLD: {hold_count} ticker-days, not scored (non-directional).")

    # ── 1c. Paper book — the pipeline's mechanical NAV lane. Corpus-scoped:
    # the name filter below deliberately does not touch it (page contract,
    # spec 2026-07-05-paper-book-band-design). Skips itself until the
    # pipeline's paper_portfolio block / paper_nav.csv export first lands.
    render_paper_book(latest_report, load_paper_nav())

    # ── 2. What we've changed — recent methodology updates ──
    changelog = load_changelog()
    strip = _changelog_strip_html(changelog)
    if strip:
        st.markdown(
            '<div class="section-head" style="margin-top:30px;">'
            "<h2>What we've changed</h2>"
            f'<span class="sub">{_changelog_sub(changelog)}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(strip, unsafe_allow_html=True)

    # ── 3. Detail drawers (collapsed — the page leads with the scorecard) ──
    # The name filter sits HERE, not at the top: it scopes only the drawers
    # below, and placing it above the corpus-wide scorecard read as if it
    # filtered that too. Popover so the section doesn't open on a wall of chips.
    tickers = sorted(sig_df["ticker"].unique())
    with st.popover(f"Filter names · {len(tickers)} tracked", use_container_width=False):
        selected_tickers = st.multiselect(
            "Names to include", tickers, default=tickers, label_visibility="collapsed",
        )
    if not selected_tickers:
        st.info("Select at least one name in the filter.")
        return

    with st.expander("By name — each name's track record + episodes", expanded=False):
        st.caption(
            "One row per name. *Trades won* = share of closed BUY/ACCUMULATE/"
            "CAUTION episodes that worked out (profit, or loss avoided). "
            "BUY/ACCUMULATE is held through HOLD/WATCH and closes on the next "
            "CAUTION; CAUTION runs until the next BUY/ACCUMULATE. Names with no "
            "closed trades sort last."
        )
        if cache_key is not None:
            episodes = _episodes_cached(
                cache_key, tuple(sorted(selected_tickers)), sig_df, prices_df
            )
        else:
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



# The paper-trade-outcomes block (a second scoring system: entry types, hit-
# invalidation, realised return by signal x entry type) was CUT 2026-07-04 —
# it duplicated the scorecard's job and was the densest thing on the page.
# Its pipeline-log data (signal_log.csv) is still exported. The paper-book
# band (tier 1c) is NOT that table returning: it renders the pipeline's own
# paper_portfolio lane — one engine, exported numbers, zero dashboard math
# (spec 2026-07-05-paper-book-band-design).
