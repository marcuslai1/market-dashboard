"""Briefing · Earnings-scorecard band.

Surfaces per-ticker ``eps_trajectory`` — the pipeline's beat/miss track record
for the core AI beneficiaries (MU / SK Hynix / LITE / PLTR), emitted on the
latest reports and rendered nowhere (review finding P1-2, third "surface the
free data" slice). Answers at a glance: are the beneficiaries beating
estimates, and are the beats accelerating? — the fundamental-performance
complement to the signal-calibration band.
"""
from __future__ import annotations

from lib.catalog import TICKER_DISPLAY
from lib.formatters import _escape_dollars, _fmt_num, _sign


def _pct(value, decimals: int = 1) -> str:
    """Signed percentage like '+41.6%' / '-3.0%', or '—' when missing."""
    if value is None:
        return "—"
    return f"{_sign(value)}{_fmt_num(value, decimals)}%"


def _display_ticker(tk: str) -> str:
    """Human display form of a watchlist key, e.g. ``000660_KS`` -> ``000660.KS``.

    ``TICKER_DISPLAY`` is a *sparse* override map — it only lists tickers whose
    display needs special glyphs (``CL_F`` -> ``CL=F``, ``VIX`` -> ``^VIX``). It
    does **not** carry the plain underscore-for-dot names (``000660_KS``), so the
    codebase-wide ``TICKER_DISPLAY.get(tk, tk)`` leaks the munged key into the UI
    for those. Prefer the override, then fall back to restoring the dot — giving
    the clean dotted ticker the cluster band already shows.
    """
    return TICKER_DISPLAY.get(tk) or str(tk).replace("_", ".")


def _eps_rows(watchlist: dict) -> list:
    """One scorecard row per watchlist entry carrying ``eps_trajectory.quarters``.

    Ordered accelerating-first, then latest surprise% desc, then ticker (for
    determinism). Entries without the field — or with empty ``quarters`` — are
    skipped. ``accelerating`` is read verbatim: it tracks EPS-level growth, not
    the surprise trend, and is never recomputed from ``surprise_pct`` here.
    """
    rows = []
    for tk, entry in (watchlist or {}).items():
        eps = (entry or {}).get("eps_trajectory") or {}
        quarters = eps.get("quarters") or []
        if not quarters:
            continue
        surprises = [q.get("surprise_pct") for q in quarters]
        latest = surprises[-1] if surprises else None
        beats = sum(1 for s in surprises if s is not None and s > 0)
        rows.append({
            "ticker": _display_ticker(tk),
            "surprises": surprises,
            "latest": latest,
            "beats": beats,
            "n": len(quarters),
            "accelerating": bool(eps.get("accelerating")),
            "accel_reason": (eps.get("accel_reason") or "").strip(),
        })
    rows.sort(key=lambda r: (
        not r["accelerating"],
        -r["latest"] if r["latest"] is not None else float("inf"),
        r["ticker"],
    ))
    return rows


def _headline(rows: list) -> str:
    """Collapsed corpus headline: 'N of M beat last quarter · K accelerating'.

    'beat' = latest surprise > 0; 'accelerating' = the field's own flag. Generic
    label when there are no rows (the render wrapper guards that path).
    """
    if not rows:
        return "Earnings scorecard"
    n = len(rows)
    beat = sum(1 for r in rows if r["latest"] is not None and r["latest"] > 0)
    accel = sum(1 for r in rows if r["accelerating"])
    return f"{beat} of {n} beat last quarter · {accel} accelerating"


def _trend_cells_html(surprises: list) -> str:
    """Surprise%-per-quarter, oldest→latest, beat green / miss red / flat muted.

    ``None`` renders as a muted '—'. Cells are joined by '→'. '' for empty input.
    """
    if not surprises:
        return ""
    cells = []
    for s in surprises:
        if s is None:
            cells.append('<span class="eps-flat">—</span>')
        elif s > 0:
            cells.append(f'<span class="eps-beat">{_pct(s)}</span>')
        elif s < 0:
            cells.append(f'<span class="eps-miss">{_pct(s)}</span>')
        else:
            cells.append(f'<span class="eps-flat">{_pct(s)}</span>')
    return '<span class="eps-trend">' + " → ".join(cells) + "</span>"


def _latest_cell_html(latest) -> str:
    """The latest-surprise cell — the same beat/miss/flat coloring as a trend cell."""
    if latest is None:
        return '<span class="eps-flat">—</span>'
    if latest > 0:
        return f'<span class="eps-beat">{_pct(latest)}</span>'
    if latest < 0:
        return f'<span class="eps-miss">{_pct(latest)}</span>'
    return f'<span class="eps-flat">{_pct(latest)}</span>'


def _scorecard_table_html(rows: list) -> str:
    """A .ep-table of ticker → latest surprise, 4-qtr trend, accel flag.

    Returns '' when there are no rows.
    """
    if not rows:
        return ""
    trs = []
    for r in rows:
        accel_html = (
            '<span class="eps-accel">▲</span>' if r["accelerating"]
            else '<span class="eps-flat">—</span>'
        )
        trs.append(
            f'<tr><td>{_escape_dollars(r["ticker"])}</td>'
            f'<td class="num">{_latest_cell_html(r["latest"])}</td>'
            f'<td>{_trend_cells_html(r["surprises"])}</td>'
            f'<td class="num">{accel_html}</td></tr>'
        )
    return (
        '<div class="tk-scroll"><table class="ep-table eps-scorecard">'
        '<thead><tr><th>Ticker</th><th class="num">Latest</th>'
        '<th>Surprise trend (oldest → latest)</th>'
        '<th class="num">Accel</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )


def _reason_lines_html(rows: list) -> str:
    """Muted '▲ TICKER — reason' lines for accelerating names with a reason.

    Returns '' when no accelerating row carries a reason.
    """
    lines = [
        f'<p class="eps-reason">▲ {_escape_dollars(r["ticker"])} — '
        f'{_escape_dollars(r["accel_reason"])}</p>'
        for r in rows
        if r["accelerating"] and r["accel_reason"]
    ]
    return "".join(lines)


def _earnings_html(watchlist: dict) -> str:
    """Full earnings-scorecard band HTML, or a muted placeholder when empty."""
    rows = _eps_rows(watchlist)
    if not rows:
        return '<div class="eps-band eps-empty">No earnings data in this report.</div>'
    parts = [
        f'<summary class="eps-summary">{_escape_dollars(_headline(rows))}</summary>',
        '<div class="eps-body">',
        _scorecard_table_html(rows),
        _reason_lines_html(rows),
        "</div>",
    ]
    return f'<details class="eps-band eps-details">{"".join(parts)}</details>'
