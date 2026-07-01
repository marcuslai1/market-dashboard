"""Briefing · Cluster band.

Surfaces the per-cluster analysis the pipeline writes into every report under
the top-level ``clusters`` key (summary / thesis_status / key_development /
data_anchors) — previously computed daily and rendered nowhere (review finding
P1-2). Each cluster is a collapsible row: the pipeline's prose paired with a
computed at-a-glance (signal mix + extension breadth) derived from the cluster's
own watchlist names.
"""
from __future__ import annotations

from collections import Counter

import streamlit as st

from lib.cards import render_section_head
from lib.catalog import SIGNAL_ORDER, TICKER_DISPLAY
from lib.formatters import _escape_dollars, _fmt_num, _sign
from lib.pills import _signal_pill_html


def _norm(ticker: str) -> str:
    """Anchor / blocked-ticker key form: dotted ticker -> underscore form."""
    return str(ticker).replace(".", "_")


def _signal_mix(tickers: list, watchlist: dict) -> list:
    """Signal -> count across *tickers*, ordered best->worst per SIGNAL_ORDER.

    Null/absent signals (and tickers missing from *watchlist*) fall into a
    ``"—"`` bucket that sorts last.
    """
    counts: Counter = Counter()
    for tk in tickers:
        sig = (watchlist.get(_norm(tk)) or {}).get("signal")
        counts[sig if sig else "—"] += 1
    ordered = [(s, counts[s]) for s in SIGNAL_ORDER if counts.get(s)]
    if counts.get("—"):
        ordered.append(("—", counts["—"]))
    return ordered


def _extension_breadth(tickers: list, extension_regime) -> tuple | None:
    """(#hard-blocked-for-extension, #members), or None when no regime data.

    Uses ``extension_regime['blocked_tickers']`` (underscore key form) as the
    precise source. Returns None when the regime block is absent so the caller
    omits the chip rather than guessing.
    """
    if not extension_regime:
        return None
    blocked = {str(t) for t in (extension_regime.get("blocked_tickers") or [])}
    n = sum(1 for tk in tickers if _norm(tk) in blocked)
    return (n, len(tickers))


def _anchor_table_html(cluster: dict, watchlist: dict) -> str:
    """A .ep-table of ticker -> live signal pill, vs-50, RSI (or '' if none)."""
    anchors = cluster.get("data_anchors") or {}
    if not anchors:
        return ""
    rows = []
    for tk in cluster.get("tickers", []) or []:
        a = anchors.get(_norm(tk))
        if not a:
            continue
        sig = (watchlist.get(_norm(tk)) or {}).get("signal")
        pill = _signal_pill_html(sig, small=True) if sig else "—"
        vs50 = a.get("vs_sma50_pct")
        rsi = a.get("rsi_14")
        vs50_str = f"{_sign(vs50)}{_fmt_num(vs50, 1)}%" if vs50 is not None else "—"
        rows.append(
            f"<tr><td>{_escape_dollars(TICKER_DISPLAY.get(_norm(tk), tk))}</td>"
            f"<td>{pill}</td>"
            f'<td class="num">{vs50_str}</td>'
            f'<td class="num">{_fmt_num(rsi, 0)}</td></tr>'
        )
    if not rows:
        return ""
    return (
        '<div class="tk-scroll"><table class="ep-table cl-anchors">'
        "<thead><tr><th>Ticker</th><th>Signal</th>"
        '<th class="num">vs 50</th><th class="num">RSI</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _glance_html(tickers: list, watchlist: dict, extension_regime) -> str:
    """Computed at-a-glance chips: signal mix, then extension breadth."""
    chips = [
        f'<span class="cl-chip">{n}&nbsp;{_escape_dollars(sig)}</span>'
        for sig, n in _signal_mix(tickers, watchlist)
    ]
    breadth = _extension_breadth(tickers, extension_regime)
    if breadth is not None:
        n, total = breadth
        warn = ' data-warn="1"' if n else ""
        chips.append(f'<span class="cl-chip cl-ext"{warn}>{n}/{total}&nbsp;ext.</span>')
    return f'<span class="cl-glance">{"".join(chips)}</span>'


def _cluster_details_html(name: str, cluster: dict, watchlist: dict,
                          extension_regime) -> str:
    tickers = cluster.get("tickers", []) or []
    dev = cluster.get("key_development") or ""
    summary = cluster.get("summary") or ""
    thesis = cluster.get("thesis_status") or ""
    dev_html = f'<span class="cl-dev">{_escape_dollars(dev)}</span>' if dev else ""
    body = []
    if thesis:
        body.append(f'<p class="cl-thesis">{_escape_dollars(thesis)}</p>')
    if summary:
        body.append(f'<p class="cl-sum">{_escape_dollars(summary)}</p>')
    body.append(_anchor_table_html(cluster, watchlist))
    return (
        '<details class="cl-details"><summary class="cl-summary">'
        f'<span class="cl-name">{_escape_dollars(str(name).replace("_", " ").title())}</span>'
        f"{_glance_html(tickers, watchlist, extension_regime)}{dev_html}"
        f'</summary><div class="cl-body">{"".join(body)}</div></details>'
    )


def _clusters_html(clusters: dict, watchlist: dict, extension_regime=None) -> str:
    if not clusters:
        return '<div class="cl-band cl-empty">No cluster breakdown in this report.</div>'
    blocks = [
        _cluster_details_html(name, c, watchlist, extension_regime)
        for name, c in clusters.items()
        if isinstance(c, dict)
    ]
    if not blocks:
        return '<div class="cl-band cl-empty">No cluster breakdown in this report.</div>'
    return f'<div class="cl-band">{"".join(blocks)}</div>'


def render_clusters(clusters: dict, watchlist: dict, extension_regime=None) -> None:
    """Briefing cluster band — the daily per-cluster analysis (review P1-2).

    Silent when the report carries no ``clusters`` block (older reports); on the
    latest report this is always present.
    """
    if not clusters:
        return
    render_section_head("Clusters", "Where each group stands today")
    st.markdown(
        _clusters_html(clusters, watchlist, extension_regime),
        unsafe_allow_html=True,
    )
