"""Watchlist drill-down card — the body that unfolds beneath a clicked row.

Pure HTML-string generation — no Streamlit calls. The output is embedded inside
the ``<details>`` element rendered by ``components.watchlist.row``.

**Reading order is the whole argument** (spec 2026-07-25 §9). The shipped version
stacked fifteen undifferentiated ``dd-section`` blocks, so the fact that a trade
was *blocked* could sit below four paragraphs of analysis. This version is
ordered by consequence:

1. identity — restated, because an open drill-down can be taller than the
   viewport and lose the row that opened it;
2. flags — the status chips, the reasons this name is rated the way it is;
3. the entry block — the single most consequential fact, so it goes first;
4. the verdict headline, then what changed, then what to do;
5. the levels plate — what you would actually act on;
6. the evidence, in two columns: measurements left, the argument right;
7. three collapsed drawers for the material only an auditor wants.

Colour is by role throughout (spec §2): the signal palette appears only on the
card's rail and its pill; ``--up``/``--down`` mean price direction; ``--brass``
means measurement; ``--stress`` means a gate, a threshold crossed, or a
falsifier. A *reason* for a rating never wears the rating's own colour.
"""
from __future__ import annotations

from components.watchlist.drilldown_drawers import (
    STRESS,
    render_drawers_html,
)
from lib.catalog import CLUSTER_MAP
from lib.charts import (
    STATUS_INFO,
    STATUS_NEG,
    STATUS_NEUTRAL,
    STATUS_POS,
    STATUS_WARN,
)
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _escape_attr,
    _escape_dollars,
    _fmt_num,
    _sign,
    _writeup_for_render,
    display_ticker,
)
from lib.levels import rr_level, trade_levels
from lib.pills import _signal_pill_html


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


def _pairs_html(items: list[tuple]) -> str:
    """Label/value reference rows on dashed hairlines.

    Dashed, not solid, to distinguish "reference rows inside a card" from the
    solid row dividers of the table above. Items are ``(label, value)`` or
    ``(label, value, colour)``; absent values drop out entirely rather than
    printing an em-dash, so a thin report shows a short list, not a list of gaps.
    """
    visible = [it for it in items if it[1] not in (None, "", "—")]
    if not visible:
        return ""
    rows = ""
    for item in visible:
        colour = item[2] if len(item) > 2 else ""
        style = f' style="color:{colour};"' if colour else ""
        rows += (
            f'<div class="dd-pair"><span class="dd-pair-lbl">{item[0]}</span>'
            f'<span class="dd-pair-val"{style}>{item[1]}</span></div>'
        )
    return rows


# ── 1. Identity ───────────────────────────────────────────────────────────────

def _header_html(tk: str, d: dict, price_str: str) -> str:
    """Ticker + cluster left, last price + signal pill right.

    Restates identity because the drill-down can be taller than the viewport, and
    a reader who has scrolled into the evidence needs to know whose evidence it is.
    """
    sig = d.get("signal", "HOLD")
    return (
        '<div class="dd-head">'
        f'<div class="dd-head-id">'
        f'<div class="dd-head-tk">{_escape_dollars(display_ticker(tk))}</div>'
        f'<div class="dd-head-sub">{CLUSTER_MAP.get(tk, "")}</div></div>'
        f'<div class="dd-head-right"><div class="dd-head-px">{price_str}</div>'
        f'{_signal_pill_html(sig)}</div>'
        '</div>'
    )


# ── 2. Flags ──────────────────────────────────────────────────────────────────

#: Why a name carries the rating it does. These are *reasons*, so they take
#: terracotta (a gate condition) or steel (context) — never the signal hues,
#: which would read as a second verdict beside the pill three inches away.
_CAUTION_SOURCE_LABELS = {
    "hard_block": ("Mechanical hard block", STRESS),
    "claude_override": ("Judgment override", STRESS),
    "base_scorer": ("Soft caution (base scorer)", STRESS),
    "rr_gate_fail": ("R:R gate failed", STRESS),
    "catalyst_override": ("Catalyst override", STATUS_INFO),
    "rcp_terminal": ("RCP terminal", STRESS),
    "fragility_single_leg": ("Fragility gate — single leg", STRESS),
    "avoid_source_missing": ("AVOID unsourced", STRESS),
}

_SKEW_COLORS = {
    "bullish": STATUS_POS,
    "bearish": STATUS_NEG,
    "mixed": STATUS_WARN,
    "neutral": STATUS_NEUTRAL,
}


def _chip(text: str, color: str, bg: str = "rgba(255,255,255,0.05)",
          spaced: bool = True) -> str:
    ls = "0.10em" if spaced else "0.06em"
    return (
        f'<span style="font-family:var(--mono);font-size:10.5px;'
        f'letter-spacing:{ls};background:{bg};color:{color};'
        f'padding:3px 8px;border-radius:3px;">{text}</span>'
    )


def _status_chips_html(d: dict) -> str:
    """The row's flags. Silent on a clean name with no advisories.

    Kept visible rather than drawered: these are the reasons behind the rating,
    and hiding them would make the pill look unexplained.
    """
    chips: list[str] = []
    signal = d.get("signal", "")
    caution_source = d.get("caution_source")
    if caution_source and signal not in {"BUY", "HOLD"}:
        # Mapped ids show the plain-English label alone — repeating the raw id
        # beside it leaked pipeline vocabulary into the UI (UX 2026-07-07).
        # Unmapped ids fall back to the raw id: it is the only label we have.
        label, color = _CAUTION_SOURCE_LABELS.get(
            caution_source, (caution_source, STATUS_NEUTRAL)
        )
        chips.append(_chip(
            f'<span style="text-transform:uppercase;">{label}</span>', color
        ))
    if d.get("momentum_warn"):
        # Plain-English label; the reason strings stay verbatim — they are report
        # data (thresholds included), only the chrome is ours. Terracotta, not
        # amber: a tape divergence is a data condition, and amber is WATCH.
        reasons = d.get("momentum_warn_reasons") or []
        reason_str = "; ".join(reasons) if reasons else "tape diverging"
        chips.append(_chip(
            f'Momentum warning · {_escape_dollars(reason_str)}', STRESS,
            "rgba(224,138,128,0.14)", spaced=False,
        ))
    anomaly = d.get("data_anomaly")
    if anomaly:
        text = str(anomaly).replace("_", " ").replace("=", " = ")
        chips.append(_chip(
            f'data anomaly · {_escape_dollars(text)}', STRESS,
            "rgba(224,138,128,0.14)", spaced=False,
        ))
    # News-sentiment skew (P1-2 slice) — the pipeline's per-name read of the day's
    # headlines. Keeps up/down: this genuinely IS market direction.
    skew = d.get("news_sentiment_skew")
    if skew in _SKEW_COLORS:
        chips.append(_chip(
            f'<span style="text-transform:uppercase;">news · {skew}</span>',
            _SKEW_COLORS[skew],
        ))
    # Premarket chip — the pipeline-authored phrase captured at report generation,
    # coloured by the move's sign. Snapshot-time context, deliberately not a live
    # quote.
    pm = d.get("premarket") or {}
    phrase = pm.get("phrase")
    if phrase:
        pm_chg = pm.get("pm_chg_pct") or 0
        color = (STATUS_POS if pm_chg > 0
                 else STATUS_NEG if pm_chg < 0
                 else STATUS_NEUTRAL)
        chips.append(_chip(_escape_dollars(phrase), color, spaced=False))
    if not chips:
        return ""
    return ('<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">'
            + "".join(chips) + '</div>')


# ── 3-4. The entry block, then the verdict ────────────────────────────────────

def _entry_block_html(d: dict, wu: dict) -> str:
    """The trade is blocked — stated before any analysis, on a terracotta rail.

    Terracotta because it is a gate condition, not a rating. Prefers the
    pipeline's plain-language ``entry_block_reader`` (top-level, present from
    2026-07-18 on); older reports fall back to the raw rule string, which rides
    the title attribute either way for grep-ability.
    """
    raw = wu.get("entry_block")
    if not raw:
        return ""
    reader_text = d.get("entry_block_reader") or raw
    return (
        f'<div class="dd-entry-block" title="{_escape_attr(raw)}">'
        f'ENTRY BLOCK · {_escape_dollars(reader_text)}</div>'
    )


def _verdict_html(wu: dict) -> str:
    """Headline, then what changed since yesterday, then what to do.

    Verdict-first: the headline is the largest text in the block. The delta
    narrative is the only italic here, so it reads as a parenthetical update
    rather than part of the thesis. "What to do" is the largest and darkest prose,
    because it is the actionable instruction — everything below it is evidence.
    """
    parts: list[str] = []
    if wu.get("headline"):
        parts.append(
            f'<div class="dd-verdict">{_escape_dollars(wu["headline"])}</div>'
        )
    delta = wu.get("prior_period_delta_narrative")
    if delta:
        parts.append(f'<div class="dd-delta">{_escape_dollars(delta)}</div>')
    if wu.get("what_to_do"):
        parts.append(
            f'<div class="dd-whatdo">{_escape_dollars(wu["what_to_do"])}</div>'
        )
    return "".join(parts)


# ── 5. The levels plate ───────────────────────────────────────────────────────

def _levels_plate_html(d: dict, ccy: str) -> str:
    """Trigger / target / invalidation / R:R in a four-cell hairline grid.

    Promoted out of the old section stack because **price levels are what you act
    on** — they should be findable without reading. The field mapping is shared
    with the Briefing action card's three-cell triplet (``lib.levels``); this is
    the same device one size up, with the ratio added.
    """
    cells = trade_levels(d, ccy, entry_label="Trigger")
    if not cells:
        return ""
    rr = rr_level(d.get("risk_reward"))
    if rr:
        cells = [*cells, rr]
    return (
        '<div class="dd-levels">'
        + "".join(
            f'<div class="dd-lv"><div class="dd-lv-lbl">{c.label}</div>'
            f'<div class="dd-lv-val" style="color:{c.color};">{c.value}</div>'
            f'<div class="dd-lv-sub">{c.sub}</div></div>'
            for c in cells
        )
        + '</div>'
    )


# ── 6. The evidence, two columns ──────────────────────────────────────────────

def _technicals_pairs_html(d: dict, price_fn) -> str:
    sma50 = d.get("sma50")
    sma50_rising = d.get("sma50_rising")
    # An unknown direction drops the parenthetical entirely rather than printing
    # "(—)". A composite value must never carry an em-dash inside its own units:
    # that reads as a broken figure rather than an absent one (the bug the row
    # cells were fixed for in the 2026-07-07 UX review).
    sma_status = (
        " (rising)" if sma50_rising is True
        else " (declining)" if sma50_rising is False
        else ""
    )
    rsi = d.get("rsi_14")
    rsi_zone = d.get("rsi_zone", "")
    vol_sig = d.get("volume_signal", "")
    vol_ratio = d.get("vol_ratio")
    chg5 = d.get("5d_pct")
    m1 = d.get("1mo_pct")
    vs50 = d.get("vs_sma50_pct")
    vs200 = d.get("vs_sma200_pct")
    vs_cluster = d.get("vs_cluster_chg_pct")
    drawdown_3mo = d.get("drawdown_3mo_pct")
    return _pairs_html([
        ("vs 50-day", f"{_sign(vs50)}{_fmt_num(vs50, 1)}%" if vs50 is not None else "—"),
        ("vs 200-day",
         f"{_sign(vs200)}{_fmt_num(vs200, 1)}%" if vs200 is not None else "—"),
        ("SMA50", f"{price_fn(sma50)}{sma_status}" if sma50 else "—"),
        ("Days above SMA50",
         str(d.get("days_above_sma50"))
         if d.get("days_above_sma50") is not None else "—"),
        ("RSI (14d)",
         f"{_fmt_num(rsi, 0)}{f' {rsi_zone}' if rsi_zone else ''}" if rsi else "—"),
        ("Volume signal",
         f"{vol_sig} ({_fmt_num(vol_ratio, 2)}x)" if vol_sig else "—"),
        ("5-day return",
         f"{_sign(chg5)}{_fmt_num(chg5, 1)}%" if chg5 is not None else "—"),
        ("1-month return",
         f"{_sign(m1)}{_fmt_num(m1, 1)}%" if m1 is not None else "—"),
        # P1-2 slice: the day's move relative to the cluster median — the
        # pipeline's relative-strength read, rendered nowhere until 2026-07-02.
        ("vs cluster (1d)",
         f"{_sign(vs_cluster)}{_fmt_num(vs_cluster, 2)}%"
         if vs_cluster is not None else "—"),
        ("3mo drawdown",
         f"{_fmt_num(drawdown_3mo, 1)}%" if drawdown_3mo is not None else "—"),
    ])


def _valuation_pairs_html(d: dict) -> str:
    """The valuation pairs.

    ``Cluster`` is deliberately absent: it is stated twice already — in the card
    header above and in the grid row's ticker cell — so a third printing would
    just be a row of noise in a column of measurements.
    """
    val = d.get("valuation") or {}
    consensus = val.get("analyst_consensus") or {}
    fpe = val.get("forward_pe")
    cluster_med_pe = val.get("cluster_median_pe")
    pe_vs_cluster = val.get("pe_vs_cluster_pct")
    rev_g = val.get("revenue_growth_pct")
    fcf_y = val.get("fcf_yield_pct")
    div_y = val.get("dividend_yield_pct")
    pb = val.get("price_to_book")
    eps_g = consensus.get("earnings_growth_pct")
    return _pairs_html([
        ("Forward P/E", f"{_fmt_num(fpe, 1)}x" if fpe else "—"),
        # The vs-cluster delta is often absent while the median is present; when
        # it is, the parenthetical drops rather than printing "(—%)".
        ("Cluster median P/E",
         f"{_fmt_num(cluster_med_pe, 1)}x"
         + (f" ({_sign(pe_vs_cluster)}{_fmt_num(pe_vs_cluster, 0)}%)"
            if pe_vs_cluster is not None else "")
         if cluster_med_pe else "—"),
        ("PEG", _fmt_num(val.get("peg_ratio"), 2)),
        ("Revenue growth",
         f"{_sign(rev_g)}{_fmt_num(rev_g, 1)}%" if rev_g is not None else "—"),
        ("FCF yield",
         f"{_sign(fcf_y)}{_fmt_num(fcf_y, 2)}%" if fcf_y is not None else "—"),
        ("Dividend yield", f"{_fmt_num(div_y, 2)}%" if div_y else "—"),
        ("Price / Book", f"{_fmt_num(pb, 2)}x" if pb else "—"),
        ("Analyst consensus",
         _consensus_str(consensus.get("recommendation"),
                        consensus.get("num_analysts"))),
        ("Est. EPS growth",
         f"{_sign(eps_g)}{_fmt_num(eps_g, 1)}%" if eps_g is not None else "—"),
    ])


def _thesis_html(d: dict) -> str:
    """Numbered pillars, the news-matched highlights, then the falsifier.

    Numbering makes the pillars a **finite argument** rather than a bullet dump —
    "these three things, and here is what would break them". The break condition
    is deliberately last and terracotta, because it is the falsifier.
    """
    parts: list[str] = []
    legs = d.get("support_legs")
    if legs is not None:
        parts.append('<div class="dd-eyebrow">Thesis pillars</div>')
        if d.get("caution_source") == "fragility_single_leg":
            parts.append(
                f'<div class="dd-line" style="color:{STRESS};font-size:12.5px;">'
                'Single-leg fragility gate triggered — signal capped to WATCH.'
                '</div>'
            )
        for i, leg in enumerate(legs or [], 1):
            parts.append(
                f'<div class="dd-pillar"><span class="dd-pillar-n">{i:02d}</span>'
                f'<span class="dd-pillar-t">{_escape_dollars(str(leg))}</span></div>'
            )
    # Pipeline-emitted guardrail bullets that matched the day's news (~5/32 names)
    # — thesis evidence, so they sit with the pillars rather than in a drawer.
    highlights = [
        str(b).strip() for b in (d.get("thesis_highlights") or []) if b and str(b).strip()
    ]
    if highlights:
        parts.append('<div class="dd-eyebrow">Thesis highlights</div>')
        for hl in highlights:
            parts.append(
                f'<div class="dd-highlight">{_escape_dollars(hl)}</div>'
            )
    break_cond = (d.get("writeup") or {}).get("thesis_break_condition")
    if break_cond:
        parts.append('<div class="dd-eyebrow">Thesis break condition</div>')
        parts.append(f'<div class="dd-break">{_escape_dollars(break_cond)}</div>')
    return "".join(parts)


# ── The card ──────────────────────────────────────────────────────────────────

def render_drilldown_detail_html(tk: str, d: dict, earnings_hist=None) -> str:
    """The whole drill-down body for one ticker, as an HTML string.

    ``earnings_hist`` (optional) is the ticker's ``earnings_history`` records,
    newest quarter first; the caller loads and filters the CSV so this module
    stays Streamlit-free. Absent → the Earnings drawer's history half is silent.
    """
    ccy = d.get("currency", "USD")
    pfx = _ccy_prefix(ccy)
    dec = _ccy_decimals(ccy)

    def _p(v) -> str:
        """Currency-prefixed price with the right decimal count for this ticker."""
        return f"{pfx}{_fmt_num(v, dec)}"

    price = d.get("price")
    price_str = _p(price) if price is not None else "—"
    wu = _writeup_for_render(d)

    # Each half of the left column gets its own eyebrow. Without them the two
    # sets run together into one undifferentiated nineteen-row list, and a reader
    # cannot tell where the tape readings end and the multiples begin — the right
    # column already labels its parts, so this is also the consistent treatment.
    tech = _technicals_pairs_html(d, _p)
    val = _valuation_pairs_html(d)
    left = (
        (f'<div class="dd-eyebrow">Technicals</div>{tech}' if tech else "")
        + (f'<div class="dd-eyebrow">Valuation</div>{val}' if val else "")
    )
    right = _thesis_html(d)
    cols = (
        f'<div class="dd-cols"><div class="dd-col-left">{left}</div>'
        f'<div class="dd-col-right">{right}</div></div>'
        if (left or right) else ""
    )

    return (
        f'<div class="dd-card" data-signal="{_escape_attr(d.get("signal", "HOLD"))}">'
        f'{_header_html(tk, d, price_str)}'
        f'{_status_chips_html(d)}'
        f'{_entry_block_html(d, wu)}'
        f'{_verdict_html(wu)}'
        f'{_levels_plate_html(d, ccy)}'
        f'{cols}'
        f'{render_drawers_html(d, _p, earnings_hist)}'
        f'</div>'
    )
