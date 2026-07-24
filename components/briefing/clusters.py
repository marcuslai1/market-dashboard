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

from lib.cards import card_container, render_section_head
from lib.catalog import SIGNAL_COLORS, SIGNAL_ORDER
from lib.formatters import _escape_dollars, _fmt_num, _sign, display_ticker
from lib.pills import _signal_pill_html, signal_text_color


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
            f"<tr><td>{_escape_dollars(display_ticker(_norm(tk)))}</td>"
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
        # "extended" not "ext." + a title gloss: the abbreviation had no
        # expansion anywhere at point of use (casual-reader review 2026-07-12).
        tip = (
            f"{n} of {total} names here are hard-blocked from entry: "
            "price is stretched too far above its 50-day trend line"
        )
        chips.append(
            f'<span class="cl-chip cl-ext"{warn} title="{tip}">'
            f"{n}/{total}&nbsp;extended</span>"
        )
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


# Single-letter count tags. ACCUMULATE and AVOID both start with "A", so AVOID
# takes X rather than a silently-colliding letter.
_SIG_TAG = {"BUY": "B", "ACCUMULATE": "A", "WATCH": "W",
            "HOLD": "H", "CAUTION": "C", "AVOID": "X"}


def cluster_anchor_count(clusters: dict) -> int:
    """Total names across all clusters — the figure the modal trigger cites."""
    return sum(
        len(c.get("tickers") or [])
        for c in (clusters or {}).values() if isinstance(c, dict)
    )


def clusters_strip_html(clusters: dict, watchlist: dict, extension_regime=None) -> str:
    """The Briefing's Clusters card — one row per group, verdict-first.

    Row anatomy (design revision 2026-07-24): a 3px left rail in the group's
    DOMINANT signal colour (the row *is* the group, so the whole edge carries
    its state — you scan the left margin and see the shape before reading a
    word), then a fixed 130px name / flexible distribution bar / 62px extension
    grid, then the punch line and its note.

    The distribution bar is a legitimate use of signal hues: it is literally a
    count of signals. Widths are proportional, and the counts beside it repeat
    the figure exactly — redundant encoding, so the bar gives proportion at a
    glance and the number gives precision for anyone who wants it.
    """
    if not clusters:
        return ""
    rows = ""
    for name, c in clusters.items():
        if not isinstance(c, dict):
            continue
        tickers = c.get("tickers", []) or []
        mix = _signal_mix(tickers, watchlist)
        total = sum(n for _s, n in mix) or 1
        dominant = max(mix, key=lambda kv: kv[1])[0] if mix else ""
        rail = SIGNAL_COLORS.get(dominant, "var(--color-divider)")

        segments = "".join(
            f'<span style="width:{(n / total) * 100:.4f}%;'
            f'background:{SIGNAL_COLORS.get(sig, "var(--color-text-4)")};"></span>'
            for sig, n in mix
        )
        counts = "".join(
            f'<b style="color:{signal_text_color(sig)};">{n}{_SIG_TAG.get(sig, "?")}</b>'
            for sig, n in mix
        )

        ext_html = ""
        breadth = _extension_breadth(tickers, extension_regime)
        if breadth is not None:
            n_ext, n_tot = breadth
            warn = ' data-warn="1"' if n_ext else ""
            ext_html = f'<div class="clx-ext"{warn}>{n_ext}/{n_tot}&nbsp;ext</div>'

        punch = c.get("thesis_status") or c.get("key_development") or ""
        note = c.get("key_development") if c.get("thesis_status") else c.get("summary")
        rows += (
            f'<div class="clx-row" style="border-left-color:{rail};">'
            f'<div class="clx-name">'
            f'{_escape_dollars(str(name).replace("_", " "))}</div>'
            f'<div class="clx-bar">'
            f'<span class="clx-track">{segments}</span>'
            f'<span class="clx-counts">{counts}</span>'
            f'</div>'
            f'{ext_html or "<div></div>"}'
            + (f'<div class="clx-punch">{_escape_dollars(punch)}</div>' if punch else "")
            + (f'<div class="clx-note">{_escape_dollars(note)}</div>' if note else "")
            + '</div>'
        )
    return card_container(
        eyebrow='Clusters<span class="eb-sub"> · where each group stands</span>',
        headline="",
        body_html=rows,
        lane="lede",
    )


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
