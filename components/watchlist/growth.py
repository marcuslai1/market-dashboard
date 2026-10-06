"""The Watchlist's experimental growth sort — pure HTML, no Streamlit.

Owner decision 2026-10-06 (MarketReport PIPELINE_FEATURES §125; spec
2026-10-06-growth-types, "Dashboard"). By default the Watchlist keeps its one fixed
cluster order (MarketReport spec 2026-10-01-info-only-watchlist, O1). A reader can ask
for the rows sorted by sales growth instead — the two-year average, or the latest
quarter — and each row then carries a growth line: both figures and the operating
margin a year earlier → now, so a company whose latest quarter turned (a loss a year
ago, a profit now) shows it even when it is not near the top.

Numbers only: no rank number, no growth type, no colour. A sales figure is a fact,
not a verdict, and the sort is the reader's choice, not the page's. The figures come
from MarketReport's ``growth_types.json`` through ``scripts/growth_types.py publish``
(``data/growth.json``); they carry their own ``as_of`` date and are the same for
every report date.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from components.watchlist.grid import column_header_html
from lib.catalog import RETIRED_TICKERS
from lib.formatters import _fmt_num, _sign, display_ticker

#: The order control's options. The default comes first.
ORDER_CLUSTERS = "Clusters"
ORDER_TWO_YEAR = "Sales growth · 2-year (experimental)"
ORDER_QUARTER = "Sales growth · latest quarter (experimental)"
ORDERS = [ORDER_CLUSTERS, ORDER_TWO_YEAR, ORDER_QUARTER]

#: Which figure each sort uses.
SORT_FIELD = {ORDER_TWO_YEAR: "avg2y", ORDER_QUARTER: "latest_q"}

_SORT_BASIS = {
    "avg2y": ("two-year average sales growth: last full year's sales to analysts' forecast "
              "for next year, % a year"),
    "latest_q": ("the latest reported quarter's sales against the same quarter a year "
                 "earlier — quarters end on different dates, shown on each row"),
}


def _num(v) -> float | None:
    """A finite number, or None (bools and NaN count as missing)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        return None
    return float(v)


def growth_by_key(data: dict) -> dict:
    """``{report watchlist key: figures}``. The file keys companies by the pipeline
    ticker (``000660.KS``); the report keys its watchlist with non-alphanumerics as
    ``_`` (``000660_KS``). ``_meta.aliases`` maps a second listing onto a company
    (``SKHY``), as the company cards do."""
    if not isinstance(data, dict):
        return {}
    figs = {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}
    out = {re.sub(r"[^0-9A-Za-z]", "_", k): v for k, v in figs.items()}
    for alias, target in ((data.get("_meta") or {}).get("aliases") or {}).items():
        if target in figs:
            out[re.sub(r"[^0-9A-Za-z]", "_", alias)] = figs[target]
    return out


def sorted_rows(watchlist: dict, growth_map: dict, field: str) -> list[tuple[str, dict]]:
    """The watchlist's names, highest ``field`` first; names without the figure last,
    A–Z. Ties go A–Z by display ticker. Retired names excluded, as in the default order."""
    items = [(tk, d) for tk, d in (watchlist or {}).items() if tk not in RETIRED_TICKERS]

    def key(row):
        v = _num((growth_map.get(row[0]) or {}).get(field))
        return (v is None, -(v or 0.0), display_ticker(row[0]).upper())

    return sorted(items, key=key)


def _pct(v, signed: bool = True) -> str:
    n = _num(v)
    if n is None:
        return "—"
    return f"{_sign(n) if signed else ''}{_fmt_num(n, 0)}%"


def _month(iso) -> str:
    """``Jun 2026`` from ``YYYY-MM-DD``; '' otherwise."""
    try:
        return date.fromisoformat(str(iso or "")[:10]).strftime("%b %Y")
    except ValueError:
        return ""


def growth_line_html(g: dict | None, field: str) -> str:
    """One line under the row's cells: two-year average · latest quarter (and when it
    ended) · operating margin a year earlier → latest quarter. The figure the rows are
    sorted by is bolded; neutral ink throughout."""
    g = g or {}
    if all(_num(g.get(f)) is None for f in ("avg2y", "latest_q", "om_ya", "om_now")):
        return '<div class="tk-growth">Sales growth · no figures on file</div>'
    two = _pct(g.get("avg2y"))
    qtr = _pct(g.get("latest_q"))
    two = f"<b>{two}</b>" if field == "avg2y" else two
    qtr = f"<b>{qtr}</b>" if field == "latest_q" else qtr
    month = _month(g.get("latest_quarter_end"))
    ended = f" (quarter to {month})" if month else ""
    margin = f'{_pct(g.get("om_ya"), signed=False)} → {_pct(g.get("om_now"), signed=False)}'
    return (
        '<div class="tk-growth">'
        f'Sales growth · 2-year average {two} a year · latest quarter {qtr}{ended}'
        f' · operating margin {margin} (a year earlier → latest quarter)'
        '</div>'
    )


def sortline_html(field: str, as_of: str | None) -> str:
    """The page's statement of the sorted order: what the figure is, that it is sales
    (not the share price), that it is not a pick list, and how old the figures are."""
    try:
        d = date.fromisoformat(str(as_of or "")[:10])
        dated = f" · figures as of {d.day} {d.strftime('%b %Y')}, the same for every report date"
    except ValueError:
        dated = ""
    return (
        '<div class="tk-sortline tk-sortline-exp">'
        f'Experimental · sorted by {_SORT_BASIS[field]}, fastest first · names without a '
        f'figure last · sales, not the share price · a sort, not a pick list{dated}'
        '</div>'
    )


def sorted_grid_html(
    rows: list[tuple[str, dict]],
    growth_map: dict,
    field: str,
    earnings_map: dict,
    row_builder: Callable[..., str],
    report_date: str | None = None,
    price_map: dict | None = None,
    profile_map: dict | None = None,
) -> str:
    """The sorted table as ONE string (the grid's one-blob rule): column header, then
    every row with its growth line, no cluster headers (the cluster stays under each
    ticker)."""
    parts = [column_header_html()]
    for tk, d in rows:
        parts.append(row_builder(tk, d,
                                 earnings_hist=(earnings_map or {}).get(tk),
                                 report_date=report_date,
                                 price_hist=(price_map or {}).get(tk),
                                 profile=(profile_map or {}).get(tk),
                                 growth_html=growth_line_html(growth_map.get(tk), field)))
    return (
        '<div class="tk-scroll" role="table" '
        'aria-label="Watchlist sorted by sales growth — click a row to expand">'
        f'{"".join(parts)}</div>'
    )


def sorted_footer_html(n_names: int) -> str:
    """The sorted page's own count and order statement."""
    return (
        '<div class="tk-foot">'
        f'{n_names} names · experimental sort by sales growth · facts only, no ratings · '
        'retired names excluded'
        '</div>'
    )
