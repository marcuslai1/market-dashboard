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

# ── Theme CSS: dark editorial (Newsreader serif + JetBrains Mono + Inter Tight) ──
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;500;600&family=Inter+Tight:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --paper:    #14140F;
  --paper-2:  #1B1B16;
  --paper-3:  #25241E;
  --ink:      #F4EFE2;
  --ink-2:    #C9C2B2;
  --ink-3:    #908A7C;
  --ink-4:    #5E5A50;
  --rule:        rgba(255, 255, 255, 0.08);
  --rule-strong: rgba(255, 255, 255, 0.20);
  --serif: 'Newsreader', Georgia, serif;
  --sans:  'Inter Tight', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono:  'JetBrains Mono', ui-monospace, monospace;
}

.stApp { background: var(--paper); color: var(--ink); font-family: var(--sans); }
.main .block-container { max-width: 1280px; padding-top: 18px; padding-bottom: 80px; }
[data-testid="stSidebar"] { background: var(--paper-2); border-right: 1px solid var(--rule-strong); }

/* Hide default Streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

/* Typography */
h1, h2, h3, h4 {
  font-family: var(--serif) !important;
  font-weight: 500 !important;
  letter-spacing: -0.01em !important;
  color: var(--ink) !important;
  text-transform: none !important;
}
h1 { font-size: 2.4rem !important; }
h2 { font-size: 1.5rem !important; }
h3 { font-size: 1.15rem !important; color: var(--ink-2) !important; }
[data-testid="stSubheader"] {
  font-family: var(--mono) !important;
  font-size: 0.78rem !important;
  font-weight: 600 !important;
  color: var(--ink-3) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.14em !important;
}
p, li, span, div, label { font-family: var(--sans); }

/* Metric cards */
[data-testid="stMetric"] {
  background: var(--paper-2);
  border: 1px solid var(--rule);
  border-radius: 0;
  padding: 12px 14px;
}
[data-testid="stMetricValue"] {
  font-family: var(--serif) !important;
  font-size: 1.6rem !important;
  font-weight: 500 !important;
  color: var(--ink) !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important;
  font-size: 10px !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-3) !important;
}
[data-testid="stMetricDelta"] {
  font-family: var(--mono) !important;
  font-size: 11px !important;
}

/* Dividers */
hr { border-color: var(--rule) !important; margin: 18px 0 !important; }

/* Expanders */
[data-testid="stExpander"] {
  background: var(--paper-2);
  border: 1px solid var(--rule);
  border-radius: 0;
  margin-bottom: 6px;
}
[data-testid="stExpander"] summary {
  font-family: var(--mono) !important;
  font-size: 11.5px !important;
  letter-spacing: 0.06em;
  color: var(--ink-2) !important;
}
[data-testid="stExpander"] summary span {
  font-family: var(--mono) !important;
  font-weight: 500 !important;
}

/* Buttons */
.stButton button {
  background: var(--paper-2);
  color: var(--ink);
  border: 1px solid var(--rule-strong);
  border-radius: 0;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 500;
  transition: background 0.15s, border-color 0.15s;
}
.stButton button:hover {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}

/* Selectbox / inputs */
.stSelectbox [data-baseweb="select"] {
  background: var(--paper-2);
  border-color: var(--rule-strong);
  border-radius: 0;
  font-family: var(--mono);
}
.stSelectbox [data-baseweb="select"]:hover { border-color: var(--ink-3); }
[data-baseweb="popover"] [data-baseweb="menu"] {
  background: var(--paper-2);
  border: 1px solid var(--rule-strong);
}

/* Radio (used for top tab nav) */
.stRadio > div { gap: 0 !important; }
.stRadio label {
  font-family: var(--mono) !important;
  font-size: 11px !important;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--ink-3) !important;
}

/* Tab nav (the real st.tabs and the masthead-radio styled like one) */
.stTabs [data-baseweb="tab-list"] {
  gap: 22px;
  border-bottom: 1.5px solid var(--ink);
}
.stTabs [data-baseweb="tab"] {
  font-family: var(--mono) !important;
  font-size: 11px !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-3) !important;
  padding: 6px 0 !important;
}
.stTabs [aria-selected="true"] {
  color: var(--ink) !important;
  font-weight: 600;
  border-bottom: 1.5px solid var(--ink) !important;
}

/* Top page-nav radio styled as tab strip */
.topnav-wrap { border-bottom: 1.5px solid var(--ink); margin-bottom: 22px; padding-bottom: 0; }
.topnav-wrap .stRadio > div {
  flex-direction: row !important;
  gap: 24px !important;
}
.topnav-wrap .stRadio label {
  padding: 6px 0 !important;
  cursor: pointer;
  border-bottom: 1.5px solid transparent;
  margin-bottom: -1.5px;
  color: var(--ink-3) !important;
  font-weight: 500;
}
.topnav-wrap .stRadio label:has(input:checked) {
  color: var(--ink) !important;
  font-weight: 600;
  border-bottom-color: var(--ink);
}
.topnav-wrap .stRadio [role="radiogroup"] > label > div:first-child { display: none !important; }

/* Dataframes */
[data-testid="stDataFrame"] {
  border: 1px solid var(--rule-strong);
  border-radius: 0;
  font-family: var(--mono);
}

/* Captions */
.stCaption, [data-testid="stCaptionContainer"] {
  font-family: var(--mono) !important;
  font-size: 11px !important;
  color: var(--ink-3) !important;
  letter-spacing: 0.04em;
}

/* Code/pre/json */
pre, code, .stCodeBlock { font-family: var(--mono) !important; }

/* Sidebar header (legacy — only used for the small refresh / status block) */
.sidebar-header {
  padding: 12px 8px 10px;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 12px;
}
.sidebar-header h2 {
  color: var(--ink) !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.14em;
  margin: 0;
  text-transform: uppercase !important;
}
.sidebar-header .subtitle {
  color: var(--ink-3);
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  margin-top: 4px;
  text-transform: uppercase;
}
.sidebar-status {
  background: var(--paper-3);
  border: 1px solid var(--rule);
  border-radius: 0;
  padding: 10px 12px;
  margin: 8px 0;
  font-family: var(--mono);
  font-size: 11px;
}
.sidebar-status .status-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}
.sidebar-status .status-label { color: var(--ink-3); }
.sidebar-status .status-value { color: var(--ink); font-weight: 600; }

/* ── Editorial masthead ── */
.masthead {
  display: grid; grid-template-columns: 1fr auto;
  align-items: end;
  border-bottom: 1.5px solid var(--ink);
  padding-bottom: 14px;
  margin: 4px 0 0;
}
.masthead .kicker {
  font-family: var(--mono);
  font-size: 10.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.masthead .title {
  font-family: var(--serif);
  font-weight: 600;
  font-size: 2.6rem;
  line-height: 0.95;
  letter-spacing: -0.02em;
  margin: 4px 0 0;
}
.masthead .title em { font-style: italic; font-weight: 500; color: var(--ink-2); }
.masthead .right {
  text-align: right;
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--ink-3);
  line-height: 1.55;
}
.masthead .right .date {
  font-family: var(--serif);
  font-size: 15px;
  color: var(--ink);
  font-weight: 500;
}
.masthead-strip {
  display: flex; justify-content: space-between;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-3);
  padding: 8px 0 12px;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 0;
}

/* Section heads (used inside Briefing) */
.section-head {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px;
  margin: 28px 0 14px;
}
.section-head h2 { margin: 0; font-size: 1.4rem !important; }
.section-head .sub {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3);
}
</style>""", unsafe_allow_html=True)


def _escape_dollars(text: str) -> str:
    """Escape $ signs so Streamlit doesn't render them as LaTeX."""
    return text.replace("$", "\\$") if text else text


def _truncate_rationale(text: str) -> str:
    """Show the first 1-2 complete sentences of the rationale."""
    if not text:
        return text
    # Find the second sentence boundary to capture 1-2 full sentences
    end = -1
    for i, ch in enumerate(text):
        if ch == '.' and i + 1 < len(text) and text[i + 1] == ' ':
            if end == -1:
                end = i + 1  # first sentence
            else:
                end = i + 1  # second sentence
                break
    # If text ends with a period (single sentence, no trailing space)
    if end == -1 and text.rstrip().endswith('.'):
        return text.rstrip()
    if end == -1:
        return text  # no sentence boundary found, show all
    return text[:end]


def _writeup_for_render(d: dict) -> dict:
    """Return {headline, what_to_do, entry_block} from new schema, or shim from legacy.

    For old reports that only have signal_rationale: headline = first sentence,
    what_to_do = remaining sentences (or None for HOLD / CAUTION-technical), and
    entry_block reads the top-level mechanical entry_block field.
    """
    wu = d.get("writeup")
    if isinstance(wu, dict):
        return {
            "headline": wu.get("headline") or "",
            "what_to_do": wu.get("what_to_do"),
            "entry_block": wu.get("entry_block") or d.get("entry_block"),
        }
    rat = (d.get("signal_rationale") or "").strip()
    if not rat:
        return {"headline": "", "what_to_do": None, "entry_block": d.get("entry_block")}
    # Split first sentence as headline, rest as what_to_do.
    headline = rat
    rest = ""
    for i, ch in enumerate(rat):
        if ch == "." and i + 1 < len(rat) and rat[i + 1] == " ":
            headline = rat[: i + 1]
            rest = rat[i + 2 :].strip()
            break
    # Suppress what_to_do for signals where new schema mandates null.
    sig = d.get("signal", "")
    cs = d.get("caution_source", "")
    if sig == "HOLD":
        rest = ""
    elif sig == "CAUTION" and cs == "hard_block":
        # Mechanical block, treat as technical_only — entry_block carries the gate.
        rest = ""
    return {
        "headline": headline,
        "what_to_do": rest or None,
        "entry_block": d.get("entry_block"),
    }


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


@st.cache_data(ttl=300)
def load_signal_log() -> pd.DataFrame:
    """Load signal_evaluation_log export (paper-trade outcomes)."""
    csv_path = DATA_DIR / "signal_log.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    for col in ["price_after_5d", "price_after_10d", "price_after_20d",
                "entry_price", "invalidation", "upside_target", "rr_ratio"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for horizon in ["5d", "10d", "20d"]:
        pa = f"price_after_{horizon}"
        if pa in df.columns:
            df[f"return_{horizon}"] = (df[pa] - df["entry_price"]) / df["entry_price"] * 100
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

SIGNAL_VERBS = {
    "BUY": "Enter now",
    "ACCUMULATE": "Add on strength",
    "WATCH": "Wait for trigger",
    "HOLD": "Maintain",
    "CAUTION": "Trim / avoid",
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

CLUSTER_MAP = {
    "NVDA": "Semis", "AMD": "Semis", "INTC": "Semis", "MU": "Semis",
    "TSM": "Semis", "AVGO": "Semis", "ASML": "Semis",
    "AMZN": "BigTech", "GOOG": "BigTech", "MSFT": "BigTech",
    "D05_SI": "SG Banks", "O39_SI": "SG Banks", "U11_SI": "SG Banks",
    "LITE": "AI Optics", "PLTR": "Defense AI", "WRD": "China Tech",
}

# ── Editorial CSS classes (briefing-page-only blocks) ──
st.markdown("""<style>
.stance-deck {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.2em; text-transform: uppercase;
  margin: 22px 0 10px;
  display: flex; align-items: center; gap: 8px;
}
.stance-deck .dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.stance-headline {
  font-family: var(--serif); font-weight: 500;
  font-size: 1.9rem; line-height: 1.18; letter-spacing: -0.01em;
  margin: 0 0 10px; color: var(--ink);
  max-width: 70ch;
}
.stance-byline {
  font-family: var(--mono); font-size: 10.5px;
  color: var(--ink-3); letter-spacing: 0.06em;
}

.count-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px;
  background: var(--rule-strong);
  border: 1px solid var(--rule-strong);
  margin-top: 18px; margin-bottom: 8px;
}
.count-cell { background: var(--paper); padding: 14px 10px; text-align: center; }
.count-cell .clabel {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase;
  color: var(--ink-3); margin-bottom: 4px;
}
.count-cell .cnum {
  font-family: var(--serif); font-size: 1.9rem;
  font-weight: 500; line-height: 1; color: var(--ink);
}
.count-cell.zero .cnum { color: var(--ink-4); }
.count-cell .cdot {
  width: 7px; height: 7px; border-radius: 50%;
  display: inline-block; margin-right: 4px; vertical-align: 1.5px;
}

.pulse-grid {
  display: grid; grid-template-columns: repeat(8, 1fr);
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: 14px 0;
  margin: 18px 0 8px;
}
.pulse-cell {
  padding: 0 14px; border-right: 1px solid var(--rule);
}
.pulse-cell:last-child { border-right: 0; }
.pulse-cell .plabel {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);
}
.pulse-cell .pprice {
  font-family: var(--serif); font-size: 1.25rem; font-weight: 500;
  letter-spacing: -0.01em; margin-top: 2px; color: var(--ink);
}
.pulse-cell .pdelta { font-family: var(--mono); font-size: 11px; margin-top: 2px; }
.up   { color: #22c55e; }
.down { color: #ef4444; }
.flat { color: var(--ink-3); }

.changes-ribbon {
  background: var(--paper-2); border: 1px solid var(--rule);
  padding: 12px 16px; margin: 12px 0 6px;
  display: flex; gap: 22px; align-items: center; flex-wrap: wrap;
  font-family: var(--mono); font-size: 12px;
}
.changes-ribbon .clabel {
  font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3); font-weight: 600;
}

.section-head { /* defined globally too — local override allowed if needed */ }

.action-card {
  background: var(--paper-2); border: 1px solid var(--rule-strong);
  border-left: 3px solid var(--ink);
  padding: 22px 26px; margin: 8px 0 16px;
  display: grid; grid-template-columns: 130px 1fr auto; gap: 24px;
  align-items: start;
}
.action-card .atag {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-3);
  line-height: 1.4;
}
.action-card .atag .pill {
  display: inline-block; font-weight: 600; padding: 3px 9px;
  border-radius: 3px; margin-top: 8px;
  background: var(--paper-3); color: var(--ink); font-size: 10px;
  letter-spacing: 0.04em;
}
.action-card .ticker {
  font-family: var(--mono); font-size: 12.5px; font-weight: 600;
  letter-spacing: 0.04em; color: var(--ink-3);
}
.action-card .head {
  font-family: var(--serif); font-size: 1.3rem; font-weight: 500;
  margin: 4px 0 8px; color: var(--ink); line-height: 1.3;
}
.action-card .plain {
  color: var(--ink-2); font-size: 14px; line-height: 1.55;
  max-width: 60ch;
}
.action-card .block {
  margin-top: 10px; font-family: var(--mono); font-size: 11.5px;
  border-left: 2px solid #f59e0b80; padding-left: 10px; color: #fbb454;
  line-height: 1.5;
}
.action-card .right {
  font-family: var(--mono); font-size: 11px;
  text-align: right; color: var(--ink-3); line-height: 1.6;
}
.action-card .right .level {
  font-family: var(--serif); font-size: 1.4rem;
  color: var(--ink); font-weight: 500; letter-spacing: -0.01em;
}

.tk-row {
  display: grid;
  grid-template-columns: 80px 1fr 110px 110px 80px 100px 60px 70px;
  gap: 12px; padding: 14px 12px;
  border-bottom: 1px solid var(--rule);
  font-family: var(--mono); font-size: 12.5px; align-items: center;
}
.tk-row.head {
  border-bottom: 1.5px solid var(--ink);
  font-size: 9.5px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3); padding: 8px 12px;
}
.tk-row .name { font-family: var(--sans); color: var(--ink-2); }
.sig-pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase;
  padding: 3px 8px; border-radius: 3px;
}
.sig-pill::before {
  content: ""; width: 6px; height: 6px;
  border-radius: 50%; background: currentColor;
}

.risk-card {
  padding: 14px 0; border-bottom: 1px solid var(--rule);
}
.risk-card .tag {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.12em;
  color: #ef4444; margin-bottom: 4px;
}
.risk-card .text { font-size: 13.5px; color: var(--ink-2); line-height: 1.55; }

.cal-day {
  display: grid; grid-template-columns: 110px 1fr; gap: 24px;
  padding: 14px 0; border-bottom: 1px solid var(--rule);
}
.cal-date {
  font-family: var(--serif); font-size: 1.1rem; font-weight: 500; color: var(--ink);
}
.cal-date .dow {
  font-family: var(--mono); font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--ink-3); display: block; margin-top: 2px;
}
.cal-event {
  display: grid; grid-template-columns: 60px 1fr;
  gap: 14px; align-items: baseline; margin-bottom: 8px;
}
.cal-impact {
  font-family: var(--mono); font-size: 9.5px; letter-spacing: 0.14em;
  text-transform: uppercase; font-weight: 600; padding: 2px 6px;
  border-radius: 2px; text-align: center; width: fit-content;
}
.cal-impact.HIGH { color: #ef4444; background: rgba(239,68,68,0.16); }
.cal-impact.MEDIUM { color: #f59e0b; background: rgba(245,158,11,0.18); }
.cal-impact.LOW { color: var(--ink-3); background: rgba(255,255,255,0.05); }
.cal-text { font-size: 13.5px; color: var(--ink-2); line-height: 1.5; }

.macro-lead {
  font-family: var(--serif); font-size: 1.2rem; font-weight: 400;
  line-height: 1.5; color: var(--ink); margin-bottom: 14px;
  max-width: 70ch;
}
.macro-action {
  font-size: 13.5px; color: var(--ink-2); line-height: 1.6;
  border-left: 2px solid var(--rule-strong); padding-left: 12px;
}

.colophon {
  margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--rule);
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.10em;
  text-transform: uppercase; color: var(--ink-4);
}
</style>""", unsafe_allow_html=True)


# ── Editorial render functions (Briefing page) ──
SIGNAL_ORDER = ["BUY", "ACCUMULATE", "WATCH", "HOLD", "CAUTION"]
WRITEUP_SIGNALS = {"BUY", "ACCUMULATE", "WATCH", "CAUTION"}
ACTIONABLE_SIGNALS = {"BUY", "ACCUMULATE", "WATCH"}

# Signal palette tints (used by sig_pill_html for backgrounds)
SIGNAL_TINTS = {
    "BUY":        "rgba(34,197,94,0.16)",
    "ACCUMULATE": "rgba(52,152,219,0.18)",
    "WATCH":      "rgba(245,158,11,0.18)",
    "HOLD":       "rgba(160,160,160,0.14)",
    "CAUTION":    "rgba(239,68,68,0.16)",
}


def _delta_class(chg, inverse=False) -> str:
    if chg is None or (isinstance(chg, float) and pd.isna(chg)) or chg == 0:
        return "flat"
    up = chg > 0
    if inverse:
        return "down" if up else "up"
    return "up" if up else "down"


def _fmt_num(n, decimals=2) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "—"
    return f"{float(n):,.{decimals}f}"


def _sign(n) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return ""
    return "+" if n > 0 else ""


def _signal_pill_html(sig: str, small: bool = False) -> str:
    color = SIGNAL_COLORS.get(sig, "#9F988B")
    tint = SIGNAL_TINTS.get(sig, "rgba(255,255,255,0.08)")
    pad = "1px 6px" if small else "3px 8px"
    fs = "9.5px" if small else "10.5px"
    return (
        f'<span class="sig-pill" style="color:{color};background:{tint};'
        f'padding:{pad};font-size:{fs};">{sig}</span>'
    )


def render_section_head(title: str, sub: str = "") -> None:
    st.markdown(
        f'<div class="section-head"><h2>{title}</h2>'
        f'<span class="sub">{sub}</span></div>',
        unsafe_allow_html=True,
    )


def render_stance(snapshot: dict, total_tracked: int) -> None:
    stance = snapshot.get("overall_stance", "—")
    posture = snapshot.get("risk_posture", "")
    counts = snapshot.get("signal_counts", {})
    deck_color = SIGNAL_COLORS.get("CAUTION", "#ef4444")
    st.markdown(
        f'<div class="stance-deck" style="color:{deck_color};">'
        f'<span class="dot" style="background:{deck_color};"></span>'
        f'<span>Today\'s Posture</span>'
        f'<span style="color:var(--ink-3);">· {total_tracked} names tracked</span>'
        f'</div>'
        f'<h2 class="stance-headline">{_escape_dollars(posture or stance)}</h2>'
        f'<div class="stance-byline">{_escape_dollars(stance.upper())} · BY THE SIGNAL DESK</div>',
        unsafe_allow_html=True,
    )
    cells = ""
    for sig in SIGNAL_ORDER:
        n = counts.get(sig, 0)
        color = SIGNAL_COLORS.get(sig, "#9F988B")
        zero_class = "zero" if n == 0 else ""
        num_color = f"color:{color};" if n > 0 else ""
        cells += (
            f'<div class="count-cell {zero_class}">'
            f'<div class="clabel"><span class="cdot" style="background:{color};"></span>{sig}</div>'
            f'<div class="cnum" style="{num_color}">{n}</div></div>'
        )
    st.markdown(f'<div class="count-grid">{cells}</div>', unsafe_allow_html=True)


PULSE_ORDER = [
    ("SPY",   "S&P 500",     False),
    ("QQQ",   "Nasdaq 100",  False),
    ("VIX",   "Fear gauge",  True),
    ("WTI",   "Crude oil",   False),
    ("Gold",  "Gold",        False),
    ("DXY",   "Dollar idx",  False),
    ("US10Y", "10-yr yield", False),
    ("SOXX",  "Semis ETF",   False),
]


def render_pulse(benchmarks: dict) -> None:
    cells = ""
    for key, label, inverse in PULSE_ORDER:
        b = benchmarks.get(key, {}) or {}
        price = b.get("price")
        chg = b.get("chg_pct")
        decimals = 0 if (price is not None and price > 1000) else 2
        cells += (
            f'<div class="pulse-cell">'
            f'<div class="plabel">{key} · {label}</div>'
            f'<div class="pprice">{_fmt_num(price, decimals)}</div>'
            f'<div class="pdelta {_delta_class(chg, inverse)}">'
            f'{_sign(chg)}{_fmt_num(chg, 2)}%</div>'
            f'</div>'
        )
    st.markdown(f'<div class="pulse-grid">{cells}</div>', unsafe_allow_html=True)


def render_changes(today_wl: dict, prev_wl: dict) -> None:
    if not prev_wl:
        return
    rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    items = []
    rationales: dict[str, str] = {}
    for tk in sorted(set(today_wl) | set(prev_wl)):
        old = prev_wl.get(tk, {}).get("signal", "—")
        new = today_wl.get(tk, {}).get("signal", "—")
        if old == new or new == "—" or old == "—":
            continue
        direction = "up" if rank.get(new, 0) > rank.get(old, 0) else "down"
        arrow_color = SIGNAL_COLORS.get(new, "#9F988B")
        display_tk = TICKER_DISPLAY.get(tk, tk)
        items.append(
            f'<span style="display:inline-flex;align-items:center;gap:8px;">'
            f'<strong style="color:var(--ink);">{display_tk}</strong>'
            f'{_signal_pill_html(old, small=True)}'
            f'<span style="color:{arrow_color};font-weight:700;">'
            f'{"↑" if direction == "up" else "↓"}</span>'
            f'{_signal_pill_html(new, small=True)}'
            f'</span>'
        )
        wu = _writeup_for_render(today_wl.get(tk, {}))
        note = wu["headline"] or (wu["what_to_do"] or "").split(". ", 1)[0]
        if note:
            rationales[display_tk] = note
    if not items:
        return
    body = '<span class="clabel">Since yesterday</span>' + " ".join(items)
    st.markdown(f'<div class="changes-ribbon">{body}</div>', unsafe_allow_html=True)
    if rationales:
        with st.expander("Why the signals moved", expanded=False):
            for tk, txt in rationales.items():
                st.markdown(f"**{tk}** — {_escape_dollars(txt)}")


def _pick_action_ticker(wl: dict) -> tuple[str | None, dict | None]:
    """Pick the single most actionable BUY/ACCUMULATE/WATCH name.

    Returns (None, None) when nothing is actionable — caller should skip the callout.
    """
    priority = {"BUY": 0, "ACCUMULATE": 1, "WATCH": 2}
    candidates = [
        (tk, d) for tk, d in wl.items()
        if d.get("signal") in priority and tk not in RETIRED_TICKERS
    ]
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: (
        priority.get(x[1].get("signal"), 99),
        -((x[1].get("risk_reward") or {}).get("ratio") or 0),
    ))
    return candidates[0]


def render_action_card(wl: dict, events: list) -> None:
    tk, d = _pick_action_ticker(wl)
    if not tk:
        # Nothing actionable today — render nothing per design.
        return
    sig = d.get("signal", "WATCH")
    color = SIGNAL_COLORS.get(sig, "#9F988B")
    display_tk = TICKER_DISPLAY.get(tk, tk)
    cluster = CLUSTER_MAP.get(tk, "")
    price = d.get("price")
    ccy = d.get("currency", "USD")
    chg = d.get("chg_pct")
    wu = _writeup_for_render(d)
    headline = wu["headline"] or ""
    body = wu["what_to_do"] or ""
    block = wu["entry_block"]
    rr_label = (d.get("risk_reward") or {}).get("ratio_label", "")

    pfx = "S$" if ccy == "SGD" else "$"
    price_str = f"{pfx}{_fmt_num(price, 2)}"
    delta_color = SIGNAL_COLORS["BUY"] if (chg or 0) >= 0 else SIGNAL_COLORS["CAUTION"]
    delta_str = f"{_sign(chg)}{_fmt_num(chg, 2)}%" if chg is not None else ""

    block_html = (
        f'<div class="block">{_escape_dollars(block)}</div>'
        if block else ""
    )

    render_section_head("If you only do one thing today",
                        "The desk's single highest-conviction action")
    st.markdown(
        f'<div class="action-card" style="border-left-color:{color};">'
        f'<div class="atag">'
        f'<div>If you only do</div><div>one thing today</div>'
        f'<span class="pill" style="background:{SIGNAL_TINTS.get(sig, "var(--paper-3)")};color:{color};">'
        f'{SIGNAL_VERBS.get(sig, sig)}</span>'
        f'</div>'
        f'<div>'
        f'<div class="ticker">{display_tk}{" · " + cluster if cluster else ""}</div>'
        f'<div class="head">{_escape_dollars(headline)}</div>'
        f'<div class="plain">{_escape_dollars(body)}</div>'
        f'{block_html}'
        f'</div>'
        f'<div class="right">'
        f'<div>Last</div>'
        f'<div class="level">{price_str}</div>'
        f'<div style="margin-top:6px;color:{delta_color};">{delta_str} today</div>'
        f'<div style="margin-top:8px;">{("R:R " + rr_label) if rr_label else ""}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_macro(macro_summary: str, geo: dict) -> None:
    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown(
            '<div class="section-head" style="margin:0 0 12px;border-bottom:0;padding-bottom:0;">'
            '<h2>The Macro Note</h2>'
            '<span class="sub">What\'s driving prices</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        if macro_summary:
            st.markdown(
                f'<p class="macro-lead">{_escape_dollars(macro_summary)}</p>',
                unsafe_allow_html=True,
            )
        if geo.get("portfolio_action"):
            st.markdown(
                f'<div class="macro-action">'
                f'<strong style="color:var(--ink);">Portfolio implication.</strong> '
                f'{_escape_dollars(geo.get("portfolio_action", ""))}</div>',
                unsafe_allow_html=True,
            )
        probs = geo.get("probabilities") or {}
        if probs:
            colors = {
                "base":        SIGNAL_COLORS["ACCUMULATE"],
                "optimistic":  SIGNAL_COLORS["BUY"],
                "pessimistic": SIGNAL_COLORS["CAUTION"],
                "wildcard":    SIGNAL_COLORS["WATCH"],
            }
            labels = {"base": "Base case", "optimistic": "Optimistic",
                      "pessimistic": "Pessimistic", "wildcard": "Wildcard"}
            segs, keys = "", ""
            for k in ["base", "optimistic", "pessimistic", "wildcard"]:
                v = probs.get(k, 0) or 0
                if v:
                    segs += (
                        f'<div style="width:{v}%;background:{colors[k]};'
                        f'display:flex;align-items:center;justify-content:center;'
                        f'color:var(--paper);font-family:var(--mono);'
                        f'font-size:11px;font-weight:600;">{v}%</div>'
                    )
                keys += (
                    f'<div><span style="display:inline-block;width:8px;height:8px;'
                    f'background:{colors[k]};margin-right:6px;"></span>'
                    f'{labels[k]}</div>'
                )
            st.markdown(
                f'<div style="margin-top:18px;">'
                f'<div style="font-family:var(--mono);font-size:10px;'
                f'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
                f'margin-bottom:8px;">Scenario odds</div>'
                f'<div style="display:flex;height:24px;border:1px solid var(--rule-strong);'
                f'margin-bottom:8px;">{segs}</div>'
                f'<div style="display:grid;grid-template-columns:repeat(2,1fr);'
                f'gap:4px 18px;font-family:var(--mono);font-size:11px;'
                f'color:var(--ink-3);">{keys}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with col2:
        st.markdown(
            '<div style="font-family:var(--mono);font-size:10px;'
            'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
            'margin-bottom:8px;margin-top:6px;">Active risks</div>',
            unsafe_allow_html=True,
        )
        for r in (geo.get("active_risks") or [])[:5]:
            tag = r.split(":", 1)[0][:24] if ":" in r else "Risk"
            st.markdown(
                f'<div class="risk-card">'
                f'<div class="tag">{_escape_dollars(tag)}</div>'
                f'<div class="text">{_escape_dollars(r)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_calendar(events: list) -> None:
    if not events:
        st.markdown(
            '<p style="color:var(--ink-3);font-size:13px;">No catalysts logged.</p>',
            unsafe_allow_html=True,
        )
        return
    grouped: dict[str, list] = {}
    for e in events:
        grouped.setdefault(e.get("date", "—"), []).append(e)
    from datetime import datetime as _dt
    for date_str in sorted(grouped.keys()):
        try:
            d = _dt.strptime(date_str, "%Y-%m-%d")
            short, dow = d.strftime("%b %d"), d.strftime("%a").upper()
        except (ValueError, TypeError):
            short, dow = date_str, ""
        events_html = ""
        for e in grouped[date_str]:
            impact = (e.get("impact") or "LOW").upper()
            events_html += (
                f'<div class="cal-event">'
                f'<span class="cal-impact {impact}">{impact}</span>'
                f'<span class="cal-text">{_escape_dollars(e.get("event", ""))}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div class="cal-day">'
            f'<div class="cal-date">{short}<span class="dow">{dow}</span></div>'
            f'<div>{events_html}</div></div>',
            unsafe_allow_html=True,
        )


def render_watchlist(watchlist: dict) -> None:
    """Editorial watchlist with click-to-expand drill-down per ticker.

    HOLD tickers do NOT get an expander (no actionable content).
    """
    rank = {"BUY": 0, "ACCUMULATE": 1, "WATCH": 2, "HOLD": 3, "CAUTION": 4}
    items = sorted(
        [(tk, d) for tk, d in watchlist.items() if tk not in RETIRED_TICKERS],
        key=lambda x: (
            rank.get(x[1].get("signal", "HOLD"), 5),
            -(x[1].get("1mo_pct") or 0),
        ),
    )
    st.markdown(
        '<div class="tk-row head">'
        '<div>Ticker</div><div>Name</div><div>Signal</div>'
        '<div style="text-align:right;">Last · Δ</div>'
        '<div style="text-align:right;">1mo</div>'
        '<div style="text-align:right;">vs 50-day</div>'
        '<div style="text-align:right;">RSI</div>'
        '<div style="text-align:right;">R:R</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    for tk, d in items:
        sig = d.get("signal", "HOLD")
        display_tk = TICKER_DISPLAY.get(tk, tk)
        ccy = d.get("currency", "USD")
        pfx = "S$" if ccy == "SGD" else "$"
        price = d.get("price")
        chg = d.get("chg_pct")
        m1 = d.get("1mo_pct")
        vs50 = d.get("vs_sma50_pct")
        rsi = d.get("rsi_14")
        rr = (d.get("risk_reward") or {}).get("ratio")
        st.markdown(
            f'<div class="tk-row">'
            f'<div style="font-weight:600;color:var(--ink);">{display_tk}</div>'
            f'<div class="name">{CLUSTER_MAP.get(tk, "")}</div>'
            f'<div>{_signal_pill_html(sig)}</div>'
            f'<div style="text-align:right;">'
            f'{pfx}{_fmt_num(price, 2)}'
            f'<div class="{_delta_class(chg)}" style="font-size:10.5px;">'
            f'{_sign(chg)}{_fmt_num(chg, 2)}%</div></div>'
            f'<div class="{_delta_class(m1)}" style="text-align:right;">'
            f'{_sign(m1)}{_fmt_num(m1, 1)}%</div>'
            f'<div style="text-align:right;">{_sign(vs50)}{_fmt_num(vs50, 1)}%</div>'
            f'<div style="text-align:right;">{_fmt_num(rsi, 0)}</div>'
            f'<div style="text-align:right;">{_fmt_num(rr, 1)}:1</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if sig not in WRITEUP_SIGNALS:
            continue  # HOLD: no expander
        wu = _writeup_for_render(d)
        with st.expander(f"  Read the {sig.lower()} call on {display_tk}"):
            block = wu["entry_block"]
            if block:
                st.markdown(
                    f'<div style="background:rgba(245,158,11,0.16);'
                    f'color:#fbb454;padding:8px 12px;border-left:3px solid #f59e0b80;'
                    f'font-family:var(--mono);font-size:11.5px;margin-bottom:12px;">'
                    f'ENTRY BLOCK · {_escape_dollars(block)}</div>',
                    unsafe_allow_html=True,
                )
            if wu["headline"]:
                st.markdown(
                    f'<div style="font-family:var(--serif);font-size:1.15rem;'
                    f'font-weight:500;color:var(--ink);margin-bottom:8px;'
                    f'line-height:1.35;">{_escape_dollars(wu["headline"])}</div>',
                    unsafe_allow_html=True,
                )
            if wu["what_to_do"]:
                st.markdown(
                    f'<div style="font-family:var(--sans);font-size:14px;'
                    f'line-height:1.6;color:var(--ink-2);max-width:75ch;">'
                    f'{_escape_dollars(wu["what_to_do"])}</div>',
                    unsafe_allow_html=True,
                )
            val = d.get("valuation", {}) or {}
            rr_obj = d.get("risk_reward", {}) or {}
            metrics = [
                ("Cluster", CLUSTER_MAP.get(tk, "—")),
                ("Forward P/E",
                 f"{_fmt_num(val.get('forward_pe'), 1)}x" if val.get("forward_pe") else "—"),
                ("PEG", _fmt_num(val.get("peg_ratio"), 2)),
                ("Revenue growth",
                 f"{_sign(val.get('revenue_growth_pct'))}{_fmt_num(val.get('revenue_growth_pct'), 1)}%"),
                ("vs 50-day", f"{_sign(vs50)}{_fmt_num(vs50, 1)}%"),
                ("RSI (14d)", _fmt_num(rsi, 0)),
                ("Risk:Reward", f"{_fmt_num(rr, 1)}:1"),
                ("Invalidation", _fmt_num(rr_obj.get("invalidation"), 2)),
            ]
            cols = st.columns(4)
            for i, (label, value) in enumerate(metrics):
                cols[i % 4].markdown(
                    f'<div style="border-bottom:1px dashed var(--rule);padding:6px 0;">'
                    f'<div style="font-family:var(--mono);font-size:9.5px;'
                    f'color:var(--ink-3);text-transform:uppercase;letter-spacing:0.08em;">'
                    f'{label}</div>'
                    f'<div style="font-family:var(--mono);font-size:13px;margin-top:2px;'
                    f'color:var(--ink);">{value}</div></div>',
                    unsafe_allow_html=True,
                )
# ── Masthead + top tab nav (rendered at top of main area) ──
_mh_reports = load_all_reports()
_mh_dates = sorted(_mh_reports.keys()) if _mh_reports else []
_mh_latest = _mh_dates[-1] if _mh_dates else "—"
_mh_first = _mh_dates[0] if _mh_dates else None
_mh_issue = "—"
if _mh_first:
    try:
        _first_d = date.fromisoformat(_mh_first)
        _last_d = date.fromisoformat(_mh_latest)
        _mh_issue = f"No. {(_last_d - _first_d).days + 1}"
    except ValueError:
        pass
_mh_market_date = _mh_reports.get(_mh_latest, {}).get("meta", {}).get("market_date", "—")
try:
    _long_date = date.fromisoformat(_mh_latest).strftime("%A, %B %d, %Y")
except ValueError:
    _long_date = _mh_latest

st.markdown(
    f'<div class="masthead">'
    f'<div>'
    f'<div class="kicker">Morning Briefing · Signal Intelligence Daily</div>'
    f'<h1 class="title">The <em>Market</em> Report</h1>'
    f'</div>'
    f'<div class="right">'
    f'<div class="date">{_long_date}</div>'
    f'<div>Singapore · 11:30 SGT · Last close {_mh_market_date}</div>'
    f'</div>'
    f'</div>'
    f'<div class="masthead-strip">'
    f'<span>Issue {_mh_issue}</span>'
    f'<span>The Signal Desk</span>'
    f'<span>Updated 11:30 SGT</span>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="topnav-wrap">', unsafe_allow_html=True)
page = st.radio(
    "Navigate",
    ["Briefing", "Daily Report", "Signal Tracker",
     "Pipeline Stats", "Scenario Log",
     "Report Comparison"],
    horizontal=True,
    label_visibility="collapsed",
    key="page_nav",
)
st.markdown('</div>', unsafe_allow_html=True)

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
# PAGE 0: Briefing
# ════════════════════════════════════════════
if page == "Briefing":
    all_reports = load_all_reports()
    if not all_reports:
        st.error("No report files found in market_data/.")
        st.stop()

    sorted_dates = sorted(all_reports.keys(), reverse=True)
    latest_date = sorted_dates[0]
    report = all_reports[latest_date]
    prev_report = all_reports[sorted_dates[1]] if len(sorted_dates) >= 2 else None

    snapshot = report.get("portfolio_snapshot", {})
    watchlist = report.get("watchlist", {})
    benchmarks = report.get("benchmarks", {})
    geo = report.get("geopolitical", {})
    events = report.get("events_this_week", []) or []

    sub_brief, sub_watch, sub_cal, sub_macro = st.tabs(
        ["Briefing", "Watchlist", "Calendar", "Macro"]
    )

    with sub_brief:
        render_stance(snapshot, len(watchlist))
        render_pulse(benchmarks)
        render_changes(
            watchlist,
            prev_report.get("watchlist", {}) if prev_report else {},
        )
        render_action_card(watchlist, events)

        macro_col, cal_col = st.columns([3, 2])
        with macro_col:
            render_macro(report.get("macro_summary", ""), geo)
        with cal_col:
            render_section_head("The Week Ahead", "Catalysts that move signals")
            render_calendar(events)

        _render_signal_guide()

    with sub_watch:
        render_section_head(
            "The Watchlist",
            f"{sum(1 for tk in watchlist if tk not in RETIRED_TICKERS)} names · "
            "click an actionable row to expand"
        )
        render_pulse(benchmarks)
        render_watchlist(watchlist)

    with sub_cal:
        render_section_head("The Week Ahead", "Earnings · macro · Fed")
        render_calendar(events)

    with sub_macro:
        render_section_head("The Macro Note", "Geopolitics · rates · cross-asset")
        render_macro(report.get("macro_summary", ""), geo)


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

    report_path = DATA_DIR / f"morning_report_{selected}.json"
    if report_path.exists():
        st.download_button(
            label="↓ Download JSON for this day",
            data=report_path.read_bytes(),
            file_name=f"morning_report_{selected}.json",
            mime="application/json",
        )

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
                continue  # hide removed tickers — watchlist edits, not signal events
            elif r_new > r_old:
                arrow = "^"
            else:
                arrow = "v"
            display_tk = TICKER_DISPLAY.get(tk, tk)
            rationale = wl_today.get(tk, {}).get("signal_rationale", "")
            short_rationale = _truncate_rationale(rationale)
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
                st.dataframe(display_df, use_container_width=True, hide_index=True)

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
    with st.expander("Historical Writeup Viewer", expanded=False):
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
        # Summary metrics
        total_rows = len(sig_log)
        by_type = sig_log["entry_type"].value_counts().to_dict()
        summary_cols = st.columns(4)
        summary_cols[0].metric("Total Signals Logged", total_rows)
        summary_cols[1].metric("Catalyst Entries", by_type.get("catalyst", 0))
        summary_cols[2].metric("Standard Entries", by_type.get("standard", 0))
        summary_cols[3].metric("Monitor (non-entry)", by_type.get("monitor", 0))

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
            st.dataframe(bd_df, use_container_width=True, hide_index=True)

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
                st.dataframe(open_display, use_container_width=True, hide_index=True)


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
