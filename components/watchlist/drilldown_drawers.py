"""The drill-down's Earnings drawer, plus the catalyst line the card reuses.

**One drawer since 2026-10-01** (MarketReport spec 2026-10-01-info-only-watchlist
§8, O6; tag ``pre-label-removal``). The "Risk & reward detail" drawer (prose exits,
the three R:R figures) and the "Pipeline detail" drawer (ACCUMULATE gates, Regime
Change Pending, the AVOID citation, the catalyst entry path) were label machinery
and went with the labels. Their one fact, the key levels, moved up to the card's
levels ladder; the earnings-result headline moved into this drawer.

Raw ``<details>`` rather than ``st.expander``: this lives *inside* a
markdown-injected ``<details>``, where a Streamlit expander cannot go. A drawer
with nothing inside does not render at all.
"""
from __future__ import annotations

from components.earnings_chart import (
    block_html,
    eps_chart_html,
    eps_currency,
    quarter_series,
    revenue_chart_html,
    revenue_currency,
)
from components.watchlist.earnings_history import _earnings_history_html
from lib.formatters import _escape_dollars, _fmt_num, _safe_href, _sign
from lib.next_earnings import days_phrase, next_earnings, short_date

#: Data-quality warnings take terracotta — the site's data-condition colour.
STRESS = "var(--stress)"


def _drilldown_section_html(title: str) -> str:
    return f'<div class="dd-section">{title}</div>'


def _drilldown_metrics_html(items: list[tuple]) -> str:
    """Metric grid. Items are ``(label, value)`` or ``(label, value, colour)``.

    The optional third element tints the VALUE with the price up/down palette —
    an "avg down move" reads as a down move. Never a rating colour.
    """
    visible = [it for it in items if it[1] not in (None, "", "—")]
    if not visible:
        return ""
    cells = ""
    for item in visible:
        label, value = item[0], item[1]
        colour = item[2] if len(item) > 2 else ""
        style = f' style="color:{colour};"' if colour else ""
        cells += (
            f'<div class="dd-metric"><div class="lbl">{label}</div>'
            f'<div class="val"{style}>{value}</div></div>'
        )
    return f'<div class="dd-metric-grid">{cells}</div>'


def _drawer(summary: str, body: str) -> str:
    """One collapsed drawer, or "" when nothing inside it populated."""
    if not body:
        return ""
    return (
        f'<details class="dd-drawer"><summary>{summary}</summary>'
        f'<div class="dd-drawer-body">{body}</div></details>'
    )


def _link_html(url) -> str:
    href = _safe_href(url or "")
    return (
        f' <a href="{href}" target="_blank" rel="noopener noreferrer" '
        f'style="color:var(--ink-3);font-family:var(--mono);font-size:11px;">[link]</a>'
        if href else ""
    )


# ── Earnings ──────────────────────────────────────────────────────────────────

def _band_html(band: dict, price_fn) -> str:
    """The pre-print band: the name's own past reactions, projected onto today's
    price. No archetype — the "priced for perfection / low bar" tag was an
    interpretive reading of extension and RSI, not a fact."""
    n_priors = band.get("n_priors")
    avg_up = band.get("avg_up_pct")
    avg_dn = band.get("avg_down_pct")
    max_up = band.get("max_up_pct")
    max_dn = band.get("max_down_pct")
    impl_up = band.get("implied_upper")
    impl_lo = band.get("implied_lower")
    temporal_phrase = band.get("temporal_phrase") or ""
    parts = [_drilldown_section_html(
        f"Past earnings reactions — {_escape_dollars(temporal_phrase)}"
        if temporal_phrase else "Past earnings reactions")]
    if avg_up is not None and impl_up is not None:
        parts.append(
            '<div class="dd-line"><strong style="color:var(--up);">Average up move.</strong> '
            f'{price_fn(impl_up)} ({_sign(avg_up)}{_fmt_num(avg_up, 1)}% avg of '
            f'{n_priors} prior prints)</div>'
        )
    if avg_dn is not None and impl_lo is not None:
        parts.append(
            '<div class="dd-line"><strong style="color:var(--down);">Average down move.</strong> '
            f'{price_fn(impl_lo)} ({_fmt_num(avg_dn, 1)}% avg of {n_priors} prior prints)</div>'
        )
    if avg_up is None and avg_dn is not None:
        parts.append(
            f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
            f'All {n_priors} prior prints moved down — no up-side reference.</div>'
        )
    if avg_dn is None and avg_up is not None:
        parts.append(
            f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
            f'All {n_priors} prior prints moved up — no down-side reference.</div>'
        )
    parts.append(_drilldown_metrics_html([
        ("Avg up move",
         f"{_sign(avg_up)}{_fmt_num(avg_up, 1)}%" if avg_up is not None else "—",
         "var(--up)"),
        ("Avg down move",
         f"{_fmt_num(avg_dn, 1)}%" if avg_dn is not None else "—",
         "var(--down)"),
        ("Max up move",
         f"{_sign(max_up)}{_fmt_num(max_up, 1)}%" if max_up is not None else "—",
         "var(--up)"),
        ("Max down move",
         f"{_fmt_num(max_dn, 1)}%" if max_dn is not None else "—",
         "var(--down)"),
    ]))
    return "".join(parts)


def _earnings_result_html(d: dict) -> str:
    """The headline that reported the print, when the news carried one."""
    ern = d.get("earnings_results_in_news")
    if not isinstance(ern, dict) or not ern.get("headline"):
        return ""
    html = f'<div class="dd-line">"{_escape_dollars(ern["headline"])}"'
    if ern.get("source"):
        html += (f' <span style="color:var(--ink-3);">— '
                 f'{_escape_dollars(ern["source"])}</span>')
    return _drilldown_section_html("Earnings result") + html + _link_html(ern.get("url")) + '</div>'


def _earnings_body_html(d: dict, price_fn, earnings_hist, report_date=None) -> str:
    """Next report date → the pre-print band → the result headline → the
    quarter charts → the quarter-on-quarter history. Each is silent when absent."""
    parts: list[str] = []
    ne = next_earnings(d, report_date)
    if ne is not None:
        when = "not available — the earnings calendar could not be read" \
            if ne.when is None else f"{short_date(ne.when)} {ne.when.year} · {days_phrase(ne)}"
        # Whose date it is (MarketReport 2026-10-10): Yahoo's own estimate, or
        # the company's notice. Plain words, no colour.
        if ne.when is not None and ne.estimated:
            when += " — Yahoo's estimate; the company has not announced the date"
        elif ne.when is not None and ne.confirmed:
            when += " — date confirmed by the company"
        parts.append(f'<div class="dd-line"><strong>Next report.</strong> {when}</div>')
    band = d.get("pre_earnings_band") or {}
    if band:
        parts.append(_band_html(band, price_fn))
    parts.append(_earnings_result_html(d))
    if earnings_hist:
        key = str((earnings_hist[0] or {}).get("ticker") or "")
        s = quarter_series(earnings_hist)
        charts = revenue_chart_html(s, revenue_currency(key)) + eps_chart_html(s, eps_currency(key))
        if charts:
            parts.append(_drilldown_section_html("Revenue and earnings per share by quarter"))
            parts.append(block_html(charts))
    eh = _earnings_history_html(earnings_hist) if earnings_hist else ""
    if eh:
        parts.append(_drilldown_section_html("Earnings history"))
        parts.append(eh)
    return "".join(parts)


# ── Catalyst (rendered in the card's News & context block) ────────────────────

def catalyst_html(d: dict) -> str:
    """The catalyst headline, source, link and date — facts only.

    Narrative-only in the pipeline since 2026-05-30; reports before that carry
    an entry-path shape (catalyst R:R, gap-fill stop, position tier). Those were
    label machinery and are not rendered for any date.
    """
    catalyst = d.get("catalyst") or {}
    if not isinstance(catalyst, dict):
        return ""
    headline = (catalyst.get("catalyst_event") or catalyst.get("headline")
                or catalyst.get("description") or "")
    if not headline:
        return ""
    c_type = str(catalyst.get("type") or catalyst.get("catalyst_type") or "").replace("_", " ")
    source = catalyst.get("catalyst_source") or catalyst.get("source") or ""
    when = (catalyst.get("catalyst_date") or catalyst.get("date")
            or catalyst.get("event_date") or "")
    html = '<div class="dd-line">'
    if c_type:
        html += f'<strong>{_escape_dollars(c_type.capitalize())}.</strong> '
    html += _escape_dollars(headline)
    if source:
        html += f' <span style="color:var(--ink-3);">— {_escape_dollars(source)}</span>'
    if when:
        html += f' <span style="color:var(--ink-3);">· {_escape_dollars(when)}</span>'
    return html + _link_html(catalyst.get("url")) + '</div>'


# ── Public entry point ────────────────────────────────────────────────────────

def render_drawers_html(d: dict, price_fn, earnings_hist=None,
                        report_date: str | None = None) -> str:
    """The Earnings drawer, or "" when it would be empty.

    ``price_fn`` is the caller's currency-aware price formatter, passed in rather
    than rebuilt so KRW names format the same here as in the card above.
    """
    return _drawer("Earnings", _earnings_body_html(d, price_fn, earnings_hist, report_date))
