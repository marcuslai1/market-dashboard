"""Watchlist drill-down · price chart — the name's price since the first report.

Owner plan 2026-10-01 (information-only site, MarketReport spec
2026-10-01-info-only-watchlist O2): **numbers only, no threshold marks** — no
support / resistance lines, no RSI bands, no stop, target or trigger. Three
series, all facts the pipeline already exports: the price each morning report
recorded, and its 50- and 200-day averages (the same averages the levels ladder
lists as rungs).

Data: ``data/market_data.csv`` (the pipeline's daily export, one row per name per
report date since 2026-03-12; ``lib.data_loader.load_price_history``). Its
``signal`` column is never read. For US listings the recorded price is the last
regular-session close; Singapore and Korea markets are usually open when the
report runs, so their points are prices from inside that day's session — the
chart says which.

Pure HTML + inline SVG, no script, like ``components.earnings_chart``: the plot
stretches to its box (``preserveAspectRatio="none"`` with non-scaling strokes),
and every label is HTML around it so text never scales with the width. No hover
layer: one per-point ``title`` per session across 33 drill-downs would roughly
double the watchlist's single markdown blob (re-sent on every live-price
refresh), so the readable numbers — first, last, high, low, with dates — are
printed above the plot and the gridlines carry their values.
"""
from __future__ import annotations

import math
from datetime import date

from lib.formatters import _escape_attr, _fmt_num, _sign

#: Plot coordinate box. The SVG is stretched to the CSS box, so only the ratio
#: of positions matters; integers keep the markup short.
_W, _H = 1000, 200
_PAD = 0.06          # vertical breathing room, as a share of the value range

#: Listings whose market is usually open when the morning report runs.
_INTRADAY_SUFFIXES = ("_SI", "_KS")

#: (row field, CSS class, legend label)
_SERIES = (
    ("price", "pc-price", "Price"),
    ("sma50", "pc-sma50", "50-day avg"),
    ("sma200", "pc-sma200", "200-day avg"),
)


def _num(v):
    """A finite float, or ``None``."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _day(iso: str) -> str:
    when = date.fromisoformat(iso)
    return f"{when.day} {when:%b}"


def series_until(rows: list[dict] | None, report_date: str | None) -> list[dict]:
    """The rows on or before ``report_date`` (all of them when it is absent), in
    date order, keeping only rows with a price. A past report shows the chart as
    it stood that day."""
    out = []
    for r in rows or []:
        when = str(r.get("date") or "")[:10]
        if not when or (report_date and when > str(report_date)):
            continue
        if _num(r.get("price")) is None:
            continue
        out.append({"date": when, "price": _num(r.get("price")),
                    "sma50": _num(r.get("sma50")), "sma200": _num(r.get("sma200"))})
    out.sort(key=lambda r: r["date"])
    return out


def nice_ticks(lo: float, hi: float, target: int = 3) -> list[float]:
    """Round gridline values inside ``[lo, hi]`` — steps of 1, 2, 2.5 or 5 × 10ⁿ."""
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step) * step
    ticks = []
    v = first
    while v <= hi + step * 1e-9:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _tick_label(v: float, step: float) -> str:
    decimals = 0 if step >= 1 else 2
    return _fmt_num(v, decimals)


def _polylines(points: list[tuple[int, float | None]], y_of, cls: str) -> str:
    """One ``<polyline>`` per unbroken run (an average is missing before it has
    enough history); a run of one point draws nothing."""
    runs: list[list[str]] = [[]]
    for x, v in points:
        if v is None:
            if runs[-1]:
                runs.append([])
            continue
        runs[-1].append(f"{x},{y_of(v)}")
    return "".join(
        f'<polyline class="{cls}" points="{" ".join(run)}" '
        'vector-effect="non-scaling-stroke"/>'
        for run in runs if len(run) >= 2
    )


def basis_note(key: str) -> str:
    """What one point is, for this listing."""
    if key.endswith(_INTRADAY_SUFFIXES):
        return ("Each point is the price the morning report recorded: this market is "
                "usually open when the report runs, so it is a price from inside that "
                "day's session, not its close.")
    return "Each point is the price the morning report recorded: the last close."


def price_chart_html(key: str, rows: list[dict] | None, report_date: str | None,
                     price_fn) -> str:
    """The chart block for one name, or ``""`` with fewer than two points.

    ``rows`` are ``{date, price, sma50, sma200}`` dicts (any order); ``price_fn``
    is the drill-down's currency-aware formatter, so the stated numbers read like
    the rest of the card.
    """
    pts = series_until(rows, report_date)
    if len(pts) < 2:
        return ""

    values = [r[f] for r in pts for f, _, _ in _SERIES if r[f] is not None]
    lo, hi = min(values), max(values)
    pad = (hi - lo) * _PAD or abs(hi) * _PAD or 1.0
    lo, hi = lo - pad, hi + pad

    def y_of(v: float) -> int:
        return round((hi - v) / (hi - lo) * _H)

    n = len(pts)

    def x_of(i: int) -> int:
        return round(i / (n - 1) * _W)

    # Gridlines with their values (HTML labels, positioned in % of the box).
    ticks = nice_ticks(lo, hi)
    step = ticks[1] - ticks[0] if len(ticks) > 1 else 1.0
    # A label sits just above its gridline; one in the top strip would ride up
    # into the facts line, so that gridline is left out.
    ticks = [t for t in ticks if y_of(t) >= _H * 0.1]
    grid = "".join(
        f'<line class="pc-grid" x1="0" x2="{_W}" y1="{y_of(t)}" y2="{y_of(t)}" '
        'vector-effect="non-scaling-stroke"/>'
        for t in ticks
    )
    y_labels = "".join(
        f'<span class="pc-ylab" style="top:{y_of(t) / _H * 100:.1f}%">'
        f'{_tick_label(t, step)}</span>'
        for t in ticks
    )

    lines = "".join(
        _polylines([(x_of(i), r[field]) for i, r in enumerate(pts)], y_of, cls)
        for field, cls, _ in reversed(_SERIES)          # price drawn last, on top
    )

    # Month starts along the bottom (session scale, so weekends take no width);
    # one too close to the right edge would run off the plot.
    x_labels = []
    prev_month = None
    for i, r in enumerate(pts):
        month = r["date"][:7]
        if month != prev_month:
            prev_month = month
            left = x_of(i) / _W * 100
            if left <= 94:
                label = date.fromisoformat(r["date"]).strftime("%b")
                x_labels.append(f'<span class="pc-xlab" style="left:{left:.1f}%">{label}</span>')

    first, last = pts[0], pts[-1]
    hi_row = max(pts, key=lambda r: r["price"])
    lo_row = min(pts, key=lambda r: r["price"])
    change = (last["price"] / first["price"] - 1) * 100 if first["price"] else None
    change_str = f" ({_sign(change)}{_fmt_num(change, 1)}%)" if change is not None else ""
    facts = (
        '<div class="pc-facts">'
        f'<span>{_day(first["date"])} → {_day(last["date"])}: '
        f'{price_fn(first["price"])} → {price_fn(last["price"])}{change_str}</span>'
        f'<span>high {price_fn(hi_row["price"])} · {_day(hi_row["date"])}</span>'
        f'<span>low {price_fn(lo_row["price"])} · {_day(lo_row["date"])}</span>'
        '</div>'
    )
    legend = (
        '<div class="pc-key">'
        + "".join(
            f'<span class="pc-key-item"><i class="pc-swatch {cls}"></i>{label}</span>'
            for field, cls, label in _SERIES
            if any(r[field] is not None for r in pts)
        )
        + '</div>'
    )
    nd = 0 if hi_row["price"] >= 10_000 else 2          # KRW prices carry no cents

    def _plain(v: float) -> str:
        return _fmt_num(v, nd)

    aria = _escape_attr(
        f"Price from {_day(first['date'])} to {_day(last['date'])}: "
        f"{_plain(first['price'])} to {_plain(last['price'])}; "
        f"high {_plain(hi_row['price'])} on {_day(hi_row['date'])}, "
        f"low {_plain(lo_row['price'])} on {_day(lo_row['date'])}."
    )
    return (
        '<div class="pc">'
        '<div class="dd-eyebrow">Price</div>'
        f'{facts}'
        '<div class="pc-plot">'
        f'<svg class="pc-svg" viewBox="0 0 {_W} {_H}" preserveAspectRatio="none" '
        f'role="img" aria-label="{aria}">{grid}{lines}</svg>'
        f'{y_labels}'
        '</div>'
        f'<div class="pc-xaxis">{"".join(x_labels)}</div>'
        f'{legend}'
        f'<div class="pc-note">{basis_note(key)}</div>'
        '</div>'
    )
