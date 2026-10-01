"""Terminology page content: the sections, as data, plus the era line.

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

**Facts only since 2026-10-01** (MarketReport spec 2026-10-01-info-only-watchlist,
O7; tag ``pre-label-removal``). The sections that defined the signal labels and
the machinery around them — the six signals, R:R, episodes and verdicts,
calibration, macro scenarios, the entry block and the catalyst entry path — were
removed with the labels; the era line says when the labels ran. Every definition
below was checked against the pipeline code on 2026-10-01.

Dollar signs are written as ``&#36;`` throughout: two bare ``$`` in one markdown
block make Streamlit parse everything between them as LaTeX.
"""
from __future__ import annotations

#: The day this site stopped rendering signal labels, for every report date.
SITE_FACTS_ONLY_SINCE = "2026-10-01"
#: The day the pipeline's evaluation log started taking rows (its scoring record).
EVAL_LOG_FROM = "2026-04-01"

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
    exists.

    Blank lines are emitted as ``&nbsp;`` lines rather than truly empty ones:
    the page is ONE CommonMark HTML block and a blank line is what closes such a
    block.
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


def era_line_html(first_labelled: str | None, last_labelled: str | None,
                  cutover: str | None) -> str:
    """The one dated line about the signal labels (spec §9, O7).

    ``first_labelled`` / ``last_labelled`` are the first and last report dates on
    file that carry a label; ``cutover`` is the first report after them that
    carries none (``None`` until the pipeline stops producing labels). The line
    makes no claim about how the labels performed — the change is a choice about
    what this site shows, not a verdict on them.
    """
    start = first_labelled or "the first report"
    if cutover:
        ran = (f"Signal labels (BUY, ACCUMULATE, WATCH, HOLD, CAUTION, AVOID) shipped in the "
               f"reports from {start} to {last_labelled}; the pipeline stopped producing them "
               f"from {cutover}.")
    else:
        ran = (f"Signal labels (BUY, ACCUMULATE, WATCH, HOLD, CAUTION, AVOID) have shipped in "
               f"the reports since {start}; the pipeline stops producing them at a planned "
               "cutover.")
    return (
        '<div class="term-era">'
        f"{ran} They were logged for scoring from {EVAL_LOG_FROM}. Since "
        f"{SITE_FACTS_ONLY_SINCE} this site shows facts only, for every report date — a "
        "choice about what the site presents, not a finding about the labels. The label "
        "history stays in the project repository and its frozen database."
        "</div>"
    )


# ── Sections ──────────────────────────────────────────────────────────────
# Order is the reader's: how the Watchlist is laid out, then the drill-down's
# blocks in the order they appear, then the Briefing's pulse strip, then the
# caveats that qualify all of it.

SECTIONS = [
    # 1 ─────────────────────────────────────────────────────────────────────
    {
        "id": "order",
        "title": "Watchlist Order",
        "descriptor": "The same order every day",
        "kw": ("order watchlist grouped group cluster clusters sort sorting alphabetical "
               "a-z rows layout fixed semis bigtech neocloud"),
        "answer": (
            "Names are grouped by cluster — the same cluster printed under each ticker — "
            "and listed in one fixed order. Nothing on the page is ranked."
        ),
        "body": (
            _grid([
                ("Groups",
                 "Largest cluster first; clusters of equal size by name. A name with no "
                 "cluster goes in an “Other” group at the end."),
                ("Names",
                 "Alphabetical by ticker inside each group."),
                ("Stability",
                 "The order is a rule, not a list, so it never moves with the day's prices and "
                 "a newly added ticker slots itself in. Retired tickers are left out."),
            ], label_w="124px")
            + _note("Every report date — including reports from before "
                    f"{SITE_FACTS_ONLY_SINCE} — renders in this order with the same columns.")
        ),
        "drawers": [],
        "history": [
            (SITE_FACTS_ONLY_SINCE, "fixed order replaces signal groups",
             "<p>The Watchlist used to group rows by signal label and sort each group by "
             "one-month return, so a name's position changed from day to day. Labels left the "
             "site on this date; the cluster order replaced them.</p>"),
        ],
    },
    # 2 ─────────────────────────────────────────────────────────────────────
    {
        "id": "levels",
        "title": "Price Levels",
        "descriptor": "The ladder at the top of every drill-down",
        "kw": ("levels level support resistance swing high low zone ladder sma50 sma200 "
               "moving average distance move last price"),
        "answer": (
            "Prices the chart has turned at — up to two below the last price (support) and "
            "two above it (resistance) — with the 50- and 200-day averages, sorted high to "
            "low. Each shows the move from the last price needed to reach it."
        ),
        "body": (
            _plate(
                "move to level = (<var>level</var> − <var>last</var>) / <var>last</var>"
            )
            + _grid([
                ("Support / resistance",
                 "Swing lows and highs (a bar's low or high that is the extreme of the five "
                 "sessions either side), merged when within 1.5% of each other. The nearest "
                 "two below the price are supports, the nearest two above are resistances. "
                 "The look-back starts at a year and shortens to six, three or one month until "
                 "the nearest support is within 30% of the price."),
                ("50- / 200-day avg",
                 "The simple average of the last 50 or 200 daily closes."),
                ("Last",
                 "The last price — the report's, or the live quote on the latest report when "
                 "live prices are on."),
            ], label_w="150px")
        ),
        "drawers": [
            ("Why some names show fewer levels",
             "<p>When the pipeline finds no swing level on one side of the price it fills the "
             "gap with a moving average or a fixed percentage of the price, so that its old "
             "risk-reward ratio had something to divide by. Those fill-ins are not prices the "
             "chart turned at, so the ladder leaves them out: a name trading above every swing "
             "high it has shows no resistance at all.</p>"),
        ],
        "history": [],
    },
    # 3 ─────────────────────────────────────────────────────────────────────
    {
        "id": "technicals",
        "title": "Technical Indicators",
        "descriptor": "Price-and-volume readings, as numbers",
        "kw": ("technical technicals rsi sma50 sma 50 sma200 moving average volume trend "
               "days above rising returns 5-day five day 1-month month cluster relative"),
        "answer": (
            "Price-and-volume readings computed from daily bars. The site prints each one as "
            "a number, with no zone word and no colour band."
        ),
        "body": _grid([
            ("RSI (14-session)",
             "Relative Strength Index with Wilder smoothing over 14 sessions, 0–100: the "
             "balance of average gains against average losses. Readings above 70 and below "
             "30 are conventionally called overbought and oversold; the site does not label "
             "them."),
            ("vs 50-day",
             "Percent distance of the last price from its 50-day average: (last − average) / "
             "average. The Watchlist gauge draws it centred on zero, clamped at ±20%."),
            ("50-day average",
             "<b>Rising</b> when the average is higher than it was ten sessions ago, otherwise "
             "<b>not rising</b>. There is no separate flat state."),
            ("Sessions above",
             "Consecutive sessions, counting back from the latest, that closed above that "
             "session's own 50-day average."),
            ("Volume",
             "The latest session's volume divided by the average of the last ten sessions "
             "(the latest included). 1.40× means 40% above that average."),
            ("5-day · 1-month",
             "Price change against the close 5 and 21 sessions earlier."),
            ("vs cluster",
             "The name's day, 5-day and 1-month change minus the median of its cluster, in "
             "percentage points. Only clusters with two or more names have one."),
        ], label_w="150px"),
        "drawers": [
            ("When the price is newer than the bars",
             "<p>Some exchanges' daily bars arrive a session late. The price is then the "
             "latest quote, the 5-day and 1-month windows count back from the quote's own "
             "session, and the averages, RSI and volume ratio are a session behind. The "
             "drill-down says so in a Data freshness chip.</p>"),
        ],
        "history": [
            (SITE_FACTS_ONLY_SINCE, "definitions corrected",
             "<p>This page said the volume ratio used a 20-day average and that “rising” "
             "compared the 50-day average with five sessions earlier at a 0.3% margin. The "
             "pipeline uses a ten-session average and a plain ten-session comparison; the "
             "definitions above are the pipeline's.</p>"),
        ],
    },
    # 4 ─────────────────────────────────────────────────────────────────────
    {
        "id": "valuation",
        "title": "Valuation Metrics",
        "descriptor": "Multiples and estimates, as reported",
        "kw": ("valuation forward pe p/e peg fcf free cash flow yield p/b book "
               "revenue growth eps estimate dividend yield cluster median premium "
               "consensus analyst sell-side yahoo"),
        "answer": (
            "Fundamental readings from Yahoo Finance. The forward P/E is also shown against "
            "the median of the name's cluster."
        ),
        "body": _grid([
            ("Forward P/E",
             "Price divided by the analyst-consensus next-twelve-month earnings per share."),
            ("Cluster median",
             "Median forward P/E across the cluster's names that have one, with this name's "
             "percent premium or discount. Clusters with fewer than two priced names have no "
             "median."),
            ("PEG",
             "Forward P/E divided by expected earnings growth, in percent."),
            ("FCF yield",
             "Trailing free cash flow divided by market capitalisation."),
            ("P/B",
             "Price divided by book value per share."),
            ("Revenue growth",
             "The latest reported quarter's revenue against the same quarter a year earlier."),
            ("EPS growth estimate",
             "Analyst consensus for next-fiscal-year EPS growth."),
            ("Dividend yield",
             "Trailing twelve-month dividends divided by the current price."),
            ("Sell-side consensus",
             "Yahoo's summary of the analysts covering the name (for example “Strong buy · "
             "59 analysts”). A third-party figure, quoted with its source; this site makes no "
             "rating of its own."),
        ], label_w="150px"),
        "drawers": [],
        "history": [],
    },
    # 5 ─────────────────────────────────────────────────────────────────────
    {
        "id": "earnings",
        "title": "Earnings",
        "descriptor": "The next report date and past reactions",
        "kw": ("earnings print report date days until next reported band reaction "
               "implied move history beat miss calendar"),
        "answer": (
            "The Watchlist's Earnings column is the next report date and the calendar days "
            "to it. Within two weeks of a print, the drill-down adds the name's own past "
            "earnings-day moves, projected onto today's price."
        ),
        "body": (
            _grid([
                ("Next report",
                 "From the Yahoo earnings calendar. “reported” means the result came out "
                 "after the last US close; “no calendar” means the calendar could not be read, "
                 "which is not the same as no date."),
                ("Days",
                 "Calendar days from the report date to the earnings date."),
            ], label_w="150px")
            + '<div class="term-subhead">Past earnings reactions</div>'
            + _plate(
                "For each of the last N earnings dates:\n"
                "  <var>next_day_return</var> = (close_t+1 − close_t) / close_t\n"
                "\n"
                "<var>avg_up_pct</var>   = mean of positive next_day_returns\n"
                "<var>avg_down_pct</var> = mean of negative next_day_returns\n"
                "<var>max_up_pct</var>   = largest positive return\n"
                "<var>max_down_pct</var> = largest negative return\n"
                "\n"
                "average up move   = current_price × (1 + <var>avg_up_pct</var>)\n"
                "average down move = current_price × (1 + <var>avg_down_pct</var>)"
            )
            + _grid([
                ("N priors",
                 "How many past prints were used, shown in the drill-down so the sample size "
                 "is visible."),
                ("One-sided",
                 "If every past reaction went one way, the other side has no average and only "
                 "the populated side is shown."),
            ], label_w="150px")
        ),
        "drawers": [
            ("What the reactions are not",
             "<p>Not an options-implied move and not a forecast: the distribution of this "
             "name's own past earnings-day moves, projected onto today's price.</p>"),
        ],
        "history": [
            (SITE_FACTS_ONLY_SINCE, "setup archetypes removed",
             "<p>The band used to carry a setup tag — “priced for perfection”, “low bar” or "
             "“neutral” — read off the 50-day distance and RSI. It was an interpretation, not "
             "a measurement, and left the site with the labels.</p>"),
        ],
    },
    # 6 ─────────────────────────────────────────────────────────────────────
    {
        "id": "news",
        "title": "News & Context",
        "descriptor": "Thesis highlights and catalysts",
        "kw": ("news context thesis highlights guardrail catalyst headline source "
               "contract earnings result"),
        "answer": (
            "Headlines tied to a name, each with its source: thesis highlights and a catalyst "
            "line. They inform; nothing on the site changes because of them."
        ),
        "body": _grid([
            ("Thesis highlights",
             "Notes from the project's tracked thesis for the name that matched that "
             "day's news."),
            ("Catalyst",
             "A dated, sourced event tied to the name — a contract, a launch, a guidance "
             "change — with the publication and a link when one was captured."),
            ("Earnings result",
             "The headline that reported a print, when the day's news carried one (in the "
             "Earnings drawer)."),
        ], label_w="150px"),
        "drawers": [],
        "history": [],
    },
    # 7 ─────────────────────────────────────────────────────────────────────
    {
        "id": "data-health",
        "title": "Data-Health Flags",
        "descriptor": "When to read a number with care",
        "kw": ("data health flag flags anomaly stale session freshness quote bar conflict "
               "price sources holiday gap warning"),
        "answer": (
            "Terracotta chips at the top of a drill-down. They describe the data, never the "
            "stock: read the numbers below them with care."
        ),
        "body": _grid([
            ("Data anomaly",
             "Two of the provider's figures disagree — two price sources more than 5% apart, "
             "or a day's change that does not fit the multi-day change — or the name has "
             "fewer than 50 daily bars, too few for a 50-day average."),
            ("No new session",
             "The market was closed: the bar and price are the previous report's."),
            ("Data freshness",
             "The price is newer than the latest daily bar, so averages and RSI are a session "
             "behind."),
            ("50-day average",
             "The price is far from its 50-day average, so the average is a distant "
             "reference."),
        ], label_w="150px"),
        "drawers": [],
        "history": [],
    },
    # 8 ─────────────────────────────────────────────────────────────────────
    {
        "id": "pulse",
        "title": "Pulse Strip",
        "descriptor": "How the benchmarks are formatted",
        "kw": ("pulse strip benchmark benchmarks spy qqq vix us10y soxx usdsgd usd/sgd "
               "sgd singapore dollar currency decimals inverted volatility"),
        "answer": (
            "Six benchmarks — SPY · QQQ · VIX · US10Y · SOXX · USD/SGD "
            "— each showing the latest level and the day's percent change. Colour "
            "follows the sign, except <b>VIX</b>, which is inverted (rising "
            "volatility is the risk-off direction), and <b>USD/SGD</b>, which stays "
            "neutral: a currency move is good for some readers and bad for others."
        ),
        "body": _grid([
            ("SPY · QQQ", "The S&amp;P 500 and Nasdaq-100 exchange-traded funds."),
            ("VIX", "The CBOE Volatility Index — 30-day implied volatility on S&amp;P 500 "
                    "options."),
            ("US10Y", "The 10-year U.S. Treasury yield, in percent."),
            ("SOXX", "The iShares Semiconductor exchange-traded fund."),
            ("USD/SGD", "Singapore dollars per US dollar at the US close (4 pm New York). A rise "
                        "means the US dollar strengthened, so a US-dollar holding is worth more "
                        "in SGD. The day's move runs US close to US close, the same window as the "
                        "stock figures."),
            ("Decimals",
             "Four-digit prices (SPY at 5,800) show 0 decimals for readability; sub-1000 "
             "prices show 2; USD/SGD shows 4."),
        ], label_w="124px"),
        "drawers": [],
        "history": [],
    },
    # 9 ─────────────────────────────────────────────────────────────────────
    {
        "id": "limitations",
        "title": "Limitations",
        "descriptor": "What this site does not do",
        "kw": ("limitations limits caveat disclaimer not advice rating ratings "
               "personalized high frequency delay"),
        "answer": (
            "Four constraints that qualify every number above. They are not "
            "boilerplate — each one names something the site genuinely does not do."
        ),
        "body": _limits([
            ("Not advice, and no ratings.",
             "The site shows prices, technicals, levels, valuation, earnings dates and "
             "headlines for a fixed watchlist. It does not rate, rank or recommend a name, "
             "and it knows nothing of the reader's positions, risk tolerance or taxes."),
            ("Once a day.",
             "Reports are produced once per weekday, around midday Singapore time, after the "
             "US close. Live prices on the latest report are the only figures that move in "
             "between."),
            ("Provider data.",
             "Prices, calendars and fundamentals come from Yahoo Finance and can be late, "
             "revised or missing; the data-health chips flag the cases the pipeline can "
             "detect."),
            ("Levels are history.",
             "A support or resistance is a price the chart turned at before. It says nothing "
             "about whether the price will turn there again."),
        ]),
        "drawers": [],
        "history": [],
    },
]
