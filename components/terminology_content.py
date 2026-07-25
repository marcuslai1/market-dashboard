"""Terminology page content: the twelve sections, as data.

Design spec: docs/superpowers/specs/2026-07-25-terminology-redesign-design.md

Copy lives here; layout lives in ``components/terminology.py``. The split exists
because a module that is 95% prose is one where the layout is unreadable — and
because ``SECTIONS`` has to be a single array that drives *both* the index rail
and the body, so a section can never exist without a nav entry or vice versa.

Every entry carries three layers, and they must look different:

  answer   plain language, one or two sentences, no formula. The thing the
           reader came for; ninety percent of them can stop here.
  body     the precise rule — plates, grids, bands. Structured, never a wall
           of paragraphs.
  drawers  the audit trail. Caveats and edge cases, behind a door.
  history  dated method changes, behind a door labelled as history. They answer
           "what changed?", not "what does this mean?" — same content, correct
           shelf.

Nothing from the old page was deleted. The page's whole claim on the reader is
that it is auditable, so every sentence survives; it was re-shelved.

Dollar signs are written as ``&#36;`` throughout: two bare ``$`` in one markdown
block make Streamlit parse everything between them as LaTeX, which silently ate
the R:R worked example and the entry-block price on the old page.
"""
from __future__ import annotations

from lib.pills import _signal_pill_html

# ── HTML helpers ──────────────────────────────────────────────────────────
# Pure string builders. No Streamlit import: this module is copy, and copy
# should be testable without booting an app.


def _plate(code: str) -> str:
    """A formula plate. Wrap variable names in <var> — they render brass,
    because a variable is a data reference and brass is the data axis.

    A <div>, NOT a <pre>, even though <pre> is the semantically obvious tag.
    Streamlit's markdown renderer overrides the `pre` component for its own
    syntax highlighting, so a raw <pre> arrives stripped of its class with the
    newlines collapsed — the formula renders as a run-on italic sentence.
    Verified in the live DOM, which is why test_formula_plates_render_as_blocks
    exists. The old page used a <div> with white-space:pre-wrap for the same
    reason; that part of it was right.

    Blank lines are emitted as ``&nbsp;`` lines rather than truly empty ones.
    Defensive, not a fixed bug: the page is ONE CommonMark HTML block and a
    blank line is what closes such a block, so an empty line inside a plate puts
    everything after it at the mercy of rehype-raw stitching the tree back
    together. The entity renders as the blank line it looks like, at no cost.
    """
    body = code.replace(chr(10) + chr(10), chr(10) + "&nbsp;" + chr(10))
    return f'<div class="term-plate">{body}</div>'


def _grid(pairs, label_w: str = "132px") -> str:
    """Fixed label column, 1fr content column, rows on hairlines.

    The 1fr is load-bearing: a content column with no flexible track collapses
    to its minimum. Every definition starting at the same x is what gives the
    page a vertical edge you can scan by label alone.
    """
    rows = "".join(
        f'<div class="term-row"><div class="term-label">{label}</div>'
        f'<div class="term-def">{body}</div></div>'
        for label, body in pairs
    )
    return f'<div class="term-grid" style="--label-w:{label_w};">{rows}</div>'


def _axis(items, label_w: str = "150px") -> str:
    """Same grid, plus a 3px rail on the favourable → mixed → unfavourable axis.

    ``axis`` is "good" | "mixed" | "poor" → up-green / brass / terracotta. Not
    the signal palette: an R:R band and an earnings archetype are readings, not
    ratings, and amber here would read as WATCH.
    """
    rows = "".join(
        f'<div class="term-row" data-axis="{axis}">'
        f'<div class="term-label">{label}</div>'
        f'<div class="term-def">{body}</div></div>'
        for axis, label, body in items
    )
    return f'<div class="term-grid term-grid-axis" style="--label-w:{label_w};">{rows}</div>'


def _note(html: str) -> str:
    """A short prose paragraph inside layer 2, for the one or two places where
    the rule genuinely is a sentence."""
    return f'<p class="term-note">{html}</p>'


def _limits(items) -> str:
    """Terracotta-railed list — the site's one colour for a trust limitation."""
    rows = "".join(
        f'<div class="term-limit"><b>{head}</b> {body}</div>' for head, body in items
    )
    return f'<div class="term-limits">{rows}</div>'


def _chips(*labels) -> str:
    """Brass band chips — a cutoff is a measurement, so it sits on the data axis."""
    return ('<div class="term-chips">'
            + "".join(f'<span class="term-chip">{t}</span>' for t in labels)
            + "</div>")


def _wait_gradient() -> str:
    """HOLD / CAUTION / AVOID as a timeline rather than four sentences.

    The passage was describing a *scale*, which is the signal that prose wants
    to be a visual. Signal-palette colour is legitimate here — these are the
    signals themselves — and the widening bar carries the horizon that the
    words "days / weeks / quarters" only assert.
    """
    tiers = [("HOLD", "days", 20), ("CAUTION", "weeks", 55), ("AVOID", "quarters", 100)]
    rows = "".join(
        f'<div class="tg-row" data-signal="{sig}">'
        f'<span class="tg-name">{sig}</span>'
        f'<span class="tg-horizon">{horizon}</span>'
        f'<span class="tg-track"><span class="tg-bar" style="width:{w}%;"></span></span>'
        f"</div>"
        for sig, horizon, w in tiers
    )
    return (f'<div class="term-gradient" role="img" aria-label="Wait horizon by '
            f'signal: HOLD days, CAUTION weeks, AVOID quarters">{rows}</div>')


# ── Sections ──────────────────────────────────────────────────────────────
# Order is the reader's, not the pipeline's: what the labels mean, then the
# number they turn on, then the inputs, then how the record is scored, then the
# caveats that qualify all of it.

SECTIONS = [
    # 1 ─────────────────────────────────────────────────────────────────────
    {
        "id": "signals",
        "title": "The Six Signals",
        "descriptor": "What each label means, and when it fires",
        "kw": ("signal signals buy accumulate watch hold caution avoid label "
               "rating pill wait gradient states ladder writeup depth"),
        "answer": (
            "Six labels, one job each: what to do about this name <i>today</i>. "
            "They are states, not rungs on a ladder — a name can go from BUY to "
            "CAUTION in a single session if news invalidates the thesis."
        ),
        "body": (
            _grid([
                (_signal_pill_html("BUY"),
                 "<b>Enter now.</b> Multiple independent thesis legs, clean technicals "
                 "near SMA50, RSI neutral, volume confirmed, R:R favourable."
                 '<div class="term-trigger">Fires when all 8 mechanical gates pass '
                 "<i>and</i> the fragility gate is satisfied — ≥2 independent support "
                 "legs, or a single catalyst with multi-day durability.</div>"),
                (_signal_pill_html("ACCUMULATE"),
                 "<b>Starter position.</b> Mechanically eligible to enter, but not all "
                 "technical conditions are perfect — start small."
                 '<div class="term-trigger">All 8 gates pass and R:R is favourable, but '
                 "the fragility gate is not satisfied — single-leg thesis, or technicals "
                 "slightly short of BUY-grade.</div>"),
                (_signal_pill_html("WATCH"),
                 "<b>Wait for trigger.</b> Thesis intact, but entry conditions are not "
                 "present today."
                 '<div class="term-trigger">One or more gates fail — extended above '
                 "SMA50, RSI overbought, R:R below 1.0. The watch trigger is the named "
                 "missing condition.</div>"),
                (_signal_pill_html("HOLD"),
                 "<b>Wait days.</b> Nothing wrong, nothing actionable today. No clear "
                 "catalyst, mixed technicals, or poor R:R."
                 '<div class="term-trigger">The default state for a tracked name with no '
                 "actionable read. Clears when the next setup or catalyst arrives.</div>"),
                (_signal_pill_html("CAUTION"),
                 "<b>Wait weeks — price is wrong.</b> A mechanical block: extended price, "
                 "broken support, or extreme valuation. The story may still be intact."
                 '<div class="term-trigger">A hard block fires — &gt;5% above SMA50 with '
                 "RSI &gt; 70, or the invalidation level breached. Clears when price "
                 "resets.</div>"),
                (_signal_pill_html("AVOID"),
                 "<b>Wait quarters — the story is broken.</b> A specific, sourced thesis "
                 "leg has broken. Not a price move, a fundamental change."
                 '<div class="term-trigger">A named thesis leg — catalyst, moat, demand '
                 "pull — invalidated by an external development. Clears only when the "
                 "broken leg repairs.</div>"),
            ], label_w="124px")
            + '<div class="term-subhead">The three-tier wait gradient</div>'
            + _wait_gradient()
            + _note(
                "HOLD, CAUTION and AVOID all mean “no entry today”, but they sit on a "
                "timeline: HOLD clears whenever a setup forms, CAUTION needs <i>price</i> "
                "to reset, AVOID needs the broken leg to <i>repair</i>."
            )
        ),
        "drawers": [
            ("Why CAUTION and AVOID score differently",
             "<p>The calibration tables judge the two on different questions. CAUTION is "
             "scored on whether you avoided a drawdown. AVOID is scored on whether you "
             "stayed off the consideration set entirely — a stricter bar, because that is "
             "what the label is asking for.</p>"),
            ("Writeup depth scales with the decision",
             "<p>The actionable signals — BUY and ACCUMULATE — carry the fullest writeups: "
             "entry zone, invalidation, R:R math and sizing. WATCH and AVOID get a focused "
             "note: the missing trigger, or the broken thesis leg plus its source. HOLD and "
             "CAUTION carry a shorter <i>standing-context</i> note — the thesis being "
             "tracked, why it is not actionable right now, and the specific level or event "
             "that would change the call. Deliberately briefer than an actionable writeup, "
             "but no longer blank.</p>"
             "<p>A name with nothing live to track — no thesis, no news, and far from any "
             "actionable level — may show no note at all. That silence is intentional, not "
             "an omission.</p>"),
        ],
        "history": [],
    },
    # 2 ─────────────────────────────────────────────────────────────────────
    {
        "id": "rr",
        "title": "Risk : Reward",
        "descriptor": "The single most-cited number on this site",
        "kw": ("rr r:r risk reward ratio headline wide stop wide-stop widestop "
               "resistance invalidation structural support geometry bands "
               "favourable unfavourable mixed target upside downside"),
        "answer": (
            "Upside to the nearest resistance, divided by downside to the "
            "invalidation. An R:R of 2.4 offers 2.4 units of reward for every 1 at "
            "risk. It is a <i>shape</i> measure, not a probability — a 5:1 that "
            "fails 90% of the time is worse than a 1.5:1 that works 70% of the time."
        ),
        "body": (
            _plate(
                "headline_rr  =  (<var>nearest_resistance</var> − <var>entry</var>) / "
                "(<var>entry</var> − <var>invalidation</var>)\n"
                "wide_stop_rr =  (<var>nearest_resistance</var> − <var>entry</var>) / "
                "(<var>entry</var> − <var>structural_support</var>)"
            )
            + _grid([
                ("entry",
                 "Current close, or the named trigger price for WATCH setups."),
                ("nearest_resistance",
                 "The closest overhead supply zone identified from price action — prior "
                 "swing high, congestion zone, round-number magnet. <i>Not</i> a distant "
                 "best-case target."),
                ("invalidation",
                 "The price at which the thesis is mechanically wrong. Typically a recent "
                 "swing low or the SMA50, whichever the writeup cites."),
                ("structural_support",
                 "A deeper, more durable level — 200-day SMA, prior breakout base, "
                 "decade-long trendline. Feeds the wide-stop variant, for a trader willing "
                 "to give the position more room."),
            ], label_w="172px")
            + '<div class="term-subhead">Why there are two numbers</div>'
            + _grid([
                ("Headline",
                 "The tightest defensible stop — the math at a quick-exit risk profile. "
                 "This is the one cited on the Briefing."),
                ("Wide-stop",
                 "Deeper support — the math if you are willing to sit through more "
                 "volatility. Both are shown in the Watchlist drill-down."),
            ], label_w="124px")
            + '<div class="term-subhead">Quality bands</div>'
            + _axis([
                ("good", "R:R ≥ 2.0",
                 "Favourable. Geometry alone supports the entry."),
                ("mixed", "1.0 ≤ R:R &lt; 2.0",
                 "Mixed. Needs a thesis or technical edge to compensate."),
                ("poor", "R:R &lt; 1.0",
                 "Unfavourable. Risk exceeds the nearest reward — generally a WATCH or "
                 "HOLD."),
            ], label_w="150px")
            + _note("Bands are advisory, not absolute.")
        ),
        "drawers": [
            ("Caveat · distant-target inflation",
             "<p>When a ticker is below its SMA50 with no nearby resistance, the "
             "<var>nearest_resistance</var> can be the SMA50 itself, many percent away — "
             "producing a flattering R:R. The realistic upside in that case is the SMA50 "
             "<i>reclaim</i>, not a continuation through it. Read R:R alongside the "
             "ticker's vs-SMA50 figure.</p>"),
        ],
        "history": [
            ("2026-07-18", "distorted ratios never reach prose",
             "<p>A stop within a fraction of a percent of price can inflate the headline "
             "ratio into nonsense — a 0.2% stop yields “46.5:1”. When the pipeline flags "
             "this (<var>rr_distorted</var>), every reader surface now quotes "
             "<b>one corrected number</b>: the summary row and drill-down substitute the "
             "wide-stop sizing ratio, tagged “tight-stop adj.”, and the writeup quotes a "
             "single pre-computed sentence — “Risk-reward about 4.4:1 — upside to "
             "&#36;427, measured to the wider structural stop at &#36;381.71.”</p>"
             "<p>The old pattern of quoting the inflated number and then disclaiming it "
             "was retired: a number the report tells you to ignore is not shown at all. "
             "When no trustworthy ratio exists, the writeup says so and points at the "
             "support and resistance levels instead.</p>"),
        ],
    },
    # 3 ─────────────────────────────────────────────────────────────────────
    {
        "id": "technicals",
        "title": "Technical Indicators",
        "descriptor": "Cutoffs and what they imply",
        "kw": ("technical rsi sma50 sma 50 sma200 moving average volume trend "
               "extended overbought oversold regime bull bear days above"),
        "answer": (
            "Five price-and-volume readings that gate entry quality. The primary "
            "one is distance from the 50-day average — closer is cleaner."
        ),
        "body": _grid([
            ("RSI (14-day)",
             "Relative Strength Index. The smoothed ratio of average gains to average "
             "losses over the last 14 sessions, scaled 0–100. Measures whether recent "
             "buying or selling pressure has been one-sided."
             + _chips("&lt;40 oversold", "40–70 neutral", "&gt;70 overbought")),
            ("vs SMA50",
             "Percent distance from the 50-day simple moving average — the medium-term "
             "trend line, and the primary entry-quality gate."
             + _chips("±2% clean entry", "2–5% above extended", "&gt;5% above blocked")),
            ("vs SMA200",
             "Percent distance from the 200-day SMA — the long-term trend line. Used to "
             "classify regime."
             + _chips("&gt;0% bull regime", "&lt;0% bear regime")),
            ("SMA50 status",
             "<b>Rising</b> if the SMA50 is above its value 5 sessions ago by &gt;0.3%; "
             "<b>declining</b> if below by &gt;0.3%; otherwise <b>flat</b>. Paired with "
             "“days above” — consecutive sessions price closed above the SMA50."
             + _chips("rising", "flat", "declining")),
            ("Volume signal",
             "Today's volume divided by the 20-day average. Confirmation: a breakout on "
             "&gt;1.5× volume is more durable than one on &lt;1.0×."
             + _chips("&gt;1.5× confirmed", "1.0–1.5× normal", "&lt;1.0× weak")),
        ], label_w="132px"),
        "drawers": [],
        "history": [],
    },
    # 4 ─────────────────────────────────────────────────────────────────────
    {
        "id": "valuation",
        "title": "Valuation Metrics",
        "descriptor": "How fundamentals reach the signal",
        "kw": ("valuation forward pe p/e peg fcf free cash flow yield p/b book "
               "revenue growth eps estimate dividend yield cluster median premium"),
        "answer": (
            "Eight fundamental readings. Most are shown against the ticker's "
            "cluster median rather than in the absolute — a 30× forward P/E means "
            "nothing until you know the cluster trades at 22×."
        ),
        "body": _grid([
            ("Forward P/E",
             "Price divided by analyst-consensus next-12-month earnings per share. Shown "
             "alongside the <i>cluster median</i> and the percent premium or discount. A "
             "premium above 30% with weakening growth is a CAUTION trigger."),
            ("Cluster median",
             "Median forward P/E across the ticker's cluster peers (see CLUSTER_MAP — "
             "NVDA's cluster is Semis: AMD, INTC, MU, TSM, AVGO, ASML). Smooths "
             "single-name distortions."),
            ("PEG",
             "Forward P/E divided by expected EPS growth, in percent. Below 1.0 is "
             "growth-adjusted cheap; above 2.0 is expensive even after growth."),
            ("FCF yield",
             "Trailing free cash flow divided by market cap — the cash-on-cash return if "
             "the business stopped reinvesting. Above 5% is generous for a growth name; "
             "below 1% is priced for perfection."),
            ("P/B",
             "Price divided by book value per share. Primarily relevant for SG Banks and "
             "capital-heavy businesses."),
            ("Revenue growth",
             "Most recent reported quarter's revenue against the same quarter a year "
             "earlier."),
            ("EPS growth estimate",
             "Analyst consensus for next-fiscal-year EPS growth. Pairs with PEG."),
            ("Dividend yield",
             "Trailing 12-month dividends divided by the current price."),
        ], label_w="150px"),
        "drawers": [],
        "history": [],
    },
    # 5 ─────────────────────────────────────────────────────────────────────
    {
        "id": "earnings",
        "title": "Earnings Setup",
        "descriptor": "Band and archetype framing for a print",
        "kw": ("earnings print setup band archetype priced for perfection low bar "
               "underdog neutral implied move reaction guidance beat binary"),
        "answer": (
            "Earnings reactions are not binary. The market reacts to the gap "
            "between results and the bar already set by valuation, positioning and "
            "recent price — so a print is framed two ways: an implied price band "
            "from the ticker's own past reactions, and an archetype naming which "
            "bar it has to clear."
        ),
        "body": (
            '<div class="term-subhead">Setup archetypes</div>'
            + _axis([
                ("poor", "Priced for perfection",
                 "<div class=\"term-trigger\">Fires on <b>vs_sma50 &gt; +15% AND RSI ≥ 70</b> "
                 "— extended <i>and</i> overbought.</div>"
                 "A beat alone may not satisfy the bar; guidance must accelerate — raised "
                 "guide, new contract tier, margin expansion. A “merely good” print is the "
                 "most likely path to a sell-the-news pullback."),
                ("good", "Low bar / underdog",
                 "<div class=\"term-trigger\">Fires on <b>drawdown_3mo ≤ −15%</b> — beaten "
                 "down off the 3-month peak.</div>"
                 "“Less bad” results — in-line guidance, stable margins, even a small miss "
                 "with a constructive forward — can spark a relief rally. Sentiment is "
                 "washed out."),
                ("mixed", "Neutral",
                 "<div class=\"term-trigger\">Neither extreme.</div>"
                 "The standard expectations game. Reaction depends on the magnitude of the "
                 "surprise and the guidance delta. The bar is neither stretched nor "
                 "depressed."),
            ], label_w="172px")
            + '<div class="term-subhead">The implied price band</div>'
            + _plate(
                "For each of the last N earnings dates:\n"
                "  <var>next_day_return</var> = (close_t+1 − close_t) / close_t\n"
                "\n"
                "<var>avg_up_pct</var>   = mean of positive next_day_returns\n"
                "<var>avg_down_pct</var> = mean of negative next_day_returns  (absolute)\n"
                "<var>max_up_pct</var>   = max positive return\n"
                "<var>max_down_pct</var> = max negative return  (absolute)\n"
                "\n"
                "implied_upper = current_price × (1 + <var>avg_up_pct</var>)\n"
                "implied_lower = current_price × (1 − <var>avg_down_pct</var>)"
            )
            + _grid([
                ("N priors",
                 "How many earnings reports were used, typically 4–8. Shown in the "
                 "drill-down so the reader can judge sample size."),
                ("Asymmetric priors",
                 "If every past reaction went one direction, the opposite-side average is "
                 "null and only the populated side is shown."),
                ("Max bands",
                 "Shown alongside the average bands as a worst-case reference, not a base "
                 "case."),
                ("Days until",
                 "Calendar days to the earnings date. Bands are most informative within "
                 "about 10 days of the event."),
            ], label_w="150px")
        ),
        "drawers": [
            ("Why the AND is deliberate",
             "<p>A stock can be +15% above its SMA50 from a single gap-up weeks ago "
             "(not parabolic), or have RSI above 70 from a slow grind (not extended). The "
             "intersection isolates names that are <b>both stretched and momentum-crowded</b> "
             "— the setup where a beat tends not to clear the bar.</p>"
             "<p>Forward P/E was deliberately dropped from the rule because yfinance's "
             "coverage is patchy across the watchlist, and a rule that fires on only some "
             "tickers is worse than none.</p>"),
            ("What the band is not",
             "<p>Not an options-implied move, and not a directional forecast. It is the "
             "empirical distribution of the ticker's own past earnings-day moves, projected "
             "onto today's price. Use it to size risk, not to pick a side.</p>"),
            ("Why “binary event” is banned",
             "<p>The pipeline's writeup prompt forbids “binary event”, “coin flip”, "
             "“binary catalyst” and “either way” when a ticker has a pre-earnings band. "
             "Earnings reactions are price-vs-bar, not 50/50 gambles — the archetype names "
             "which bar matters and the band quantifies the typical move size. A writeup "
             "still using binary framing on a tagged ticker is a validator miss worth "
             "flagging.</p>"),
        ],
        "history": [],
    },
    # 6 ─────────────────────────────────────────────────────────────────────
    {
        "id": "episodes",
        "title": "Signal Episodes & Verdicts",
        "descriptor": "How the calibration table is built",
        "kw": ("episode episodes verdict verdicts entry exit return profit loss "
               "avoided missed quiet active run during outcome history tracker"),
        "answer": (
            "Consecutive same-signal days for one ticker collapse into a single "
            "<i>episode</i> with an entry, an exit, a return and a verdict. The "
            "load-bearing detail is the exit rule: episodes are scored on trade "
            "economics, not on signal-window boundaries."
        ),
        "body": (
            _plate(
                "BUY / ACCUMULATE episode:\n"
                "  <var>entry</var>  = price on the first BUY/ACCUMULATE day\n"
                "  <var>exit</var>   = price on the next CAUTION or AVOID day for that ticker\n"
                "           (HOLD and WATCH do NOT close the episode)\n"
                "  if no CAUTION/AVOID yet → episode is active, exit = latest close\n"
                "\n"
                "CAUTION / AVOID episode:\n"
                "  <var>entry</var>  = price on the first CAUTION/AVOID day\n"
                "  <var>exit</var>   = price on the next BUY/ACCUMULATE for that ticker\n"
                "  if no BUY/ACCUMULATE yet → active, exit = latest close\n"
                "\n"
                "WATCH / HOLD episode:\n"
                "  non-actionable. exit = last-day price.\n"
                "\n"
                "<var>return_pct</var>     = (exit − entry) / entry\n"
                "<var>run_during_pct</var> = (peak intra-episode price − entry) / entry"
            )
            + _note(
                "The exit rule reflects how the signals are meant to be traded: "
                "“<i>when an ACCUMULATE or BUY changes to another, it doesn't mean I should "
                "immediately sell — it just means it's no longer suitable to enter.</i>” A "
                "one-day ACCUMULATE flipping to HOLD does not return 0%; it stays open "
                "until a CAUTION or AVOID closes it."
            )
            + '<div class="term-subhead">Verdicts</div>'
            + _grid([
                ("✓ profit", "BUY / ACCUMULATE — <var>return_pct</var> &gt; 0 at exit."),
                ("✗ loss", "BUY / ACCUMULATE — <var>return_pct</var> ≤ 0 at exit."),
                ("✓ avoided", "CAUTION — <var>return_pct</var> &lt; 0; staying out spared a "
                              "drawdown. AVOID — same rule, the story-broken read paid off."),
                ("✗ wrong", "CAUTION — <var>return_pct</var> ≥ 0; the name kept working "
                            "without you. AVOID uses the same threshold, which is stricter "
                            "in intent: AVOID means off the consideration set entirely."),
                ("⚠ missed", "WATCH — <var>run_during_pct</var> ≥ 5%. There was a real move "
                             "and the trigger never fired."),
                ("— quiet", "WATCH — <var>run_during_pct</var> &lt; 5%. Nothing meaningful "
                            "happened."),
                ("— non-directional", "HOLD is never scored. It is the absence of a call."),
                ("⏳ active", "Any signal. The episode has not closed; the current return is "
                             "shown but is not final."),
            ], label_w="150px")
        ),
        "drawers": [
            ("Default filter",
             "<p>The outcome history shows only actionable episodes — BUY, ACCUMULATE, "
             "CAUTION, AVOID, plus triggered WATCH. HOLD and quiet WATCH are toggled off "
             "by default.</p>"),
            ("Paper Trade Outcomes · post-cutover only",
             "<p>The pipeline's <var>signal_evaluation_log</var> only stabilised on "
             "<b>2026-04-19</b>, when the catalyst-entry path landed. The table filters to "
             "that cutover by default; read pre-cutover rows as exploratory. Until roughly "
             "three months of post-cutover data accumulate, the metrics are directional, "
             "not statistical.</p>"),
        ],
        "history": [],
    },
    # 7 ─────────────────────────────────────────────────────────────────────
    {
        "id": "calibration",
        "title": "Aggregate Calibration",
        "descriptor": "Cross-watchlist hit rates",
        "kw": ("calibration aggregate win rate hit rate accuracy decay half-life "
               "shrinkage prior alpha closed only per signal thin cells"),
        "answer": (
            "Per signal type, the share of <i>closed</i> episodes that reached a ✓ "
            "verdict. It measures directional accuracy, not profit."
        ),
        "body": (
            _plate(
                "<var>win_rate</var>(signal)   = count(✓ episodes for signal) / "
                "count(closed episodes for signal)\n"
                "<var>avg_return</var>(signal) = mean(return_pct over closed episodes for signal)\n"
                "<var>avg_run</var>(signal)    = mean(run_during_pct over closed episodes for signal)"
            )
            + _grid([
                ("Closed-only",
                 "Active episodes are excluded from win-rate denominators — their verdict "
                 "is not yet known."),
                ("Per-signal, not per-day",
                 "A 30-day BUY counts once, not 30 times. This keeps persistent calls from "
                 "inflating the denominator."),
                ("HOLD is never counted",
                 "HOLD is non-directional; including it would dilute every metric toward "
                 "50/50."),
            ], label_w="172px")
        ),
        "drawers": [
            ("Decay half-life · 90 days",
             "<p>In the full-corpus “decayed” figures, old outcomes fade smoothly instead "
             "of dropping off a lookback cliff: a 90-day-old result carries half a vote, a "
             "180-day-old result a quarter. This lets the calibration read the whole "
             "history without letting stale regimes outvote the recent one.</p>"),
            ("Shrinkage",
             "<p>“Shrunk” figures blend small samples toward a skeptical prior — 0% alpha, "
             "50% hit rate — until they earn their way out. A signal with fewer than 5 "
             "episodes reads mostly as the prior, and the observed value takes over as "
             "episodes accumulate. Thin cells looking muted is the method working, not "
             "missing data.</p>"),
        ],
        "history": [],
    },
    # 8 ─────────────────────────────────────────────────────────────────────
    {
        "id": "paper-book",
        "title": "Paper Book",
        "descriptor": "How the mechanical portfolio trades and is scored",
        "kw": ("paper book portfolio nav benchmark spy soxx buy sell stop rule "
               "stop-rule lane lanes flat trail wide no-stop tranche tranches "
               "weight drawdown inception fx exit delist rebased"),
        "answer": (
            "A mechanical portfolio that trades the pipeline's own signals — no "
            "discretion, no hindsight. It answers one question: if you had "
            "followed the signals literally since inception on 2026-04-19, would "
            "you have beaten the market? It is measurement only, and never feeds "
            "back into the signals, buckets or writeups."
        ),
        "body": (
            _plate(
                "<var>book_return</var> = (current_NAV / inception_NAV − 1) × 100   "
                "# cash + positions marked to market\n"
                "<var>spy_return</var>  = (SPY_close_today / SPY_close_inception − 1) × 100\n"
                "<var>soxx_return</var> = (SOXX_close_today / SOXX_close_inception − 1) × 100"
            )
            + _grid([
                ("NAV",
                 "Net asset value — the whole book's worth, cash plus every open position "
                 "marked at its latest price. The chart rebases NAV and both benchmarks to "
                 "100 at inception, so a line at 106 means +6% since 2026-04-19. Foreign "
                 "holdings convert to USD at the day's FX rate."),
                ("vs SPY / SOXX",
                 "The book's <i>total</i> return — realized gains plus the mark-to-market of "
                 "open positions — against simply buying and holding the index over the "
                 "exact same dates. Not realized-gains-only, and not re-weighted to today's "
                 "holdings. SOXX is kept off the chart, where its swings would flatten the "
                 "book-vs-SPY gap, and shown in the data table instead."),
                ("When it buys",
                 "A <b>BUY</b> fills a full 10%-of-NAV position in one go. An "
                 "<b>ACCUMULATE</b> adds a 5% slice that day, and another 5% each further "
                 "day it persists, up to the same 10% cap. It buys only with available cash "
                 "and never exceeds target."),
                ("When it sells",
                 "Every exit liquidates the <i>whole</i> position — no partial trims. There "
                 "are exactly three triggers: <b>stop</b> (price falls to the position's "
                 "stop level; the fill is the worse of the stop or that day's open, so a "
                 "gap-down pays the gap), <b>AVOID exit</b> (the signal turns AVOID while "
                 "held — rare by design, since AVOID needs a sourced thesis break), and "
                 "<b>delist exit</b> (the ticker drops off the watchlist)."),
            ], label_w="150px")
            + '<div class="term-subhead">Stop-rule lanes</div>'
            + _note(
                "Four copies of the book run in parallel, differing <i>only</i> in the stop "
                "rule, to measure which rule works best — same buys, same everything else."
            )
            + _grid([
                ("flat <span class=\"term-tag\">headline</span>",
                 "Entry-day invalidation, frozen for the life of the trade."),
                ("trail",
                 "Re-anchors each day to the latest published invalidation — can tighten or "
                 "loosen."),
                ("no-stop",
                 "No price stop at all; exits only on AVOID or delist."),
                ("wide",
                 "Frozen like flat, but uses the deeper structural support when it is wider "
                 "than the headline stop — more room."),
            ], label_w="124px")
            + _note(
                "The <b>flat</b> lane is the headline curve; the other three render as a "
                "single numbers-only line beneath it. They are lanes of the same book, "
                "never a ranking."
            )
            + '<div class="term-subhead">Position fields</div>'
            + _grid([
                ("Weight", "A position's size as a percent of the book — roughly 10% each."),
                ("Stop", "The price at which that position auto-sells, per the lane's rule."),
                ("Tranches",
                 "How many slices built the position. 1 = a BUY or a single ACCUMULATE day; "
                 "2 = two ACCUMULATE days."),
                ("Max drawdown",
                 "The largest peak-to-trough dip the position has taken while held. A risk "
                 "gauge, not a realized loss."),
            ], label_w="124px")
            + _limits([
                ("Single-regime caveat.",
                 "The book has run through only one market regime — a broadly rising market "
                 "since April 2026. The returns are hypothesis-grade, not a performance "
                 "verdict, which is exactly what the exported banner says."),
            ])
        ),
        "drawers": [],
        "history": [],
    },
    # 9 ─────────────────────────────────────────────────────────────────────
    {
        "id": "macro",
        "title": "Macro Scenarios & Odds",
        "descriptor": "What the probability bar represents",
        "kw": ("macro scenario scenarios odds probability probabilities soft landing "
               "stagflation hard landing reacceleration carry forward scenario log"),
        "answer": (
            "Probabilities across a small set of named scenarios — typically three "
            "or four, such as soft landing, stagflation, hard landing, "
            "reacceleration. They are a subjective read of available evidence, "
            "<b>not</b> a market-implied or model-derived distribution."
        ),
        "body": _grid([
            ("Sum to 100%",
             "The set is exhaustive and mutually exclusive on any given day."),
            ("Days when probabilities moved",
             "The Scenario Log filters out flat-line days where the prior day's odds were "
             "carried forward unchanged. Only days with a delta in any scenario appear."),
            ("Carry-forward is the default",
             "Most days the macro picture does not change; the pipeline carries yesterday's "
             "odds rather than re-fitting noise."),
        ], label_w="172px"),
        "drawers": [],
        "history": [],
    },
    # 10 ────────────────────────────────────────────────────────────────────
    {
        "id": "entry-block",
        "title": "Entry Block & Catalyst Context",
        "descriptor": "Advisory caveats layered on the signal",
        "kw": ("entry block blocked catalyst context tier-1 tier 1 extension "
               "wait state writeup imperative conditional narrowness"),
        "answer": (
            "An advisory flag the writeup can raise when a BUY or ACCUMULATE "
            "name's mechanics — price, RSI — make entry imprudent today. The raw "
            "signal stays pure technicals; the block is the contextual caveat "
            "layered on top, not a hard gate."
        ),
        "body": _grid([
            ("Entry block",
             "The writeup's judgment that the name is not enterable right now, even though "
             "the signal is actionable."),
            ("Catalyst context",
             "When an extended name (&gt;5% above SMA50) has a verified Tier-1 catalyst — an "
             "earnings beat with a guidance raise, or a named contract with a dollar value; "
             "narrowness test: specific event, quantifiable impact, specific date — the "
             "pipeline surfaces it as <i>writeup context only</i>. It explains why the name "
             "is interesting and what would have to happen before it becomes actionable: a "
             "consolidation that resets the extension, or a second independent thesis leg."),
        ], label_w="150px"),
        "drawers": [],
        "history": [
            ("2026-07-18", "plain-language entry blocks",
             "<p>Entry blocks used to render as raw rule-engine strings — “Sustained trend "
             "exception not met: 10.8% (&gt;=10% ceiling), RSI 80 (&gt;=65)” — readable only "
             "if you knew the rule table. Reports now carry a plain-language rendering of "
             "the same decision: “Entry blocked: price is 10.8% above its 50-day average and "
             "the strong-trend exception doesn't apply — momentum is overheated (RSI 80)”. "
             "The drill-down shows that version; the raw rule string is preserved in the "
             "hover tooltip. Both are generated from the same rule evaluation and cannot "
             "disagree.</p>"),
            ("2026-07-18", "wait-state writeups describe conditions, not instructions",
             "<p>Live entry imperatives — “Entry at &#36;904 with a tight stop” — are "
             "reserved for BUY and ACCUMULATE writeups. A WATCH, HOLD, CAUTION or AVOID "
             "writeup phrases every level conditionally: “becomes actionable on a settle "
             "above &#36;904 with volume”. If you can extract a buy instruction from a "
             "wait-state writeup, that is a defect, not advice.</p>"),
            ("2026-05-30", "the catalyst entry path was removed",
             "<p>Catalyst context used to be a “catalyst entry path” that relaxed the "
             "extension block, letting an extended name reach ACCUMULATE. It was removed: "
             "it never actually triggered an entry in production — its gap-fill stop put "
             "R:R below the entry threshold — and its only effect would have been to act on "
             "the most-extended names, which the benchmark-relative calibration shows "
             "underperform. A detected catalyst no longer changes the signal; the name stays "
             "CAUTION on its extension.</p>"),
        ],
    },
    # 11 ────────────────────────────────────────────────────────────────────
    {
        "id": "pulse",
        "title": "Pulse Strip",
        "descriptor": "How the eight benchmarks are formatted",
        "kw": ("pulse strip benchmark benchmarks spy qqq vix wti gold dxy us10y "
               "soxx decimals inverted volatility"),
        "answer": (
            "Eight benchmarks — SPY · QQQ · VIX · WTI · Gold · DXY · US10Y · SOXX "
            "— each showing the latest level and the day's percent change. Colour "
            "follows the sign, except <b>VIX</b>, which is inverted: rising "
            "volatility is the risk-off direction."
        ),
        "body": _grid([
            ("VIX", "The CBOE Volatility Index — 30-day implied volatility on S&amp;P 500 "
                    "options."),
            ("WTI", "West Texas Intermediate front-month crude, in USD per barrel."),
            ("DXY", "The U.S. Dollar Index against a basket of major currencies."),
            ("US10Y", "The 10-year U.S. Treasury yield, in percent."),
            ("Decimals",
             "Four-digit prices (SPY at 5,800) show 0 decimals for readability; sub-1000 "
             "prices show 2."),
        ], label_w="124px"),
        "drawers": [],
        "history": [],
    },
    # 12 ────────────────────────────────────────────────────────────────────
    {
        "id": "limitations",
        "title": "Limitations",
        "descriptor": "What this site does not do",
        "kw": ("limitations limits caveat disclaimer not advice backtest "
               "personalized high frequency probability subjective"),
        "answer": (
            "Five constraints that qualify every number above. They are not "
            "boilerplate — each one names something the method genuinely cannot do."
        ),
        "body": _limits([
            ("Not personalized advice.",
             "Signals are computed on a fixed watchlist and assume no view of the reader's "
             "existing positions, risk tolerance, or tax situation."),
            ("Not a backtest.",
             "The calibration tables are forward-only — they evaluate signals as they were "
             "issued in real time, with no look-ahead. Sample sizes stay small until roughly "
             "three months of post-cutover data accrue."),
            ("Not high-frequency.",
             "Reports are produced once per session, pre-open SGT. Intraday moves are not "
             "reflected until the next run."),
            ("R:R is geometry, not probability.",
             "A high R:R does not mean a trade is likely to work — it means the math is "
             "favourable <i>if</i> it does."),
            ("Macro odds are subjective.",
             "The scenario probabilities are an uncalibrated narrative lean, not measured "
             "forecasts — no outcome scoring exists for them. A structured read of evidence, "
             "not a market-implied distribution."),
        ]),
        "drawers": [],
        "history": [],
    },
]
