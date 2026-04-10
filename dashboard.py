"""MarketReport Analytics Dashboard.

Run with: streamlit run dashboard.py
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Config ──
DATA_DIR = Path(__file__).parent / "data"

# Tickers removed from the watchlist — filter from all dashboard views.
# Historical data is preserved in the raw JSONs/SQLite if needed.
RETIRED_TICKERS = {"C6L_SI", "Z74_SI", "XLE", "VUAA_L", "COHR"}

st.set_page_config(page_title="MarketReport Dashboard", layout="wide")

# ── Theme CSS: navy-blue dark theme matching PDF report palette ──
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Global: navy-blue dark theme ── */
.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #1a1a2e;
}
[data-testid="stSidebar"] {
    background: #121f3d;
    border-right: 1px solid #2a3a5c;
}

/* ── Metric cards: panel treatment ── */
[data-testid="stMetric"] {
    background: #16213e;
    border: 1px solid #2a3a5c;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #b0b0b0 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
}

/* ── Typography: tighter, financial ── */
h1 {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
    color: #e0e0e0 !important;
}
h2, [data-testid="stSubheader"] {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: #e0e0e0 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
h3 {
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: #b0b0b0 !important;
}

/* ── Dividers ── */
hr {
    border-color: #2a2a4a !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #16213e;
    border: 1px solid #2a3a5c;
    border-radius: 8px;
}
[data-testid="stExpander"] summary span {
    font-weight: 600 !important;
    font-size: 0.9em;
}

/* ── Selectbox / inputs ── */
.stSelectbox [data-baseweb="select"] {
    background-color: #16213e;
    border-color: #2a3a5c;
    border-radius: 6px;
}
.stSelectbox [data-baseweb="select"]:hover {
    border-color: #3498db;
}
[data-baseweb="popover"] [data-baseweb="menu"] {
    background-color: #121f3d;
    border: 1px solid #2a3a5c;
}

/* ── Buttons ── */
.stButton button {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #2a3a5c;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85em;
    transition: background 0.15s, border-color 0.15s;
}
.stButton button:hover {
    background-color: #16213e;
    border-color: #3498db;
    color: #ffffff;
}

/* ── Dataframes ── */
[data-testid="stDataFrame"] {
    border: 1px solid #2a3a5c;
    border-radius: 8px;
    overflow: hidden;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid #2a3a5c;
}
.stTabs [data-baseweb="tab"] {
    color: #b0b0b0;
    font-size: 0.85em;
    font-weight: 500;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    color: #e0e0e0 !important;
    font-weight: 600;
    border-bottom: 2px solid #3498db !important;
}

/* ── Captions ── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.78rem !important;
    color: #b0b0b0 !important;
}

/* ── Sidebar header ── */
.sidebar-header {
    text-align: center;
    padding: 16px 8px 12px;
    border-bottom: 1px solid #2a3a5c;
    margin-bottom: 12px;
}
.sidebar-header h2 {
    color: #e0e0e0 !important;
    font-size: 1.1em !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em;
    margin: 0;
    text-transform: none !important;
}
.sidebar-header .subtitle {
    color: #b0b0b0;
    font-size: 0.75em;
    margin-top: 2px;
}

/* ── Sidebar status badge ── */
.sidebar-status {
    background: #16213e;
    border: 1px solid #2a3a5c;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 8px 0;
    font-size: 0.8em;
}
.sidebar-status .status-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 0;
}
.sidebar-status .status-label { color: #b0b0b0; }
.sidebar-status .status-value { color: #e0e0e0; font-weight: 600; }
</style>""", unsafe_allow_html=True)


def _escape_dollars(text: str) -> str:
    """Escape $ signs so Streamlit doesn't render them as LaTeX."""
    return text.replace("$", "\\$") if text else text


def _price_str(price, currency: str = "USD") -> str:
    """Format a price with currency-aware prefix, escaped for Streamlit."""
    if price is None:
        return "—"
    pfx = "S\\$" if currency == "SGD" else "\\$"
    return f"{pfx}{price:,.2f}"


# ── Data loading (cached) ──
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
    csv_path = DATA_DIR / "market_data.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        if "ticker" in df.columns:
            df = df[~df["ticker"].isin(RETIRED_TICKERS)]
    return df


@st.cache_data(ttl=300)
def load_pipeline_stats() -> pd.DataFrame:
    """Load pipeline article stats from CSV export."""
    csv_path = DATA_DIR / "pipeline_stats.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    extra_cols = ["yfinance_articles", "yfinance_chars", "tavily_articles",
                  "tavily_chars", "system_prompt_chars", "watchlist_data_chars",
                  "memory_chars", "total_prompt_chars"]
    # Ensure all expected columns exist (fill missing with NaN)
    for c in extra_cols:
        if c not in df.columns:
            df[c] = float("nan")
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_token_usage() -> pd.DataFrame:
    """Load Claude API usage from CSV export."""
    csv_path = DATA_DIR / "claude_analysis.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=300)
def load_report_memory() -> dict:
    """Load report_memory.json for narrative tracking."""
    mem_path = DATA_DIR / "report_memory.json"
    # Also check legacy path for local development
    if not mem_path.exists():
        mem_path = Path(__file__).parent / "market_data" / "report_memory.json"
    if not mem_path.exists():
        return {}
    try:
        return json.loads(mem_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


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
                "rationale": data.get("signal_rationale", ""),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


_SCENARIO_NORMALIZE = {
    "base_case": "base", "optimistic_case": "optimistic",
    "pessimistic_case": "pessimistic",
}


def _norm_scenario(name: str) -> str:
    """Normalise scenario key to a consistent short name, then title-case."""
    key = name.lower().strip()
    key = _SCENARIO_NORMALIZE.get(key, key)
    return key.replace("_", " ").title()


def _get_probs(rpt):
    """Extract scenario probabilities from either new or legacy format.

    Returns dict of {scenario_name: (display_string, midpoint_float)}.
    """
    geo = rpt.get("geopolitical", {})
    # New format: geopolitical.probabilities = {base: 50, ...}
    probs = geo.get("probabilities", {})
    if probs:
        return {_norm_scenario(k): (str(v), float(v) if v is not None else None) for k, v in probs.items()}
    # Legacy format: geopolitical.scenarios = {base_case: {probability: "50-55%"}}
    result = {}
    for name, sc in geo.get("scenarios", {}).items():
        prob_str = sc.get("probability", "—")
        mid = None
        try:
            cleaned = prob_str.replace("%", "").strip()
            if "-" in cleaned:
                lo, hi = cleaned.split("-")
                mid = (float(lo) + float(hi)) / 2
            elif cleaned:
                mid = float(cleaned)
        except (ValueError, AttributeError, TypeError):
            pass
        result[_norm_scenario(name)] = (prob_str, mid)
    return result


def extract_scenario_history(reports: dict) -> pd.DataFrame:
    """Build scenario probability tracking from all reports."""
    rows = []
    for date_str, report in reports.items():
        geo = report.get("geopolitical", {})

        # New simple format: geopolitical.probabilities = {base: 50, optimistic: 22, ...}
        probs = geo.get("probabilities", {})
        if probs:
            for name, val in probs.items():
                mid = None
                prob_str = ""
                try:
                    mid = float(val)
                    prob_str = f"{int(mid)}%"
                except (ValueError, TypeError):
                    pass
                rows.append({
                    "date": pd.to_datetime(date_str),
                    "scenario": _norm_scenario(name),
                    "probability_str": prob_str,
                    "probability_mid": mid,
                    "description": "",
                })
            continue  # Skip legacy format if new format present

        # Legacy format: geopolitical.scenarios = {base_case: {probability: "50-55%", ...}}
        scenarios = geo.get("scenarios", {})
        for name, sc in scenarios.items():
            prob_str = sc.get("probability", "")
            # Parse "50-55%" into midpoint
            mid = None
            try:
                cleaned = prob_str.replace("%", "").strip()
                if "-" in cleaned:
                    lo, hi = cleaned.split("-")
                    mid = (float(lo) + float(hi)) / 2
                elif cleaned:
                    mid = float(cleaned)
            except (ValueError, AttributeError):
                pass
            rows.append({
                "date": pd.to_datetime(date_str),
                "scenario": _norm_scenario(name),
                "probability_str": prob_str,
                "probability_mid": mid,
                "description": sc.get("description", ""),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def compute_signal_streaks(reports: dict) -> pd.DataFrame:
    """Compute consecutive days each ticker has held its current signal.

    Returns a DataFrame with columns: ticker, signal, days, vs_sma50_start, vs_sma50_end.
    vs_sma50_start/end track whether the ticker moved closer to entry during the streak.
    """
    sorted_dates = sorted(reports.keys(), reverse=True)
    if not sorted_dates:
        return pd.DataFrame()

    latest_report = reports[sorted_dates[0]]
    latest_wl = latest_report.get("watchlist", {})

    rows = []
    for ticker, data in latest_wl.items():
        current_signal = data.get("signal", "")
        if not current_signal:
            continue
        streak = 1
        vs_sma50_end = data.get("vs_sma50_pct")
        vs_sma50_start = vs_sma50_end

        for prev_date in sorted_dates[1:]:
            prev_wl = reports.get(prev_date, {}).get("watchlist", {})
            prev_data = prev_wl.get(ticker, {})
            if prev_data.get("signal") == current_signal:
                streak += 1
                prev_vs = prev_data.get("vs_sma50_pct")
                if prev_vs is not None:
                    vs_sma50_start = prev_vs
            else:
                break

        rows.append({
            "ticker": ticker,
            "signal": current_signal,
            "days": streak,
            "vs_sma50_start": vs_sma50_start,
            "vs_sma50_end": vs_sma50_end,
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


_SGX_SUFFIXES = {"_SI"}


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
    for ticker, grp in actionable.groupby("ticker"):
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


SIGNAL_COLORS = {
    "BUY": "#22c55e",
    "ACCUMULATE": "#3498db",
    "WATCH": "#f59e0b",
    "HOLD": "#6b7280",
    "CAUTION": "#ef4444",
}

# Streamlit markdown only supports named colors (:red[text], :green[text], etc.)
SIGNAL_ST_COLORS = {
    "BUY": "green",
    "ACCUMULATE": "blue",
    "WATCH": "orange",
    "HOLD": "gray",
    "CAUTION": "red",
}


def _render_signal_guide() -> None:
    """Render the collapsible Signal Guide panel."""
    with st.expander("Signal Guide", expanded=False):
        guide_html = f"""
<table style="width:100%;border-collapse:collapse;font-size:0.85em;margin-bottom:12px;">
<thead>
<tr style="border-bottom:1px solid #2a3a5c;">
  <th style="padding:6px 8px;text-align:left;color:#b0b0b0;width:120px;">Signal</th>
  <th style="padding:6px 8px;text-align:left;color:#b0b0b0;">If You Don't Own It</th>
  <th style="padding:6px 8px;text-align:left;color:#b0b0b0;">If You Already Own It</th>
</tr>
</thead>
<tbody>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;"><span style="color:#22c55e;font-weight:700;">● BUY</span></td>
  <td style="padding:8px;color:#e0e0e0;">Thesis has multiple independent support legs, technicals are clean (near 50-day SMA, RSI neutral, volume confirmed), and R:R is favourable. Consider entering.</td>
  <td style="padding:8px;color:#e0e0e0;">Hold and monitor. The thesis is working.</td>
</tr>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;"><span style="color:#3498db;font-weight:700;">● ACCUMULATE</span></td>
  <td style="padding:8px;color:#e0e0e0;">All 8 mechanical gates passed. R:R is favourable and thesis supports entry, but not all technical conditions are perfect. Start a position.</td>
  <td style="padding:8px;color:#e0e0e0;">Add to your position if sizing allows.</td>
</tr>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;"><span style="color:#f59e0b;font-weight:700;">● WATCH</span></td>
  <td style="padding:8px;color:#e0e0e0;">Thesis is intact but entry conditions aren't met yet — waiting for a specific trigger (pullback to SMA, volume confirmation, catalyst). Not actionable today.</td>
  <td style="padding:8px;color:#e0e0e0;">Hold. Nothing has changed to warrant action.</td>
</tr>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;"><span style="color:#6b7280;font-weight:700;">● HOLD</span></td>
  <td style="padding:8px;color:#e0e0e0;">Not interesting for entry — no clear catalyst, mixed technicals, or poor R:R. Ignore it.</td>
  <td style="padding:8px;color:#e0e0e0;">Keep your position. Thesis hasn't broken, but there's no reason to add.</td>
</tr>
<tr>
  <td style="padding:8px;"><span style="color:#ef4444;font-weight:700;">● CAUTION</span></td>
  <td style="padding:8px;color:#e0e0e0;">Stay away. Thesis is degrading, key support is broken, or valuation is extreme.</td>
  <td style="padding:8px;color:#e0e0e0;">Consider trimming or exiting. Something material has changed.</td>
</tr>
</tbody>
</table>
<div style="font-size:0.82em;color:#b0b0b0;line-height:1.5;margin-bottom:10px;">
<b style="color:#e0e0e0;">Key distinction:</b> WATCH, HOLD, and CAUTION all mean "don't enter now" — but for different reasons.
WATCH means "this is interesting, wait for a better price."
HOLD means "nothing to see here."
CAUTION means "actively avoid."
The difference matters when a signal changes — a WATCH moving to BUY is a setup working as expected,
while a HOLD moving to BUY is a new development worth investigating.
</div>
<div style="font-size:0.82em;color:#b0b0b0;line-height:1.5;margin-bottom:10px;">
<b style="color:#e0e0e0;">Signals are states, not a ladder.</b> A signal can change to any other signal in a single session.
A BUY becoming HOLD overnight doesn't mean the framework failed — it means new information changed the
situation fundamentally (e.g. a catalyst collapsed). There is no requirement for signals to move
one step at a time.
</div>
<div style="font-size:0.82em;color:#b0b0b0;line-height:1.5;margin-bottom:14px;">
<b style="color:#e0e0e0;">Fragility Gate:</b> BUY requires multiple independent support legs — distinct reasons the stock
should appreciate that don't depend on each other. If the entire thesis rests on a single catalyst whose failure would
collapse the case, the maximum signal is WATCH until the catalyst demonstrates multi-day durability or a second
independent leg emerges.
</div>
<div style="font-size:0.85em;margin-bottom:6px;"><b style="color:#e0e0e0;">Reading the Numbers</b></div>
<table style="width:100%;border-collapse:collapse;font-size:0.82em;">
<thead>
<tr style="border-bottom:1px solid #2a3a5c;">
  <th style="padding:6px 8px;text-align:left;color:#b0b0b0;width:100px;">Metric</th>
  <th style="padding:6px 8px;text-align:left;color:#b0b0b0;">What It Means</th>
  <th style="padding:6px 8px;text-align:left;color:#b0b0b0;width:280px;">Cell Colours</th>
</tr>
</thead>
<tbody>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;color:#e0e0e0;font-weight:600;">RSI</td>
  <td style="padding:8px;color:#b0b0b0;">Relative Strength Index (14-day). Measures whether a stock has been bought or sold too aggressively in recent sessions. Not a signal on its own — context matters.</td>
  <td style="padding:8px;color:#b0b0b0;">
    <span style="background:#1a3a2a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">Below 40</span> oversold (potentially attractive)
    &nbsp;&nbsp;<span style="padding:2px 6px;color:#e0e0e0;">40–70</span> neutral
    &nbsp;&nbsp;<span style="background:#3a1a1a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">Above 70</span> overbought (avoid)
  </td>
</tr>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;color:#e0e0e0;font-weight:600;">vs SMA50</td>
  <td style="padding:8px;color:#b0b0b0;">How far the current price is from the 50-day simple moving average — the stock's recent trend line. The pipeline uses this as the primary entry gate: the closer to the SMA, the cleaner the entry.</td>
  <td style="padding:8px;color:#b0b0b0;">
    <span style="background:#1a3a2a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">Within ±2%</span> clean entry zone
    &nbsp;&nbsp;<span style="background:#3a2a1a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">2–5% above</span> extended
    &nbsp;&nbsp;<span style="background:#3a1a1a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">&gt;5% above</span> blocked
  </td>
</tr>
<tr style="border-bottom:1px solid #2a3a5c20;">
  <td style="padding:8px;color:#e0e0e0;font-weight:600;">R:R</td>
  <td style="padding:8px;color:#b0b0b0;">Risk-to-Reward ratio. Compares the potential upside (to nearest resistance) against the downside (to the invalidation/stop level). An R:R of 2.4 means you stand to gain 2.4x what you're risking. Uses the nearest target only — not a distant best-case.</td>
  <td style="padding:8px;color:#b0b0b0;">
    <span style="background:#1a3a2a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">Above 2.0</span> favourable
    &nbsp;&nbsp;<span style="background:#3a2a1a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">1.0–2.0</span> mixed
    &nbsp;&nbsp;<span style="background:#3a1a1a;padding:2px 6px;border-radius:3px;color:#e0e0e0;">Below 1.0</span> unfavourable
  </td>
</tr>
<tr>
  <td style="padding:8px;color:#e0e0e0;font-weight:600;">Entry Block</td>
  <td style="padding:8px;color:#b0b0b0;">If present, the pipeline has mechanically blocked entry for this ticker — usually because the price is too far above the SMA50 or RSI is extreme. "None" means no block is active.</td>
  <td style="padding:8px;color:#b0b0b0;">—</td>
</tr>
</tbody>
</table>"""
        st.markdown(guide_html, unsafe_allow_html=True)


# ── Metric color helpers ──
def _metric_bg(value: float | None, thresholds: list[tuple[object, str]],
               default: str = "transparent") -> str:
    """Return a muted background color for a metric value.

    *thresholds* is a list of (test, color) pairs evaluated in order.
    Each *test* is a callable ``(value) -> bool``.
    """
    if value is None:
        return default
    for test, color in thresholds:
        if test(value):
            return color
    return default


_GREEN_BG = "#1a3a2a"
_ORANGE_BG = "#3a2a1a"
_RED_BG = "#3a1a1a"

_RSI_THRESHOLDS: list[tuple[object, str]] = [
    (lambda v: v < 40, _GREEN_BG),
    (lambda v: v > 70, _RED_BG),
]

_VS_SMA50_THRESHOLDS: list[tuple[object, str]] = [
    (lambda v: v > 5, _RED_BG),
    (lambda v: 2 < v <= 5, _ORANGE_BG),
    (lambda v: -2 <= v <= 2, _GREEN_BG),
    (lambda v: v < -2, _GREEN_BG),
]

_RR_THRESHOLDS: list[tuple[object, str]] = [
    (lambda v: v >= 2.0, _GREEN_BG),
    (lambda v: 1.0 <= v < 2.0, _ORANGE_BG),
    (lambda v: v < 1.0, _RED_BG),
]


# Reverse ticker_to_key: restore dots/hyphens/carets for display
TICKER_DISPLAY = {
    "D05_SI": "D05.SI", "O39_SI": "O39.SI", "U11_SI": "U11.SI",
    "DX_Y_NYB": "DX-Y.NYB", "CL_F": "CL=F", "GC_F": "GC=F",
    "VIX": "^VIX", "TNX": "^TNX",
}

# ── Sidebar header ──
st.sidebar.markdown(
    '<div class="sidebar-header">'
    '<h2>MarketReport</h2>'
    '<div class="subtitle">Signal Intelligence Dashboard</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Sidebar navigation ──
page = st.sidebar.radio(
    "Navigate",
    ["Today's Snapshot", "Daily Report", "Signal Tracker",
     "Pipeline Stats", "Ticker Comparison", "Scenario Log",
     "Report Comparison"],
    label_visibility="collapsed",
)

st.sidebar.divider()

# ── Mini status summary ──
_status_reports = load_all_reports()
_latest_date = max(_status_reports.keys()) if _status_reports else "—"
_latest_rpt = _status_reports.get(_latest_date, {})
_sig_counts = _latest_rpt.get("portfolio_snapshot", {}).get("signal_counts", {})

_status_html = '<div class="sidebar-status">'
_status_html += (
    '<div class="status-row">'
    '<span class="status-label">Latest report</span>'
    f'<span class="status-value">{_latest_date}</span></div>'
)
_status_html += (
    '<div class="status-row">'
    '<span class="status-label">Tickers</span>'
    f'<span class="status-value">{sum(_sig_counts.values())}</span></div>'
)
_sig_dots = ""
for _sig, _color in [("BUY", "#22c55e"), ("ACCUMULATE", "#3498db"),
                      ("WATCH", "#f59e0b"), ("HOLD", "#6b7280"),
                      ("CAUTION", "#ef4444")]:
    _cnt = _sig_counts.get(_sig, 0)
    if _cnt:
        _sig_dots += (
            f'<span style="color:{_color};font-weight:700;margin-right:8px;">'
            f'●{_cnt}</span>'
        )
_status_html += (
    '<div class="status-row" style="margin-top:4px;">'
    '<span class="status-label">Signals</span>'
    f'<span>{_sig_dots}</span></div>'
)
_status_html += '</div>'
st.sidebar.markdown(_status_html, unsafe_allow_html=True)

st.sidebar.divider()

# ── Date range filter ──
_default_end = date.today()
_default_start = _default_end - timedelta(days=30)
_range_presets = {"30 days": 30, "7 days": 7, "All": None}
_preset = st.sidebar.radio("Range", list(_range_presets.keys()), horizontal=True, key="range_preset")
_preset_days = _range_presets[_preset]
if _preset_days is not None:
    _pre_start = _default_end - timedelta(days=_preset_days)
else:
    _pre_start = date(2020, 1, 1)  # effectively "all time"
date_range = st.sidebar.date_input(
    "Date range", value=(_pre_start, _default_end), key="date_range"
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    DATE_START, DATE_END = date_range
else:
    DATE_START, DATE_END = _pre_start, _default_end


def filter_reports(reports: dict) -> dict:
    """Filter reports dict to the selected date range."""
    filtered = {}
    for date_str, rpt in reports.items():
        try:
            d = date.fromisoformat(date_str)
            if DATE_START <= d <= DATE_END:
                filtered[date_str] = rpt
        except ValueError:
            continue
    return filtered


def filter_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Filter price DataFrame to the selected date range."""
    if df.empty:
        return df
    return df[(df["date"].dt.date >= DATE_START) & (df["date"].dt.date <= DATE_END)]


st.sidebar.divider()

# ── Signal legend (coloured dots) ──
st.sidebar.markdown(
    '<div style="font-size:0.8em;color:#b0b0b0;line-height:1.6;">'
    '<span style="color:#22c55e;font-weight:700;">● BUY</span> — Enter now<br>'
    '<span style="color:#3498db;font-weight:700;">● ACCUMULATE</span> — Add on strength<br>'
    '<span style="color:#f59e0b;font-weight:700;">● WATCH</span> — Waiting for trigger<br>'
    '<span style="color:#6b7280;font-weight:700;">● HOLD</span> — Maintain<br>'
    '<span style="color:#ef4444;font-weight:700;">● CAUTION</span> — Trim / avoid'
    '</div>',
    unsafe_allow_html=True,
)

if st.sidebar.button("↻ Refresh Data"):
    st.cache_data.clear()
    st.rerun()


# ════════════════════════════════════════════
# PAGE 0: Today's Snapshot
# ════════════════════════════════════════════
if page == "Today's Snapshot":
    all_reports = load_all_reports()
    if not all_reports:
        st.error("No report files found in market_data/.")
        st.stop()

    sorted_dates = sorted(all_reports.keys(), reverse=True)
    latest_date = sorted_dates[0]
    report = all_reports[latest_date]
    prev_report = all_reports[sorted_dates[1]] if len(sorted_dates) >= 2 else None
    memory = load_report_memory()

    st.title("Today's Snapshot")
    st.caption(f"Report: **{latest_date}**")

    # ── Stance + signal count pills ──
    snapshot = report.get("portfolio_snapshot", {})
    stance = snapshot.get("overall_stance", "")
    signal_counts = snapshot.get("signal_counts", {})

    hcols = st.columns([3, 1, 1, 1, 1, 1])
    if stance:
        hcols[0].markdown(f"### {_escape_dollars(stance)}")
    else:
        hcols[0].markdown("### —")
    for i, sig in enumerate(["BUY", "ACCUMULATE", "WATCH", "HOLD", "CAUTION"]):
        count = signal_counts.get(sig, 0)
        color = SIGNAL_COLORS.get(sig, "#6b7280")
        hcols[i + 1].markdown(
            f"<div style='text-align:center;padding:4px;border-radius:6px;"
            f"background-color:{color}20;border:1px solid {color}'>"
            f"<b style='color:{color}'>{sig}</b><br>"
            f"<span style='font-size:1.4em;font-weight:bold'>{count}</span></div>",
            unsafe_allow_html=True,
        )

    _render_signal_guide()

    # ── Key benchmarks ──
    st.divider()
    benchmarks = report.get("benchmarks", {})
    SNAPSHOT_BM = ["SPY", "VIX", "WTI", "Gold", "SOXX"]
    bm_cols = st.columns(len(SNAPSHOT_BM))
    for i, bm_name in enumerate(SNAPSHOT_BM):
        bm = benchmarks.get(bm_name, {})
        price = bm.get("price")
        chg = bm.get("chg_pct")
        if chg is not None:
            delta_color = "inverse" if bm_name == "VIX" else "normal"
            bm_cols[i].metric(
                bm_name,
                f"{price:,.2f}" if price is not None else "—",
                f"{chg:+.2f}%",
                delta_color=delta_color,
            )
        else:
            bm_cols[i].metric(bm_name, f"{price:,.2f}" if price else "—")

    # ── Signal changes since yesterday ──
    st.divider()
    st.subheader("Signal Changes Since Yesterday")

    if prev_report is None:
        st.info("Only one report available — no comparison possible.")
    else:
        wl_today = report.get("watchlist", {})
        wl_yesterday = prev_report.get("watchlist", {})
        signal_rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
        changes = []

        for tk in sorted(set(wl_today) | set(wl_yesterday)):
            sig_old = wl_yesterday.get(tk, {}).get("signal", "—")
            sig_new = wl_today.get(tk, {}).get("signal", "—")
            if sig_old == sig_new:
                continue
            r_old = signal_rank.get(sig_old, 0)
            r_new = signal_rank.get(sig_new, 0)
            if sig_old == "—":
                arrow = "+"
            elif sig_new == "—":
                arrow = "-"
            elif r_new > r_old:
                arrow = "^"
            else:
                arrow = "v"

            display_tk = TICKER_DISPLAY.get(tk, tk)
            rationale = wl_today.get(tk, {}).get("signal_rationale", "")
            short_rationale = rationale[:150] + "..." if len(rationale) > 150 else rationale
            st_old = SIGNAL_ST_COLORS.get(sig_old, "gray")
            st_new = SIGNAL_ST_COLORS.get(sig_new, "gray")

            changes.append({
                "ticker": display_tk,
                "from_sig": sig_old,
                "to_sig": sig_new,
                "arrow": arrow,
                "rationale": short_rationale,
                "st_old": st_old,
                "st_new": st_new,
            })

        if changes:
            for c in changes:
                st.markdown(
                    f"**{c['ticker']}** {c['arrow']} "
                    f":{c['st_old']}[{c['from_sig']}] → :{c['st_new']}[{c['to_sig']}]"
                )
                if c["rationale"]:
                    st.caption(_escape_dollars(c["rationale"]))
        else:
            st.success("No signal changes since yesterday — steady state.")

    # ── Closest to Entry + Earnings ──
    st.divider()
    lo_cols = st.columns(2)

    with lo_cols[0]:
        st.subheader("Closest to Entry")
        watchlist = report.get("watchlist", {})
        closest = []
        for tk, d in watchlist.items():
            vs50 = d.get("vs_sma50_pct")
            sig = d.get("signal", "")
            if vs50 is not None and sig in ("WATCH", "HOLD") and vs50 > -2:
                closest.append((tk, vs50, sig))
        closest.sort(key=lambda x: abs(x[1]))

        if closest:
            for tk, vs50, sig in closest[:5]:
                display_tk = TICKER_DISPLAY.get(tk, tk)
                direction = "above" if vs50 > 0 else "below"
                st_c = SIGNAL_ST_COLORS.get(sig, "gray")
                st.markdown(
                    f"**{display_tk}**: {abs(vs50):.1f}% {direction} SMA50 "
                    f"— :{st_c}[{sig}]"
                )
        else:
            st.caption("No WATCH/HOLD tickers near SMA50.")

    with lo_cols[1]:
        st.subheader("Earnings This Week")
        earnings = report.get("earnings_calendar", [])
        approaching = [
            e for e in earnings
            if isinstance(e.get("days_until"), (int, float)) and e["days_until"] <= 7
        ]
        if approaching:
            for e in approaching:
                st.markdown(
                    f"**{e.get('ticker', '?')}**: "
                    f"{e.get('days_until', '?')} days away"
                )
        else:
            st.caption("No watchlist earnings within 7 days.")

    # ── Active Narratives ──
    st.divider()
    narratives = memory.get("active_narratives", [])
    active_narr = [n for n in narratives if n.get("status") == "active"]

    ncols = st.columns([1, 4])
    with ncols[0]:
        st.metric("Active Narratives", len(active_narr))
    with ncols[1]:
        if active_narr:
            top = max(active_narr, key=lambda n: n.get("last_updated", ""))
            st.markdown(f"**Latest:** {top.get('title', 'N/A')}")
            st.caption(_escape_dollars(top.get("summary", "")[:200]))

    if len(active_narr) > 1:
        with st.expander(f"All {len(active_narr)} active narratives"):
            for n in active_narr:
                title = n.get("title", "?")
                started = n.get("started", "?")
                tickers = ", ".join(n.get("affected_tickers", []))
                st.markdown(f"- **{title}** (since {started}) — {tickers}")


# ════════════════════════════════════════════
# PAGE 1: Daily Report Viewer
# ════════════════════════════════════════════
elif page == "Daily Report":
    st.title("Daily Report")
    reports = filter_reports(load_all_reports())
    if not reports:
        st.error("No report files found for the selected date range.")
        st.stop()

    dates = sorted(reports.keys(), reverse=True)
    selected = st.selectbox("Report Date", dates)
    report = reports[selected]
    watchlist = report.get("watchlist", {})
    all_reports = reports

    # ── 1. STANCE + SIGNAL COUNTS ──
    meta = report.get("meta", {})
    snapshot = report.get("portfolio_snapshot", {})
    signal_counts = snapshot.get("signal_counts", {})

    stance = snapshot.get("overall_stance", "")
    if stance:
        st.markdown(f"### {_escape_dollars(stance)}")

    scols = st.columns(5)
    for i, sig in enumerate(["BUY", "ACCUMULATE", "WATCH", "HOLD", "CAUTION"]):
        count = signal_counts.get(sig, 0)
        color = SIGNAL_COLORS.get(sig, "#6b7280")
        scols[i].markdown(
            f"<div style='text-align:center;padding:6px;border-radius:6px;"
            f"background-color:{color}20;border:1px solid {color}'>"
            f"<b style='color:{color}'>{sig}</b><br>"
            f"<span style='font-size:1.6em;font-weight:bold'>{count}</span></div>",
            unsafe_allow_html=True,
        )

    _render_signal_guide()

    # ── 2. ACTION SUMMARY — "What do I do today?" ──
    st.divider()
    st.subheader("Action Summary")
    action = report.get("action_summary", {})
    category_labels = {
        "consider_adding": ("Consider Adding", "green"),
        "accumulate": ("Accumulate", "blue"),
        "watch_for_entry": ("Watch for Entry", "orange"),
        "on_deck": ("On Deck — Fundamentally Attractive", "blue"),
        "caution_trim": ("Caution — Thesis Weakened", "red"),
        "new_stocks_to_watch": ("New Stocks to Watch", "blue"),
        "hold_no_action": ("Hold — No Action", "gray"),
    }
    any_actions = False
    for key, (label, color) in category_labels.items():
        items = action.get(key, [])
        if not items:
            continue
        any_actions = True
        st.markdown(f"**:{color}[{label}]** ({len(items)})")
        for item in items:
            if isinstance(item, dict):
                ticker = item.get("ticker", "?")
                note = _escape_dollars(item.get("note", ""))
                entry = _escape_dollars(item.get("entry_level", ""))
                line = f"- **{ticker}**: {note}"
                if entry:
                    line += f" | *{entry}*"
            else:
                line = f"- **{item}**"
            st.markdown(line)
    if not any_actions:
        st.caption("No actionable signals today.")

    # ── 3. SIGNAL CHANGES — "What's different?" ──
    st.divider()
    st.subheader("Signal Changes")

    sorted_dates = sorted(all_reports.keys())
    sel_idx = sorted_dates.index(selected) if selected in sorted_dates else -1
    prev_date = sorted_dates[sel_idx - 1] if sel_idx > 0 else None
    prev_report = all_reports.get(prev_date) if prev_date else None

    if prev_report is None:
        st.caption("No previous report to compare.")
    else:
        wl_today = watchlist
        wl_yesterday = prev_report.get("watchlist", {})
        signal_rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
        changes = []

        for tk in sorted(set(wl_today) | set(wl_yesterday)):
            sig_old = wl_yesterday.get(tk, {}).get("signal", "—")
            sig_new = wl_today.get(tk, {}).get("signal", "—")
            if sig_old == sig_new:
                continue
            r_old = signal_rank.get(sig_old, 0)
            r_new = signal_rank.get(sig_new, 0)
            if sig_old == "—":
                arrow = "+"
            elif sig_new == "—":
                arrow = "-"
            elif r_new > r_old:
                arrow = "^"
            else:
                arrow = "v"
            display_tk = TICKER_DISPLAY.get(tk, tk)
            rationale = wl_today.get(tk, {}).get("signal_rationale", "")
            short_rationale = rationale[:200] + "..." if len(rationale) > 200 else rationale
            st_old = SIGNAL_ST_COLORS.get(sig_old, "gray")
            st_new = SIGNAL_ST_COLORS.get(sig_new, "gray")
            changes.append({
                "ticker": display_tk, "from_sig": sig_old, "to_sig": sig_new,
                "arrow": arrow, "rationale": short_rationale,
                "st_old": st_old, "st_new": st_new,
            })

        if changes:
            for c in changes:
                st.markdown(
                    f"**{c['ticker']}** {c['arrow']} "
                    f":{c['st_old']}[{c['from_sig']}] -> :{c['st_new']}[{c['to_sig']}]"
                )
                if c["rationale"]:
                    st.caption(_escape_dollars(c["rationale"]))
        else:
            st.success("No signal changes — steady state.")

    # ── 4. WATCHLIST TABLE — scannable grid ──
    st.divider()
    st.subheader("Watchlist")
    st.caption(
        "Cell colors indicate entry quality: "
        "green = favourable, orange = caution, red = avoid"
    )
    if watchlist:
        wl_rows = []
        for tk, d in watchlist.items():
            sig = d.get("signal", "?")
            rr = d.get("risk_reward", {})
            curr = d.get("currency", "USD")
            pfx = "S$" if curr == "SGD" else "$"
            rsi_raw = d.get("rsi_14")
            vs50_raw = d.get("vs_sma50_pct")
            rr_raw = rr.get("ratio")
            rr_distorted = rr.get("rr_distorted", False)
            rr_display = "—"
            if rr_raw:
                rr_display = f"{rr_raw:.1f}*" if rr_distorted else f"{rr_raw:.1f}"
            wl_rows.append({
                "Ticker": TICKER_DISPLAY.get(tk, tk),
                "Price": f"{pfx}{d.get('price', 0):,.2f}" if d.get("price") else "—",
                "Chg%": f"{d.get('chg_pct', 0):+.2f}%" if d.get("chg_pct") is not None else "—",
                "Signal": sig,
                "RSI": f"{rsi_raw:.1f}" if rsi_raw else "—",
                "vs SMA50": f"{vs50_raw:+.1f}%" if vs50_raw is not None else "—",
                "R:R": rr_display,
                "_tk_key": tk,
                "_sig_rank": {"BUY": 1, "ACCUMULATE": 2, "WATCH": 3, "HOLD": 4, "CAUTION": 5}.get(sig, 6),
                "_rsi_raw": rsi_raw,
                "_vs50_raw": vs50_raw,
                "_rr_raw": rr_raw,
            })
        wl_df = pd.DataFrame(wl_rows).sort_values("_sig_rank")

        # Color-code the signal column
        def _signal_color(val):
            colors = {"BUY": "#22c55e", "ACCUMULATE": "#3498db", "WATCH": "#f59e0b",
                      "HOLD": "#6b7280", "CAUTION": "#ef4444"}
            c = colors.get(val, "#6b7280")
            return f"color: {c}; font-weight: bold"

        # Metric background color-coding
        def _rsi_bg(row_idx):
            raw = wl_df.iloc[row_idx]["_rsi_raw"]
            bg = _metric_bg(raw, _RSI_THRESHOLDS)
            return f"background-color: {bg}"

        def _vs50_bg(row_idx):
            raw = wl_df.iloc[row_idx]["_vs50_raw"]
            bg = _metric_bg(raw, _VS_SMA50_THRESHOLDS)
            return f"background-color: {bg}"

        def _rr_bg(row_idx):
            raw = wl_df.iloc[row_idx]["_rr_raw"]
            bg = _metric_bg(raw, _RR_THRESHOLDS)
            return f"background-color: {bg}"

        display_df = wl_df.drop(columns=["_tk_key", "_sig_rank", "_rsi_raw", "_vs50_raw", "_rr_raw"])

        def _apply_metric_bg(styler):
            """Apply muted background colors to RSI, vs SMA50, R:R cells."""
            rsi_styles = [_metric_bg(v, _RSI_THRESHOLDS) for v in wl_df["_rsi_raw"]]
            vs50_styles = [_metric_bg(v, _VS_SMA50_THRESHOLDS) for v in wl_df["_vs50_raw"]]
            rr_styles = [_metric_bg(v, _RR_THRESHOLDS) for v in wl_df["_rr_raw"]]

            bg_df = pd.DataFrame("", index=display_df.index, columns=display_df.columns)
            for i, idx in enumerate(display_df.index):
                bg_df.at[idx, "RSI"] = f"background-color: {rsi_styles[i]}"
                bg_df.at[idx, "vs SMA50"] = f"background-color: {vs50_styles[i]}"
                bg_df.at[idx, "R:R"] = f"background-color: {rr_styles[i]}"
            return bg_df

        styled = (
            display_df.style
            .map(_signal_color, subset=["Signal"])
            .apply(lambda _: _apply_metric_bg(None), axis=None)
        )
        st.dataframe(styled, hide_index=True, use_container_width=True)

        # Footnote for distorted R:R
        has_distorted = any(
            d.get("risk_reward", {}).get("rr_distorted", False)
            for d in watchlist.values()
        )
        if has_distorted:
            st.caption(
                "\\* R:R is distorted — invalidation or upside target is too close "
                "to price for the ratio to be meaningful. See the writeup for context."
            )

        # Expanders for individual ticker rationales
        st.caption("Click a ticker below for the full signal rationale.")
        # Group by signal for cleaner browsing
        for tk, d in watchlist.items():
            signal = d.get("signal", "?")
            rationale = d.get("signal_rationale", "")
            if not rationale:
                continue
            display_tk = TICKER_DISPLAY.get(tk, tk)
            st_color = SIGNAL_ST_COLORS.get(signal, "gray")
            curr = d.get("currency", "USD")
            price = d.get("price")
            price_str = _price_str(price, curr) if price else ""
            with st.expander(f"{display_tk} {price_str} — :{st_color}[{signal}]"):
                rsi_val = d.get("rsi_14")
                vs50_val = d.get("vs_sma50_pct")
                entry_block = d.get("entry_block")
                rr = d.get("risk_reward", {})
                rr_val = rr.get("ratio")
                rr_distorted = rr.get("rr_distorted", False)

                rsi_bg = _metric_bg(rsi_val, _RSI_THRESHOLDS)
                vs50_bg = _metric_bg(vs50_val, _VS_SMA50_THRESHOLDS)
                rr_bg = _metric_bg(rr_val, _RR_THRESHOLDS)

                rsi_str = f"{rsi_val:.1f}" if rsi_val else "—"
                vs50_str = f"{vs50_val:+.1f}%" if vs50_val is not None else "—"
                eb_str = (entry_block[:30] if entry_block else "None")
                rr_str = "—"
                if rr_val:
                    rr_str = f"{rr_val:.1f}*" if rr_distorted else f"{rr_val:.1f}"

                _card = (
                    '<div style="display:flex;gap:8px;margin-bottom:10px;">'
                    f'<div style="flex:1;background:{rsi_bg};border:1px solid #2a3a5c;'
                    f'border-radius:8px;padding:10px 12px;text-align:center;">'
                    f'<div style="font-size:0.7rem;color:#b0b0b0;text-transform:uppercase;'
                    f'letter-spacing:0.06em;">RSI</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;color:#e0e0e0;">{rsi_str}</div></div>'
                    f'<div style="flex:1;background:{vs50_bg};border:1px solid #2a3a5c;'
                    f'border-radius:8px;padding:10px 12px;text-align:center;">'
                    f'<div style="font-size:0.7rem;color:#b0b0b0;text-transform:uppercase;'
                    f'letter-spacing:0.06em;">vs SMA50</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;color:#e0e0e0;">{vs50_str}</div></div>'
                    f'<div style="flex:1;background:#16213e;border:1px solid #2a3a5c;'
                    f'border-radius:8px;padding:10px 12px;text-align:center;">'
                    f'<div style="font-size:0.7rem;color:#b0b0b0;text-transform:uppercase;'
                    f'letter-spacing:0.06em;">Entry Block</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;color:#e0e0e0;">{eb_str}</div></div>'
                    f'<div style="flex:1;background:{rr_bg};border:1px solid #2a3a5c;'
                    f'border-radius:8px;padding:10px 12px;text-align:center;">'
                    f'<div style="font-size:0.7rem;color:#b0b0b0;text-transform:uppercase;'
                    f'letter-spacing:0.06em;">R:R</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;color:#e0e0e0;">{rr_str}</div></div>'
                    '</div>'
                )
                st.markdown(_card, unsafe_allow_html=True)
                st.markdown(_escape_dollars(rationale))

    # ── 5. BENCHMARKS & MACRO ──
    st.divider()
    st.subheader("Market Pulse")
    macro = report.get("macro_summary", "")
    if macro:
        st.write(_escape_dollars(macro))

    benchmarks = report.get("benchmarks", {})
    if benchmarks:
        bm_cols = st.columns(min(len(benchmarks), 5))
        SNAPSHOT_BM = ["SPY", "VIX", "WTI", "Gold", "SOXX", "QQQ", "DXY", "US10Y"]
        shown = [b for b in SNAPSHOT_BM if b in benchmarks]
        for i, bm_name in enumerate(shown[:5]):
            bm = benchmarks[bm_name]
            price = bm.get("price")
            chg = bm.get("chg_pct")
            if chg is not None:
                delta_color = "inverse" if bm_name == "VIX" else "normal"
                bm_cols[i % 5].metric(
                    bm_name,
                    f"{price:,.2f}" if price is not None else "—",
                    f"{chg:+.2f}%", delta_color=delta_color,
                )
            else:
                bm_cols[i % 5].metric(bm_name, f"{price:,.2f}" if price else "—")

    comm = report.get("commodities_note", "")
    if comm:
        st.caption(f"**Commodities:** {_escape_dollars(comm)}")

    # ── 6. DEEP DIVES (expandable) ──
    st.divider()

    # Clusters
    clusters = report.get("clusters", {})
    if clusters:
        st.subheader("Cluster Deep Dives")
        for name, cdata in clusters.items():
            with st.expander(f"**{name.replace('_', ' ').title()}** — {cdata.get('thesis_status', '')}"):
                st.write(_escape_dollars(cdata.get("summary", "")))
                kd = cdata.get("key_development", "")
                if kd:
                    st.caption(f"**Key development:** {kd}")

    # Interconnected
    inter = report.get("interconnected", [])
    if inter:
        with st.expander(f"Interconnected Stocks ({len(inter)})"):
            for item in inter:
                tk = item.get("ticker", "?")
                name = item.get("name", "")
                reason = item.get("reason", "")
                entry_note = item.get("entry_note", "")
                price = item.get("price")
                chg = item.get("chg_pct")
                curr = item.get("currency", "USD")
                label = f"**{tk}**"
                if name:
                    label += f" ({name})"
                if price is not None:
                    label += f" — {_price_str(price, curr)}"
                if chg is not None:
                    label += f" ({chg:+.2f}%)"
                st.markdown(label)
                if reason:
                    st.caption(_escape_dollars(reason))
                if entry_note:
                    st.caption(f"Entry: {_escape_dollars(entry_note)}")

    # Geopolitical
    geo = report.get("geopolitical", {})
    has_geo = geo.get("active_risks") or geo.get("market_impact") or geo.get("scenarios")
    if has_geo:
        with st.expander("Geopolitical Scenarios"):
            risks = geo.get("active_risks", [])
            if risks:
                for r in risks:
                    st.markdown(f"- {_escape_dollars(r)}")
            impact_text = geo.get("market_impact", "") or geo.get("macro_outlook", "")
            if impact_text:
                st.info(_escape_dollars(impact_text))
            new_since = geo.get("new_since_yesterday", "")
            if new_since:
                st.warning(f"**New today:** {_escape_dollars(new_since)}")
            probs = geo.get("probabilities", {})
            if probs:
                prob_cols = st.columns(4)
                for col, (label, key) in zip(prob_cols, [("Base", "base"), ("Optimistic", "optimistic"),
                                                          ("Pessimistic", "pessimistic"), ("Wildcard", "wildcard")]):
                    val = probs.get(key, "?")
                    col.metric(label, f"{val}%")
            port_action = geo.get("portfolio_action", "")
            if port_action:
                st.success(f"**Action:** {_escape_dollars(port_action)}")
            scenarios = geo.get("scenarios", {})
            for sc_name, sc in scenarios.items():
                prob = sc.get("probability", "?")
                sc_label = sc_name.replace("_", " ").title()
                st.markdown(f"**{sc_label}** — {prob}")
                st.write(_escape_dollars(sc.get("description", "")))

    # Events
    events = report.get("events_this_week", [])
    if events:
        with st.expander(f"Key Events ({len(events)})"):
            ev_df = pd.DataFrame(events)
            if "date" in ev_df.columns:
                ev_df = ev_df.sort_values("date")
            st.dataframe(ev_df, width="stretch", hide_index=True)

    # Macro Trigger Map
    trigger_map = report.get("macro_trigger_map", [])
    # Flatten if double-nested
    if trigger_map and isinstance(trigger_map[0], list):
        trigger_map = [item for sublist in trigger_map for item in sublist]
    if trigger_map:
        with st.expander(f"Macro Trigger Map ({len(trigger_map)})"):
            for tm in trigger_map:
                if not isinstance(tm, dict):
                    continue
                event_name = tm.get("event", "")
                event_date = tm.get("date", "")
                header = f"**{event_name}**"
                if event_date:
                    header += f" ({event_date})"
                st.markdown(header)
                bullish = tm.get("bullish_outcome", "")
                upgrades = tm.get("bullish_upgrades", [])
                if bullish:
                    upgrade_str = ", ".join(upgrades) if upgrades else ""
                    bull_text = f":green[Bullish:] {_escape_dollars(bullish)}"
                    if upgrade_str:
                        bull_text += f" -> {upgrade_str}"
                    st.markdown(bull_text)
                bearish = tm.get("bearish_outcome", "")
                impacts = tm.get("bearish_impact", [])
                if bearish:
                    impact_str = ", ".join(impacts) if impacts else ""
                    bear_text = f":red[Bearish:] {_escape_dollars(bearish)}"
                    if impact_str:
                        bear_text += f" -> {impact_str}"
                    st.markdown(bear_text)
                st.markdown("---")

    # ── Entry Trigger Tracker ──
    import re as _re
    on_deck = action.get("on_deck", [])
    watch_entry = action.get("watch_for_entry", [])
    trigger_items = on_deck + watch_entry
    if trigger_items:
        with st.expander(f"Entry Trigger Tracker ({len(trigger_items)})"):
            for item in trigger_items:
                tk = item.get("ticker", "?")
                note = item.get("note", "")
                trigger = item.get("trigger", "")
                text = note or trigger
                price_match = _re.search(r'\$(\d[\d,.]*)', trigger or note)
                tk_price = watchlist.get(tk, {}).get("price")
                distance_pct = None
                target_price = None
                if price_match and tk_price:
                    try:
                        target_price = float(price_match.group(1).replace(",", ""))
                        distance_pct = (target_price - tk_price) / tk_price * 100
                    except (ValueError, ZeroDivisionError):
                        pass
                if distance_pct is not None:
                    abs_d = abs(distance_pct)
                    if abs_d <= 2:
                        ind = ":green[within 2%]"
                    elif abs_d <= 5:
                        ind = f":orange[{abs_d:.1f}% away]"
                    else:
                        ind = f":red[{abs_d:.1f}% away]"
                    direction = "above" if distance_pct > 0 else "below"
                    st.markdown(
                        f"**{tk}** — trigger \\${target_price:,.0f} | "
                        f"current \\${tk_price:,.2f} ({abs_d:.1f}% {direction}) {ind}"
                    )
                else:
                    st.markdown(f"**{tk}**")
                if text:
                    st.caption(_escape_dollars(text))

    # ── Watchlist Bias Over Time ──
    st.divider()
    st.subheader("Watchlist Bias Over Time")
    bias_rows = []
    for d in sorted(reports.keys()):
        wl = reports[d].get("watchlist", {})
        counts = {"BUY": 0, "ACCUMULATE": 0, "WATCH": 0, "HOLD": 0, "CAUTION": 0}
        for tk_data in wl.values():
            sig = tk_data.get("signal", "")
            if sig in counts:
                counts[sig] += 1
        counts["date"] = pd.to_datetime(d)
        bias_rows.append(counts)

    if bias_rows:
        bias_df = pd.DataFrame(bias_rows)
        fig_bias = go.Figure()
        for sig, color in [("BUY", "#22c55e"), ("ACCUMULATE", "#3498db"),
                           ("WATCH", "#f59e0b"), ("HOLD", "#6b7280"),
                           ("CAUTION", "#ef4444")]:
            fig_bias.add_trace(go.Bar(
                x=bias_df["date"], y=bias_df[sig],
                name=sig, marker_color=color,
            ))
        fig_bias.update_layout(
            barmode="stack", height=250,
            yaxis_title="Tickers",
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_bias, use_container_width=True)

    # ── Benchmark Trends ──
    st.subheader("Benchmark Trends")
    all_reports_sorted = sorted(reports.items())
    bench_series: dict[str, list] = {}
    bench_dates: list = []
    for d_str, rpt in all_reports_sorted:
        bench_dates.append(pd.to_datetime(d_str))
        for bm_name, bm_data in rpt.get("benchmarks", {}).items():
            bench_series.setdefault(bm_name, []).append(bm_data.get("price"))
    default_benchmarks = ["SPY", "VIX", "WTI", "SOXX", "US10Y"]
    available_bm = [b for b in bench_series if len(bench_series[b]) == len(bench_dates)]
    show_bm = st.multiselect(
        "Benchmarks", available_bm,
        default=[b for b in default_benchmarks if b in available_bm],
        key="bm_trend",
    )
    if show_bm and bench_dates:
        fig_bm = go.Figure()
        bm_colors = {"SPY": "#3b82f6", "QQQ": "#8b5cf6", "VIX": "#ef4444",
                      "WTI": "#f59e0b", "Gold": "#fbbf24", "SOXX": "#22c55e",
                      "DXY": "#6b7280", "US10Y": "#ec4899"}
        for bm_name in show_bm:
            vals = bench_series[bm_name]
            base = next((v for v in vals if v is not None), None)
            if base and base != 0:
                pct_vals = [(v / base - 1) * 100 if v is not None else None for v in vals]
                fig_bm.add_trace(go.Scatter(
                    x=bench_dates, y=pct_vals,
                    mode="lines+markers", name=bm_name,
                    line=dict(color=bm_colors.get(bm_name, "#6b7280"), width=2),
                ))
        fig_bm.add_hline(y=0, line_dash="dot", line_color="#4b5563", line_width=1)
        fig_bm.update_layout(
            yaxis_title="% Change from Start",
            height=350, margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            hovermode="x unified",
        )
        st.plotly_chart(fig_bm, use_container_width=True)


# ════════════════════════════════════════════
# PAGE 2: Signal Tracker
# ════════════════════════════════════════════
elif page == "Signal Tracker":
    st.title("Signal Tracker")
    reports = filter_reports(load_all_reports())
    sig_df = extract_signal_history(reports)
    prices_df = filter_prices(load_sqlite_prices())

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

    # ── Signal Accuracy Scorecard (all tickers, independent of selector) ──
    st.subheader("Signal Accuracy Scorecard")
    st.caption(
        "BUY/WATCH: did the price go **up** after the signal? (positive = correct) | "
        "HOLD/CAUTION: did the price go **down** after the signal? (negative = correct — you avoided a loss)"
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

        # B) Signal performance table — all 4 types
        st.markdown("**Performance by Signal Type**")
        perf_rows = []
        for sig_type in ["BUY", "ACCUMULATE", "WATCH", "CAUTION"]:
            sig_data = acc_df[acc_df["signal"] == sig_type]
            count = len(sig_data)
            if count == 0:
                continue
            is_defensive = sig_type == "CAUTION"
            row = {"Signal": sig_type, "Count": count}
            for label in ["5d", "10d", "20d"]:
                valid = sig_data[f"return_{label}"].dropna()
                if len(valid) >= min_samples:
                    if is_defensive:
                        row[f"{label} Correct %"] = f"{(valid <= 0).mean() * 100:.1f}%"
                    else:
                        row[f"{label} Correct %"] = f"{(valid > 0).mean() * 100:.1f}%"
                    row[f"{label} Avg Return"] = f"{valid.mean():+.1f}%"
                    excess = sig_data[f"excess_{label}"].dropna()
                    if len(excess) >= min_samples:
                        row[f"{label} Avg Excess"] = f"{excess.mean():+.1f}%"
                    else:
                        row[f"{label} Avg Excess"] = "—"
                else:
                    row[f"{label} Correct %"] = "—"
                    row[f"{label} Avg Return"] = "—"
                    row[f"{label} Avg Excess"] = "—"
            perf_rows.append(row)

        if perf_rows:
            st.dataframe(pd.DataFrame(perf_rows), width="stretch", hide_index=True)

        # C) Individual signal detail table
        st.markdown("**Individual Signal Detail**")
        detail_filter = st.radio(
            "Show", ["All", "BUY only", "ACCUMULATE only", "WATCH only", "CAUTION only"],
            horizontal=True, key="acc_filter"
        )
        detail = acc_df.copy()
        filter_map = {
            "BUY only": "BUY", "ACCUMULATE only": "ACCUMULATE",
            "WATCH only": "WATCH", "CAUTION only": "CAUTION",
        }
        if detail_filter in filter_map:
            detail = detail[detail["signal"] == filter_map[detail_filter]]
        detail = detail.sort_values("date", ascending=False)
        detail["date"] = detail["date"].dt.strftime("%Y-%m-%d")
        detail["price"] = detail["price"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "—")

        for label in ["5d", "10d", "20d"]:
            detail[f"{label} Return"] = detail[f"return_{label}"].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "Pending"
            )
            detail[f"{label} SPY"] = detail[f"spy_{label}"].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A"
            )
            detail[f"{label} Excess"] = detail[f"excess_{label}"].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
            )

        display_cols = ["date", "ticker", "signal", "price",
                        "5d Return", "5d SPY", "5d Excess",
                        "10d Return", "10d SPY", "10d Excess"]
        display_df = detail[display_cols].rename(columns={
            "date": "Date", "ticker": "Ticker", "signal": "Signal", "price": "Entry Price",
        })
        st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()

    # ── Signal history heatmap ──
    st.subheader("Signal History")
    signal_map = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    filtered = sig_df[sig_df["ticker"].isin(selected_tickers)].copy()
    filtered["signal_num"] = filtered["signal"].map(signal_map)

    pivot = filtered.pivot_table(
        index="ticker", columns="date", values="signal_num", aggfunc="first"
    )
    pivot_labels = filtered.pivot_table(
        index="ticker", columns="date", values="signal", aggfunc="first"
    )

    if not pivot.empty:
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[d.strftime("%b %d") for d in pivot.columns],
            y=pivot.index.tolist(),
            text=pivot_labels.values,
            texttemplate="%{text}",
            colorscale=[
                [0, "#ef4444"],     # CAUTION (1)
                [0.25, "#6b7280"],  # HOLD (2)
                [0.5, "#f59e0b"],   # WATCH (3)
                [0.75, "#3498db"],  # ACCUMULATE (4)
                [1, "#22c55e"],     # BUY (5)
            ],
            zmin=1, zmax=5,
            showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
        ))
        fig.update_layout(height=max(200, 40 * len(selected_tickers)), margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # ── Signal Persistence ──
    st.subheader("Signal Persistence")
    streak_df = compute_signal_streaks(reports)
    if not streak_df.empty:
        display_streaks = streak_df[streak_df["ticker"].isin(selected_tickers)].copy()
        display_streaks = display_streaks.sort_values("days", ascending=False)

        # Color-code days column for display
        def _streak_label(row):
            d = row["days"]
            if d >= 11:
                return f"{d} days"
            elif d >= 6:
                return f"{d} days"
            return f"{d} days"

        display_streaks["Days at Signal"] = display_streaks.apply(_streak_label, axis=1)
        streak_table = display_streaks[["ticker", "signal", "Days at Signal"]].rename(columns={
            "ticker": "Ticker", "signal": "Signal",
        })
        st.dataframe(streak_table, width="stretch", hide_index=True)

        # Stale WATCH callouts
        stale = display_streaks[
            (display_streaks["signal"] == "WATCH") & (display_streaks["days"] >= 10)
        ]
        for _, row in stale.iterrows():
            approaching = ""
            if row["vs_sma50_start"] is not None and row["vs_sma50_end"] is not None:
                if row["vs_sma50_end"] < row["vs_sma50_start"]:
                    approaching = " (but moving closer to entry)"
                else:
                    approaching = ", not approaching entry"
            st.warning(
                f"Stale — **{row['ticker']}** at WATCH for {row['days']} consecutive days{approaching}"
            )

    st.divider()

    # ── Per-ticker price + signal chart (%-normalized range) ──
    st.subheader("Price & SMA50 Over Time")
    st.caption("Y axis shows actual prices. All charts use the same percentage range so moves are visually comparable.")

    # First pass: find the max % swing across all selected tickers
    max_pct_swing = 5.0  # minimum ±5%
    ticker_chart_data = {}
    for ticker in selected_tickers:
        db_ticker = _report_ticker_to_db(ticker)
        tk_prices = prices_df[prices_df["ticker"] == db_ticker].sort_values("date") if not prices_df.empty else pd.DataFrame()
        tk_signals = filtered[filtered["ticker"] == ticker].sort_values("date")
        ticker_chart_data[ticker] = (tk_prices, tk_signals)

        if not tk_prices.empty:
            prices_arr = tk_prices["last_price"].dropna()
            if len(prices_arr) >= 2:
                mid = (prices_arr.max() + prices_arr.min()) / 2
                if mid > 0:
                    swing = (prices_arr.max() - prices_arr.min()) / mid * 100
                    max_pct_swing = max(max_pct_swing, swing)

    # Add some padding
    chart_pct_range = max_pct_swing * 0.6  # half-range with padding

    # Second pass: render charts with consistent range
    for ticker in selected_tickers:
        tk_prices, tk_signals = ticker_chart_data[ticker]

        if tk_prices.empty and tk_signals.empty:
            continue

        fig = go.Figure()

        mid_price = None
        if not tk_prices.empty:
            prices_arr = tk_prices["last_price"].dropna()
            mid_price = (prices_arr.max() + prices_arr.min()) / 2
            y_min = mid_price * (1 - chart_pct_range / 100)
            y_max = mid_price * (1 + chart_pct_range / 100)

            fig.add_trace(go.Scatter(
                x=tk_prices["date"], y=tk_prices["last_price"],
                mode="lines+markers", name="Price",
                line=dict(color="#3b82f6", width=2),
            ))
            if tk_prices["sma_50"].notna().any():
                fig.add_trace(go.Scatter(
                    x=tk_prices["date"], y=tk_prices["sma_50"],
                    mode="lines", name="SMA50",
                    line=dict(color="#f59e0b", width=1, dash="dash"),
                ))

            fig.update_yaxes(range=[y_min, y_max])

        # Signal markers from reports
        if not tk_signals.empty and tk_signals["price"].notna().any():
            for _, row in tk_signals.iterrows():
                color = SIGNAL_COLORS.get(row["signal"], "#6b7280")
                fig.add_trace(go.Scatter(
                    x=[row["date"]], y=[row["price"]],
                    mode="markers",
                    marker=dict(size=14, color=color, symbol="diamond",
                                line=dict(width=2, color="white")),
                    name=row["signal"],
                    hovertext="<br>".join(
                        [f"<b>{row['signal']}</b>"] +
                        [row.get("rationale", "")[i:i+80]
                         for i in range(0, min(len(row.get("rationale", "")), 400), 80)]
                    ),
                    showlegend=False,
                ))

        fig.update_layout(
            title=ticker, height=300,
            margin=dict(l=0, r=0, t=40, b=0),
            xaxis_title="", yaxis_title="Price",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Signal change log ──
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

    # ── Feature 2: Historical Writeup Viewer ──
    st.subheader("Historical Writeup Viewer")
    st.caption("Read the full signal rationale for a ticker across dates to see how the narrative evolves.")

    all_tickers_writeup = sorted(sig_df["ticker"].unique())
    writeup_ticker = st.selectbox("Ticker", all_tickers_writeup, key="writeup_ticker")

    if writeup_ticker:
        tk_writeups = sig_df[sig_df["ticker"] == writeup_ticker].sort_values("date", ascending=False)
        if tk_writeups.empty:
            st.info("No data for this ticker.")
        else:
            prev_signal = None
            for _, row in tk_writeups.iterrows():
                date_label = row["date"].strftime("%Y-%m-%d")
                signal = row["signal"]
                rationale = row.get("rationale", "") or ""
                price = row.get("price")
                price_str = f" — ${price:,.2f}" if price is not None else ""

                # Detect signal change (compared to next chronological day, since we're newest-first)
                signal_changed = prev_signal is not None and signal != prev_signal

                header = f"**{date_label}** | {signal}{price_str}"
                if signal_changed:
                    header += f"  *(changed from {prev_signal})*"

                if signal_changed:
                    st.markdown(
                        f"<div style='border-left:4px solid #f59e0b;padding-left:12px;"
                        f"margin-bottom:8px;background-color:#f59e0b10;padding:8px;border-radius:4px'>"
                        f"{header}<br><span style='font-size:0.9em'>{_escape_dollars(rationale)}</span></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    with st.container():
                        st.markdown(header)
                        if rationale:
                            st.caption(_escape_dollars(rationale))

                prev_signal = signal


# ════════════════════════════════════════════
# PAGE 3: Ticker Comparison Overlay
# ════════════════════════════════════════════
elif page == "Ticker Comparison":
    st.title("Ticker Comparison Overlay")
    st.caption("Compare two tickers' key metrics side by side.")

    reports = filter_reports(load_all_reports())
    sig_df = extract_signal_history(reports)
    prices_df = filter_prices(load_sqlite_prices())

    if sig_df.empty:
        st.warning("No signal data available yet.")
        st.stop()

    all_tickers = sorted(sig_df["ticker"].unique())
    col_a, col_b = st.columns(2)
    with col_a:
        ticker_a = st.selectbox("Ticker A", all_tickers, index=0, key="cmp_a")
    with col_b:
        default_b = min(1, len(all_tickers) - 1)
        ticker_b = st.selectbox("Ticker B", all_tickers, index=default_b, key="cmp_b")

    if ticker_a == ticker_b:
        st.info("Select two different tickers to compare.")
        st.stop()

    def _get_ticker_data(ticker):
        db_tk = _report_ticker_to_db(ticker)
        tk_prices = prices_df[prices_df["ticker"] == db_tk].sort_values("date") if not prices_df.empty else pd.DataFrame()
        tk_signals = sig_df[sig_df["ticker"] == ticker].sort_values("date")
        return tk_prices, tk_signals

    prices_a, signals_a = _get_ticker_data(ticker_a)
    prices_b, signals_b = _get_ticker_data(ticker_b)

    # ── RSI over time ──
    st.subheader("RSI Comparison")
    fig_rsi = go.Figure()
    if not prices_a.empty and prices_a["rsi_14"].notna().any():
        fig_rsi.add_trace(go.Scatter(
            x=prices_a["date"], y=prices_a["rsi_14"],
            mode="lines+markers", name=ticker_a,
            line=dict(color="#3b82f6", width=2),
        ))
    if not prices_b.empty and prices_b["rsi_14"].notna().any():
        fig_rsi.add_trace(go.Scatter(
            x=prices_b["date"], y=prices_b["rsi_14"],
            mode="lines+markers", name=ticker_b,
            line=dict(color="#ef4444", width=2),
        ))
    # Reference lines at 30/70
    fig_rsi.add_hline(y=30, line_dash="dot", line_color="#22c55e", annotation_text="Oversold (30)")
    fig_rsi.add_hline(y=70, line_dash="dot", line_color="#ef4444", annotation_text="Overbought (70)")
    fig_rsi.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), yaxis_title="RSI", hovermode="x unified")
    st.plotly_chart(fig_rsi, use_container_width=True)

    # ── Price vs SMA50 % over time ──
    st.subheader("Price vs SMA50 (%)")
    fig_sma = go.Figure()
    for ticker, tk_prices, color in [(ticker_a, prices_a, "#3b82f6"), (ticker_b, prices_b, "#ef4444")]:
        if not tk_prices.empty and tk_prices["sma_50"].notna().any():
            pct = ((tk_prices["last_price"] - tk_prices["sma_50"]) / tk_prices["sma_50"] * 100).round(2)
            fig_sma.add_trace(go.Scatter(
                x=tk_prices["date"], y=pct,
                mode="lines+markers", name=ticker,
                line=dict(color=color, width=2),
            ))
    fig_sma.add_hline(y=0, line_dash="dash", line_color="#6b7280")
    fig_sma.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), yaxis_title="% from SMA50", hovermode="x unified")
    st.plotly_chart(fig_sma, use_container_width=True)

    # ── Signal timeline side by side ──
    st.subheader("Signal Timeline")
    signal_map = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    combined_signals = []
    for ticker, tk_signals in [(ticker_a, signals_a), (ticker_b, signals_b)]:
        for _, row in tk_signals.iterrows():
            combined_signals.append({
                "date": row["date"],
                "ticker": ticker,
                "signal": row["signal"],
                "signal_num": signal_map.get(row["signal"], 0),
            })

    if combined_signals:
        cdf = pd.DataFrame(combined_signals)
        pivot = cdf.pivot_table(index="ticker", columns="date", values="signal_num", aggfunc="first")
        pivot_labels = cdf.pivot_table(index="ticker", columns="date", values="signal", aggfunc="first")

        fig_sig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[d.strftime("%b %d") for d in pivot.columns],
            y=pivot.index.tolist(),
            text=pivot_labels.values,
            texttemplate="%{text}",
            colorscale=[
                [0, "#ef4444"],     # CAUTION
                [0.25, "#6b7280"],  # HOLD
                [0.5, "#f59e0b"],   # WATCH
                [0.75, "#3498db"],  # ACCUMULATE
                [1, "#22c55e"],     # BUY
            ],
            zmin=1, zmax=5,
            showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
        ))
        fig_sig.update_layout(height=150, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_sig, use_container_width=True)
    else:
        st.caption("No signal data for selected tickers.")


# ════════════════════════════════════════════
# PAGE 4: Scenario Log
# ════════════════════════════════════════════
elif page == "Scenario Log":
    st.title("Scenario Probability Tracking")
    reports = filter_reports(load_all_reports())
    sc_df = extract_scenario_history(reports)

    if sc_df.empty:
        st.warning("No scenario data available yet.")
        st.stop()

    # Probability over time chart
    st.subheader("Probabilities Over Time")
    scenarios = sc_df["scenario"].unique()
    scenario_colors = {
        "Base": "blue",
        "Optimistic": "green",
        "Pessimistic": "red",
        "Wildcard": "violet",
    }

    fig = go.Figure()
    for sc_name in scenarios:
        sc_data = sc_df[sc_df["scenario"] == sc_name].sort_values("date")
        if sc_data["probability_mid"].notna().any():
            fig.add_trace(go.Scatter(
                x=sc_data["date"], y=sc_data["probability_mid"],
                mode="lines+markers",
                name=sc_name,
                line=dict(color={"Base": "#3b82f6", "Optimistic": "#22c55e",
                                 "Pessimistic": "#ef4444", "Wildcard": "#a855f7"
                                 }.get(sc_name, "#6b7280"), width=2),
                hovertemplate=f"<b>{sc_name}</b><br>"
                              "%{x|%b %d}: %{customdata}<extra></extra>",
                customdata=sc_data["probability_str"],
            ))
    # Overlay HIGH-impact events as vertical markers
    event_annotations = []
    for d_str, rpt in reports.items():
        events = rpt.get("events_this_week", [])
        for ev in events:
            impact = ev.get("impact", "")
            if impact != "HIGH":
                continue
            ev_date = ev.get("date", d_str)
            ev_text = ev.get("event", "")[:30]
            try:
                event_annotations.append((pd.to_datetime(ev_date), ev_text))
            except Exception:
                continue  # Skip unparseable dates like "Q2 2026"
    # Deduplicate by date+text, limit to 5
    seen = set()
    unique_events = []
    for ev_date, ev_text in sorted(event_annotations):
        key = (ev_date.strftime("%Y-%m-%d"), ev_text)
        if key not in seen:
            seen.add(key)
            unique_events.append((ev_date, ev_text))
    for ev_date, ev_text in unique_events[:5]:
        fig.add_vline(
            x=ev_date, line_dash="dash", line_color="#6b7280", line_width=1,
        )
        fig.add_annotation(
            x=ev_date, y=1.05, yref="paper",
            text=ev_text, showarrow=False,
            font=dict(size=9, color="#9ca3af"),
            textangle=-30,
        )

    fig.update_layout(
        yaxis_title="Probability %", height=400,
        margin=dict(l=0, r=0, t=60, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Scenario descriptions by date
    st.subheader("Scenario Detail by Date")
    dates = sorted(sc_df["date"].unique(), reverse=True)
    for d in dates:
        day_data = sc_df[sc_df["date"] == d]
        with st.expander(f"**{pd.Timestamp(d).strftime('%Y-%m-%d')}**"):
            for _, row in day_data.iterrows():
                color = scenario_colors.get(row["scenario"], "#6b7280")
                st.markdown(
                    f"**:{color}[{row['scenario']}]** — {row['probability_str']}"
                )
                st.caption(row["description"] if row["description"] else "")


# ════════════════════════════════════════════
# PAGE 5: Pipeline Stats
# ════════════════════════════════════════════
elif page == "Pipeline Stats":
    st.title("Pipeline Statistics")
    token_df = load_token_usage()
    reports = filter_reports(load_all_reports())

    if token_df.empty:
        st.warning("No pipeline data available yet.")
        st.stop()

    # ── Cost & timing overview ──
    st.subheader("API Usage Over Time")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=token_df["date"], y=token_df["token_count"],
        name="Tokens", marker_color="#3b82f6",
    ))
    fig.update_layout(
        yaxis_title="Token Count", height=300,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Generation time
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=token_df["date"], y=token_df["generation_time_seconds"],
        mode="lines+markers", name="Gen Time",
        line=dict(color="#f59e0b", width=2),
    ))
    fig2.update_layout(
        yaxis_title="Seconds", height=250,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Summary stats
    cols = st.columns(4)
    cols[0].metric("Total Reports", len(token_df))
    cols[1].metric("Avg Tokens", f"{token_df['token_count'].mean():,.0f}")
    cols[2].metric("Avg Gen Time", f"{token_df['generation_time_seconds'].mean():.0f}s")
    cols[3].metric("Model", token_df["model_used"].iloc[-1] if len(token_df) else "—")

    # ── Estimated Cost ──
    st.subheader("Estimated API Cost")
    # Per-million-token rates (USD) — hardcoded, Anthropic pricing as of 2025
    COST_RATES = {
        "sonnet": {"input": 3.0, "output": 15.0},
        "opus": {"input": 15.0, "output": 75.0},
        "haiku": {"input": 0.25, "output": 1.25},
    }

    def _estimate_cost(row):
        model = (row.get("model_used") or "").lower()
        rate = COST_RATES.get("sonnet")  # default
        for key in COST_RATES:
            if key in model:
                rate = COST_RATES[key]
                break
        tokens = row.get("token_count", 0) or 0
        # Approximate 70/30 input/output split (pipeline sends large prompts)
        input_tokens = tokens * 0.7
        output_tokens = tokens * 0.3
        return (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000

    cost_df = token_df.copy()
    cost_df["cost_usd"] = cost_df.apply(_estimate_cost, axis=1)
    cost_df["cumulative_cost"] = cost_df["cost_usd"].cumsum()
    cost_df["cost_7d_avg"] = cost_df["cost_usd"].rolling(7, min_periods=1).mean()

    cost_cols = st.columns(3)
    cost_cols[0].metric("Total Cost", f"${cost_df['cost_usd'].sum():.2f}")
    cost_cols[1].metric("Avg Cost/Report", f"${cost_df['cost_usd'].mean():.2f}")
    latest_cost = cost_df["cost_usd"].iloc[-1] if len(cost_df) else 0
    cost_cols[2].metric("Latest Report", f"${latest_cost:.2f}")

    fig_cost = go.Figure()
    fig_cost.add_trace(go.Bar(
        x=cost_df["date"], y=cost_df["cost_usd"],
        name="Per Report", marker_color="#3b82f6", opacity=0.6,
    ))
    fig_cost.add_trace(go.Scatter(
        x=cost_df["date"], y=cost_df["cost_7d_avg"],
        mode="lines", name="7d Avg",
        line=dict(color="#f59e0b", width=2),
    ))
    fig_cost.update_layout(
        yaxis_title="Cost (USD)", height=250,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig_cost, use_container_width=True)

    # Cumulative cost
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(
        x=cost_df["date"], y=cost_df["cumulative_cost"],
        mode="lines+markers", name="Cumulative",
        line=dict(color="#22c55e", width=2),
        fill="tozeroy", fillcolor="rgba(34,197,94,0.1)",
    ))
    fig_cum.update_layout(
        yaxis_title="Cumulative Cost (USD)", height=200,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig_cum, use_container_width=True)

    # ── Report sizes ──
    st.subheader("Report Sizes")
    sizes = []
    for date_str, report in sorted(reports.items()):
        wl = report.get("watchlist", {})
        action = report.get("action_summary", {})
        sizes.append({
            "Date": date_str,
            "Watchlist Tickers": len(wl),
            "Watch": len(action.get("watch_for_entry", [])),
            "Buy": len(action.get("consider_adding", [])),
            "Accumulate": len(action.get("accumulate", [])),
            "On Deck": len(action.get("on_deck", [])),
            "Hold": len(action.get("hold_no_action", [])),
            "Caution": len(action.get("caution_trim", [])),
            "Interconnected": len(report.get("interconnected", [])),
        })
    if sizes:
        st.dataframe(pd.DataFrame(sizes), width="stretch", hide_index=True)

    # ── Articles Fed to Prompt ──
    st.subheader("Articles Fed to Prompt")
    ps_df = load_pipeline_stats()
    if ps_df.empty:
        st.info("No pipeline stats recorded yet.")
    else:
        # Article count metrics
        art_cols = st.columns(4)
        art_cols[0].metric("Avg Tavily Fetched", f"{ps_df['articles_fetched'].mean():.0f}")
        art_cols[1].metric("Avg Tavily After Filter", f"{ps_df['articles_after_filter'].mean():.0f}")
        art_cols[2].metric("Avg Blocked", f"{ps_df['articles_blocked'].mean():.0f}")
        # yfinance may be null for older rows
        yf_col = ps_df["yfinance_articles"].dropna()
        art_cols[3].metric("Avg yFinance", f"{yf_col.mean():.0f}" if len(yf_col) else "—")

        # Article count chart — stacked by source
        fig_art = go.Figure()
        fig_art.add_trace(go.Bar(
            x=ps_df["date"], y=ps_df["articles_after_filter"],
            name="Tavily", marker_color="#3b82f6",
        ))
        if ps_df["yfinance_articles"].notna().any():
            fig_art.add_trace(go.Bar(
                x=ps_df["date"], y=ps_df["yfinance_articles"],
                name="yFinance", marker_color="#f59e0b",
            ))
        fig_art.update_layout(
            barmode="stack",
            yaxis_title="Article Count", height=300,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_art, use_container_width=True)

        # ── Prompt Size Breakdown ──
        has_breakdown = ps_df["total_prompt_chars"].notna().any()
        if has_breakdown:
            st.subheader("Prompt Size Breakdown")
            # Latest run metrics
            latest = ps_df.dropna(subset=["total_prompt_chars"]).iloc[-1] if has_breakdown else None
            if latest is not None:
                pb_cols = st.columns(5)
                pb_cols[0].metric("System Prompt", f"{latest['system_prompt_chars']:,.0f} chars")
                pb_cols[1].metric("Watchlist Data", f"{latest['watchlist_data_chars']:,.0f} chars")
                pb_cols[2].metric("yFinance News", f"{latest['yfinance_chars']:,.0f} chars")
                pb_cols[3].metric("Tavily News", f"{latest['tavily_chars']:,.0f} chars")
                pb_cols[4].metric("Memory", f"{latest['memory_chars']:,.0f} chars")

            # Stacked area chart over time
            breakdown_df = ps_df.dropna(subset=["total_prompt_chars"])
            if len(breakdown_df) > 0:
                fig_pb = go.Figure()
                components = [
                    ("system_prompt_chars", "System Prompt", "#6366f1"),
                    ("watchlist_data_chars", "Watchlist Data", "#3b82f6"),
                    ("yfinance_chars", "yFinance News", "#f59e0b"),
                    ("tavily_chars", "Tavily News", "#22c55e"),
                    ("memory_chars", "Memory", "#ec4899"),
                ]
                for col, name, color in components:
                    fig_pb.add_trace(go.Bar(
                        x=breakdown_df["date"], y=breakdown_df[col],
                        name=name, marker_color=color,
                    ))
                fig_pb.update_layout(
                    barmode="stack",
                    yaxis_title="Chars", height=300,
                    margin=dict(l=0, r=0, t=30, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_pb, use_container_width=True)


# ════════════════════════════════════════════
# PAGE 6: Report Comparison
# ════════════════════════════════════════════
elif page == "Report Comparison":
    st.title("Report Comparison")
    reports = filter_reports(load_all_reports())
    if len(reports) < 2:
        st.warning("Need at least 2 reports to compare.")
        st.stop()

    dates = sorted(reports.keys(), reverse=True)

    # ── Multi-Day Trend Summary ──
    st.subheader("Multi-Day Trend Summary")
    window_options = {3: "3 days", 5: "5 days", 7: "7 days", 14: "14 days", 30: "30 days"}
    window = st.select_slider(
        "Show changes over last", options=list(window_options.keys()),
        value=7, format_func=lambda x: window_options[x], key="trend_window"
    )

    sorted_dates_asc = sorted(reports.keys())
    if len(sorted_dates_asc) >= 2:
        # Find the oldest report within the window
        latest_date = sorted_dates_asc[-1]
        cutoff = (date.fromisoformat(latest_date) - timedelta(days=window)).isoformat()
        window_dates = [d for d in sorted_dates_asc if d >= cutoff]

        if len(window_dates) >= 2:
            start_date = window_dates[0]
            end_date = window_dates[-1]
            rpt_start = reports[start_date]
            rpt_end = reports[end_date]
            wl_start = rpt_start.get("watchlist", {})
            wl_end = rpt_end.get("watchlist", {})

            signal_rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
            trend_changes = []
            upgrades = 0
            downgrades = 0
            all_tks = sorted(set(wl_start) | set(wl_end))

            for tk in all_tks:
                sig_s = wl_start.get(tk, {}).get("signal", "—")
                sig_e = wl_end.get(tk, {}).get("signal", "—")
                if sig_s == sig_e:
                    continue
                r_s = signal_rank.get(sig_s, 0)
                r_e = signal_rank.get(sig_e, 0)
                direction = "upgrade" if r_e > r_s else "downgrade"
                if sig_s == "—":
                    direction = "new"
                elif sig_e == "—":
                    direction = "removed"
                if direction == "upgrade":
                    upgrades += 1
                elif direction == "downgrade":
                    downgrades += 1

                # Price change over window
                price_s = wl_start.get(tk, {}).get("price")
                price_e = wl_end.get(tk, {}).get("price")
                price_chg = ""
                if price_s and price_e:
                    price_chg = f"{(price_e - price_s) / price_s * 100:+.1f}%"

                trend_changes.append({
                    "Ticker": tk,
                    f"Signal ({start_date})": sig_s,
                    f"Signal ({end_date})": sig_e,
                    "Direction": direction,
                    "Price Chg": price_chg or "—",
                })

            # Check for volatile tickers (changed signal more than once in window)
            volatile_tickers = []
            for tk in all_tks:
                signal_changes = 0
                prev_sig = None
                for wd in window_dates:
                    sig = reports[wd].get("watchlist", {}).get(tk, {}).get("signal")
                    if sig and sig != prev_sig and prev_sig is not None:
                        signal_changes += 1
                    if sig:
                        prev_sig = sig
                if signal_changes >= 2:
                    volatile_tickers.append((tk, signal_changes))

            # Summary stats
            net = upgrades - downgrades
            net_label = f"net {'+' if net >= 0 else ''}{net}"
            tcols = st.columns(3)
            tcols[0].metric("Upgrades", upgrades)
            tcols[1].metric("Downgrades", downgrades)
            tcols[2].metric("Net", net_label)

            if volatile_tickers:
                volatile_str = ", ".join(f"**{tk}** ({n}x)" for tk, n in sorted(volatile_tickers, key=lambda x: -x[1]))
                st.caption(f"Volatile signals: {volatile_str}")

            if trend_changes:
                st.dataframe(pd.DataFrame(trend_changes), width="stretch", hide_index=True)
            else:
                st.caption(f"No signal changes in the last {window_options[window]}.")

            # Scenario probability drift over window
            st.markdown("**Scenario Drift**")

            probs_s = _get_probs(rpt_start)
            probs_e = _get_probs(rpt_end)
            sc_all = sorted(set(probs_s) | set(probs_e))

            drift_rows = []
            for sc_name in sc_all:
                p_s_str, mid_s = probs_s.get(sc_name, ("—", None))
                p_e_str, mid_e = probs_e.get(sc_name, ("—", None))
                drift_val = (mid_e - mid_s) if (mid_s is not None and mid_e is not None) else None
                drift_rows.append({
                    "Scenario": sc_name.replace("_", " ").title(),
                    f"Prob ({start_date})": p_s_str,
                    f"Prob ({end_date})": p_e_str,
                    "Drift (pp)": f"{drift_val:+.1f}" if drift_val is not None else "—",
                    "_abs_drift": abs(drift_val) if drift_val is not None else 0,
                })
            if drift_rows:
                drift_df = pd.DataFrame(drift_rows).sort_values("_abs_drift", ascending=False)
                st.dataframe(drift_df.drop(columns=["_abs_drift"]), width="stretch", hide_index=True)
        else:
            st.caption(f"Only 1 report in the last {window_options[window]} — need at least 2.")

    st.divider()

    # ── Pairwise Comparison ──
    st.subheader("Pairwise Comparison")
    ccols = st.columns(2)
    with ccols[0]:
        date_a = st.selectbox("Report A (older)", dates[1:], index=0, key="cmp_a")
    with ccols[1]:
        date_b = st.selectbox("Report B (newer)", dates, index=0, key="cmp_b")

    if date_a == date_b:
        st.info("Select two different dates to compare.")
        st.stop()

    rpt_a = reports[date_a]
    rpt_b = reports[date_b]
    wl_a = rpt_a.get("watchlist", {})
    wl_b = rpt_b.get("watchlist", {})

    # ── Signal Changes ──
    st.subheader("Signal Changes")
    signal_rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    sig_changes = []
    all_tickers = sorted(set(wl_a) | set(wl_b))
    for tk in all_tickers:
        sig_a = wl_a.get(tk, {}).get("signal", "—")
        sig_b = wl_b.get(tk, {}).get("signal", "—")
        if sig_a != sig_b:
            r_a = signal_rank.get(sig_a, 0)
            r_b = signal_rank.get(sig_b, 0)
            direction = "upgrade" if r_b > r_a else "downgrade"
            if sig_a == "—":
                direction = "new"
            elif sig_b == "—":
                direction = "removed"
            sig_changes.append({
                "Ticker": tk,
                f"Signal ({date_a})": sig_a,
                f"Signal ({date_b})": sig_b,
                "Direction": direction,
                "Rationale": wl_b.get(tk, {}).get("signal_rationale", "")[:150],
            })

    if sig_changes:
        df_sc = pd.DataFrame(sig_changes)
        # Color-code direction
        st.dataframe(df_sc, width="stretch", hide_index=True)
    else:
        st.caption("No signal changes between these dates.")

    # ── Probability Drift ──
    st.subheader("Scenario Probability Drift")
    probs_a = _get_probs(rpt_a)
    probs_b = _get_probs(rpt_b)
    sc_all = sorted(set(probs_a) | set(probs_b))

    prob_rows = []
    for sc_name in sc_all:
        p_a_str, mid_a = probs_a.get(sc_name, ("—", None))
        p_b_str, mid_b = probs_b.get(sc_name, ("—", None))
        drift = None
        if mid_a is not None and mid_b is not None:
            drift = mid_b - mid_a
        label = sc_name.replace("_", " ").title()
        prob_rows.append({
            "Scenario": label,
            f"Prob ({date_a})": p_a_str,
            f"Prob ({date_b})": p_b_str,
            "Drift (pp)": f"{drift:+.1f}" if drift is not None else "—",
        })
    if prob_rows:
        st.dataframe(pd.DataFrame(prob_rows), width="stretch", hide_index=True)

    # ── Interconnected Stocks Diff ──
    st.subheader("Interconnected Stocks Diff")
    inter_a = {s.get("ticker", s.get("name", "?")) for s in rpt_a.get("interconnected", [])}
    inter_b = {s.get("ticker", s.get("name", "?")) for s in rpt_b.get("interconnected", [])}
    added = inter_b - inter_a
    removed = inter_a - inter_b
    if added:
        st.markdown(f"**Added:** {', '.join(sorted(added))}")
    if removed:
        st.markdown(f"**Removed:** {', '.join(sorted(removed))}")
    if not added and not removed:
        st.caption("No changes to interconnected stocks.")

    # ── Key Metric Shifts ──
    st.subheader("Key Metric Shifts")
    metric_rows = []
    for tk in all_tickers:
        da = wl_a.get(tk, {})
        db = wl_b.get(tk, {})
        price_a = da.get("price")
        price_b = db.get("price")
        rsi_a = da.get("rsi_14")
        rsi_b = db.get("rsi_14")
        vs50_a = da.get("vs_sma50_pct")
        vs50_b = db.get("vs_sma50_pct")

        # Only show tickers with meaningful changes
        if price_a is None and price_b is None:
            continue

        price_chg = ""
        if price_a and price_b:
            pct = (price_b - price_a) / price_a * 100
            price_chg = f"{pct:+.2f}%"

        rsi_chg = ""
        if rsi_a is not None and rsi_b is not None:
            rsi_chg = f"{rsi_b - rsi_a:+.1f}"

        vs50_chg = ""
        if vs50_a is not None and vs50_b is not None:
            vs50_chg = f"{vs50_b - vs50_a:+.1f}pp"

        curr_a = da.get("currency", "USD")
        curr_b = db.get("currency", "USD")
        pfx = "S$" if curr_b == "SGD" or curr_a == "SGD" else "$"
        metric_rows.append({
            "Ticker": tk,
            f"Price ({date_a})": f"{pfx}{price_a:,.2f}" if price_a else "—",
            f"Price ({date_b})": f"{pfx}{price_b:,.2f}" if price_b else "—",
            "Price Chg": price_chg or "—",
            "RSI Chg": rsi_chg or "—",
            "vs SMA50 Chg": vs50_chg or "—",
        })
    if metric_rows:
        st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)
