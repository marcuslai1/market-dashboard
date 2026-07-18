"""Terminology page: methodology + formulas reference."""
from __future__ import annotations

import streamlit as st

from lib.cards import render_section_head


def render_terminology_page() -> None:
    """Render the Terminology page."""
    # Page-level h1 (matches Pipeline / Scenario / Report Comparison, which open
    # with st.title) so every page has exactly one top-level heading. (UX-CC-2)
    st.title("Terminology & Methodology")
    st.caption("How every number on this site is computed")

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
<thead><tr><th scope="col">Signal</th><th scope="col">Meaning</th><th scope="col">Trigger</th></tr></thead>
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
  <td><b>Wait days.</b> Nothing wrong, nothing actionable today. No clear catalyst, mixed technicals, or poor R:R.</td>
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
<div class="term-prose">
<b>Writeup depth scales with the decision.</b> The actionable signals — BUY and
ACCUMULATE — carry the fullest writeups: entry zone, invalidation, R:R math and
sizing. WATCH and AVOID get a focused note (the missing trigger, or the broken
thesis leg plus its source). HOLD and CAUTION carry a shorter <i>standing-context</i>
note — the thesis being tracked, why it is not actionable right now, and the
specific level or event that would change the call. It is deliberately briefer
than an actionable writeup, but no longer blank. A name with nothing live to
track — no thesis, no news, and far from any actionable level — may show no note
at all; that silence is intentional, not an omission.
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
<thead><tr><th scope="col">Band</th><th scope="col">Reading</th></tr></thead>
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
<div class="term-prose">
<b>Distorted ratios never reach prose (since 2026-07-18).</b> A stop within a
fraction of a percent of price can inflate the headline ratio into
nonsense (a 0.2% stop yields "46.5:1"). When the pipeline flags this
(<i>rr_distorted</i>), every reader surface quotes <b>one</b> corrected
number: the summary row and drill-down substitute the wide-stop sizing
ratio (tagged "tight-stop adj."), and the writeup quotes a single
pre-computed sentence — "Risk-reward about 4.4:1 — upside to $427,
measured to the wider structural stop at $381.71." The old pattern of
quoting the inflated number and then disclaiming it was retired: a number
the report tells you to ignore is not shown at all. When no trustworthy
ratio exists, the writeup says so and points at the support/resistance
levels instead.
</div>
""", unsafe_allow_html=True)

    # ---- Technicals ----
    render_section_head("Technical Indicators", "Bucket cutoffs and what they imply")
    st.markdown("""
<table class="term-table">
<thead><tr><th scope="col">Metric</th><th scope="col">Definition</th><th scope="col">Bands</th></tr></thead>
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
<thead><tr><th scope="col">Metric</th><th scope="col">Definition &amp; use</th></tr></thead>
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
<thead><tr><th scope="col">Archetype</th><th scope="col">Trigger</th><th scope="col">What "good news" must look like</th></tr></thead>
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
<thead><tr><th scope="col">Verdict</th><th scope="col">Rule</th></tr></thead>
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
<div class="term-prose">
<b>Decay half-life (90 days).</b> In the full-corpus "decayed" figures, old
outcomes fade smoothly instead of dropping off a lookback cliff: a 90-day-old
result carries half a vote, a 180-day-old result a quarter. This lets the
calibration read the whole history without letting stale regimes outvote the
recent one.
</div>
<div class="term-prose">
<b>Shrinkage.</b> "Shrunk" figures blend small samples toward a skeptical prior
— 0% alpha, 50% hit rate — until they earn their way out: a signal with fewer
than 5 episodes reads mostly as the prior, and the observed value takes over as
episodes accumulate. Thin cells looking muted is the method working, not
missing data.
</div>
""", unsafe_allow_html=True)

    # ---- Paper Book ----
    render_section_head("Paper Book", "How the mechanical portfolio trades and is scored")
    st.markdown("""
<div class="term-prose">
The <b>paper book</b> is a mechanical portfolio that trades the pipeline's own
signals — no discretion, no hindsight. It answers one question: if you had
followed the signals literally since inception (2026-04-19), would you have beaten
the market? It is <b>measurement only</b> — it never feeds back into the signals,
buckets, or writeups.
</div>
<div class="term-prose">
<b>NAV, rebased to 100.</b> NAV (net asset value) is the whole book's worth — cash
plus every open position marked at its latest price. The chart rebases NAV and both
benchmarks to 100 at inception, so a line at 106 means +6% since 2026-04-19. Foreign
holdings convert to USD at the day's FX rate.
</div>
<div class="term-formula">book_return = (current_NAV / inception_NAV − 1) × 100      # cash + positions marked to market
spy_return  = (SPY_close_today / SPY_close_inception − 1) × 100    # plain buy-and-hold, same window
soxx_return = (SOXX_close_today / SOXX_close_inception − 1) × 100</div>
<div class="term-prose">
<b>What "vs SPY / SOXX" means.</b> It compares the book's <i>total</i> return —
realized gains <i>plus</i> the current mark-to-market of open positions — against
simply buying and holding SPY (or the SOXX semiconductor ETF) over the exact same
dates. It is <b>not</b> realized-gains-only, and <b>not</b> re-weighted to today's
holdings: the benchmarks are plain buy-and-hold. "Trailing the benchmark" means the
book's total return is below the index's; "leading" means above. SOXX is kept off
the chart (its swings would flatten the book-vs-SPY gap) and shown in the data table.
</div>
<div class="term-prose">
<b>When it buys.</b> A <b>BUY</b> signal fills a full 10%-of-NAV position in one go.
An <b>ACCUMULATE</b> signal adds a 5% slice ("tranche") that day, and another 5%
each further day it persists, up to the same 10% cap. It buys only with available
cash and never exceeds target.
</div>
<div class="term-prose">
<b>When it sells.</b> Every exit liquidates the <i>whole</i> position — no partial
trims. There are exactly three exit triggers:
</div>
<ul class="term-bullets">
<li><b>Stop.</b> Price falls to the position's stop level. Fill is the worse of the stop or that day's open, so a gap-down pays the gap.</li>
<li><b>AVOID exit.</b> The signal turns AVOID while the position is held — rare by design, since AVOID needs a sourced thesis break.</li>
<li><b>Delist exit.</b> The ticker drops off the watchlist entirely.</li>
</ul>
<div class="term-prose">
<b>Stop-rule lanes.</b> Four copies of the book run in parallel, differing <i>only</i>
in the stop rule, to measure which rule works best — same buys, same everything else:
</div>
<table class="term-table">
<thead><tr><th scope="col">Lane</th><th scope="col">Stop rule</th></tr></thead>
<tbody>
<tr><td><b>flat</b> (headline)</td><td>Entry-day invalidation, frozen for the life of the trade.</td></tr>
<tr><td><b>trail</b></td><td>Re-anchors each day to the latest published invalidation — can tighten or loosen.</td></tr>
<tr><td><b>no-stop</b></td><td>No price stop at all; exits only on AVOID or delist.</td></tr>
<tr><td><b>wide</b></td><td>Frozen like flat, but uses the deeper structural support when it is wider than the headline stop — more room.</td></tr>
</tbody>
</table>
<div class="term-prose">
The <b>flat</b> lane is the headline curve; the other three render as a single
numbers-only line beneath it. They are lanes of the same book, never a ranking.
</div>
<ul class="term-bullets">
<li><b>Weight</b> — a position's size as a % of the book (~10% target each).</li>
<li><b>Stop</b> — the price at which that position auto-sells, per the lane's rule.</li>
<li><b>Tranches</b> — how many slices built the position (1 = a BUY or a single ACCUMULATE day; 2 = two ACCUMULATE days).</li>
<li><b>Max drawdown</b> — the largest peak-to-trough dip that position has taken while held. A risk gauge, not a realized loss.</li>
</ul>
<div class="term-prose">
<b>Single-regime caveat.</b> The book has run through only one market regime (a
broadly rising market since April 2026). The returns are hypothesis-grade, not a
performance verdict — which is exactly what the exported banner says.
</div>
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

    # ---- Entry Block & Catalyst Context ----
    render_section_head("Entry Block & Catalyst Context", "Advisory caveats layered on the signal")
    st.markdown("""
<div class="term-prose">
<b>Entry block</b> is an advisory flag the writeup may set when a name's
mechanicals (price, RSI) make entry imprudent <i>even though the signal
is BUY or ACCUMULATE</i>. It is the writeup's judgment, not a hard gate —
the raw signal remains pure technicals; entry_block is the contextual
caveat layered on top.
</div>
<div class="term-prose">
<b>Plain-language blocks (since 2026-07-18).</b> Entry blocks used to render
as raw rule-engine strings ("Sustained trend exception not met: 10.8%
(&gt;=10% ceiling), RSI 80 (&gt;=65)") — readable only if you knew the rule
table. Reports now carry a plain-language rendering of the same decision
("Entry blocked: price is 10.8% above its 50-day average and the
strong-trend exception doesn't apply — momentum is overheated (RSI 80)"),
and the drill-down shows that version; the raw rule string is preserved
in the hover tooltip. The two are generated from the same rule evaluation
and cannot disagree.
</div>
<div class="term-prose">
<b>Wait-state writeups describe conditions, not instructions (since
2026-07-18).</b> Live entry imperatives ("Entry at $904 with a tight
stop") are reserved for BUY and ACCUMULATE writeups. A WATCH, HOLD,
CAUTION, or AVOID writeup phrases every level conditionally ("becomes
actionable on a settle above $904 with volume") — if you can extract a
buy instruction from a wait-state writeup, that is a defect, not advice.
</div>
<div class="term-prose">
<b>Catalyst context.</b> When an extended name (&gt;5% above SMA50) has a
verified Tier-1 catalyst (earnings beat + guidance raise, or a named
contract with a dollar value; narrowness test: specific event,
quantifiable impact, specific date), the pipeline surfaces it as
<i>writeup context only</i>. It explains why the name is interesting and
what would have to happen — a consolidation that resets the extension, or
a second independent thesis leg — before it becomes actionable.
</div>
<div class="term-prose">
This used to be a "catalyst entry path" that relaxed the extension block
(letting an extended name reach ACCUMULATE). That was removed on
<b>2026-05-30</b>: it never actually triggered an entry in production (its
gap-fill stop put R:R below the entry threshold), and its only effect would
have been to act on the most-extended names — which the benchmark-relative
calibration shows underperform. A detected catalyst no longer changes the
signal; the name stays CAUTION on its extension.
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
<li><b>Macro odds are subjective.</b> The scenario probabilities are an uncalibrated narrative lean, not measured forecasts — no outcome scoring exists for them. They are a structured read of evidence, not a market-implied distribution.</li>
</ul>
""", unsafe_allow_html=True)
