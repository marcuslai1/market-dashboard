"""Watchlist grid builders — pure HTML, no Streamlit.

Everything the dense grid needs except the row itself: the fixed display order
(cluster groups), the column header, the group headers, the single wrapper blob,
and the two pieces of footnote copy.

**Information only since 2026-10-01** (MarketReport spec
2026-10-01-info-only-watchlist, O1 / O6; tag ``pre-label-removal``). The signal
groups, the signal filter chips, the ● Changed marker and the "day N" count went
with the labels; every report date — old ones included — renders facts only.

Two constructions here are load-bearing and easy to break:

1. **One blob.** The column header, every group header and every row are emitted
   in ONE string, because a ``<div>`` opened in one ``st.markdown`` and closed in
   another does not wrap sibling Streamlit blocks — the browser auto-closes it,
   and ``.tk-scroll`` stops containing the rows.
2. **A fixed order.** The rows never re-sort by a daily quantity. The order is a
   rule (``ordered_groups``), so a new ticker slots itself in with no upkeep.
   (The experimental growth sort, ``components.watchlist.growth``, is a separate
   view a reader asks for; it sorts by quarterly sales figures, never a price.)
"""
from __future__ import annotations

import statistics
from collections.abc import Callable

from lib.catalog import CLUSTER_MAP, RETIRED_TICKERS
from lib.formatters import _escape_dollars, _fmt_num, _sign, display_ticker

#: The group a name with no cluster lands in. Always last, whatever its size.
OTHER_CLUSTER = "Other"

#: (label, alignment). Order is the grid's own; the phone-width labels in
#: theme.css (``nth-child`` 2–7) must follow it.
_COLUMNS: list[tuple[str, str]] = [
    ("Ticker", "left"),
    ("Last · Δ", "right"),
    ("5 d", "right"),
    ("1 mo", "right"),
    ("vs 50-day", "center"),
    ("RSI", "right"),
    ("Earnings", "right"),
]


def cluster_of(tk: str, d: dict) -> str:
    """The report's own ``cluster`` (post-cutover), else the catalog's."""
    return (d or {}).get("cluster") or CLUSTER_MAP.get(tk) or OTHER_CLUSTER


def ordered_groups(watchlist: dict) -> list[tuple[str, list[tuple[str, dict]]]]:
    """``[(cluster, [(ticker, entry), …]), …]`` in the fixed display order.

    The rule (spec §4, O1): cluster groups, largest first, then by name; names
    A–Z by display ticker inside a group; retired names excluded.

    A post-cutover report stamps ``cluster`` on every entry and is already in
    this order (the pipeline's ``display_order``), so its JSON order is used as
    is — consecutive names of one cluster form a group. A report without the
    stamp gets the same rule applied here from ``assets/catalog.json``.
    """
    items = [(tk, d) for tk, d in (watchlist or {}).items() if tk not in RETIRED_TICKERS]
    if items and all((d or {}).get("cluster") for _, d in items):
        groups: list[tuple[str, list[tuple[str, dict]]]] = []
        for tk, d in items:
            c = d["cluster"]
            if groups and groups[-1][0] == c:
                groups[-1][1].append((tk, d))
            else:
                groups.append((c, [(tk, d)]))
        return groups
    by_cluster: dict[str, list[tuple[str, dict]]] = {}
    for tk, d in items:
        by_cluster.setdefault(cluster_of(tk, d), []).append((tk, d))
    for rows in by_cluster.values():
        rows.sort(key=lambda row: display_ticker(row[0]).upper())
    return sorted(
        by_cluster.items(),
        key=lambda kv: (kv[0] == OTHER_CLUSTER, -len(kv[1]), kv[0].casefold()),
    )


def column_header_html() -> str:
    """The column labels.

    Two rule weights, on purpose (see ``.tk-row.tk-head`` in theme.css): a
    strong top rule opens the data zone, a faint bottom rule only separates
    labels from rows.
    """
    cells = "".join(
        f'<div role="columnheader" class="tk-h-{align}">{label}</div>'
        for label, align in _COLUMNS
    )
    return f'<div class="tk-row tk-head" role="row">{cells}</div>'


#: (report field, label, decimals) for the group header's cluster move — the
#: same three windows as the row's Δ / 5 d / 1 mo cells.
_MOVE_FIELDS: list[tuple[str, str, int]] = [
    ("chg_pct", "day", 2),
    ("5d_pct", "5 d", 1),
    ("1mo_pct", "1 mo", 1),
]


def cluster_move(rows: list[tuple[str, dict]]) -> dict[str, float]:
    """``{field: median}`` of the members' day / 5-day / 1-month moves.

    The median, not the mean, and over the same members, because it is the
    baseline the pipeline's own ``vs_cluster_*`` deltas are measured against
    (MarketReport ``report_data_narrative._inject_cluster_relative_strength``):
    a name's "vs cluster · day" in its drill-down is its Δ minus this figure. A
    window with fewer than two numeric values is left out — a one-name median is
    the row itself.
    """
    out: dict[str, float] = {}
    for field, _, _ in _MOVE_FIELDS:
        values = [v for v in ((d or {}).get(field) for _, d in rows)
                  if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v]
        if len(values) >= 2:
            out[field] = statistics.median(values)
    return out


def group_header_html(cluster: str, count: int, move: dict | None = None) -> str:
    """Name + count + a hairline that fills the width + the cluster's move.

    Neutral ink, the move included: a cluster is a grouping, not a rating, and
    the header is a divider, not a cell — the rows below carry the up/down
    colour. 11px uppercase, not a real heading size — these are dividers inside
    ONE table, not sections of a document.
    """
    move = move or {}
    parts = [f'{label} {_sign(move[field])}{_fmt_num(move[field], dec)}%'
             for field, label, dec in _MOVE_FIELDS if field in move]
    move_html = (
        f'<span class="tk-group-move">median · {" · ".join(parts)}</span>' if parts else ""
    )
    return (
        '<div class="tk-group" role="row">'
        f'<span class="tk-group-name">{_escape_dollars(cluster)}</span>'
        f'<span class="tk-group-count">{count}</span>'
        '<span class="tk-group-rule"></span>'
        f'{move_html}'
        '</div>'
    )


def build_grid_html(
    groups,
    earnings_map: dict,
    row_builder: Callable[..., str],
    report_date: str | None = None,
    price_map: dict | None = None,
    profile_map: dict | None = None,
) -> str:
    """The whole table as one string: wrapper, column header, groups, rows.

    ``earnings_map`` / ``price_map`` / ``profile_map`` are per-ticker side data
    (earnings history, price history, company card) handed to each row's drill-down."""
    parts = [column_header_html()]
    for cluster, rows in groups:
        parts.append(group_header_html(cluster, len(rows), cluster_move(rows)))
        for tk, d in rows:
            parts.append(row_builder(tk, d,
                                     earnings_hist=(earnings_map or {}).get(tk),
                                     report_date=report_date,
                                     price_hist=(price_map or {}).get(tk),
                                     profile=(profile_map or {}).get(tk)))
    return (
        '<div class="tk-scroll" role="table" '
        'aria-label="Watchlist — click a row to expand">'
        f'{"".join(parts)}</div>'
    )


def method_note_html() -> str:
    """The pieces of encoding a reader cannot infer from looking."""
    return (
        '<div class="tk-method">'
        '<b>vs 50-day</b> is the distance of the last price from its 50-day '
        'average; the bar is centred on zero and clamps at ±20%, the figure '
        'beneath is exact. <b>RSI</b> is the 14-session relative strength index. '
        '<b>Earnings</b> is the next report date and the calendar days to it.'
        '</div>'
    )


def footer_html(n_names: int, n_groups: int) -> str:
    """The page's own count and order statement."""
    return (
        '<div class="tk-foot">'
        f'{n_names} names in {n_groups} groups · facts only, no ratings · '
        'retired names excluded'
        '</div>'
    )
