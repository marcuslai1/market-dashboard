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

/* Restore Material Symbols font on icon glyphs so dropdown chevrons,
   expander toggles, etc. don't render their ligature names as raw text
   ("arrow_drop_down", "expand_more", ...). Must come AFTER the broad
   span/div override above. */
[data-testid="stIconMaterial"],
span.material-icons,
span.material-icons-outlined,
span.material-icons-rounded,
span.material-icons-sharp,
span.material-symbols-outlined,
span.material-symbols-rounded,
span.material-symbols-sharp,
span[class*="material-symbols"],
span[class*="material-icons"] {
  font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
               'Material Icons Rounded', 'Material Icons' !important;
  font-feature-settings: 'liga' !important;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}

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
[data-testid="stExpander"] summary span:not([data-testid="stIconMaterial"]):not([class*="material-"]) {
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

/* Top page-nav: the .topnav-wrap div is rendered into its own stMarkdown
   block as a hidden sibling marker; we use :has() + adjacent-sibling to
   reach the stRadio that immediately follows it and restyle it as a tab strip. */
.topnav-wrap { display: none; }

[data-testid="stMarkdown"]:has(.topnav-wrap) + [data-testid="stRadio"] {
  border-bottom: 1.5px solid var(--ink);
  margin-bottom: 22px;
}
[data-testid="stMarkdown"]:has(.topnav-wrap) + [data-testid="stRadio"] > label {
  display: none !important;
}
[data-testid="stMarkdown"]:has(.topnav-wrap) + [data-testid="stRadio"] [role="radiogroup"] {
  flex-direction: row !important;
  gap: 28px !important;
  border: none !important;
}
[data-testid="stMarkdown"]:has(.topnav-wrap) + [data-testid="stRadio"] [role="radiogroup"] > label {
  font-family: var(--mono) !important;
  font-size: 11px !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase;
  color: var(--ink-3) !important;
  padding: 8px 0 10px !important;
  margin-bottom: -1.5px !important;
  cursor: pointer;
  border-bottom: 1.5px solid transparent !important;
  font-weight: 500;
  background: transparent !important;
}
[data-testid="stMarkdown"]:has(.topnav-wrap) + [data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {
  display: none !important;
}
[data-testid="stMarkdown"]:has(.topnav-wrap) + [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
  color: var(--ink) !important;
  font-weight: 600;
  border-bottom-color: var(--ink) !important;
}

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
    """Return {headline, prior_period_delta_narrative, what_to_do, entry_block} from
    new schema, or shim from legacy.

    For old reports that only have signal_rationale: headline = first sentence,
    what_to_do = remaining sentences (or None for HOLD / CAUTION-technical), and
    entry_block reads the top-level mechanical entry_block field.
    """
    wu = d.get("writeup")
    if isinstance(wu, dict):
        return {
            "headline": wu.get("headline") or "",
            "prior_period_delta_narrative": wu.get("prior_period_delta_narrative"),
            "what_to_do": wu.get("what_to_do"),
            "entry_block": wu.get("entry_block") or d.get("entry_block"),
        }
    rat = (d.get("signal_rationale") or "").strip()
    if not rat:
        return {"headline": "", "prior_period_delta_narrative": None, "what_to_do": None, "entry_block": d.get("entry_block")}
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
        "prior_period_delta_narrative": None,
        "what_to_do": rest or None,
        "entry_block": d.get("entry_block"),
    }


def _legacy_rationale_from(d: dict) -> str:
    """Flatten the writeup into one string for legacy views (Historical
    Writeup Viewer, Compare-dates Rationale column). Concatenates
    headline + prior_period_delta_narrative + what_to_do for the new schema;
    falls back to signal_rationale for old reports.
    """
    wu = d.get("writeup")
    if isinstance(wu, dict):
        h = (wu.get("headline") or "").strip()
        delta = (wu.get("prior_period_delta_narrative") or "").strip()
        wt = (wu.get("what_to_do") or "").strip()
        pieces = [p for p in (h, delta, wt) if p]
        return " ".join(pieces)
    return d.get("signal_rationale", "") or ""


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
                  "memory_chars", "total_prompt_chars", "computed_cost_usd",
                  "cache_hit_tokens", "cache_miss_tokens"]
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
                "rationale": _legacy_rationale_from(data),
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

/* Native <details> drill-down — entire ticker row is the click target */
details.tk-details { margin: 0; padding: 0; border: 0; background: transparent; }
details.tk-details > summary {
  list-style: none;
  cursor: pointer;
  display: grid;
  grid-template-columns: 80px 1fr 110px 110px 80px 100px 60px 70px;
  gap: 12px; padding: 14px 12px;
  border-bottom: 1px solid var(--rule);
  font-family: var(--mono); font-size: 12.5px; align-items: center;
  transition: background 0.12s;
}
details.tk-details > summary::-webkit-details-marker { display: none; }
details.tk-details > summary::marker { content: ""; }
details.tk-details > summary:hover { background: var(--paper-2); }
details.tk-details[open] > summary { background: var(--paper-2); border-bottom-color: var(--rule-strong); }
details.tk-details > summary .name { font-family: var(--sans); color: var(--ink-2); }
.tk-drilldown {
  background: var(--paper-2);
  padding: 18px 22px 22px;
  border-bottom: 1px solid var(--rule);
}
.tk-drilldown .dd-section {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3); font-weight: 600;
  margin: 18px 0 8px; padding-bottom: 4px;
  border-bottom: 1px solid var(--rule);
}
.tk-drilldown .dd-section:first-child { margin-top: 0; }
.tk-drilldown .dd-line {
  font-size: 13px; color: var(--ink-2);
  margin-bottom: 6px; line-height: 1.55;
}
.tk-drilldown .dd-metric-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 0 18px;
}
.tk-drilldown .dd-metric {
  border-bottom: 1px dashed var(--rule);
  padding: 6px 0;
}
.tk-drilldown .dd-metric .lbl {
  font-family: var(--mono); font-size: 9.5px;
  color: var(--ink-3); text-transform: uppercase;
  letter-spacing: 0.08em;
}
.tk-drilldown .dd-metric .val {
  font-family: var(--mono); font-size: 13px;
  margin-top: 2px; color: var(--ink);
}
.tk-drilldown .dd-entry-block {
  background: rgba(245,158,11,0.16);
  color: #fbb454;
  padding: 8px 12px;
  border-left: 3px solid #f59e0b80;
  font-family: var(--mono); font-size: 11.5px;
  margin-bottom: 12px;
}
.tk-drilldown .dd-headline {
  font-family: var(--serif); font-size: 1.15rem;
  font-weight: 500; color: var(--ink);
  margin-bottom: 8px; line-height: 1.35;
}
.tk-drilldown .dd-whatdo {
  font-family: var(--sans); font-size: 14px;
  line-height: 1.6; color: var(--ink-2);
  max-width: 75ch; margin-bottom: 14px;
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


def render_catalyst_playbook(trigger_map: list) -> None:
    """Render `macro_trigger_map` — bull/bear playbook per upcoming macro event.

    Each entry has {event, date, bullish_outcome, bullish_upgrades[],
    bearish_outcome, bearish_impact[]}. Renders nothing when the list is
    empty. Defensive against the legacy nested-array shape (the pipeline
    flattens, but old reports may still carry [[…]] structure).
    """
    if not trigger_map:
        return
    # Defensive flatten in case an old report carries the pre-fix nested shape.
    if all(isinstance(x, list) for x in trigger_map):
        trigger_map = [item for sub in trigger_map for item in sub]
    render_section_head(
        "Catalyst Playbook",
        "How signals shift on each upcoming binary",
    )
    bull_color = SIGNAL_COLORS["BUY"]
    bear_color = SIGNAL_COLORS["CAUTION"]
    for ev in trigger_map:
        if not isinstance(ev, dict):
            continue
        name = ev.get("event", "—")
        when = ev.get("date", "")
        bull = ev.get("bullish_outcome") or ""
        bear = ev.get("bearish_outcome") or ""
        ups = ev.get("bullish_upgrades") or []
        impacts = ev.get("bearish_impact") or []

        ups_html = "".join(
            f'<li style="margin-bottom:3px;">{_escape_dollars(u)}</li>'
            for u in ups
        )
        impacts_html = "".join(
            f'<li style="margin-bottom:3px;">{_escape_dollars(i)}</li>'
            for i in impacts
        )
        st.markdown(
            f'<div style="border:1px solid var(--rule);background:var(--paper-2);'
            f'padding:14px 18px 12px;margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;border-bottom:1px solid var(--rule);'
            f'padding-bottom:8px;margin-bottom:10px;">'
            f'<span style="font-family:var(--serif);font-size:1.1rem;'
            f'font-weight:500;color:var(--ink);">{_escape_dollars(name)}</span>'
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.10em;text-transform:uppercase;color:var(--ink-3);">'
            f'{when}</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">'
            f'<div>'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.14em;text-transform:uppercase;color:{bull_color};'
            f'font-weight:600;margin-bottom:4px;">▲ Bullish path</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.5;'
            f'margin-bottom:8px;">{_escape_dollars(bull)}</div>'
            f'<ul style="margin:0;padding-left:18px;font-family:var(--mono);'
            f'font-size:11.5px;color:var(--ink-2);line-height:1.5;">{ups_html}</ul>'
            f'</div>'
            f'<div>'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.14em;text-transform:uppercase;color:{bear_color};'
            f'font-weight:600;margin-bottom:4px;">▼ Bearish path</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.5;'
            f'margin-bottom:8px;">{_escape_dollars(bear)}</div>'
            f'<ul style="margin:0;padding-left:18px;font-family:var(--mono);'
            f'font-size:11.5px;color:var(--ink-2);line-height:1.5;">{impacts_html}</ul>'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_contrarian_candidates(contrarians: list) -> None:
    """Render `contrarian_candidates` (RSI < 38 oversold names with thesis).

    The pipeline emits these only when at least one watchlist or near-watchlist
    name is genuinely oversold and has a coherent recovery thesis. Empty most
    days; when it fires, surface it prominently so the contrarian setup isn't
    lost in the wall of CAUTION.
    """
    if not contrarians:
        return
    render_section_head(
        "Contrarian Candidates",
        "Oversold names with a setup, not just a falling knife",
    )
    for c in contrarians:
        if not isinstance(c, dict):
            continue
        ticker = c.get("ticker", "—")
        display = TICKER_DISPLAY.get(ticker, ticker)
        rsi = c.get("rsi")
        rsi_str = f"RSI {_fmt_num(rsi, 0)}" if rsi is not None else ""
        thesis = c.get("thesis") or c.get("rationale") or ""
        trigger = c.get("trigger") or c.get("entry_trigger") or ""
        st.markdown(
            f'<div style="border-left:3px solid #22c55e;background:var(--paper-2);'
            f'padding:12px 16px;margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;margin-bottom:6px;">'
            f'<span style="font-family:var(--mono);font-weight:600;'
            f'color:var(--ink);font-size:13px;">{display}</span>'
            f'<span style="font-family:var(--mono);font-size:11px;'
            f'color:var(--ink-3);">{rsi_str}</span>'
            f'</div>'
            f'<div style="color:var(--ink-2);font-size:13px;line-height:1.55;">'
            f'{_escape_dollars(thesis)}</div>'
            + (
                f'<div style="margin-top:6px;font-family:var(--mono);font-size:11px;'
                f'color:#22c55e;">Trigger · {_escape_dollars(trigger)}</div>'
                if trigger else ""
            )
            + '</div>',
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
        st.markdown(_render_ticker_details_html(tk, d), unsafe_allow_html=True)


def _drilldown_section_html(title: str) -> str:
    return f'<div class="dd-section">{title}</div>'


def _drilldown_metrics_html(items: list[tuple[str, str]]) -> str:
    visible = [(label, value) for label, value in items if value not in (None, "", "—")]
    if not visible:
        return ""
    cells = "".join(
        f'<div class="dd-metric"><div class="lbl">{label}</div>'
        f'<div class="val">{value}</div></div>'
        for label, value in visible
    )
    return f'<div class="dd-metric-grid">{cells}</div>'


def _render_drilldown_detail_html(tk: str, d: dict) -> str:
    """HTML-string version of _render_drilldown_detail — returns one block of HTML
    suitable for embedding inside a <details> element. No Streamlit calls."""
    ccy = d.get("currency", "USD")
    pfx = "S$" if ccy == "SGD" else "$"
    val = d.get("valuation", {}) or {}
    rr_obj = d.get("risk_reward", {}) or {}
    sma50 = d.get("sma50")
    sma200 = d.get("sma200")
    sma50_rising = d.get("sma50_rising")
    sma_status = (
        "rising" if sma50_rising is True
        else "declining" if sma50_rising is False
        else "—"
    )
    days_above = d.get("days_above_sma50")
    rsi = d.get("rsi_14")
    rsi_zone = d.get("rsi_zone", "")
    vol_sig = d.get("volume_signal", "")
    vol_ratio = d.get("vol_ratio")
    chg5 = d.get("5d_pct")
    m1 = d.get("1mo_pct")
    vs50 = d.get("vs_sma50_pct")
    vs200 = d.get("vs_sma200_pct")

    parts: list[str] = []

    # ── Status strip (caution_source + momentum_warn) ──
    # Compact, visible without expanding any section. Shown only when there's
    # something worth flagging — silent on clean BUY/HOLD with no advisories.
    caution_source = d.get("caution_source")
    momentum_warn = d.get("momentum_warn")
    momentum_reasons = d.get("momentum_warn_reasons") or []
    signal = d.get("signal", "")
    cs_labels = {
        "hard_block": ("Mechanical hard block", "#ef4444"),
        "claude_override": ("Judgment override", "#f59e0b"),
        "base_scorer": ("Soft caution (base scorer)", "#f59e0b"),
        "rr_gate_fail": ("R:R gate failed", "#ef4444"),
        "catalyst_override": ("Catalyst override", "#3498db"),
    }
    status_chips: list[str] = []
    if caution_source and signal in {"CAUTION", "AVOID"}:
        label, color = cs_labels.get(
            caution_source, (caution_source, "#9ca3af")
        )
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.10em;text-transform:uppercase;'
            f'background:rgba(255,255,255,0.05);color:{color};'
            f'padding:3px 8px;border-radius:3px;">'
            f'{label} · {caution_source}</span>'
        )
    if momentum_warn:
        reason_str = "; ".join(momentum_reasons) if momentum_reasons else "tape diverging"
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.06em;background:rgba(245,158,11,0.16);'
            f'color:#fbb454;padding:3px 8px;border-radius:3px;">'
            f'momentum_warn · {_escape_dollars(reason_str)}</span>'
        )
    if status_chips:
        parts.append(
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">'
            + "".join(status_chips) + '</div>'
        )

    # ── Catalyst block (paper-trade entry path) ──
    catalyst = d.get("catalyst") or {}
    if catalyst:
        c_rr = d.get("catalyst_rr") or {}
        c_tier = d.get("catalyst_position_tier") or {}
        c_type = catalyst.get("type") or catalyst.get("catalyst_type") or ""
        c_headline = catalyst.get("headline") or catalyst.get("description") or ""
        c_source = catalyst.get("source") or ""
        c_url = catalyst.get("url") or ""
        c_date = catalyst.get("date") or catalyst.get("event_date") or ""
        c_pre_price = catalyst.get("pre_catalyst_close")
        c_rr_ratio = c_rr.get("ratio") or c_rr.get("ratio_raw")
        c_rr_inv = c_rr.get("invalidation")
        c_tier_name = c_tier.get("tier") or ""
        c_max_size = c_tier.get("max_size_pct")

        parts.append(_drilldown_section_html("Catalyst entry path · paper trade only"))
        if c_headline:
            head_html = (
                f'<div class="dd-line"><strong>{_escape_dollars(c_type) or "Catalyst"}.</strong> '
                f'{_escape_dollars(c_headline)}'
            )
            if c_source:
                head_html += f' <span style="color:var(--ink-3);">— {_escape_dollars(c_source)}</span>'
            if c_url:
                head_html += (
                    f' <a href="{c_url}" target="_blank" '
                    f'style="color:var(--ink-3);font-family:var(--mono);'
                    f'font-size:11px;">[link]</a>'
                )
            head_html += '</div>'
            parts.append(head_html)
        cat_metrics = [
            ("Catalyst date", c_date or "—"),
            (
                "Catalyst R:R",
                f"{_fmt_num(c_rr_ratio, 2)}:1" if c_rr_ratio else "—",
            ),
            (
                "Gap-fill invalidation",
                f"{pfx}{_fmt_num(c_rr_inv, 2)}" if c_rr_inv else (
                    f"{pfx}{_fmt_num(c_pre_price, 2)}" if c_pre_price else "—"
                ),
            ),
            (
                "Position tier",
                f"{c_tier_name} ({_fmt_num(c_max_size, 0)}% max)"
                if c_tier_name and c_max_size is not None
                else (c_tier_name or "—"),
            ),
        ]
        parts.append(_drilldown_metrics_html(cat_metrics))

    upside_target = rr_obj.get("upside_target")
    upside_pct = rr_obj.get("upside_pct")
    upside_reason = rr_obj.get("upside_reason", "")
    invalidation = rr_obj.get("invalidation")
    invalidation_reason = rr_obj.get("invalidation_reason", "")
    inv_pct = rr_obj.get("downside_pct")
    structural = rr_obj.get("structural_support")
    struct_pct = rr_obj.get("structural_support_pct")
    wide_stop = rr_obj.get("wide_stop_rr")
    rr_label = rr_obj.get("ratio_label", "")
    rr_quality = rr_obj.get("rr_quality", "")

    has_rr = any(v is not None for v in [upside_target, invalidation, structural, wide_stop])
    if has_rr:
        parts.append(_drilldown_section_html("Risk & Reward"))
        if upside_target is not None:
            line = f"<strong>Upside target.</strong> {pfx}{_fmt_num(upside_target, 2)}"
            if upside_pct is not None:
                line += f" (+{_fmt_num(upside_pct, 1)}%)"
            if upside_reason:
                line += f" — {_escape_dollars(upside_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        if invalidation is not None:
            line = f"<strong>Invalidation.</strong> {pfx}{_fmt_num(invalidation, 2)}"
            if inv_pct is not None:
                line += f" (-{_fmt_num(inv_pct, 1)}%)"
            if invalidation_reason:
                line += f" — {_escape_dollars(invalidation_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        rr_metrics = [
            ("Headline R:R", f"{rr_label} ({rr_quality})" if rr_label else "—"),
            ("Wide-stop R:R", f"{_fmt_num(wide_stop, 2)}:1" if wide_stop else "—"),
            (
                "Structural support",
                f"{pfx}{_fmt_num(structural, 2)} (-{_fmt_num(struct_pct, 1)}%)"
                if structural else "—",
            ),
        ]
        parts.append(_drilldown_metrics_html(rr_metrics))

    # ── ACCUMULATE Gates ──
    # The 6 mechanical gates the pipeline pre-computes for every ticker.
    # Always rendered so readers can see why a name does or doesn't qualify.
    gates = d.get("accumulate_gates") or {}
    if gates:
        gate_labels = {
            "g1_signal_eligible": "Signal eligible",
            "g2_rr_above_2": "R:R ≥ 2.0",
            "g3_rr_observed": "R:R observed",
            "g5_no_earnings_5d": "No earnings ≤7d",
            "g6_vix_ok": "VIX < 30",
            "g8_rr_robust": "R:R robust",
        }
        all_pass = gates.get("all_mechanical_pass")
        chip_html_list: list[str] = []
        for gkey, glabel in gate_labels.items():
            gate_val = gates.get(gkey)
            if gate_val is True:
                bg, fg, mark = "rgba(34,197,94,0.18)", "#22c55e", "✓"
            elif gate_val is False:
                bg, fg, mark = "rgba(239,68,68,0.18)", "#ef4444", "✗"
            else:
                bg, fg, mark = "rgba(255,255,255,0.05)", "var(--ink-3)", "—"
            chip_html_list.append(
                f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'background:{bg};color:{fg};padding:4px 9px;border-radius:3px;'
                f'font-family:var(--mono);font-size:11px;font-weight:600;'
                f'letter-spacing:0.04em;">'
                f'<span style="font-size:13px;">{mark}</span>{glabel}</span>'
            )
        summary_color = (
            "#22c55e" if all_pass is True
            else "#ef4444" if all_pass is False
            else "var(--ink-3)"
        )
        summary_text = (
            "All mechanical gates pass — Claude judgment determines ACCUMULATE"
            if all_pass is True
            else "One or more mechanical gates fail — ACCUMULATE blocked"
            if all_pass is False
            else "Gate status unknown"
        )
        parts.append(_drilldown_section_html("ACCUMULATE gates"))
        parts.append(
            '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">'
            + "".join(chip_html_list) + '</div>'
        )
        parts.append(
            f'<div class="dd-line" style="color:{summary_color};font-size:12.5px;">'
            f'{summary_text}</div>'
        )

    band = d.get("pre_earnings_band") or {}
    if band:
        days_until = band.get("days_until")
        earn_date = band.get("earnings_date") or "—"
        temporal_phrase = band.get("temporal_phrase") or ""
        n_priors = band.get("n_priors")
        avg_up = band.get("avg_up_pct")
        avg_dn = band.get("avg_down_pct")
        max_up = band.get("max_up_pct")
        max_dn = band.get("max_down_pct")
        impl_up = band.get("implied_upper")
        impl_lo = band.get("implied_lower")
        archetype = band.get("setup_archetype")
        rationale = band.get("setup_rationale") or ""
        archetype_pretty = {
            "priced_for_perfection": "Priced for perfection",
            "low_bar_underdog": "Low bar / underdog",
            "neutral": "Neutral",
        }.get(archetype, archetype or "—")
        archetype_color = {
            "priced_for_perfection": "#ef4444",
            "low_bar_underdog": "#22c55e",
            "neutral": "#9ca3af",
        }.get(archetype, "#9ca3af")
        section_label = f"Earnings setup — {temporal_phrase}" if temporal_phrase else "Earnings setup"
        parts.append(_drilldown_section_html(section_label))
        if archetype:
            parts.append(
                f'<div class="dd-line">'
                f'<strong style="color:{archetype_color};">{archetype_pretty}</strong>'
                f' — {_escape_dollars(rationale)}'
                f'</div>'
            )
        # Implied bull / bear from prior-print averages.
        if avg_up is not None and impl_up is not None:
            parts.append(
                f'<div class="dd-line">'
                f'<strong>Bull case.</strong> {pfx}{_fmt_num(impl_up, 2)} '
                f'({_sign(avg_up)}{_fmt_num(avg_up, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_dn is not None and impl_lo is not None:
            parts.append(
                f'<div class="dd-line">'
                f'<strong>Bear case.</strong> {pfx}{_fmt_num(impl_lo, 2)} '
                f'({_fmt_num(avg_dn, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_up is None and avg_dn is not None:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'All {n_priors} priors moved down — no symmetric bull-side reference.'
                f'</div>'
            )
        if avg_dn is None and avg_up is not None:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'All {n_priors} priors moved up — no symmetric bear-side reference.'
                f'</div>'
            )
        band_metrics = [
            ("Earnings date", earn_date),
            ("Days until", str(days_until) if days_until is not None else "—"),
            (
                "Avg up move",
                f"{_sign(avg_up)}{_fmt_num(avg_up, 1)}%" if avg_up is not None else "—",
            ),
            (
                "Avg down move",
                f"{_fmt_num(avg_dn, 1)}%" if avg_dn is not None else "—",
            ),
            (
                "Max up move",
                f"{_sign(max_up)}{_fmt_num(max_up, 1)}%" if max_up is not None else "—",
            ),
            (
                "Max down move",
                f"{_fmt_num(max_dn, 1)}%" if max_dn is not None else "—",
            ),
        ]
        parts.append(_drilldown_metrics_html(band_metrics))

    parts.append(_drilldown_section_html("Technicals"))
    drawdown_3mo = d.get("drawdown_3mo_pct")
    tech_metrics = [
        ("vs 50-day", f"{_sign(vs50)}{_fmt_num(vs50, 1)}%" if vs50 is not None else "—"),
        ("vs 200-day", f"{_sign(vs200)}{_fmt_num(vs200, 1)}%" if vs200 is not None else "—"),
        ("SMA50",
         f"{pfx}{_fmt_num(sma50, 2)} ({sma_status})" if sma50 else "—"),
        ("Days above SMA50", str(days_above) if days_above is not None else "—"),
        ("RSI (14d)", f"{_fmt_num(rsi, 0)} {rsi_zone}" if rsi else "—"),
        ("Volume signal",
         f"{vol_sig} ({_fmt_num(vol_ratio, 2)}x)" if vol_sig else "—"),
        ("5-day return",
         f"{_sign(chg5)}{_fmt_num(chg5, 1)}%" if chg5 is not None else "—"),
        ("1-month return",
         f"{_sign(m1)}{_fmt_num(m1, 1)}%" if m1 is not None else "—"),
        ("3mo drawdown",
         f"{_fmt_num(drawdown_3mo, 1)}%" if drawdown_3mo is not None else "—"),
    ]
    parts.append(_drilldown_metrics_html(tech_metrics))

    supports = d.get("support_zones") or []
    resistances = d.get("resistance_zones") or []
    if supports or resistances:
        parts.append(_drilldown_section_html("Key Levels"))
        if supports:
            parts.append(
                '<div class="dd-line"><strong>Support:</strong> '
                + ", ".join(f"{pfx}{_fmt_num(s, 2)}" for s in supports)
                + '</div>'
            )
        if resistances:
            parts.append(
                '<div class="dd-line"><strong>Resistance:</strong> '
                + ", ".join(f"{pfx}{_fmt_num(r, 2)}" for r in resistances)
                + '</div>'
            )

    fpe = val.get("forward_pe")
    peg = val.get("peg_ratio")
    rev_g = val.get("revenue_growth_pct")
    cluster_med_pe = val.get("cluster_median_pe")
    pe_vs_cluster = val.get("pe_vs_cluster_pct")
    fcf_y = val.get("fcf_yield_pct")
    div_y = val.get("dividend_yield_pct")
    pb = val.get("price_to_book")
    consensus = (val.get("analyst_consensus") or {})
    rec = consensus.get("recommendation", "")
    n_analysts = consensus.get("num_analysts")
    eps_g = consensus.get("earnings_growth_pct")

    val_metrics = [
        ("Cluster", CLUSTER_MAP.get(tk, "—")),
        ("Forward P/E", f"{_fmt_num(fpe, 1)}x" if fpe else "—"),
        ("Cluster median P/E",
         f"{_fmt_num(cluster_med_pe, 1)}x ({_sign(pe_vs_cluster)}{_fmt_num(pe_vs_cluster, 0)}%)"
         if cluster_med_pe else "—"),
        ("PEG", _fmt_num(peg, 2)),
        ("Revenue growth",
         f"{_sign(rev_g)}{_fmt_num(rev_g, 1)}%" if rev_g is not None else "—"),
        ("FCF yield", f"{_sign(fcf_y)}{_fmt_num(fcf_y, 2)}%" if fcf_y is not None else "—"),
        ("Dividend yield", f"{_fmt_num(div_y, 2)}%" if div_y else "—"),
        ("Price / Book", f"{_fmt_num(pb, 2)}x" if pb else "—"),
        ("Analyst consensus",
         f"{rec} ({n_analysts})" if rec and n_analysts else (rec or "—")),
        ("Est. EPS growth",
         f"{_sign(eps_g)}{_fmt_num(eps_g, 1)}%" if eps_g is not None else "—"),
    ]
    parts.append(_drilldown_section_html("Valuation"))
    parts.append(_drilldown_metrics_html(val_metrics))

    return "".join(parts)


def _render_ticker_details_html(tk: str, d: dict) -> str:
    """Build a complete <details> block: row as summary, writeup+drilldown as body."""
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

    summary = (
        '<summary>'
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
        '</summary>'
    )

    wu = _writeup_for_render(d)
    body_parts: list[str] = []
    if wu["entry_block"]:
        body_parts.append(
            f'<div class="dd-entry-block">ENTRY BLOCK · '
            f'{_escape_dollars(wu["entry_block"])}</div>'
        )
    if wu["headline"]:
        body_parts.append(
            f'<div class="dd-headline">{_escape_dollars(wu["headline"])}</div>'
        )
    delta = wu.get("prior_period_delta_narrative")
    if delta:
        body_parts.append(
            f'<div class="dd-whatdo" style="opacity:0.85;font-style:italic;">{_escape_dollars(delta)}</div>'
        )
    if wu["what_to_do"]:
        body_parts.append(
            f'<div class="dd-whatdo">{_escape_dollars(wu["what_to_do"])}</div>'
        )
    body_parts.append(_render_drilldown_detail_html(tk, d))
    body = f'<div class="tk-drilldown">{"".join(body_parts)}</div>'

    return f'<details class="tk-details">{summary}{body}</details>'


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
    ["Briefing", "Watchlist", "Signal Tracker",
     "Pipeline Stats", "Scenario Log",
     "Report Comparison", "Terminology"],
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
    trigger_map = report.get("macro_trigger_map", []) or []
    contrarians = report.get("contrarian_candidates", []) or []

    render_stance(snapshot, len(watchlist))
    render_pulse(benchmarks)
    render_changes(
        watchlist,
        prev_report.get("watchlist", {}) if prev_report else {},
    )
    render_action_card(watchlist, events)
    render_catalyst_playbook(trigger_map)
    render_contrarian_candidates(contrarians)

    macro_col, cal_col = st.columns([3, 2])
    with macro_col:
        render_macro(report.get("macro_summary", ""), geo)
    with cal_col:
        render_section_head("The Week Ahead", "Catalysts that move signals")
        render_calendar(events)

    st.markdown(
        '<div style="margin-top:28px;padding:14px 16px;border-top:1px solid var(--rule);'
        'font-family:var(--mono);font-size:11px;letter-spacing:0.18em;'
        'text-transform:uppercase;color:var(--ink-3);">'
        'Methodology &amp; formulas → see the <b style="color:var(--ink);">Terminology</b> tab'
        '</div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════
# PAGE: Watchlist (full drill-down view; covers any past report date)
# ════════════════════════════════════════════
elif page == "Watchlist":
    all_reports = load_all_reports()
    if not all_reports:
        st.error("No report files found in market_data/.")
        st.stop()
    sorted_dates = sorted(all_reports.keys(), reverse=True)
    selected_date = st.selectbox(
        "Report date", sorted_dates, index=0, key="watchlist_date"
    )
    report = all_reports[selected_date]
    watchlist = report.get("watchlist", {})
    benchmarks = report.get("benchmarks", {})

    sub_label = f"{sum(1 for tk in watchlist if tk not in RETIRED_TICKERS)} names · click any row to expand"
    if selected_date != sorted_dates[0]:
        sub_label += f" · viewing {selected_date}"
    render_section_head("The Watchlist", sub_label)
    render_pulse(benchmarks)
    render_watchlist(watchlist)


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

    scenario_colors = {
        "Base":        "#3b82f6",
        "Optimistic":  "#22c55e",
        "Pessimistic": "#ef4444",
        "Wildcard":    "#a855f7",
    }
    st_color_names = {
        "Base": "blue", "Optimistic": "green",
        "Pessimistic": "red", "Wildcard": "violet",
    }

    # ── Compact time-series (small chart) ──
    st.subheader("Probabilities Over Time")
    fig = go.Figure()
    for sc_name in sc_df["scenario"].unique():
        sc_data = sc_df[sc_df["scenario"] == sc_name].sort_values("date")
        if sc_data["probability_mid"].notna().any():
            fig.add_trace(go.Scatter(
                x=sc_data["date"], y=sc_data["probability_mid"],
                mode="lines+markers", name=sc_name,
                line=dict(color=scenario_colors.get(sc_name, "#6b7280"), width=2),
                hovertemplate=f"<b>{sc_name}</b><br>%{{x|%b %d}}: %{{customdata}}<extra></extra>",
                customdata=sc_data["probability_str"],
            ))
    fig.update_layout(
        yaxis_title="Probability %", height=240,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Days when probabilities actually moved ──
    st.subheader("Days when probabilities moved")
    st.caption(
        "By design the prompt carries forward yesterday's odds unless a named event justifies a shift — "
        "this table shows only the days where Claude actually changed at least one scenario."
    )
    move_rows = []
    for sc_name in sc_df["scenario"].unique():
        sc_data = sc_df[sc_df["scenario"] == sc_name].sort_values("date")
        prev_p, prev_d = None, None
        for _, row in sc_data.iterrows():
            p = row["probability_mid"]
            if p is None or pd.isna(p):
                continue
            if prev_p is not None and abs(p - prev_p) >= 0.5:
                move_rows.append({
                    "Date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                    "Scenario": sc_name,
                    "From": f"{prev_p:.0f}%",
                    "To": f"{p:.0f}%",
                    "Δ": f"{p - prev_p:+.0f}",
                    "New description": row.get("description") or "",
                })
            prev_p = p
            prev_d = row["date"]

    if move_rows:
        moves_df = pd.DataFrame(move_rows).sort_values("Date", ascending=False).reset_index(drop=True)
        st.dataframe(moves_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No probability shifts in the selected date range.")

    # ── Latest scenario detail (collapsed) ──
    latest_d = sc_df["date"].max()
    if pd.notna(latest_d):
        latest_data = sc_df[sc_df["date"] == latest_d]
        with st.expander(f"Latest scenarios — {pd.Timestamp(latest_d).strftime('%Y-%m-%d')}", expanded=False):
            for _, row in latest_data.iterrows():
                cn = st_color_names.get(row["scenario"], "gray")
                st.markdown(
                    f"**:{cn}[{row['scenario']}]** — {row['probability_str']}"
                )
                if row.get("description"):
                    st.caption(_escape_dollars(row["description"]))


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

    render_section_head("Cost & Tokens", "API spend and runtime per report")

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

    # ── API Cost (authoritative — read from pipeline_stats.computed_cost_usd) ──
    # Pre-2026-05-05 rows used Sonnet+Haiku rates and overstate spend by ~10x.
    # Post-cutover rows are cache-aware DeepSeek v4 Pro. We render both ranges
    # so the step-change is visible rather than silently averaging across them.
    st.subheader("API Cost")
    ps_for_cost = load_pipeline_stats()
    cost_df = ps_for_cost.dropna(subset=["computed_cost_usd"]).sort_values("date").copy()
    if cost_df.empty:
        st.info("No cost data available — pipeline_stats.computed_cost_usd is empty.")
    else:
        cost_df["cost_usd"] = cost_df["computed_cost_usd"].astype(float)
        cost_df["cumulative_cost"] = cost_df["cost_usd"].cumsum()
        cost_df["cost_7d_avg"] = cost_df["cost_usd"].rolling(7, min_periods=1).mean()

        cutover_str = "2026-05-05"
        cutover = pd.Timestamp(cutover_str)
        post = cost_df[cost_df["date"] >= cutover]
        pre = cost_df[cost_df["date"] < cutover]

        cost_cols = st.columns(4)
        cost_cols[0].metric(
            "Total (post-cutover)",
            f"${post['cost_usd'].sum():.2f}" if not post.empty else "—",
        )
        cost_cols[1].metric(
            "Avg / run (post)",
            f"${post['cost_usd'].mean():.4f}" if not post.empty else "—",
        )
        cost_cols[2].metric(
            "Latest run",
            f"${cost_df['cost_usd'].iloc[-1]:.4f}",
        )
        cost_cols[3].metric(
            "Pre-cutover total",
            f"${pre['cost_usd'].sum():.2f}" if not pre.empty else "—",
            help="Sonnet+Haiku pricing constants — overstated ~10x. Kept for history.",
        )

        st.caption(
            "Pre-2026-05-05 rows used Sonnet+Haiku rates (overstated ~10x). "
            "Post-cutover rows reflect cache-aware DeepSeek v4 Pro spend "
            "($0.27 input miss / $0.07 input hit / $1.10 output per MTok)."
        )

        fig_cost = go.Figure()
        if not pre.empty:
            fig_cost.add_trace(go.Bar(
                x=pre["date"], y=pre["cost_usd"],
                name="Pre-cutover (Sonnet+Haiku)",
                marker_color="#6b7280", opacity=0.5,
            ))
        if not post.empty:
            fig_cost.add_trace(go.Bar(
                x=post["date"], y=post["cost_usd"],
                name="Post-cutover (DeepSeek)",
                marker_color="#3b82f6", opacity=0.85,
            ))
        fig_cost.add_trace(go.Scatter(
            x=cost_df["date"], y=cost_df["cost_7d_avg"],
            mode="lines", name="7d avg",
            line=dict(color="#f59e0b", width=2),
        ))
        # Plotly's add_vline annotation midpoint does sum(X)/len(X) which
        # blows up on pd.Timestamp; pass the date as a millisecond epoch
        # so the math works. The visual is identical.
        cutover_ms = int(cutover.timestamp() * 1000)
        fig_cost.add_vline(
            x=cutover_ms, line=dict(color="#ef4444", dash="dash", width=1),
            annotation_text="DeepSeek cutover",
            annotation_position="top right",
        )
        fig_cost.update_layout(
            yaxis_title="Cost (USD)", height=260,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
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

    # ── Prompt Cache Telemetry ──
    st.subheader("Prompt Cache")
    cache_df = ps_for_cost.copy()
    has_cache_data = (
        "cache_hit_tokens" in cache_df.columns
        and "cache_miss_tokens" in cache_df.columns
        and ((cache_df["cache_hit_tokens"].fillna(0)
              + cache_df["cache_miss_tokens"].fillna(0)) > 0).any()
    )
    if not has_cache_data:
        st.info(
            "Cache telemetry will appear after the next pipeline run. "
            "DeepSeek's automatic prefix cache is read from `response.usage` "
            "and stored in `pipeline_stats.cache_hit_tokens` / `cache_miss_tokens`."
        )
    else:
        cdf = cache_df.dropna(
            subset=["cache_hit_tokens", "cache_miss_tokens"], how="all"
        ).copy()
        cdf["cache_hit_tokens"] = cdf["cache_hit_tokens"].fillna(0)
        cdf["cache_miss_tokens"] = cdf["cache_miss_tokens"].fillna(0)
        cdf["total_input"] = cdf["cache_hit_tokens"] + cdf["cache_miss_tokens"]
        cdf = cdf[cdf["total_input"] > 0].sort_values("date")
        cdf["hit_ratio"] = cdf["cache_hit_tokens"] / cdf["total_input"]
        # Savings: hit tokens cost $0.07/MTok instead of $0.27/MTok — $0.20/MTok saved.
        cdf["savings_usd"] = cdf["cache_hit_tokens"] * (0.27 - 0.07) / 1_000_000

        latest = cdf.iloc[-1]
        avg_ratio = cdf["hit_ratio"].mean()
        total_savings = cdf["savings_usd"].sum()

        cc_cols = st.columns(4)
        cc_cols[0].metric("Latest hit ratio", f"{latest['hit_ratio']:.1%}")
        cc_cols[1].metric("Avg hit ratio", f"{avg_ratio:.1%}")
        cc_cols[2].metric(
            "Latest hit tokens",
            f"{int(latest['cache_hit_tokens']):,}",
            help="Cached input tokens billed at $0.07/MTok instead of $0.27/MTok.",
        )
        cc_cols[3].metric(
            "Cumulative savings",
            f"${total_savings:.4f}",
            help="Versus billing all input as cache miss ($0.27/MTok).",
        )

        fig_cache = go.Figure()
        fig_cache.add_trace(go.Bar(
            x=cdf["date"], y=cdf["cache_hit_tokens"],
            name="Cache hit", marker_color="#22c55e",
        ))
        fig_cache.add_trace(go.Bar(
            x=cdf["date"], y=cdf["cache_miss_tokens"],
            name="Cache miss", marker_color="#ef4444",
        ))
        fig_cache.update_layout(
            barmode="stack",
            yaxis_title="Input tokens",
            height=240,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_cache, use_container_width=True)

        st.caption(
            "If hit ratio sits near 0%, the user prompt's first dynamic block "
            "is breaking the prefix immediately — reorder static blocks "
            "(catalysts JSON, portfolio_count_directive, field-contracts, "
            "crisis_block) above the data_json block to extend the cacheable "
            "prefix. Savings figures assume a flat $0.20/MTok delta."
        )

    render_section_head("Pipeline Volume", "Articles ingested and prompt size")

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

    render_section_head("Multi-Day Trend", "How posture and signals shifted across a window")
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

    render_section_head("Pairwise Comparison", "Side-by-side diff between any two dates")
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
                "Rationale": _legacy_rationale_from(wl_b.get(tk, {}))[:150],
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


# ════════════════════════════════════════════
# PAGE 7: Terminology — methodology & formulas reference
# ════════════════════════════════════════════
elif page == "Terminology":
    render_section_head(
        "Terminology & Methodology",
        "How every number on this site is computed",
    )

    st.markdown(
        '<div style="font-family:var(--sans);color:var(--ink-2);'
        'font-size:0.95rem;line-height:1.6;max-width:78ch;margin:8px 0 28px;">'
        "This page documents the formulas behind every signal, score, and chart on the site. "
        "It is intended for readers who want to audit the method rather than take the output on faith. "
        "Definitions are stated in plain language first, then with the precise rule the pipeline uses."
        "</div>",
        unsafe_allow_html=True,
    )

    # ---- The Six Signals ----
    render_section_head("The Six Signals", "What each label means and when it fires")
    st.markdown("""
<style>
.term-table { width:100%; border-collapse:collapse; font-family:var(--sans);
  font-size:0.92rem; margin: 6px 0 22px; }
.term-table th, .term-table td {
  text-align:left; vertical-align:top; padding:10px 12px;
  border-bottom:1px solid var(--rule); color:var(--ink-2);
}
.term-table th {
  font-family:var(--mono); font-weight:600; font-size:11px;
  letter-spacing:0.16em; text-transform:uppercase; color:var(--ink-3);
  border-bottom:1px solid var(--rule-strong);
}
.term-table td b { color: var(--ink); font-weight:600; }
.term-pill {
  font-family:var(--mono); font-weight:700; font-size:10px;
  letter-spacing:0.14em; text-transform:uppercase;
  padding:3px 8px; border-radius:3px; display:inline-block;
}
.term-formula {
  font-family:var(--mono); font-size:0.88rem; color:var(--ink);
  background:var(--paper-3); border-left:2px solid var(--rule-strong);
  padding:10px 14px; margin:10px 0 18px; white-space:pre-wrap;
  border-radius:0 3px 3px 0;
}
.term-prose {
  font-family:var(--sans); color:var(--ink-2); font-size:0.94rem;
  line-height:1.65; max-width:78ch; margin:6px 0 14px;
}
.term-prose b { color: var(--ink); }
.term-bullets { font-family:var(--sans); color:var(--ink-2);
  font-size:0.92rem; line-height:1.7; max-width:78ch;
  margin: 4px 0 18px; padding-left: 18px; }
.term-bullets li { margin-bottom: 4px; }
.term-bullets b { color: var(--ink); }
</style>
<table class="term-table">
<thead><tr><th>Signal</th><th>Meaning</th><th>Trigger</th></tr></thead>
<tbody>
<tr>
  <td><span class="term-pill" style="background:rgba(34,197,94,0.16);color:#22c55e;">● BUY</span></td>
  <td><b>Enter now.</b> Multiple independent thesis legs, clean technicals near SMA50, RSI neutral, volume confirmed, R:R favourable.</td>
  <td>All 8 mechanical gates pass <i>and</i> the fragility gate is satisfied (≥2 independent support legs, or a single catalyst with multi-day durability).</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(52,152,219,0.18);color:#3498db;">● ACCUMULATE</span></td>
  <td><b>Starter position.</b> Mechanically eligible to enter, but not all technical conditions are perfect — start small.</td>
  <td>All 8 mechanical gates pass and R:R is favourable, but the fragility gate is not satisfied (single-leg thesis, or technicals slightly short of BUY-grade).</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(245,158,11,0.18);color:#f59e0b;">● WATCH</span></td>
  <td><b>Wait for trigger.</b> Thesis intact, but entry conditions are not present today.</td>
  <td>One or more mechanical gates fail (e.g. extended above SMA50, RSI overbought, R:R below 1.0). The watch trigger is the named missing condition.</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(160,160,160,0.14);color:#9ca3af;">● HOLD</span></td>
  <td><b>Wait days.</b> Nothing wrong, nothing interesting. No clear catalyst, mixed technicals, or poor R:R.</td>
  <td>Default state for a tracked name with no actionable read. Clears when the next setup or catalyst arrives.</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(239,68,68,0.16);color:#ef4444;">● CAUTION</span></td>
  <td><b>Wait weeks (price wrong).</b> Mechanical block — extended price, broken support, or extreme valuation. Story may still be intact.</td>
  <td>A mechanical hard block fires (e.g. >5% above SMA50 with RSI &gt; 70, or invalidation level breached). Clears when price resets.</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(185,28,28,0.20);color:#ef4444;">● AVOID</span></td>
  <td><b>Wait quarters (story broken).</b> A specific, sourced thesis leg has broken — not a price move, a fundamental change.</td>
  <td>Sourced caution: a named thesis leg (catalyst, moat, demand pull) has been invalidated by an external development. Clears only when the broken leg repairs.</td>
</tr>
</tbody>
</table>
<div class="term-prose">
<b>Three-tier wait gradient.</b> HOLD, CAUTION, and AVOID all mean "no entry today,"
but they sit on a timeline. HOLD clears in days (a setup may form anytime).
CAUTION needs <i>price</i> to reset — typically weeks. AVOID needs the broken thesis
leg to <i>repair</i> — quarters or longer. The site's calibration tables score them differently:
CAUTION is judged by whether you avoided a drawdown; AVOID is judged by whether
you stayed off the consideration set entirely.
</div>
<div class="term-prose">
<b>Signals are states, not a ladder.</b> A name can move from BUY to CAUTION in a single
session if news invalidates the thesis. There is no requirement that signals step one
rung at a time.
</div>
""", unsafe_allow_html=True)

    # ---- Risk : Reward ----
    render_section_head("Risk : Reward (R:R)", "The single most-cited number on this site")
    st.markdown("""
<div class="term-prose">
R:R compares <b>upside to the nearest resistance</b> against <b>downside to the
invalidation/stop level</b>. An R:R of 2.4 means the position offers 2.4 units of
potential reward for every 1 unit at risk. It is a <i>shape</i> measure, not a
probability — a 5:1 R:R that fails 90% of the time is worse than a 1.5:1 that
works 70% of the time.
</div>
<div class="term-formula">headline_rr  =  (nearest_resistance − entry) / (entry − invalidation)
wide_stop_rr =  (nearest_resistance − entry) / (entry − structural_support)</div>
<ul class="term-bullets">
<li><b>entry</b> — current close, or the named trigger price for WATCH setups.</li>
<li><b>nearest_resistance</b> — the closest overhead supply zone identified from price action (prior swing high, congestion zone, round-number magnet). <i>Not</i> a distant best-case target.</li>
<li><b>invalidation</b> — the price at which the thesis is mechanically wrong. Typically a recent swing low or the SMA50, whichever the writeup cites.</li>
<li><b>structural_support</b> — a deeper, more durable level (200-day SMA, prior breakout base, decade-long trendline). Used to compute the wide-stop variant when the trader wants to give the position more room.</li>
</ul>
<div class="term-prose">
<b>Why two R:R numbers?</b> The headline R:R uses the tightest defensible stop —
it tells you the math at a quick-exit risk profile. The wide-stop R:R uses
deeper support — it tells you the math if you are willing to sit through more
volatility. Headline is the default cited on the Briefing; both are shown in
the Watchlist drill-down.
</div>
<div class="term-prose">
<b>Quality bands</b> — bands are advisory, not absolute. Below 1.0 means you
are risking more than you stand to gain at the nearest target; above 2.0 means
the geometry favours the trade.
</div>
<table class="term-table">
<thead><tr><th>Band</th><th>Reading</th></tr></thead>
<tbody>
<tr><td><b>R:R ≥ 2.0</b></td><td>Favourable. Geometry alone supports the entry.</td></tr>
<tr><td><b>1.0 ≤ R:R &lt; 2.0</b></td><td>Mixed. Need a thesis or technical edge to compensate.</td></tr>
<tr><td><b>R:R &lt; 1.0</b></td><td>Unfavourable. Risk exceeds the nearest reward — generally a WATCH or HOLD.</td></tr>
</tbody>
</table>
<div class="term-prose">
<b>Caveat — distant-target inflation.</b> When a ticker is below its SMA50 with
no nearby resistance, the "nearest_resistance" can be the SMA50 itself many
percent away, producing a flattering R:R. The realistic upside in that case is
the SMA50 reclaim — not a continuation through it. Read R:R alongside the
ticker's vs-SMA50 reading.
</div>
""", unsafe_allow_html=True)

    # ---- Technicals ----
    render_section_head("Technical Indicators", "Bucket cutoffs and what they imply")
    st.markdown("""
<table class="term-table">
<thead><tr><th>Metric</th><th>Definition</th><th>Bands</th></tr></thead>
<tbody>
<tr>
  <td><b>RSI (14-day)</b></td>
  <td>Relative Strength Index. Smoothed ratio of average gains to average losses over the last 14 sessions, scaled 0–100. Measures whether recent buying or selling pressure has been one-sided.</td>
  <td>&lt;40 oversold · 40–70 neutral · &gt;70 overbought</td>
</tr>
<tr>
  <td><b>vs SMA50</b></td>
  <td>Percent distance from the 50-day simple moving average — the medium-term trend line. Used as the primary entry-quality gate: closer is cleaner.</td>
  <td>±2% clean entry · 2–5% above extended · &gt;5% above blocked</td>
</tr>
<tr>
  <td><b>vs SMA200</b></td>
  <td>Percent distance from the 200-day SMA — the long-term trend line. Used to classify regime: above SMA200 = bull, below = bear.</td>
  <td>&gt;0% bull regime · &lt;0% bear regime</td>
</tr>
<tr>
  <td><b>SMA50 status</b></td>
  <td><b>rising</b> if the SMA50 is above its value 5 sessions ago by &gt;0.3%; <b>declining</b> if below by &gt;0.3%; otherwise <b>flat</b>. Paired with "days above" — the count of consecutive sessions price closed above the SMA50.</td>
  <td>rising / flat / declining</td>
</tr>
<tr>
  <td><b>Volume signal</b></td>
  <td>Today's volume divided by the 20-day average volume. Confirmation: a breakout on &gt;1.5× volume is more durable than one on &lt;1.0×.</td>
  <td>&gt;1.5× confirmed · 1.0–1.5× normal · &lt;1.0× weak</td>
</tr>
</tbody>
</table>
""", unsafe_allow_html=True)

    # ---- Valuation ----
    render_section_head("Valuation Metrics", "How fundamentals are read into the signal")
    st.markdown("""
<table class="term-table">
<thead><tr><th>Metric</th><th>Definition &amp; use</th></tr></thead>
<tbody>
<tr>
  <td><b>Forward P/E</b></td>
  <td>Price divided by analyst-consensus next-12-month earnings per share. The site shows the ticker's value alongside its <i>cluster median</i> (e.g. Semis, BigTech, SG Banks) and the percent premium/discount. Premium &gt; 30% with weakening growth is a CAUTION trigger.</td>
</tr>
<tr>
  <td><b>Cluster median</b></td>
  <td>Median forward P/E across the ticker's cluster peers (see CLUSTER_MAP — e.g. NVDA's cluster is Semis: AMD, INTC, MU, TSM, AVGO, ASML). Smoothes single-name distortions.</td>
</tr>
<tr>
  <td><b>PEG</b></td>
  <td>Forward P/E divided by expected EPS growth (%). Below 1.0 = growth-adjusted cheap; above 2.0 = expensive even after growth.</td>
</tr>
<tr>
  <td><b>FCF yield</b></td>
  <td>Trailing free cash flow divided by market cap. The cash-on-cash return if the business stopped reinvesting. Above 5% is generous for a growth name; below 1% is priced for perfection.</td>
</tr>
<tr>
  <td><b>P/B</b></td>
  <td>Price divided by book value per share. Primarily relevant for SG Banks and capital-heavy businesses.</td>
</tr>
<tr>
  <td><b>Revenue growth</b></td>
  <td>Most recent reported quarter's revenue vs the same quarter prior year (year-over-year).</td>
</tr>
<tr>
  <td><b>EPS growth estimate</b></td>
  <td>Analyst consensus next-fiscal-year EPS growth. Pairs with PEG.</td>
</tr>
<tr>
  <td><b>Dividend yield</b></td>
  <td>Trailing 12-month dividends divided by current price.</td>
</tr>
</tbody>
</table>
""", unsafe_allow_html=True)

    # ---- Earnings Setup (Band + Archetype) ----
    render_section_head("Earnings Setup", "Band and archetype framing for upcoming prints")
    st.markdown("""
<div class="term-prose">
Earnings reactions are <b>not binary events</b>. The market reacts to the gap
between actuals + guidance and the bar already set by valuation, positioning,
and recent price. The dashboard exposes this in two layers: (1) an implied
<b>price band</b> from the ticker's own past earnings reactions, and (2) a
mechanical <b>setup archetype</b> that names what kind of bar the print is
clearing.
</div>
<table class="term-table">
<thead><tr><th>Archetype</th><th>Trigger</th><th>What "good news" must look like</th></tr></thead>
<tbody>
<tr>
  <td><span class="term-pill" style="background:rgba(239,68,68,0.18);color:#ef4444;">Priced for perfection</span></td>
  <td><b>vs_sma50 &gt; +15% AND RSI ≥ 70</b> — extended <i>and</i> overbought.</td>
  <td>A beat alone may not satisfy the bar — guidance must accelerate (raised guide, new contract tier, margin expansion). A "merely good" print is the most likely path to a sell-the-news pullback.</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(34,197,94,0.18);color:#22c55e;">Low bar / underdog</span></td>
  <td><b>drawdown_3mo ≤ -15%</b> — beaten down off the 3-month peak.</td>
  <td>"Less bad" results — in-line guidance, stable margins, even a small miss with a constructive forward — can spark a relief rally. Sentiment is washed out.</td>
</tr>
<tr>
  <td><span class="term-pill" style="background:rgba(160,160,160,0.14);color:#9ca3af;">Neutral</span></td>
  <td>Neither extreme.</td>
  <td>Standard expectations game. Reaction depends on the magnitude of the surprise and the guidance delta. The bar is neither stretched nor depressed.</td>
</tr>
</tbody>
</table>
<div class="term-prose">
The <b>AND</b> in priced-for-perfection is deliberate. A stock can be +15%
above its SMA50 from a single gap-up weeks ago (not parabolic) or have RSI
above 70 from a slow grind (not extended). The intersection isolates names
that are <i>both</i> stretched and momentum-crowded — the setup where a
beat tends not to clear the bar. Forward P/E was deliberately dropped from
the rule because yfinance's coverage is patchy across the watchlist; a rule
that fires on only some tickers is worse than none.
</div>
<div class="term-prose">
The implied <b>price band</b> sits alongside the archetype:
</div>
<div class="term-formula">For each of the last N earnings dates:
  next_day_return = (close_t+1 − close_t) / close_t

avg_up_pct   = mean of positive next_day_returns
avg_down_pct = mean of negative next_day_returns  (absolute value)
max_up_pct   = max positive return
max_down_pct = max negative return  (absolute value)

implied_upper = current_price × (1 + avg_up_pct)
implied_lower = current_price × (1 − avg_down_pct)</div>
<ul class="term-bullets">
<li><b>N priors</b> — number of earnings reports used (typically 4–8). Shown in the drill-down so the reader can judge sample size.</li>
<li><b>Asymmetric priors</b> — if all past reactions were one direction, the opposite-side average is null. The dashboard handles this by showing only the populated side.</li>
<li><b>Max bands</b> — shown alongside the average bands as a worst-case reference, not a base case.</li>
<li><b>Days until</b> — calendar days from today to the earnings date. Bands are most informative within ~10 days of the event.</li>
</ul>
<div class="term-prose">
<b>What this is not.</b> Not an options-implied move, not a directional forecast.
It is the empirical distribution of the ticker's own past earnings-day moves,
projected onto today's price. Use it to size risk, not to pick a side.
</div>
<div class="term-prose">
<b>Why "binary event" is banned.</b> The pipeline's writeup prompt forbids
the phrases "binary event," "coin flip," "binary catalyst," and "either way"
when a ticker has a pre-earnings band. Earnings reactions are price-vs-bar,
not 50/50 gambles — the archetype names which bar matters and the band
quantifies the typical move size. If you see a writeup still using
"binary" framing on a tagged ticker, that's a validator miss worth flagging.
</div>
""", unsafe_allow_html=True)

    # ---- Signal Episodes & Verdicts ----
    render_section_head("Signal Episodes & Verdicts", "How the calibration table is built")
    st.markdown("""
<div class="term-prose">
The Signal Tracker's outcome history collapses consecutive same-signal rows
per ticker into <b>episodes</b>. Each episode has an entry price, an exit price,
a return, and a verdict. The exit rule is the load-bearing detail: signal
episodes are scored on <b>trade economics</b>, not on signal-window boundaries.
</div>
<div class="term-formula">BUY / ACCUMULATE episode:
  entry  = price on the first BUY/ACCUMULATE day
  exit   = price on the next CAUTION or AVOID day for that ticker
           (HOLD and WATCH do NOT close the episode)
  if no CAUTION/AVOID yet → episode is active, exit = latest close

CAUTION / AVOID episode:
  entry  = price on the first CAUTION/AVOID day
  exit   = price on the next BUY/ACCUMULATE for that ticker
  if no BUY/ACCUMULATE yet → active, exit = latest close

WATCH / HOLD episode:
  non-actionable. exit = last-day price.

return_pct       = (exit − entry) / entry
run_during_pct   = (peak intra-episode price − entry) / entry</div>
<div class="term-prose">
The exit rule reflects how the signals are meant to be traded:
"<i>when an ACCUMULATE/BUY changes to another, it doesn't mean I should
immediately sell — it just means it's no longer suitable to enter.</i>"
A 1-day ACCUMULATE flipping to HOLD does not return 0%; it stays open
until a CAUTION or AVOID closes it.
</div>
<table class="term-table">
<thead><tr><th>Verdict</th><th>Rule</th></tr></thead>
<tbody>
<tr><td><b>✓ profit</b> (BUY/ACCUMULATE)</td><td>return_pct &gt; 0 at exit.</td></tr>
<tr><td><b>✗ loss</b> (BUY/ACCUMULATE)</td><td>return_pct ≤ 0 at exit.</td></tr>
<tr><td><b>✓ avoided</b> (CAUTION)</td><td>return_pct &lt; 0 — staying out spared a drawdown.</td></tr>
<tr><td><b>✗ wrong</b> (CAUTION)</td><td>return_pct ≥ 0 — the name kept working without you.</td></tr>
<tr><td><b>✓ avoided</b> (AVOID)</td><td>return_pct &lt; 0 — story-broken read paid off.</td></tr>
<tr><td><b>✗ wrong</b> (AVOID)</td><td>return_pct ≥ 0 (stricter threshold than CAUTION — AVOID intends "off the consideration set entirely").</td></tr>
<tr><td><b>⚠ missed</b> (WATCH)</td><td>run_during_pct ≥ 5% — there was a real move and the trigger never fired.</td></tr>
<tr><td><b>— quiet</b> (WATCH)</td><td>run_during_pct &lt; 5% — nothing meaningful happened.</td></tr>
<tr><td><b>— non-directional</b> (HOLD)</td><td>HOLD is never scored. It is the absence of a call.</td></tr>
<tr><td><b>⏳ active</b> (any)</td><td>Episode has not yet closed. Verdict prefix; current return shown but not final.</td></tr>
</tbody>
</table>
<div class="term-prose">
<b>Default filter.</b> The outcome history shows only actionable episodes
(BUY / ACCUMULATE / CAUTION / AVOID, plus triggered WATCH). HOLD and
quiet WATCH are toggled off by default.
</div>
<div class="term-prose">
<b>Paper Trade Outcomes — post-cutover only.</b> The pipeline's
signal_evaluation_log only stabilised on <b>2026-04-19</b> (when the
catalyst-entry path landed). The table filters to that cutover by default;
read pre-cutover rows as exploratory. Until ~3 months of post-cutover data
accumulates, the metrics should be read as directional, not statistical.
</div>
""", unsafe_allow_html=True)

    # ---- Aggregate Calibration ----
    render_section_head("Aggregate Calibration", "Cross-watchlist hit rates")
    st.markdown("""
<div class="term-prose">
The aggregate calibration table reports, per signal type, the share of
closed episodes that hit "✓" verdicts. It is a measure of <i>directional
accuracy</i>, not P&amp;L.
</div>
<div class="term-formula">win_rate(signal) = count(✓ episodes for signal) / count(closed episodes for signal)
avg_return(signal) = mean(return_pct over closed episodes for signal)
avg_run(signal)    = mean(run_during_pct over closed episodes for signal)</div>
<ul class="term-bullets">
<li><b>Closed-only.</b> Active episodes are excluded from win-rate denominators — their verdict is not yet known.</li>
<li><b>Per-signal, not per-day.</b> A 30-day BUY counts once, not 30 times. This avoids inflating the denominator with persistent calls.</li>
<li><b>HOLD is never counted.</b> HOLD is non-directional — including it would dilute every metric toward 50/50.</li>
</ul>
""", unsafe_allow_html=True)

    # ---- Macro Scenarios ----
    render_section_head("Macro Scenarios & Odds", "What the probability bar represents")
    st.markdown("""
<div class="term-prose">
The macro section assigns probabilities to a small set of named scenarios
(typically 3–4: e.g. <i>Soft landing</i>, <i>Stagflation</i>, <i>Hard
landing</i>, <i>Reacceleration</i>). The probabilities are a subjective
read of available evidence, <b>not</b> a market-implied or model-derived
distribution.
</div>
<ul class="term-bullets">
<li><b>Sum to 100%.</b> The set is exhaustive and mutually exclusive on any given day.</li>
<li><b>"Days when probabilities moved"</b> — the Scenario Log filters out flat-line days where the prior day's odds were carried forward unchanged. Only days with a delta in any scenario appear in that table.</li>
<li><b>Carry-forward is the default.</b> Most days the macro picture does not change; the pipeline carries yesterday's odds rather than re-fitting noise.</li>
</ul>
""", unsafe_allow_html=True)

    # ---- Entry Block & Catalyst Path ----
    render_section_head("Entry Block & Catalyst Path", "When mechanical rules are softened")
    st.markdown("""
<div class="term-prose">
<b>Entry block</b> is an advisory flag the writeup may set when a name's
mechanicals (price, RSI) make entry imprudent <i>even though the signal
is BUY or ACCUMULATE</i>. It is the writeup's judgment, not a hard gate —
the raw signal remains pure technicals; entry_block is the contextual
caveat layered on top.
</div>
<div class="term-prose">
<b>Catalyst entry path.</b> A specific exception to the &gt;5%-above-SMA50
extension block: when a verified catalyst (named, sourced, with a known
trigger date) is in play and the trend is durable, the pipeline allows
entry despite extension. This path is paper-trade-only until at least
two months and five completed entries have accumulated to validate the
loosening. Episodes opened via this path are tagged in the Paper Trade
Outcomes table.
</div>
""", unsafe_allow_html=True)

    # ---- Pulse Strip ----
    render_section_head("Pulse Strip", "How the 8 benchmarks are formatted")
    st.markdown("""
<div class="term-prose">
The pulse strip on the Briefing and Watchlist pages shows 8 benchmarks:
<b>SPY · QQQ · VIX · WTI · Gold · DXY · US10Y · SOXX</b>. Each cell shows
the latest level and the day's percent change. Color is computed from
the change sign — except <b>VIX</b>, which is inverted (VIX up = red,
VIX down = green) since rising volatility is the risk-off direction.
</div>
<ul class="term-bullets">
<li><b>4-digit prices</b> (e.g. SPY at 5,800) are shown with 0 decimals for readability.</li>
<li><b>Sub-1000 prices</b> are shown with 2 decimals.</li>
<li><b>VIX</b> is the CBOE Volatility Index — 30-day implied vol on S&amp;P 500 options.</li>
<li><b>WTI</b> is West Texas Intermediate front-month crude in USD/bbl.</li>
<li><b>DXY</b> is the U.S. Dollar Index against a basket of major currencies.</li>
<li><b>US10Y</b> is the 10-year U.S. Treasury yield, in percent.</li>
</ul>
""", unsafe_allow_html=True)

    # ---- Limitations ----
    render_section_head("Limitations", "What this site does not do")
    st.markdown("""
<ul class="term-bullets">
<li><b>Not personalized advice.</b> Signals are computed on a fixed watchlist and assume no view of the reader's existing positions, risk tolerance, or tax situation.</li>
<li><b>Not a backtest.</b> The calibration tables are forward-only — they evaluate signals as they were issued in real time, with no look-ahead. Sample sizes are small until ~3 months of post-cutover data accrue.</li>
<li><b>Not high-frequency.</b> Reports are produced once per session (pre-open SGT). Intraday moves are not reflected until the next run.</li>
<li><b>R:R is geometry, not probability.</b> A high R:R does not mean a trade is likely to work — it means the math is favourable <i>if</i> it does.</li>
<li><b>Macro odds are subjective.</b> The scenario probabilities are a structured read of evidence, not a market-implied distribution.</li>
</ul>
""", unsafe_allow_html=True)
