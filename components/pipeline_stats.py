"""Pipeline health page: is the pipeline healthy, and is it costing what it should?

Arithmetic: lib/pipeline_metrics.py (this module renders; it does not derive).

This is the only page whose reader is the operator rather than the investor —
the person who runs the pipeline and pays for it. That one fact drives the
structure (a verdict first, evidence after) and the colour freedom: the page
carries no signal pills and no price moves, so neither reserved palette is in
play and each metric can wear its own hue. Hue here says WHICH metric, never
whether the reading is good; a reader crossing from a green +9.4% on a Watchlist
row should not have to switch interpretive modes silently.

The page it replaces was telemetry — seven charts, 21 tiles, eight inline
tables, and nowhere a statement of whether anything was wrong.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.cards import render_section_head
from lib.charts import (
    CHART_LINE,
    METRIC_COLORS,
    PLOTLY_CONFIG,
    chart_data_table,
    style_fig,
)
from lib.data_loader import load_pipeline_stats, load_token_usage
from lib.pipeline_metrics import (
    RATE_HIT_NEW,
    RATE_HIT_OLD,
    RATE_MISS_NEW,
    RATE_MISS_OLD,
    REPRICE,
    THRESHOLDS,
    USD_TO_SGD,
    breached,
    cache_stats,
    cost_stats,
    overall_status,
    post_cutover,
    prompt_composition,
    reliability,
)


def _money(v, dp: int = 4) -> str:
    """USD value rendered in SGD (fixed USD_TO_SGD; stored figures stay USD).

    Entity dollar so Streamlit never parses a pair of them as LaTeX.
    """
    if v is None or pd.isna(v):
        return "—"
    return f"S&#36;{float(v) * USD_TO_SGD:,.{dp}f}"


def _sparkline(values, key: str, breach: bool) -> str:
    """Filled-area sparkline with an HTML endpoint dot.

    The wash matters: five bare lines read as five identical squiggles, whereas
    a filled silhouette gives each cell a shape you can tell apart peripherally.

    The dot is an HTML element over a position:relative, overflow:hidden wrapper
    rather than an SVG <circle>, because the SVG uses preserveAspectRatio:none —
    a circle inside it stretches into an oval as the cell widens and paints past
    the cell edge into the grid divider. An HTML element keeps a fixed pixel
    size at any cell width, and the wrapper's overflow clips anything that tries
    to escape.
    """
    vals = [float(v) for v in values if v is not None and not pd.isna(v)]
    if len(vals) < 2:
        return '<div class="pm-spark"></div>'
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)
    pts = [((i / (n - 1)) * 100.0, (1 - (v - lo) / span) * 100.0)
           for i, v in enumerate(vals)]
    line = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    area = f"0,100 {line} 100,100"
    hue = f"var(--metric-{key})" if not breach else "var(--stress)"
    return (
        f'<div class="pm-spark">'
        f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
        f'<polygon points="{area}" fill="{hue}" opacity="0.17"></polygon>'
        f'<polyline points="{line}" fill="none" stroke="{hue}" '
        f'stroke-width="1.75" vector-effect="non-scaling-stroke"></polyline>'
        f'</svg>'
        f'<span class="pm-dot" style="top:{pts[-1][1]:.2f}%;'
        f'border-color:{hue};"></span>'
        f'</div>'
    )


def _threshold_text(key: str, value) -> tuple[str, bool]:
    """('within ceiling $0.08', False) — the budget, and whether it is broken."""
    t = THRESHOLDS[key]
    limit = t["limit"]
    shown = {
        "cost": _money(limit, 3),
        "cache": f"{limit:.0%}",
        "input": f"{limit:,.0f}",
        "gen": f"{limit:,.0f}s",
        "articles": f"{limit:,.0f}",
    }[key]
    hit = breached(key, value)
    word = "over" if t["kind"] == "ceiling" else "under"
    return (f"{word if hit else 'within'} {t['kind']} {shown}", hit)


def _delta(latest, baseline) -> tuple[str, str]:
    """(arrow, magnitude) as a percent move against a stated baseline.

    Flat gets a neutral arrow: 'nothing happened' should not wear the accent.
    """
    if latest is None or baseline in (None, 0) or pd.isna(latest) or pd.isna(baseline):
        return "—", ""
    pct = (float(latest) - float(baseline)) / abs(float(baseline)) * 100.0
    if abs(pct) < 1.0:
        return "—", "flat"
    return ("▲" if pct > 0 else "▼"), f"{abs(pct):.0f}%"


def _cell_html(c: dict) -> str:
    """One strip cell: swatch + label → value → delta → trend → threshold.

    On a breach, rail, swatch, label, line, fill, dot, arrow, delta and the
    threshold line all flip to terracotta. If a breached cell kept its hue and
    only gained a glyph, the page's most important state would be its subtlest —
    the exception colour has to beat the identity colour.
    """
    state = ' data-breach="1"' if c["breach"] else ""
    arrow, mag = c["delta"]
    flat = ' data-flat="1"' if mag in ("", "flat") else ""
    warn = "⚠ " if c["breach"] else ""
    return (
        f'<div class="pm-cell" data-metric="{c["key"]}"{state}>'
        f'<div class="pm-cell-label"><span class="pm-swatch"></span>{c["label"]}</div>'
        f'<div class="pm-value">{c["value"]}'
        f'<span class="pm-unit">{c["unit"]}</span></div>'
        f'<div class="pm-delta"{flat}><span class="pm-arrow">{arrow}</span>'
        f'<span class="pm-mag">{mag}</span>'
        f'<span class="pm-basis">{c["basis"]}</span></div>'
        f'{_sparkline(c["series"], c["key"], c["breach"])}'
        f'<div class="pm-threshold">{warn}{c["threshold"]}</div>'
        f'</div>'
    )


def _verdict_html(word: str, key: str, thesis: str, rel: dict) -> str:
    """The one element that must not be skimmed past, so it is the one card.

    Everything below it is plain — that material is the evidence.
    """
    miss = (f' · {rel["missed"]} weekday{"s" if rel["missed"] != 1 else ""} '
            "with no run" if rel["missed"] else " · no weekday missed")
    warn = (f'<span class="pm-rel-warn">⚠ {rel["warnings"]:,} validator '
            f'warning{"s" if rel["warnings"] != 1 else ""} across '
            f'{rel["checks"]} checks on the latest run</span>'
            if rel["warnings"] else
            '<span class="pm-rel-ok">✓ no validator warnings on the latest run</span>')
    return (
        f'<div class="pm-verdict blueprint" data-status="{key}">'
        '<i class="corner tl"></i><i class="corner tr"></i>'
        '<i class="corner bl"></i><i class="corner br"></i>'
        f'<div class="pm-status"><span class="pm-status-dot"></span>'
        f'<span class="pm-status-word">{word}</span></div>'
        f'<div class="pm-thesis"><p>{thesis}</p>'
        f'<div class="pm-reliability">'
        f'<span class="pm-rel-ok">✓ {rel["runs"]} runs over {rel["weekdays"]} '
        f'weekdays{miss}</span>{warn}</div></div>'
        '</div>'
    )


def _composition_html(blocks: list[dict]) -> str:
    """Stacked bar + ranked rows for the prompt's shares of one run.

    A single-hue ramp is hard to discriminate at adjacent steps, so the encoding
    is made redundant rather than merely retuned: a wide 100→22 spread, hairline
    dividers in the page ground between segments, the percentage printed inside
    the three largest bands, and a per-row share bar underneath. Position,
    length and printed value all carry the same information, so matching a band
    to a row never depends on telling two blues apart.
    """
    steps = [100, 78, 56, 38, 22]
    segs = ""
    for i, b in enumerate(blocks):
        step = steps[min(i, len(steps) - 1)]
        label = (f'<span class="pm-seg-pct" data-ink="{"rev" if i < 2 else "dark"}">'
                 f'{b["share"]:.0f}%</span>') if i < 3 and b["share"] >= 8 else ""
        segs += (f'<span class="pm-seg" style="width:{b["share"]:.2f}%;'
                 f'--step:{step}%;">{label}</span>')

    rows = ""
    for i, b in enumerate(blocks):
        step = steps[min(i, len(steps) - 1)]
        rows += (
            f'<div class="pm-crow">'
            f'<span class="pm-rank">{i + 1}</span>'
            f'<span class="pm-cname">{b["name"]}</span>'
            f'<span class="pm-cbar"><span style="width:{b["share"]:.2f}%;'
            f'--step:{step}%;"></span></span>'
            f'<span class="pm-cpct">{b["share"]:.1f}%</span>'
            f'<span class="pm-cchars">{b["chars"]:,} chars</span>'
            f'<span class="pm-cnote">{b["note"]}</span>'
            f'</div>'
        )
    return (f'<div class="pm-compbar" role="img" aria-label="Prompt composition '
            f'by share">{segs}</div><div class="pm-crows">{rows}</div>')


_DIAGNOSIS = (
    '<div class="pm-diagnosis">'
    '<div class="pm-diag-head">If the ratio falls near zero</div>'
    '<p>The user prompt\'s first dynamic block is breaking the prefix '
    'immediately. Reorder the static blocks — <code>catalysts JSON</code>, '
    '<code>portfolio_count_directive</code>, <code>field-contracts</code>, '
    '<code>crisis_block</code> — above the <code>data_json</code> block, so the '
    'cacheable prefix extends past them.</p>'
    '<p class="pm-diag-note">Savings price each run at the cached-vs-uncached '
    'input delta of the card in force on its date — S&#36;0.26/MTok before '
    '17 Aug 2026, S&#36;0.82/MTok from the V4 repricing.</p>'
    '</div>'
)


def render_pipeline_stats_page(reports: dict) -> None:
    """Render the Pipeline health page.

    Args:
        reports: filtered reports dict (date-keyed). Its date span drives the
            range clip so the sidebar Range control actually applies here.
    """
    render_section_head(
        "Pipeline health",
        "Is the pipeline healthy, and is it costing what it should?",
        masthead=True,
    )

    _rk = sorted(reports.keys())
    _lo = pd.Timestamp(_rk[0]) if _rk else None
    _hi = pd.Timestamp(_rk[-1]) if _rk else None

    def _clip(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or _lo is None or "date" not in df.columns:
            return df
        return df[(df["date"] >= _lo) & (df["date"] <= _hi)]

    ps = _clip(load_pipeline_stats())
    tokens = _clip(load_token_usage())

    if ps.empty and tokens.empty:
        st.warning("No pipeline data in the selected date range.")
        return

    # Stated once, at the top, in a chip. The old page repeated "totals cover
    # the N reports in the selected range" under several sections while the
    # control itself lived in the sidebar; saying it once means every number
    # below inherits the scope without restating it.
    if _lo is not None:
        st.markdown(
            f'<div class="pm-range">Range · {_lo:%d %b %Y} → {_hi:%d %b %Y}</div>',
            unsafe_allow_html=True,
        )

    cost = cost_stats(ps)
    cache = cache_stats(ps)
    rel = reliability(ps)
    post = post_cutover(ps)
    tok_post = post_cutover(tokens)

    # ── The five metric identities ──
    cells = []
    if cost:
        series = list(cost["series"]["cost"].tail(28))
        thr, hit = _threshold_text("cost", cost["latest"])
        cells.append({
            "key": "cost", "label": "Cost / run",
            "value": _money(cost["latest"]), "unit": "",
            "delta": _delta(cost["latest"], cost["avg7"]),
            "basis": "vs 7-run avg", "series": series,
            "threshold": thr, "breach": hit, "near": False,
        })
    if cache:
        series = list(cache["series"]["ratio"].tail(28))
        thr, hit = _threshold_text("cache", cache["latest"])
        cells.append({
            "key": "cache", "label": "Cache hit",
            "value": f"{cache['latest'] * 100:.1f}", "unit": "%",
            "delta": _delta(cache["latest"], cache["mean"]),
            "basis": "vs avg", "series": series,
            "threshold": thr, "breach": hit, "near": False,
        })
        inp = cache["total_input"]
        thr, hit = _threshold_text("input", inp)
        cells.append({
            "key": "input", "label": "Input tokens",
            "value": f"{inp / 1000:.0f}", "unit": "k",
            "delta": _delta(inp, (post["cache_hit_tokens"].fillna(0)
                                  + post["cache_miss_tokens"].fillna(0)).mean()),
            "basis": "vs avg",
            "series": list((post["cache_hit_tokens"].fillna(0)
                            + post["cache_miss_tokens"].fillna(0)).tail(28)),
            "threshold": thr, "breach": hit, "near": False,
        })
    if not tok_post.empty and "generation_time_seconds" in tok_post.columns:
        g = pd.to_numeric(tok_post["generation_time_seconds"], errors="coerce").dropna()
        if len(g):
            thr, hit = _threshold_text("gen", g.iloc[-1])
            cells.append({
                "key": "gen", "label": "Gen time",
                "value": f"{g.iloc[-1]:.0f}", "unit": "s",
                "delta": _delta(g.iloc[-1], g.mean()), "basis": "vs avg",
                "series": list(g.tail(28)), "threshold": thr,
                "breach": hit, "near": False,
            })
    if not post.empty and "articles_after_filter" in post.columns:
        a = pd.to_numeric(post["articles_after_filter"], errors="coerce").dropna()
        if len(a):
            thr, hit = _threshold_text("articles", a.iloc[-1])
            cells.append({
                "key": "articles", "label": "Articles fed",
                "value": f"{a.iloc[-1]:.0f}", "unit": "",
                "delta": _delta(a.iloc[-1], a.mean()), "basis": "vs avg",
                "series": list(a.tail(28)), "threshold": thr,
                "breach": hit, "near": False,
            })

    word, status_key = overall_status(cells)
    if cost and cache:
        thesis = (f"Costing {_money(cost['latest'])} a run with "
                  f"{cache['latest']:.0%} of input served from cache — about "
                  f"{_money(cost['monthly'], 2)} a month at this cadence.")
    elif cost:
        thesis = (f"Costing {_money(cost['latest'])} a run — about "
                  f"{_money(cost['monthly'], 2)} a month at this cadence.")
    else:
        thesis = "No post-cutover cost telemetry in this range."

    st.markdown(_verdict_html(word, status_key, thesis, rel), unsafe_allow_html=True)
    if cells:
        st.markdown(
            '<div class="pm-strip">'
            + "".join(_cell_html(c) for c in cells)
            + "</div>",
            unsafe_allow_html=True,
        )

    # ── Unit cost ──
    if cost:
        render_section_head("Unit cost", "What a run costs, and what that is per month")
        st.markdown(
            '<div class="pm-tiles">'
            f'<div class="pm-tile" data-metric="cost"><div class="pm-tile-label">'
            f'Latest run</div><div class="pm-tile-val">{_money(cost["latest"])}'
            f'</div><div class="pm-tile-sub">7-run avg {_money(cost["avg7"])}</div></div>'
            f'<div class="pm-tile" data-metric="cost"><div class="pm-tile-label">'
            f'Run rate</div><div class="pm-tile-val">{_money(cost["monthly"], 2)}'
            f'<span class="pm-tile-unit">/mo</span></div>'
            f'<div class="pm-tile-sub">from {cost["runs"]} runs in range</div></div>'
            f'<div class="pm-tile" data-counterfactual="1"><div class="pm-tile-label">'
            f'Without cache</div><div class="pm-tile-val">'
            f'{_money(cost["monthly_uncached"], 2)}<span class="pm-tile-unit">/mo</span>'
            f'</div><div class="pm-tile-sub" data-metric="cache">cache saves '
            f'{_money(cost["saving_per_run"])} a run</div></div>'
            # "Spent in range", not "since cutover": every figure on this page
            # inherits the range chip at the top, and this one is no exception.
            # Labelling a range-clipped total as a lifetime total is the same
            # class of error as the cumsum this redesign fixed.
            f'<div class="pm-tile"><div class="pm-tile-label">Spent in range'
            f'</div><div class="pm-tile-val">{_money(cost["total"], 2)}</div>'
            f'<div class="pm-tile-sub">post-cutover runs only</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        last28 = cost["series"].tail(28).copy()
        last28["cost"] = last28["cost"] * USD_TO_SGD   # display currency
        med = float(last28["cost"].median())
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=last28["date"], y=last28["cost"], name="Cost / run",
            marker_color=METRIC_COLORS["cost"],
            # Opacity carries the outlier read without spending a second colour:
            # the trend and the expensive runs come out of one series.
            marker_opacity=[0.95 if v > med else 0.62 for v in last28["cost"]],
        ))
        fig.add_trace(go.Scatter(
            x=last28["date"],
            y=last28["cost"].rolling(7, min_periods=1).mean(),
            mode="lines", name="7-run avg",
            line=dict(color=CHART_LINE, width=2),
        ))
        fig.update_layout(
            yaxis_title="SGD / run", height=260,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(style_fig(fig), use_container_width=True, config=PLOTLY_CONFIG)
        st.caption(
            "Cost per run, last 28 post-cutover runs. Bars above the median "
            "carry full opacity."
        )
        chart_data_table(last28)

        # Pre-cutover rows are quarantined rather than deleted: the record is
        # preserved, the arithmetic is not corrupted. A running total spanning
        # two pricing regimes is not a number.
        pre = ps[ps["date"] < pd.Timestamp("2026-05-05")].dropna(
            subset=["computed_cost_usd"])
        if not pre.empty:
            with st.expander(
                f"Pre-cutover history · {len(pre)} runs, excluded from every "
                "figure above"
            ):
                st.caption(
                    "Runs before 2026-05-05 were priced with Sonnet+Haiku "
                    "constants and overstate spend roughly 10x. They are kept "
                    "for the record and excluded from every total, average and "
                    "projection on this page — averaging across two pricing "
                    "regimes produces a number that describes neither."
                )
                st.dataframe(
                    pre[["date", "computed_cost_usd"]],
                    width="stretch", hide_index=True,
                )

    # ── Prompt cache ──
    if cache:
        render_section_head("Prompt cache", "How much input is served from the cached prefix")
        verdict = ("Working as intended" if cache["latest"] >= 0.5
                   else "Degraded" if cache["latest"] >= THRESHOLDS["cache"]["limit"]
                   else "Broken")
        st.markdown(
            f'<p class="pm-lede">{verdict} — {cache["latest"]:.1%} of input '
            "tokens are being served from the cached prefix.</p>",
            unsafe_allow_html=True,
        )
        hit_pct = cache["latest"] * 100
        # Rate labels follow the card in force on the latest run's date, so
        # the legend stays truthful on both sides of the 08-17 repricing.
        _new_card = (cache.get("latest_date") is not None
                     and cache["latest_date"] >= REPRICE)
        _r_hit = RATE_HIT_NEW if _new_card else RATE_HIT_OLD
        _r_miss = RATE_MISS_NEW if _new_card else RATE_MISS_OLD
        st.markdown(
            f'<div class="pm-cachebar">'
            f'<span class="pm-cache-hit" style="width:{hit_pct:.2f}%;"></span>'
            f'<span class="pm-cache-miss" style="width:{100 - hit_pct:.2f}%;"></span>'
            f'</div>'
            f'<div class="pm-cachelegend">'
            f'<span data-metric="cache">{cache["hit_tokens"]:,} hit · '
            f'S&#36;{_r_hit * USD_TO_SGD:.3f}/MTok</span>'
            f'<span>{cache["miss_tokens"]:,} miss · '
            f'S&#36;{_r_miss * USD_TO_SGD:.2f}/MTok</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns([0.54, 0.46], vertical_alignment="top")
        with left:
            st.markdown(
                '<div class="pm-tiles pm-tiles-3">'
                f'<div class="pm-tile" data-metric="cache"><div class="pm-tile-label">'
                f'Latest</div><div class="pm-tile-val">{cache["latest"]:.1%}</div></div>'
                f'<div class="pm-tile" data-metric="cache"><div class="pm-tile-label">'
                f'Average</div><div class="pm-tile-val">{cache["mean"]:.1%}</div>'
                f'<div class="pm-tile-sub">a single day can mislead</div></div>'
                f'<div class="pm-tile" data-metric="cache"><div class="pm-tile-label">'
                f'Saved to date</div><div class="pm-tile-val">'
                f'{_money(cache["saved_total"], 2)}</div></div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with right:
            # Visible even while the cache is healthy: it is the runbook entry
            # for the failure mode, and it is needed at the moment it breaks —
            # exactly when nobody wants to go hunting for it.
            st.markdown(_DIAGNOSIS, unsafe_allow_html=True)

    # ── What's in the prompt ──
    blocks = prompt_composition(ps)
    if blocks:
        render_section_head("What's in the prompt", "Where the input tokens go")
        st.markdown(
            '<p class="pm-lede">Input size is what drives unit cost, so this is '
            "the lever. Shown as shares of the latest run rather than five time "
            "series: the question is what dominates, not how each moved.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(_composition_html(blocks), unsafe_allow_html=True)
        cols = [c for c in ("date", "system_prompt_chars", "watchlist_data_chars",
                            "tavily_chars", "yfinance_chars", "memory_chars")
                if c in post.columns]
        with st.expander("Composition over time"):
            st.caption(
                "The secondary question — how each block moved — kept out of "
                "the way of the primary one."
            )
            st.dataframe(post[cols].tail(28), width="stretch", hide_index=True)

    # ── Ingest volume ──
    if not post.empty and "articles_fetched" in post.columns:
        render_section_head("Ingest volume", "Where the article counts come from")
        latest = post.iloc[-1]

        def _n(col):
            v = pd.to_numeric(latest.get(col), errors="coerce")
            return "—" if pd.isna(v) else f"{v:,.0f}"

        st.markdown(
            '<div class="pm-ingest">'
            f'<div class="pm-irow"><span>{_n("articles_fetched")}</span>'
            '<b>Fetched</b><i>Everything Tavily returned for the day\'s queries</i></div>'
            f'<div class="pm-irow"><span>{_n("articles_after_filter")}</span>'
            '<b>After filter</b><i>What survived relevance and dedup — this is '
            'what reaches the prompt</i></div>'
            f'<div class="pm-irow"><span>{_n("articles_blocked")}</span>'
            '<b>Blocked</b><i>Dropped by the source blocklist</i></div>'
            f'<div class="pm-irow"><span>{_n("yfinance_articles")}</span>'
            '<b>yFinance</b><i>Per-ticker headlines, fetched separately</i></div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # The honest cost of giving one page its own palette: a reader arriving from
    # the Watchlist needs to know the rules changed, and this is where it is paid.
    st.markdown(
        '<div class="pm-footer">No signal colours and no up/down green-red '
        "appear on this page. Each hue identifies a metric; terracotta means a "
        "reading is outside its budget.</div>",
        unsafe_allow_html=True,
    )
