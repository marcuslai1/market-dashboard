"""Quarter-on-quarter earnings history — the drill-down's expected-vs-actual table.

Moved out of ``drilldown.py`` verbatim in the 2026-07-25 redesign: it is ~140
lines with one responsibility, and it is now the body of a collapsed drawer
rather than a section in a fifteen-block stack. Pure HTML, no Streamlit.

Data comes from the separate ``earnings_history.csv`` export, threaded in by the
caller (``components.watchlist.watchlist``), so this module stays Streamlit-free.
"""
from __future__ import annotations

from lib.formatters import _fmt_num, _sign


def _eh_num(v):
    """The value, or None for missing / NaN (CSV records carry float NaN)."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    return v


def _eh_big(v) -> str:
    """Big currency figure with T/B/M suffix (scale-clear, currency-agnostic)."""
    v = _eh_num(v)
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.2f}T"
    if a >= 1e9:
        return f"{v / 1e9:.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    return _fmt_num(v, 0)


def _eh_surprise_html(s) -> str:
    """Beat/miss cell — ▲ green / ▼ red / — muted. Icon + %, never color-alone."""
    s = _eh_num(s)
    if s is None:
        return '<span class="eps-flat">—</span>'
    if s > 0:
        return f'<span class="eps-beat">▲ +{_fmt_num(s, 1)}%</span>'
    if s < 0:
        return f'<span class="eps-miss">▼ {_fmt_num(s, 1)}%</span>'
    return f'<span class="eps-flat">{_fmt_num(s, 1)}%</span>'


def _eh_sparkline_svg(vals_chrono, w: int = 128, h: int = 26, pad: int = 4) -> str:
    """Inline SVG trend line of reported EPS (oldest→latest). '' if < 2 points."""
    pts = [float(v) for v in vals_chrono if _eh_num(v) is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1.0
    n = len(pts)

    def _x(i):
        return pad + (w - 2 * pad) * (i / (n - 1))

    def _y(v):
        return pad + (h - 2 * pad) * (1 - (v - lo) / rng)

    poly = " ".join(f"{_x(i):.1f},{_y(v):.1f}" for i, v in enumerate(pts))
    ex, ey = _x(n - 1), _y(pts[-1])
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'preserveAspectRatio="none" role="img" aria-label="Reported EPS trend, '
        f'oldest to latest">'
        f'<polyline points="{poly}" fill="none" stroke="var(--ink-3)" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="2.6" fill="var(--ink)"/></svg>'
    )


def _earnings_history_html(rows) -> str:
    """Quarter-on-quarter expected-vs-actual table + a reported-EPS sparkline.

    ``rows`` are the ticker's ``earnings_history`` records, newest quarter first
    (as exported). Returns '' when empty. The coming (not-yet-reported) quarter
    renders as a tinted 'upcoming' row carrying the estimate only — revenue there
    is the forward consensus snapshot (marked ``est``), not an actual.
    """
    if not rows:
        return ""
    trs = []
    reported_eps_newest_first = []
    for r in rows:
        label = r.get("fiscal_label") or r.get("quarter_end") or "—"
        est = _eh_num(r.get("eps_estimate"))
        act = _eh_num(r.get("eps_actual"))
        est_s = _fmt_num(est, 2) if est is not None else "—"
        if act is None:                                   # coming quarter
            rev = _eh_big(r.get("revenue_estimate"))
            rev_s = (f'{rev} <span class="eps-flat" style="font-size:9px;">est</span>'
                     if rev != "—" else "—")
            cells = (
                f'<td class="num" data-l="EPS est">{est_s}</td>'
                f'<td class="num" data-l="EPS act"><span class="eps-flat">—</span></td>'
                f'<td class="num" data-l="Surprise">'
                f'<span style="font-family:var(--mono);font-size:9px;'
                f'letter-spacing:0.08em;text-transform:uppercase;color:var(--ink-3);'
                f'border:1px solid var(--rule-strong);border-radius:3px;'
                f'padding:1px 5px;">upcoming</span></td>'
                f'<td class="num" data-l="Revenue">{rev_s}</td>'
                f'<td class="num" data-l="Rev YoY">—</td>'
                f'<td class="num" data-l="Gross m.">—</td>'
                f'<td class="num" data-l="Op m.">—</td>'
            )
            trs.append(f'<tr style="background:rgba(52,152,219,0.05);">'
                       f'<td>{label}</td>{cells}</tr>')
            continue
        reported_eps_newest_first.append(act)
        yoy = _eh_num(r.get("revenue_yoy_pct"))
        gm = _eh_num(r.get("gross_margin_pct"))
        om = _eh_num(r.get("operating_margin_pct"))
        trs.append(
            f'<tr><td>{label}</td>'
            f'<td class="num" data-l="EPS est">{est_s}</td>'
            f'<td class="num" data-l="EPS act">{_fmt_num(act, 2)}</td>'
            f'<td class="num" data-l="Surprise">'
            f'{_eh_surprise_html(r.get("eps_surprise_pct"))}</td>'
            f'<td class="num" data-l="Revenue">{_eh_big(r.get("revenue_actual"))}</td>'
            f'<td class="num" data-l="Rev YoY">'
            f'{f"{_sign(yoy)}{_fmt_num(yoy, 1)}%" if yoy is not None else "—"}</td>'
            f'<td class="num" data-l="Gross m.">'
            f'{f"{_fmt_num(gm, 1)}%" if gm is not None else "—"}</td>'
            f'<td class="num" data-l="Op m.">'
            f'{f"{_fmt_num(om, 1)}%" if om is not None else "—"}</td></tr>'
        )
    # Sparkline reads oldest→latest; reported rows arrive newest-first.
    spark = _eh_sparkline_svg(list(reversed(reported_eps_newest_first)))
    spark_html = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0 8px;">'
        f'<span style="font-family:var(--mono);font-size:9.5px;letter-spacing:0.1em;'
        f'text-transform:uppercase;color:var(--ink-3);">Reported EPS</span>{spark}</div>'
        if spark else ""
    )
    table = (
        '<div class="tk-scroll"><table class="ep-table stack-m">'
        '<thead><tr><th>Quarter</th><th class="num">EPS est</th>'
        '<th class="num">EPS act</th><th class="num">Surprise</th>'
        '<th class="num">Revenue</th><th class="num">Rev YoY</th>'
        '<th class="num">Gross m.</th><th class="num">Op m.</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )
    return spark_html + table
