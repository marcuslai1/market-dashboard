"""Masthead, top navigation, and sidebar signal guide.

`render_masthead_and_nav` draws the editorial brand band at the top of the
page and the top-of-main-area radio that selects the active page. It returns
the selected page name so callers can drive their page-routing chain.

`render_signal_guide` is the sidebar Signal Guide expander — table of signal
colors and reading-the-numbers reference. Kept here as page chrome.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from lib.data_loader import load_all_reports

_NAV_PAGES = [
    "Briefing",
    "Watchlist",
    "Signal Tracker",
    "Pipeline Stats",
    "Scenario Log",
    "Report Comparison",
    "Terminology",
]


def render_masthead_and_nav() -> str:
    """Render the masthead + top-nav radio. Returns the selected page name."""
    reports = load_all_reports()
    dates = sorted(reports.keys()) if reports else []
    latest = dates[-1] if dates else "—"
    first = dates[0] if dates else None
    issue = "—"
    if first:
        try:
            first_d = date.fromisoformat(first)
            last_d = date.fromisoformat(latest)
            issue = f"No. {(last_d - first_d).days + 1}"
        except ValueError:
            pass
    market_date = reports.get(latest, {}).get("meta", {}).get("market_date", "—")
    try:
        long_date = date.fromisoformat(latest).strftime("%A, %B %d, %Y")
    except ValueError:
        long_date = latest

    st.markdown(
        f'<div class="masthead">'
        f'<div>'
        f'<div class="kicker">Morning Briefing · Signal Intelligence Daily</div>'
        f'<h1 class="title">The <em>Market</em> Report</h1>'
        f'</div>'
        f'<div class="right">'
        f'<div class="date">{long_date}</div>'
        f'<div>Singapore · 11:30 SGT · Last close {market_date}</div>'
        f'</div>'
        f'</div>'
        f'<div class="masthead-strip">'
        f'<span>Issue {issue}</span>'
        f'<span>The Signal Desk</span>'
        f'<span>Updated 11:30 SGT</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="topnav-wrap">', unsafe_allow_html=True)
    page = st.radio(
        "Navigate",
        _NAV_PAGES,
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return page


def render_signal_guide() -> None:
    """Render the collapsible Signal Guide panel."""
    with st.expander("Signal Guide", expanded=False):
        guide_html = """
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
