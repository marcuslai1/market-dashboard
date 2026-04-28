"""MarketReport — Editorial dashboard (Streamlit port of the HTML redesign).

Run with: streamlit run dashboard_editorial.py

Drop this alongside your existing dashboard.py. It reuses the same
data/morning_report_*.json files. Once you're happy, rename to
dashboard.py and retire the old file.

Design principles ported from the HTML version:
  - Paper-toned background (#F6F2E9), ink #1A1A1A
  - Newsreader serif headlines · Inter Tight UI · JetBrains Mono numbers
  - Signal palette in oklch (shared chroma 0.13)
  - Editorial layout: masthead → stance hero → pulse strip → action card →
    watchlist (with expandable drill-downs) → macro → calendar
  - Writeups gated by signal: BUY/ACCUMULATE/WATCH/CAUTION show full
    rationale; HOLD shows only a one-line "no action" caption
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

# ─────────────────────────────── Config ────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
RETIRED_TICKERS = {"C6L_SI", "Z74_SI", "XLE", "VUAA_L", "COHR"}

st.set_page_config(
    page_title="The MarketReport — Morning Briefing",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Signal palette — converted from oklch (shared chroma 0.13, lightness ~0.55)
SIGNAL_COLORS = {
    "BUY":        "#4F8C46",
    "ACCUMULATE": "#4A6FB0",
    "WATCH":      "#C99A2E",
    "HOLD":       "#8A847A",
    "CAUTION":    "#C45643",
}
SIGNAL_TINTS = {
    "BUY":        "rgba(79,140,70,0.10)",
    "ACCUMULATE": "rgba(74,111,176,0.10)",
    "WATCH":      "rgba(201,154,46,0.14)",
    "HOLD":       "rgba(138,132,122,0.10)",
    "CAUTION":    "rgba(196,86,67,0.10)",
}
SIGNAL_VERB = {
    "BUY": "Enter now", "ACCUMULATE": "Add on strength",
    "WATCH": "Wait for trigger", "HOLD": "Maintain",
    "CAUTION": "Trim / avoid",
}
WRITEUP_SIGNALS = {"BUY", "ACCUMULATE", "WATCH", "CAUTION"}

# ──────────────────────────── Editorial CSS ────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;500;600&family=Inter+Tight:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --paper: #F6F2E9; --paper-2: #EFEADD; --paper-3: #E6DFCE;
  --ink: #1A1A1A; --ink-2: #4A463E; --ink-3: #7A736A; --ink-4: #A8A097;
  --rule: rgba(26,26,26,0.08); --rule-strong: rgba(26,26,26,0.20);
  --serif: 'Newsreader', Georgia, serif;
  --sans:  'Inter Tight', -apple-system, sans-serif;
  --mono:  'JetBrains Mono', ui-monospace, monospace;
}

.stApp { background: var(--paper); color: var(--ink); font-family: var(--sans); }
.main .block-container { max-width: 1280px; padding-top: 24px; padding-bottom: 80px; }
[data-testid="stSidebar"] { background: var(--paper-2); border-right: 1px solid var(--rule-strong); }

/* Typography */
h1, h2, h3 { font-family: var(--serif) !important; font-weight: 500 !important;
             letter-spacing: -0.01em !important; color: var(--ink) !important;
             text-transform: none !important; }
h1 { font-size: 2.6rem !important; }
h2 { font-size: 1.6rem !important; }
h3 { font-size: 1.2rem !important; }
p, li, span, div { font-family: var(--sans); }

/* Hide default Streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

/* Metrics — paper-card treatment */
[data-testid="stMetric"] {
  background: var(--paper-2);
  border: 1px solid var(--rule-strong);
  border-radius: 0;
  padding: 12px 14px;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important;
  font-size: 10px !important;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-3) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--serif) !important;
  font-size: 1.6rem !important;
  font-weight: 500 !important;
  color: var(--ink) !important;
}
[data-testid="stMetricDelta"] { font-family: var(--mono) !important; font-size: 11px !important; }

/* Buttons / inputs — paper neutral */
.stButton > button {
  background: var(--paper-2); color: var(--ink);
  border: 1px solid var(--rule-strong); border-radius: 0;
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.06em;
  text-transform: uppercase; font-weight: 500;
}
.stButton > button:hover { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.stSelectbox [data-baseweb="select"] {
  background: var(--paper-2); border-color: var(--rule-strong); border-radius: 0;
}
.stRadio label { font-family: var(--mono) !important; font-size: 11px !important;
                 text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-2) !important; }

/* Expanders */
[data-testid="stExpander"] {
  background: var(--paper-2); border: 1px solid var(--rule);
  border-radius: 0; margin-bottom: 6px;
}
[data-testid="stExpander"] summary { font-family: var(--mono) !important;
  font-size: 12px !important; letter-spacing: 0.04em; }

/* Dividers */
hr { border-color: var(--rule) !important; margin: 18px 0 !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1.5px solid var(--ink); }
.stTabs [data-baseweb="tab"] {
  font-family: var(--mono) !important; font-size: 11px !important;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3) !important; padding: 6px 0;
}
.stTabs [aria-selected="true"] {
  color: var(--ink) !important; font-weight: 600;
  border-bottom: 1.5px solid var(--ink) !important;
}

/* DataFrame */
[data-testid="stDataFrame"] {
  border: 1px solid var(--rule-strong); border-radius: 0;
}

/* Captions */
.stCaption, [data-testid="stCaptionContainer"] {
  font-family: var(--mono) !important; font-size: 11px !important;
  color: var(--ink-3) !important; letter-spacing: 0.04em;
}

/* ── Custom editorial blocks (rendered via st.markdown) ── */
.masthead {
  display: grid; grid-template-columns: 1fr auto;
  align-items: end; border-bottom: 1.5px solid var(--ink);
  padding-bottom: 14px; margin-bottom: 4px;
}
.masthead .kicker {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-3);
}
.masthead .title {
  font-family: var(--serif); font-weight: 600;
  font-size: 3rem; line-height: 0.95; letter-spacing: -0.02em;
  margin: 4px 0 0;
}
.masthead .title em { font-style: italic; font-weight: 500; color: var(--ink-2); }
.masthead .right { text-align: right; font-family: var(--mono);
  font-size: 11px; color: var(--ink-3); line-height: 1.55; }
.masthead .right .date {
  font-family: var(--serif); font-size: 16px;
  color: var(--ink); font-weight: 500;
}
.masthead-strip {
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-3);
  padding: 8px 0 18px; border-bottom: 1px solid var(--rule);
}

.stance-deck {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.2em; text-transform: uppercase;
  margin: 22px 0 10px; display: flex; align-items: center; gap: 8px;
}
.stance-deck .dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.stance-headline {
  font-family: var(--serif); font-weight: 500;
  font-size: 2rem; line-height: 1.15; letter-spacing: -0.01em;
  margin: 0 0 12px; color: var(--ink);
}
.stance-byline {
  font-family: var(--mono); font-size: 11px;
  color: var(--ink-3); letter-spacing: 0.06em;
}

.count-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px;
  background: var(--rule-strong);
  border: 1px solid var(--rule-strong);
}
.count-cell {
  background: var(--paper); padding: 14px 10px; text-align: center;
}
.count-cell .clabel {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);
  margin-bottom: 4px;
}
.count-cell .cnum { font-family: var(--serif); font-size: 2rem;
  font-weight: 500; line-height: 1; }
.count-cell.zero .cnum { color: var(--ink-4); }
.count-cell .cdot {
  width: 7px; height: 7px; border-radius: 50%;
  display: inline-block; margin-right: 4px; vertical-align: 1.5px;
}

.section-head {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1px solid var(--rule); padding-bottom: 10px;
  margin: 32px 0 16px;
}
.section-head h2 { margin: 0; font-size: 1.5rem !important; }
.section-head .sub {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3);
}

.action-card {
  background: var(--paper-2); border: 1px solid var(--rule-strong);
  padding: 22px 26px; margin: 8px 0 16px;
  display: grid; grid-template-columns: 130px 1fr auto; gap: 24px;
  align-items: center;
}
.action-card .atag {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-3);
}
.action-card .atag .pill {
  display: inline-block; font-weight: 600; padding: 3px 9px;
  border-radius: 3px; margin-top: 6px;
  background: var(--paper-3); color: var(--ink); font-size: 10px;
}
.action-card .ticker {
  font-family: var(--mono); font-size: 13px; font-weight: 600;
  letter-spacing: 0.04em; color: var(--ink-3);
}
.action-card .head {
  font-family: var(--serif); font-size: 1.4rem; font-weight: 500;
  margin: 4px 0 6px;
}
.action-card .plain { color: var(--ink-2); font-size: 14.5px; max-width: 60ch; }
.action-card .right {
  font-family: var(--mono); font-size: 11px;
  text-align: right; color: var(--ink-3); line-height: 1.6;
}
.action-card .right .level {
  font-family: var(--serif); font-size: 1.1rem;
  color: var(--ink); font-weight: 500;
}

.pulse-grid {
  display: grid; grid-template-columns: repeat(8, 1fr);
  border: 1px solid var(--rule); padding: 14px 0;
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
  font-family: var(--serif); font-size: 1.3rem; font-weight: 500;
  letter-spacing: -0.01em; margin-top: 2px;
}
.pulse-cell .pdelta { font-family: var(--mono); font-size: 11px; margin-top: 2px; }
.up { color: #4F8C46; }
.down { color: #C45643; }
.flat { color: var(--ink-3); }

.tk-row {
  display: grid; grid-template-columns: 80px 1fr 110px 100px 80px 100px 60px 60px 130px;
  gap: 12px; padding: 14px 12px;
  border-bottom: 1px solid var(--rule);
  font-family: var(--mono); font-size: 13px; align-items: center;
}
.tk-row.head {
  border-bottom: 1.5px solid var(--ink);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3); padding: 8px 12px;
}
.tk-row .name { font-family: var(--sans); color: var(--ink-2); }
.sig-pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase;
  padding: 3px 8px; border-radius: 3px;
}
.sig-pill::before { content: ""; width: 6px; height: 6px;
  border-radius: 50%; background: currentColor; }

.risk-card {
  padding: 14px 0; border-bottom: 1px solid var(--rule);
}
.risk-card .tag {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--caution, #C45643); margin-bottom: 4px;
}
.risk-card .text { font-size: 13.5px; color: var(--ink-2); line-height: 1.55; }

.cal-day {
  display: grid; grid-template-columns: 110px 1fr; gap: 24px;
  padding: 14px 0; border-bottom: 1px solid var(--rule);
}
.cal-date {
  font-family: var(--serif); font-size: 1.1rem; font-weight: 500;
}
.cal-date .dow {
  font-family: var(--mono); font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--ink-3); display: block; margin-top: 2px;
}
.cal-event {
  display: grid; grid-template-columns: 70px 60px 1fr;
  gap: 14px; align-items: baseline; margin-bottom: 8px;
}
.cal-tk { font-family: var(--mono); font-size: 12px; font-weight: 600; }
.cal-impact {
  font-family: var(--mono); font-size: 9.5px; letter-spacing: 0.14em;
  text-transform: uppercase; font-weight: 600; padding: 2px 6px;
  border-radius: 2px; text-align: center; width: fit-content;
}
.cal-impact.HIGH { color: #C45643; background: rgba(196,86,67,0.10); }
.cal-impact.MEDIUM { color: #C99A2E; background: rgba(201,154,46,0.14); }
.cal-text { font-size: 13.5px; color: var(--ink-2); line-height: 1.5; }

.colophon {
  margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--rule);
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-4);
}

.changes-ribbon {
  background: var(--paper-2); border: 1px solid var(--rule);
  padding: 12px 16px; margin: 12px 0;
  display: flex; gap: 22px; align-items: center; flex-wrap: wrap;
}
.changes-ribbon .clabel {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-3);
}
</style>""", unsafe_allow_html=True)

# ────────────────────────── Data loading ──────────────────────────
@st.cache_data(ttl=300)
def load_all_reports() -> dict[str, dict]:
    reports = {}
    for f in sorted(DATA_DIR.glob("morning_report_*.json")):
        date_str = f.stem.replace("morning_report_", "")
        try:
            reports[date_str] = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
    return reports

TICKER_DISPLAY = {
    "D05_SI": "D05.SI", "O39_SI": "O39.SI", "U11_SI": "U11.SI",
    "DX_Y_NYB": "DX-Y.NYB", "CL_F": "CL=F", "GC_F": "GC=F",
    "VIX": "^VIX", "TNX": "^TNX",
}

# ────────────────────────── Helpers ──────────────────────────
def fmt(n, d=2):
    if n is None or pd.isna(n):
        return "—"
    return f"{float(n):,.{d}f}"

def sign(n):
    if n is None or pd.isna(n):
        return ""
    return "+" if n > 0 else ""

def delta_class(n, inverse=False):
    if n is None or pd.isna(n) or n == 0:
        return "flat"
    up = n > 0
    if inverse:
        return "down" if up else "up"
    return "up" if up else "down"

def signal_pill(sig: str, small: bool = False) -> str:
    color = SIGNAL_COLORS.get(sig, "#8A847A")
    tint = SIGNAL_TINTS.get(sig, "rgba(0,0,0,0.05)")
    pad = "1px 6px" if small else "3px 8px"
    fs = "9.5px" if small else "10.5px"
    return (f'<span class="sig-pill" style="color:{color};background:{tint};'
            f'padding:{pad};font-size:{fs};">{sig}</span>')

def render_masthead(report_date: str, market_date: str):
    long_date = pd.to_datetime(report_date).strftime("%A, %B %-d, %Y") \
        if hasattr(pd.to_datetime(report_date), "strftime") else report_date
    st.markdown(f"""
<div class="masthead">
  <div>
    <div class="kicker">Morning Briefing · Signal Intelligence Daily</div>
    <h1 class="title">The <em>Market</em> Report</h1>
  </div>
  <div class="right">
    <div class="date">{long_date}</div>
    <div>Singapore · 11:30 SGT · Last close {market_date}</div>
  </div>
</div>
<div class="masthead-strip">
  <span>Volume IV · No. 117</span>
  <span>The Signal Desk</span>
  <span>Updated 11:30 SGT</span>
</div>
""", unsafe_allow_html=True)

def render_stance(stance: str, plain: str, counts: dict):
    st.markdown(f"""
<div class="stance-deck" style="color:{SIGNAL_COLORS['CAUTION']};">
  <span class="dot" style="background:{SIGNAL_COLORS['CAUTION']};"></span>
  <span>Today's Posture</span>
  <span style="color:var(--ink-3);">· {sum(counts.values())} names tracked</span>
</div>
<h2 class="stance-headline">{plain or stance}</h2>
<div class="stance-byline">{stance.upper()} · BY THE SIGNAL DESK</div>
""", unsafe_allow_html=True)

    cells = ""
    for sig in ["BUY", "ACCUMULATE", "WATCH", "HOLD", "CAUTION"]:
        n = counts.get(sig, 0)
        color = SIGNAL_COLORS[sig]
        zero_class = "zero" if n == 0 else ""
        num_color = f"color:{color};" if n > 0 else ""
        cells += (f'<div class="count-cell {zero_class}">'
                  f'<div class="clabel"><span class="cdot" style="background:{color};"></span>{sig}</div>'
                  f'<div class="cnum" style="{num_color}">{n}</div></div>')
    st.markdown(f'<div class="count-grid" style="margin-top:18px;">{cells}</div>',
                unsafe_allow_html=True)

def render_pulse(benchmarks: dict):
    order = ["SPY", "QQQ", "VIX", "WTI", "Gold", "DXY", "US10Y", "SOXX"]
    units = {"SPY":"S&P 500","QQQ":"Nasdaq 100","DXY":"Dollar","WTI":"Crude oil",
             "Gold":"Gold","VIX":"Fear gauge","US10Y":"10-yr yield","SOXX":"Semis ETF"}
    cells = ""
    for k in order:
        b = benchmarks.get(k, {})
        if not b:
            continue
        price = b.get("price")
        chg = b.get("chg_pct")
        inverse = (k == "VIX")
        cls = delta_class(chg, inverse)
        d = b.get("price")
        decimals = 0 if (d and d > 1000) else 2
        cells += (
            f'<div class="pulse-cell">'
            f'<div class="plabel">{k} · {units.get(k, "")}</div>'
            f'<div class="pprice">{fmt(price, decimals)}</div>'
            f'<div class="pdelta {cls}">{sign(chg)}{fmt(chg, 2)}%</div>'
            f'</div>'
        )
    st.markdown(f'<div class="pulse-grid">{cells}</div>', unsafe_allow_html=True)

def render_section_head(title: str, sub: str = ""):
    st.markdown(
        f'<div class="section-head"><h2>{title}</h2>'
        f'<span class="sub">{sub}</span></div>',
        unsafe_allow_html=True,
    )

def render_action_card(ticker: str, data: dict):
    sig = data.get("signal", "")
    color = SIGNAL_COLORS.get(sig, "#8A847A")
    name = ticker
    display_tk = TICKER_DISPLAY.get(ticker, ticker)
    price = data.get("price")
    ccy = data.get("currency", "USD")
    pfx = "S$" if ccy == "SGD" else "$"
    chg = data.get("chg_pct", 0)
    rationale = data.get("signal_rationale", "")
    # Take first 1-2 sentences
    headline = ""
    body = rationale
    parts = rationale.split(". ", 1)
    if len(parts) >= 1:
        headline = parts[0].rstrip(".") + "."
    if len(parts) > 1:
        body = parts[1]
    delta_color = SIGNAL_COLORS["BUY"] if chg > 0 else SIGNAL_COLORS["CAUTION"]
    st.markdown(f"""
<div class="action-card" style="border-left:4px solid {color};">
  <div class="atag">
    <div>If you only do</div>
    <div>one thing today</div>
    <div class="pill">{SIGNAL_VERB.get(sig, '—')}</div>
  </div>
  <div>
    <div class="ticker">{display_tk} · {name}</div>
    <div class="head">{headline}</div>
    <div class="plain">{body[:280]}{'…' if len(body) > 280 else ''}</div>
  </div>
  <div class="right">
    <div>Last</div>
    <div class="level">{pfx}{fmt(price, 2)}</div>
    <div style="margin-top:6px;color:{delta_color};">{sign(chg)}{fmt(chg, 2)}% today</div>
  </div>
</div>
""", unsafe_allow_html=True)

def render_changes(today_wl: dict, prev_wl: dict):
    rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    items = []
    for tk in sorted(set(today_wl) | set(prev_wl)):
        old = prev_wl.get(tk, {}).get("signal", "—")
        new = today_wl.get(tk, {}).get("signal", "—")
        if old == new or new == "—" or old == "—":
            continue
        direction = "up" if rank.get(new, 0) > rank.get(old, 0) else "down"
        arr_color = SIGNAL_COLORS.get(new, "#8A847A")
        display_tk = TICKER_DISPLAY.get(tk, tk)
        items.append(
            f'<span style="display:inline-flex;align-items:center;gap:8px;'
            f'font-family:var(--mono);font-size:12px;">'
            f'<strong>{display_tk}</strong>'
            f'{signal_pill(old, small=True)}'
            f'<span style="color:{arr_color};font-weight:700;">{"↑" if direction == "up" else "↓"}</span>'
            f'{signal_pill(new, small=True)}'
            f'</span>'
        )
    if not items:
        return
    body = '<span class="clabel">Since yesterday</span>' + " ".join(items)
    st.markdown(f'<div class="changes-ribbon">{body}</div>', unsafe_allow_html=True)

def render_watchlist(watchlist: dict):
    # Sort by signal priority then 1mo move
    rank = {"BUY": 0, "ACCUMULATE": 1, "WATCH": 2, "HOLD": 3, "CAUTION": 4}
    items = sorted(
        [(tk, d) for tk, d in watchlist.items() if tk not in RETIRED_TICKERS],
        key=lambda x: (rank.get(x[1].get("signal", "HOLD"), 5),
                       -(x[1].get("1mo_pct") or 0)),
    )

    # Header
    st.markdown("""
<div class="tk-row head">
  <div>Ticker</div><div>Name</div><div>Signal</div>
  <div style="text-align:right;">Last · Δ</div>
  <div style="text-align:right;">1mo</div>
  <div style="text-align:right;">vs 50-day</div>
  <div style="text-align:right;">RSI</div>
  <div style="text-align:right;">R:R</div>
  <div>Action</div>
</div>
""", unsafe_allow_html=True)

    for tk, d in items:
        sig = d.get("signal", "HOLD")
        display_tk = TICKER_DISPLAY.get(tk, tk)
        ccy = d.get("currency", "USD")
        pfx = "S$" if ccy == "SGD" else "$"
        price = d.get("price")
        chg = d.get("chg_pct", 0)
        m1 = d.get("1mo_pct")
        vs50 = d.get("vs_sma50_pct")
        rsi = d.get("rsi_14")
        rr = (d.get("risk_reward") or {}).get("ratio")
        chg_cls = delta_class(chg)
        m1_cls = delta_class(m1)
        # Ticker name fallback
        name = tk

        st.markdown(f"""
<div class="tk-row">
  <div style="font-weight:600;">{display_tk}</div>
  <div class="name">{name}</div>
  <div>{signal_pill(sig)}</div>
  <div style="text-align:right;">
    {pfx}{fmt(price, 2)}
    <div class="{chg_cls}" style="font-size:10.5px;">{sign(chg)}{fmt(chg, 2)}%</div>
  </div>
  <div class="{m1_cls}" style="text-align:right;">{sign(m1)}{fmt(m1, 1)}%</div>
  <div style="text-align:right;">{sign(vs50)}{fmt(vs50, 1)}%</div>
  <div style="text-align:right;">{fmt(rsi, 0)}</div>
  <div style="text-align:right;">{fmt(rr, 1)}:1</div>
  <div style="font-family:var(--sans);color:var(--ink-3);font-size:11.5px;">
    {SIGNAL_VERB.get(sig, '')}
  </div>
</div>
""", unsafe_allow_html=True)

        # Writeup gating: only BUY/ACCUMULATE/WATCH/CAUTION get an expander
        if sig in WRITEUP_SIGNALS:
            with st.expander(f"  Read the {sig.lower()} call on {display_tk}"):
                rationale = d.get("signal_rationale", "")
                block = d.get("entry_block")
                if block:
                    st.markdown(
                        f'<div style="background:rgba(196,86,67,0.10);'
                        f'color:{SIGNAL_COLORS["CAUTION"]};padding:8px 12px;'
                        f'font-family:var(--mono);font-size:12px;margin-bottom:12px;">'
                        f'ENTRY BLOCK · {block}</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f'<div style="font-family:var(--serif);font-size:1.05rem;'
                    f'line-height:1.55;color:var(--ink);max-width:75ch;">'
                    f'{rationale}</div>',
                    unsafe_allow_html=True,
                )
                # Numbers grid
                val = d.get("valuation", {}) or {}
                rr_obj = d.get("risk_reward", {}) or {}
                metrics = [
                    ("Cluster", val.get("cluster_name", "—")),
                    ("Forward P/E", f"{fmt(val.get('forward_pe'), 1)}x" if val.get("forward_pe") else "—"),
                    ("PEG", fmt(val.get("peg_ratio"), 2)),
                    ("Revenue growth", f"{sign(val.get('revenue_growth_pct'))}{fmt(val.get('revenue_growth_pct'), 1)}%"),
                    ("vs 50-day avg", f"{sign(vs50)}{fmt(vs50, 1)}%"),
                    ("RSI (14d)", fmt(rsi, 0)),
                    ("Risk:Reward", f"{fmt(rr, 1)}:1"),
                    ("Invalidation", fmt(rr_obj.get("invalidation"), 2)),
                ]
                cols = st.columns(4)
                for i, (label, value) in enumerate(metrics):
                    cols[i % 4].markdown(
                        f'<div style="border-bottom:1px dashed var(--rule);'
                        f'padding:8px 0;">'
                        f'<div style="font-family:var(--mono);font-size:10px;'
                        f'color:var(--ink-3);text-transform:uppercase;'
                        f'letter-spacing:0.06em;">{label}</div>'
                        f'<div style="font-family:var(--mono);font-size:13px;'
                        f'margin-top:2px;">{value}</div></div>',
                        unsafe_allow_html=True,
                    )

def render_macro(macro_summary: str, geo: dict):
    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown(
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
            f'margin-bottom:6px;">The Macro Note</div>'
            f'<div style="font-family:var(--serif);font-size:1.3rem;'
            f'line-height:1.5;font-weight:400;color:var(--ink);'
            f'margin-bottom:14px;">{macro_summary}</div>'
            f'<div style="font-size:14px;color:var(--ink-2);line-height:1.65;">'
            f'<strong>Portfolio implication.</strong> {geo.get("portfolio_action", "")}'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Probabilities bar
        probs = geo.get("probabilities", {})
        if probs:
            colors = {"base": SIGNAL_COLORS["ACCUMULATE"],
                      "optimistic": SIGNAL_COLORS["BUY"],
                      "pessimistic": SIGNAL_COLORS["CAUTION"],
                      "wildcard": SIGNAL_COLORS["WATCH"]}
            labels = {"base": "Base case", "optimistic": "Optimistic",
                      "pessimistic": "Pessimistic", "wildcard": "Wildcard"}
            segs = ""
            for k in ["base", "optimistic", "pessimistic", "wildcard"]:
                v = probs.get(k, 0)
                if v:
                    segs += (f'<div style="width:{v}%;background:{colors[k]};'
                             f'display:flex;align-items:center;justify-content:center;'
                             f'color:var(--paper);font-family:var(--mono);'
                             f'font-size:11px;font-weight:600;">{v}%</div>')
            keys = ""
            for k in ["base", "optimistic", "pessimistic", "wildcard"]:
                keys += (f'<div><span style="display:inline-block;width:8px;height:8px;'
                         f'background:{colors[k]};margin-right:6px;"></span>'
                         f'{labels[k]}</div>')
            st.markdown(
                f'<div style="margin-top:18px;">'
                f'<div class="sub" style="font-family:var(--mono);font-size:10px;'
                f'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
                f'margin-bottom:8px;">Scenario odds</div>'
                f'<div style="display:flex;height:28px;border:1px solid var(--rule-strong);'
                f'margin-bottom:8px;">{segs}</div>'
                f'<div style="display:grid;grid-template-columns:repeat(2,1fr);'
                f'gap:4px 18px;font-family:var(--mono);font-size:10.5px;'
                f'color:var(--ink-3);">{keys}</div></div>',
                unsafe_allow_html=True,
            )
    with col2:
        st.markdown(
            '<div style="font-family:var(--mono);font-size:10px;'
            'letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);'
            'margin-bottom:8px;">Active risks</div>',
            unsafe_allow_html=True,
        )
        for r in geo.get("active_risks", []):
            tag = r.split(":")[0][:24] if ":" in r else "Risk"
            text = r
            st.markdown(
                f'<div class="risk-card">'
                f'<div class="tag" style="color:{SIGNAL_COLORS["CAUTION"]};">{tag}</div>'
                f'<div class="text">{text}</div></div>',
                unsafe_allow_html=True,
            )

def render_calendar(events: list):
    grouped = {}
    for e in events:
        grouped.setdefault(e.get("date", "—"), []).append(e)
    for date_str, evs in sorted(grouped.items()):
        try:
            d = pd.to_datetime(date_str)
            short = d.strftime("%b %-d")
            dow = d.strftime("%a").upper()
        except Exception:
            short, dow = date_str, ""
        events_html = ""
        for e in evs:
            impact = e.get("impact", "MEDIUM")
            events_html += (
                f'<div class="cal-event">'
                f'<span class="cal-tk">{e.get("ticker", "—")}</span>'
                f'<span class="cal-impact {impact}">{impact}</span>'
                f'<span class="cal-text">{e.get("event", "")}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div class="cal-day">'
            f'<div class="cal-date">{short}<span class="dow">{dow}</span></div>'
            f'<div>{events_html}</div></div>',
            unsafe_allow_html=True,
        )

# ──────────────────────────── Main app ────────────────────────────
all_reports = load_all_reports()
if not all_reports:
    st.error("No report files found in data/.")
    st.stop()

dates = sorted(all_reports.keys(), reverse=True)
latest_date = dates[0]
report = all_reports[latest_date]
prev_report = all_reports[dates[1]] if len(dates) > 1 else {}

render_masthead(latest_date, report.get("meta", {}).get("market_date", "—"))

# ─── Tabs (replacing the sidebar nav) ───
tab_brief, tab_watch, tab_cal, tab_macro, tab_archive = st.tabs(
    ["Briefing", "Watchlist", "Calendar", "Macro", "Archive"]
)

with tab_brief:
    snapshot = report.get("portfolio_snapshot", {})
    render_stance(
        snapshot.get("overall_stance", ""),
        snapshot.get("risk_posture", ""),
        snapshot.get("signal_counts", {}),
    )
    render_pulse(report.get("benchmarks", {}))
    render_changes(
        report.get("watchlist", {}),
        prev_report.get("watchlist", {}),
    )

    # Pick a hero ticker — prefer first WATCH, else first BUY/ACCUMULATE
    wl = report.get("watchlist", {})
    hero = None
    for sig in ["BUY", "ACCUMULATE", "WATCH"]:
        for tk, d in wl.items():
            if tk in RETIRED_TICKERS:
                continue
            if d.get("signal") == sig:
                hero = (tk, d)
                break
        if hero:
            break
    if hero:
        render_section_head("If you only do one thing today",
                            "The desk's single highest-conviction action")
        render_action_card(hero[0], hero[1])

    render_section_head("The Macro Note", "What's driving prices")
    render_macro(report.get("macro_summary", ""), report.get("geopolitical", {}))

    render_section_head("The Week Ahead", "Catalysts that move signals")
    render_calendar(report.get("events_this_week", []))

with tab_watch:
    render_section_head("The Watchlist",
                        f"{len(report.get('watchlist', {}))} names · "
                        "writeups on actionable signals only")
    render_pulse(report.get("benchmarks", {}))
    render_watchlist(report.get("watchlist", {}))

with tab_cal:
    render_section_head("The Week Ahead", "Earnings · Macro · Fed")
    render_calendar(report.get("events_this_week", []))

with tab_macro:
    render_section_head("The Macro Note", "Geopolitics · Rates · Cross-asset")
    render_macro(report.get("macro_summary", ""), report.get("geopolitical", {}))

with tab_archive:
    render_section_head("Report Archive",
                        f"{len(dates)} reports · select a date to view")
    selected = st.selectbox("Report Date", dates)
    st.json(all_reports[selected], expanded=False)

# Footer
st.markdown(
    f'<div class="colophon">'
    f'<div>The MarketReport · Signal Desk</div>'
    f'<div>Generated {latest_date} · {len(report.get("watchlist", {}))} names tracked</div>'
    f'</div>',
    unsafe_allow_html=True,
)
