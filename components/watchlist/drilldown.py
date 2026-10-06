"""Watchlist drill-down card — the body that unfolds beneath a clicked row.

Pure HTML-string generation — no Streamlit calls. The output is embedded inside
the ``<details>`` element rendered by ``components.watchlist.row``.

**Facts only since 2026-10-01** (MarketReport spec 2026-10-01-info-only-watchlist
§8, O6; tag ``pre-label-removal``). Reading order:

1. identity — restated, because an open drill-down can be taller than the
   viewport and lose the row that opened it (no pill);
2. data-health chips — what to distrust in the numbers below;
3. the price chart — the price since the first report and its 50- / 200-day
   averages, no threshold marks (``components.watchlist.price_chart``);
4. the levels ladder, the technicals and the valuation, side by side;
5. the Company profile drawer — what the company does, its revenue mix, customers,
   competitors and recent changes to the business, from MarketReport's checked cards
   (``components.watchlist.company_profile``; the same card on every report date);
6. the Earnings drawer (band, charts, history, the result headline);
7. news & context — the name's recent headlines (``recent_news``, from the
   pipeline cutover on), thesis highlights and the catalyst headline.

Gone with the labels: the entry-block card, the writeup verdict / what-to-do,
the caution-source and momentum chips, the trigger / target / invalidation / R:R
plate, the R:R and pipeline-detail drawers, the thesis pillars and break
condition (model writeup), the news-skew chip. Old reports keep those keys in
their JSON; nothing here reads them.
"""
from __future__ import annotations

import re
from datetime import date

from components.earnings_chart import reports_in_foreign_currency
from components.watchlist.company_profile import company_profile_html
from components.watchlist.drilldown_drawers import (
    STRESS,
    catalyst_html,
    render_drawers_html,
)
from components.watchlist.grid import cluster_of
from components.watchlist.price_chart import price_chart_html
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _delta_class,
    _escape_dollars,
    _fmt_num,
    _safe_href,
    _sign,
    display_ticker,
)
from lib.levels import level_ladder


def _consensus_str(rec, n_analysts) -> str:
    """Human form of yfinance's snake_case recommendation, or '—'.

    'strong_buy (58)' read as a raw field leak; 'none' is yfinance's literal
    no-coverage sentinel, not a rating (UX 2026-07-07).
    """
    if not rec or str(rec).lower() == "none":
        return "—"
    label = str(rec).replace("_", " ").strip().capitalize()
    if n_analysts:
        return f"{label} · {int(n_analysts)} analysts"
    return label


def _pct(v, decimals: int = 1) -> str:
    return f"{_sign(v)}{_fmt_num(v, decimals)}%" if v is not None else "—"


def _pairs_html(items: list[tuple]) -> str:
    """Label/value reference rows on dashed hairlines.

    Dashed, not solid, to distinguish "reference rows inside a card" from the
    solid row dividers of the table above. Absent values drop out entirely
    rather than printing an em-dash, so a thin report shows a short list, not a
    list of gaps.
    """
    return "".join(
        f'<div class="dd-pair"><span class="dd-pair-lbl">{label}</span>'
        f'<span class="dd-pair-val">{value}</span></div>'
        for label, value in items if value not in (None, "", "—")
    )


# ── 1. Identity ───────────────────────────────────────────────────────────────

def _header_html(tk: str, d: dict, price_str: str) -> str:
    """Ticker + cluster left, last price + the day's change right."""
    chg = d.get("chg_pct")
    chg_html = (f'<div class="dd-head-chg {_delta_class(chg)}">{_pct(chg, 2)}</div>'
                if chg is not None else "")
    return (
        '<div class="dd-head">'
        '<div class="dd-head-id">'
        f'<div class="dd-head-tk">{_escape_dollars(display_ticker(tk))}</div>'
        f'<div class="dd-head-sub">{_escape_dollars(cluster_of(tk, d))}</div></div>'
        f'<div class="dd-head-right"><div class="dd-head-px">{price_str}</div>'
        f'{chg_html}</div>'
        '</div>'
    )


# ── 2. Data-health chips ──────────────────────────────────────────────────────

#: Sentences that restate a label or an entry instruction rather than a data
#: condition. Old reports carry a few ("Signal suppressed." on a price-source
#: conflict, "…for entry guidance instead." on the SMA50 note); the fact in front
#: of them stays, the sentence goes.
_LABEL_SENTENCE = re.compile(
    r"(?i:\b(?:signal|entry|entries)\b)|\b(?:BUY|ACCUMULATE|WATCH|HOLD|CAUTION|AVOID)\b"
)


def fact_text(text) -> str:
    """A data-health string with its label / instruction sentences removed.

    ``|`` joins two independent facts in ``data_anomaly``; each part is split into
    sentences and filtered separately, and the parts rejoin with a middot.
    """
    parts: list[str] = []
    for part in str(text or "").split("|"):
        sentences = re.split(r"(?<=[.!?])\s+", part.strip())
        kept = " ".join(s for s in sentences if s and not _LABEL_SENTENCE.search(s))
        if kept:
            parts.append(kept)
    return " · ".join(parts)


def _chip(label: str, text: str = "") -> str:
    """One data-health chip. Terracotta is the site's data-condition colour
    (theme.css ``--stress``): it says "read the numbers below with care", never
    anything about the stock."""
    body = f'{label} · {_escape_dollars(text)}' if text else label
    return f'<span class="dd-chip" style="color:{STRESS};">{body}</span>'


def _health_chips_html(d: dict) -> str:
    """Silent on a clean name."""
    chips: list[str] = []
    anomaly = fact_text(str(d.get("data_anomaly") or "").replace("_", " ").replace("=", " = "))
    if anomaly:
        chips.append(_chip("Data anomaly", anomaly))
    elif d.get("price_source_conflict"):
        chips.append(_chip("Price sources disagree"))
    if d.get("stale_session"):
        chips.append(_chip("No new session", fact_text(d.get("stale_session_note"))))
    freshness = fact_text(d.get("data_freshness_note"))
    if freshness:
        chips.append(_chip("Data freshness", freshness))
    if d.get("_history_hole_suspect"):
        chips.append(_chip("Price history gap suspected"))
    sma_note = fact_text(d.get("sma50_warning"))
    if sma_note:
        chips.append(_chip("50-day average", sma_note))
    if not chips:
        return ""
    return f'<div class="dd-chips">{"".join(chips)}</div>'


# ── 3. Levels, technicals, valuation ──────────────────────────────────────────

def _ladder_html(d: dict, price_fn) -> str:
    """Every stated level, high → low, with the last price as its own rung.

    Neutral ink throughout: a level above the price is not "upside" and one below
    is not "risk" — they are prices the chart has turned at, and the averages.
    The right column is the move from the last price to the level.
    """
    rungs = level_ladder(d)
    if not rungs:
        return ""
    rows = "".join(
        f'<div class="dd-rung" data-kind="{r.kind}">'
        f'<span class="dd-rung-lbl">{r.label}</span>'
        f'<span class="dd-rung-px">{price_fn(r.price)}</span>'
        f'<span class="dd-rung-pct">{_pct(r.pct) if r.pct is not None else ""}</span>'
        '</div>'
        for r in rungs
    )
    return (
        '<div class="dd-eyebrow">Levels</div>'
        '<div class="dd-ladder">'
        '<div class="dd-rung dd-rung-head"><span>Level</span><span>Price</span>'
        '<span>Move to it</span></div>'
        f'{rows}</div>'
    )


def _technicals_html(d: dict) -> str:
    rising = d.get("sma50_rising")
    trend = "rising" if rising is True else "not rising" if rising is False else "—"
    days_above = d.get("days_above_sma50")
    vol_ratio = d.get("vol_ratio")
    rsi = d.get("rsi_14")
    pairs = _pairs_html([
        ("RSI (14-session)", _fmt_num(rsi, 0) if rsi is not None else "—"),
        ("vs 50-day", _pct(d.get("vs_sma50_pct"))),
        ("50-day average", trend),
        ("Sessions above 50-day", str(days_above) if days_above is not None else "—"),
        ("Volume", f"{_fmt_num(vol_ratio, 2)}× 10-session avg"
         if vol_ratio is not None else "—"),
        ("5-day return", _pct(d.get("5d_pct"))),
        ("1-month return", _pct(d.get("1mo_pct"))),
        ("vs cluster · day", _pct(d.get("vs_cluster_chg_pct"), 2)),
        ("vs cluster · 5-day", _pct(d.get("vs_cluster_5d_pct"))),
        ("vs cluster · 1-month", _pct(d.get("vs_cluster_1mo_pct"))),
    ])
    return f'<div class="dd-eyebrow">Technicals</div>{pairs}' if pairs else ""


def _fy_label(iso) -> str:
    """'2028-01-31' → ' · FY to Jan 2028'; '' when absent or malformed."""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return ""
    return f" · FY to {d.strftime('%b')} {d.year}"


def _valuation_html(d: dict, tk: str = "") -> str:
    """The valuation pairs. The analyst rating is a sourced third-party fact —
    Yahoo's sell-side consensus — and is labelled as such.

    P/B and FCF yield drop for a US listing of a foreign reporter on every date:
    Yahoo can divide the dollar price by home-currency book value and cash flow
    (ASML P/B 1,557.8 on 2026-10-01) and does not say which basis it used. The pipeline withholds both from 2026-10-02;
    this covers the reports before that."""
    val = d.get("valuation") or {}
    consensus = val.get("analyst_consensus") or {}
    fpe = val.get("forward_pe")
    cluster_med_pe = val.get("cluster_median_pe")
    pe_vs_cluster = val.get("pe_vs_cluster_pct")
    div_y = val.get("dividend_yield_pct")
    foreign = reports_in_foreign_currency(tk)
    pb = None if foreign else val.get("price_to_book")
    fcf = None if foreign else val.get("fcf_yield_pct")
    pairs = _pairs_html([
        ("Forward P/E",
         f"{_fmt_num(fpe, 1)}x{_fy_label(val.get('forward_pe_fy_end'))}" if fpe else "—"),
        # The vs-cluster delta is often absent while the median is present; when
        # it is, the parenthetical drops rather than printing "(—%)".
        ("Cluster median P/E",
         f"{_fmt_num(cluster_med_pe, 1)}x"
         + (f" ({_sign(pe_vs_cluster)}{_fmt_num(pe_vs_cluster, 0)}%)"
            if pe_vs_cluster is not None else "")
         if cluster_med_pe else "—"),
        ("PEG", _fmt_num(val.get("peg_ratio"), 2)),
        # Revenue: the last reported quarter, then analysts' sales growth this FY and next
        # (pipeline 2026-10-06) — together they show whether growth is speeding up or fading.
        ("Revenue growth, last quarter y/y", _pct(val.get("revenue_growth_pct"))),
        ("Est. revenue growth, this FY", _pct(val.get("revenue_growth_this_fy_pct"))),
        ("Est. revenue growth, next FY", _pct(val.get("revenue_growth_next_fy_pct"))),
        ("FCF yield", _pct(fcf, 2)),
        ("Dividend yield", f"{_fmt_num(div_y, 2)}%" if div_y else "—"),
        ("Price / Book", f"{_fmt_num(pb, 2)}x" if pb else "—"),
        ("Sell-side consensus (Yahoo)",
         _consensus_str(consensus.get("recommendation"), consensus.get("num_analysts"))),
        # Analysts' next-fiscal-year growth (pipeline 2026-10-02). The older field is
        # the last REPORTED quarter against a year earlier — it was labelled an
        # estimate here until 2026-10-02 (NVDA 127.8 % vs the analysts' 68.5 %).
        ("Est. EPS growth, next FY", _pct(val.get("eps_growth_next_fy_pct"))),
        ("EPS growth, last quarter y/y", _pct(consensus.get("earnings_growth_pct"))),
    ])
    return f'<div class="dd-eyebrow">Valuation</div>{pairs}' if pairs else ""


# ── 5. News & context ─────────────────────────────────────────────────────────

#: The pipeline ships at most 3 per name (the harvest's cap); a longer list is
#: still cut here so a contract change cannot turn the card into a feed.
_MAX_NEWS = 5


def _news_date(value) -> str:
    """``30 Sep`` from ``YYYY-MM-DD`` (or an ISO datetime); anything else verbatim."""
    raw = str(value or "").strip()
    try:
        when = date.fromisoformat(raw[:10])
    except ValueError:
        return _escape_dollars(raw)
    return f"{when.day} {when:%b}"


def _recent_news_html(d: dict) -> str:
    """The name's recent headlines — title (linked when the link is http/https),
    then publisher · date. Report contract (spec S2): ``recent_news`` is a list of
    ``{title, publisher, date, link}``, newest first; absent or ``[]`` renders
    nothing — no "no news" line, because an empty list is the normal state for
    most non-US names. No summary, no sentiment: a headline is a fact, its tone
    is not."""
    items = d.get("recent_news")
    if not isinstance(items, list):
        return ""
    rows: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        href = _safe_href(item.get("link"))
        title_html = (
            f'<a class="dd-news-title" href="{href}" target="_blank" '
            f'rel="noopener noreferrer">{_escape_dollars(title)}</a>'
            if href else
            f'<span class="dd-news-title">{_escape_dollars(title)}</span>'
        )
        meta = " · ".join(
            m for m in (_escape_dollars(str(item.get("publisher") or "").strip()),
                        _news_date(item.get("date")))
            if m
        )
        rows.append(
            f'<div class="dd-news-item">{title_html}'
            + (f'<div class="dd-news-meta">{meta}</div>' if meta else "")
            + '</div>'
        )
        if len(rows) == _MAX_NEWS:
            break
    if not rows:
        return ""
    return '<div class="dd-sub">Recent news</div>' + "".join(rows)


def _news_html(d: dict) -> str:
    """Recent headlines, thesis highlights (the pipeline's guardrail bullets that
    matched the day's news) and the catalyst headline. Silent when all three are
    absent."""
    parts: list[str] = []
    news = _recent_news_html(d)
    if news:
        parts.append(news)
    highlights = [
        str(b).strip() for b in (d.get("thesis_highlights") or []) if b and str(b).strip()
    ]
    if highlights:
        parts.append('<div class="dd-sub">Thesis highlights</div>')
        parts.extend(f'<div class="dd-highlight">{_escape_dollars(hl)}</div>'
                     for hl in highlights)
    cat = catalyst_html(d)
    if cat:
        parts.append('<div class="dd-sub">Catalyst</div>')
        parts.append(cat)
    if not parts:
        return ""
    return f'<div class="dd-news"><div class="dd-eyebrow">News &amp; context</div>{"".join(parts)}</div>'


# ── The card ──────────────────────────────────────────────────────────────────

def render_drilldown_detail_html(tk: str, d: dict, earnings_hist=None,
                                 report_date: str | None = None,
                                 price_hist=None, profile=None) -> str:
    """The whole drill-down body for one ticker, as an HTML string.

    ``earnings_hist`` (optional) is the ticker's ``earnings_history`` records,
    newest quarter first; the caller loads and filters the CSV so this module
    stays Streamlit-free. ``report_date`` dates a day-count-only earnings entry
    and ends the price chart (``price_hist``, the name's market_data.csv rows) on
    the report's own day. ``profile`` (optional) is the name's company card.
    """
    ccy = d.get("currency", "USD")
    pfx = _ccy_prefix(ccy)
    dec = _ccy_decimals(ccy)

    def _p(v) -> str:
        """Currency-prefixed price with the right decimal count for this ticker."""
        return f"{pfx}{_fmt_num(v, dec)}"

    price = d.get("price")
    price_str = _p(price) if price is not None else "—"
    cols = [c for c in (_ladder_html(d, _p), _technicals_html(d), _valuation_html(d, tk)) if c]
    cols_html = (
        '<div class="dd-cols dd-cols-3">'
        + "".join(f'<div class="dd-col">{c}</div>' for c in cols)
        + '</div>'
        if cols else ""
    )
    return (
        '<div class="dd-card">'
        f'{_header_html(tk, d, price_str)}'
        f'{_health_chips_html(d)}'
        f'{price_chart_html(tk, price_hist, report_date, _p)}'
        f'{cols_html}'
        f'{company_profile_html(profile)}'
        f'{render_drawers_html(d, _p, earnings_hist, report_date=report_date)}'
        f'{_news_html(d)}'
        '</div>'
    )
