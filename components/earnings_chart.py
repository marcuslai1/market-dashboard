"""Earnings trajectory charts — revenue and EPS by quarter, analysts vs what happened.

Owner 2026-09-29: the numbers alone ("41.5 → 51.4") hide the shape; a chart shows the
speed-up and the expected slowdown at a glance. Two forms from one series builder:

- ``revenue_chart_html`` — solid bars = reported quarters, a dashed-outline bar = the
  coming quarter (analysts' estimate; the company's own forecast as a band when known),
  a neutral tick on each past bar = what analysts expected beforehand, and a
  "vs previous quarter" multiplier row (1.2×, 1.7×, ~1.2×) so the speed-up is a number.
- ``eps_chart_html`` — same grammar for earnings per share, drawn from a zero line
  because EPS can be negative, with a "vs analysts" row.
- ``mini=True`` — the thumbnail for the briefing's "reporting this week" grid: bars and
  the outlined estimate only, plus one line of multipliers.

Rules carried from the dashboard: one hue (earnings violet, ``--metric-gen``) and no
green/red — beat or miss is read from the tick's position, never a colour (colour is a
claim); estimates are always visibly different from results (outline, "~"); marks are
thin with a square baseline and a hairline axis. Pure HTML + ``.ec-`` CSS, no script:
hover text is native ``title``.

Data: ``earnings_history.csv`` records (the pipeline's export; revenue estimates exist
only for quarters the pipeline snapshotted before the result, since late July 2026)
merged with ``data/revenue_estimates.json`` — web-sourced past estimates and a few
missing actuals, each with its provider and source. The CSV wins where both have a value.
"""
from __future__ import annotations

import datetime as _dt
import html

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# Revenue is in the REPORTING currency, which for four US-listed names is not the USD they
# trade in (TSMC reports TWD, ASML and Nokia EUR, WeRide RMB). EPS for TSM is Yahoo's
# per-ADR figure in USD; for the other ADRs the currency is not confirmed, so the chart
# says whose units they are instead of guessing.
_SUFFIX_REPORTING = {"_KS": "KRW", "_SI": "SGD", "_DE": "EUR", "_PA": "EUR"}
_REVENUE_CCY = {"TSM": "TWD", "ASML": "EUR", "NOK": "EUR", "WRD": "RMB", "SKHY": "KRW"}
_EPS_CCY = {"TSM": "US$ per ADR", "ASML": "Yahoo Finance units", "NOK": "Yahoo Finance units",
            "WRD": "Yahoo Finance units", "SKHY": "Yahoo Finance units"}


def revenue_currency(key: str) -> str:
    if key in _REVENUE_CCY:
        return _REVENUE_CCY[key]
    return next((c for sfx, c in _SUFFIX_REPORTING.items() if key.endswith(sfx)), "US$")


def eps_currency(key: str) -> str:
    return _EPS_CCY.get(key) or revenue_currency(key)


def merge_backfill(records: list, backfill: dict | None) -> list:
    """The ticker's CSV records with ``data/revenue_estimates.json`` folded in.

    A backfilled value only fills a blank (the pipeline's own figure always wins); a
    quarter only the backfill knows is added. Filled fields are marked (``_rev_est_src``,
    ``_rev_src``) so the chart can name the source. Order: newest quarter first, as exported.
    """
    backfill = backfill or {}
    out, seen = [], set()
    for r in records or []:
        r = dict(r)
        qe = str(r.get("quarter_end") or "")[:10]
        seen.add(qe)
        b = backfill.get(qe) or {}
        if _n(r.get("revenue_estimate")) is not None:
            r["_rev_est_src"] = "pipeline snapshot (Yahoo Finance average)"
        elif _n(b.get("revenue_estimate")) is not None:
            r["revenue_estimate"] = b["revenue_estimate"]
            r["_rev_est_src"] = " · ".join(x for x in (b.get("provider"), b.get("source_title")) if x) or "web source"
        if _n(r.get("revenue_actual")) is None and _n(b.get("revenue_actual")) is not None:
            r["revenue_actual"] = b["revenue_actual"]
            r["_rev_src"] = b.get("actual_source") or "web source"
        out.append(r)
    for qe, b in backfill.items():
        if qe in seen or qe.startswith("_"):
            continue
        r = {"quarter_end": qe, "revenue_actual": b.get("revenue_actual"), "_rev_src": b.get("actual_source")}
        if _n(b.get("revenue_estimate")) is not None:
            r["revenue_estimate"] = b["revenue_estimate"]
            r["_rev_est_src"] = " · ".join(x for x in (b.get("provider"), b.get("source_title")) if x) or "web source"
        out.append(r)
    return sorted(out, key=lambda r: str(r.get("quarter_end")), reverse=True)


def _n(v):
    """A finite number, or None (CSV records carry float NaN for blanks)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _t(s) -> str:
    return html.escape(str(s), quote=True)


def period_label(quarter_end: str) -> tuple[str, str]:
    """('Mar–May', '2026') for a quarter ending 2026-05-31 — the three months it covers."""
    d = _dt.date.fromisoformat(str(quarter_end)[:10])
    start = (d.month - 3) % 12
    return f"{_MONTHS[start]}–{_MONTHS[d.month - 1]}", str(d.year)


def _mi(qe: str) -> int:
    """Month index of a quarter end (year*12+month) — quarters are back to back when 3 apart."""
    return int(qe[:4]) * 12 + int(qe[5:7])


def _qe_from_mi(mi: int) -> str:
    y, m = divmod(mi - 1, 12)
    return f"{y:04d}-{m + 1:02d}-28"


def _with_gaps(qs: list[dict]) -> list[dict]:
    """Insert a {qe, missing: True} slot for each quarter absent between two on file."""
    out = []
    for q in qs:
        if out and not out[-1].get("missing"):
            k = _mi(out[-1]["qe"]) + 3
            while k < _mi(q["qe"]) - 1:
                out.append({"qe": _qe_from_mi(k), "missing": True})
                k += 3
        out.append(q)
    return out


def quarter_series(rows, backfill: dict | None = None, limit: int = 5) -> dict:
    """A ticker's records (any order; raw CSV or already ``merge_backfill``-ed) as a series.

    Returns ``{"past": [...oldest→newest, at most `limit`], "coming": {...} | None}``;
    each quarter is ``{qe, rev, rev_est, rev_est_src, eps, eps_est}``, or ``{qe, missing}``
    for a quarter not on file between two that are.
    """
    rows = merge_backfill(rows, backfill) if backfill else list(rows or [])
    by_q = {}
    for r in rows:
        qe = str(r.get("quarter_end") or "")[:10]
        if qe:
            by_q[qe] = r
    past, coming = [], None
    for qe in sorted(by_q):
        r = by_q[qe]
        q = {"qe": qe, "rev": _n(r.get("revenue_actual")), "eps": _n(r.get("eps_actual")),
             "eps_est": _n(r.get("eps_estimate")), "rev_est": _n(r.get("revenue_estimate"))}
        q["rev_est_src"] = r.get("_rev_est_src") or ("pipeline snapshot (Yahoo Finance average)"
                                                    if q["rev_est"] is not None else None)
        if q["rev"] is None and q["eps"] is None:
            if q["rev_est"] is not None or q["eps_est"] is not None:
                coming = coming or q                          # the nearest not-yet-reported quarter
            continue
        past.append(q)
    past = _with_gaps(past)[-limit:]
    while past and past[0].get("missing"):
        past = past[1:]
    gap = bool(coming and past and _mi(coming["qe"]) - _mi(past[-1]["qe"]) > 4)
    if gap:                                   # the quarter before the coming one is not on file
        past = [*past, {"qe": _qe_from_mi(_mi(coming["qe"]) - 3), "missing": True}][-limit:]
    return {"past": past, "coming": coming}


def _unit(vmax: float) -> tuple[float, str]:
    a = abs(vmax)
    if a >= 1e12:
        return 1e12, "trillions"
    if a >= 1e9:
        return 1e9, "billions"
    if a >= 1e6:
        return 1e6, "millions"
    return 1.0, ""


def _num_label(v: float, nd: int = 1) -> str:
    return f"{v:,.{nd}f}".replace("-", "−")


def _val_label(v: float) -> str:
    """Bar label: 1 decimal, 2 below 10 so small revenues (0.03, 0.78) stay readable."""
    return _num_label(v, 2 if abs(v) < 10 else 1)


def _mult(cur, prev) -> str:
    """cur / prev as '1.7×' (with the % drop spelled out below 1×). prev is None when the
    quarter before is not on file — no multiplier then, never one across a gap."""
    if cur is None or prev is None or prev <= 0 or cur <= 0:
        return ""
    m = cur / prev
    s = f"{m:.1f}×"
    return s + (f" ({(m - 1) * 100:+.0f}%)".replace("-", "−") if m < 1 else "")


def _pct(cur, ref) -> str:
    if cur is None or ref is None or ref == 0:
        return ""
    return f"{(cur / ref - 1) * 100:+.0f}%".replace("-", "−")


def _pos(v: float, lo: float, hi: float) -> float:
    return (v - lo) / (hi - lo) * 100 if hi > lo else 0.0


def _chart(cols: list[dict], lo: float, hi: float, *, mini: bool, aria: str, rows_below: list) -> str:
    """cols: [{label, year, bar, tick, tip, coming: {est, band, whisker}}]; values already scaled."""
    zero = _pos(0.0, lo, hi)
    body = ""
    for c in cols:
        inner = ""
        if c.get("bar") is not None:
            v = c["bar"]
            b0, b1 = sorted((_pos(0.0, lo, hi), _pos(v, lo, hi)))
            neg = " ec-neg" if v < 0 else ""
            inner += f'<span class="ec-bar{neg}" style="bottom:{b0:.2f}%;height:{b1 - b0:.2f}%"></span>'
            if not mini and c.get("val"):
                top = max(b1, _pos(c["tick"], lo, hi) if c.get("tick") is not None else b1)
                inner += f'<span class="ec-val" style="bottom:calc({top:.2f}% + 3px)">{_t(c["val"])}</span>'
        cm = c.get("coming")
        if cm:
            if cm.get("band"):
                g0, g1 = (_pos(x, lo, hi) for x in cm["band"])
                inner += f'<span class="ec-band" style="bottom:{g0:.2f}%;height:{max(g1 - g0, 0.8):.2f}%"></span>'
            if cm.get("whisker"):
                w0, w1 = (_pos(x, lo, hi) for x in cm["whisker"])
                inner += f'<span class="ec-whisker" style="bottom:{w0:.2f}%;height:{w1 - w0:.2f}%"></span>'
            if cm.get("est") is not None:
                e0, e1 = sorted((zero, _pos(cm["est"], lo, hi)))
                inner += f'<span class="ec-est" style="bottom:{e0:.2f}%;height:{e1 - e0:.2f}%"></span>'
                if not mini and cm.get("val"):
                    top = max(e1, _pos(cm["whisker"][1], lo, hi) if cm.get("whisker") else e1)
                    inner += f'<span class="ec-val ec-val-est" style="bottom:calc({top:.2f}% + 3px)">{_t(cm["val"])}</span>'
        if c.get("tick") is not None and not mini:          # marks are unreadable at thumbnail size
            inner += f'<span class="ec-tick" style="bottom:{_pos(c["tick"], lo, hi):.2f}%"></span>'
        if c.get("missing"):
            inner += '<span class="ec-miss">not on file</span>' if not mini else '<span class="ec-miss">·</span>'
        lab = "" if mini else f'<span class="ec-x">{_t(c["label"])}<small>{_t(c["year"])}</small></span>'
        axis = f'<span class="ec-zero" style="bottom:{zero:.2f}%"></span>'
        body += (f'<div class="ec-col{" ec-coming" if cm else ""}" title="{_t(c.get("tip", ""))}">'
                 f'<div class="ec-plot">{axis}{inner}</div>{lab}</div>')
    rows = "".join(
        f'<div class="ec-row"><span class="ec-rh">{_t(h)}</span>'
        + "".join(f'<span class="ec-rc">{_t(v)}</span>' for v in vals) + "</div>"
        for h, vals in rows_below if any(vals))
    return (f'<div class="ec{" ec-mini" if mini else ""}" role="img" aria-label="{_t(aria)}" '
            f'style="--ec-n:{len(cols)}"><div class="ec-cols">{body}</div>{rows}</div>')


def revenue_chart_html(series: dict, currency: str = "US$", company: tuple | None = None,
                       whisker: tuple | None = None, mini: bool = False) -> str:
    """Revenue bars by quarter. ``company`` = (low, high) forecast for the coming quarter,
    ``whisker`` = (lowest, highest) analyst estimate — both full units, optional."""
    # A reported quarter whose revenue is not on file (EPS only) keeps its slot, drawn empty.
    past = [q if q.get("rev") is not None or q.get("missing") else {"qe": q["qe"], "missing": True}
            for q in series.get("past") or []]
    coming = series.get("coming")
    if sum(1 for q in past if not q.get("missing")) < 2:
        return ""
    vals = [q["rev"] for q in past if not q.get("missing")] + [q["rev_est"] for q in past if q.get("rev_est")]
    cest = coming.get("rev_est") if coming else None
    vals += [x for x in (cest, *(company or ()), *(whisker or ())) if x]
    scale, unit = _unit(max(vals))
    hi = max(vals) / scale * 1.12
    cols, mults, vs_an = [], [], []
    prev = None
    for q in past:
        lab, yr = period_label(q["qe"])
        if q.get("missing"):
            cols.append({"label": lab, "year": yr, "missing": True, "tip": f"{lab} {yr}: not on file"})
            mults.append("")
            vs_an.append("")
            prev = None
            continue
        est = q.get("rev_est")
        tip = f"{lab} {yr}: revenue {currency} {q['rev'] / scale:,.2f} {unit}"
        if est:
            tip += f"; analysts expected {est / scale:,.2f} ({q.get('rev_est_src') or 'source not recorded'})"
        cols.append({"label": lab, "year": yr, "bar": q["rev"] / scale, "val": _val_label(q["rev"] / scale),
                     "tick": est / scale if est else None, "tip": tip})
        mults.append(_mult(q["rev"], prev))
        vs_an.append(_pct(q["rev"], est))
        prev = q["rev"]
    coming_note = ""
    if coming and (cest or company):
        lab, yr = period_label(coming["qe"])
        band = tuple(x / scale for x in company) if company else None
        wh = tuple(x / scale for x in whisker) if whisker else None
        tip = f"{lab} {yr} (coming): analysts expect {cest / scale:,.2f} {unit}" if cest else f"{lab} {yr} (coming)"
        if company:
            tip += f"; company forecast {company[0] / scale:,.2f}–{company[1] / scale:,.2f}"
        cols.append({"label": lab, "year": yr, "coming": {"est": cest / scale if cest else None, "band": band,
                     "whisker": wh, "val": f"~{_val_label(cest / scale)}" if cest else ""}, "tip": tip})
        m_an = _mult(cest, prev)
        m_co = _mult(sum(company) / 2, prev) if company else ""
        mults.append("~" + (m_an or m_co) if (m_an or m_co) else "")
        vs_an.append("")
        parts = []
        if cest and prev:
            parts.append(f"analysts ~{cest / prev:.2f}×")
        if company and prev:
            parts.append(f"company forecast ~{sum(company) / 2 / prev:.2f}×")
        coming_note = ("Coming quarter vs the last: " + " · ".join(parts)) if parts else ""
    on_file = [q for q in past if not q.get("missing")]
    yoy = ""
    if on_file:
        last = on_file[-1]
        ago = next((q for q in on_file if _mi(last["qe"]) - _mi(q["qe"]) == 12), None)
        if ago:
            yoy = _mult(last["rev"], ago["rev"]) or ""
    aria = (f"Revenue by quarter, {currency} {unit}: " + ", ".join(
        f"{c['label']} {c['year']} {c['val']}" for c in cols if c.get("bar") is not None)
        + (f"; coming quarter analysts expect {cest / scale:,.1f}" if cest else ""))
    if mini:
        last_m = mults[len(past) - 1] if past and not past[-1].get("missing") else ""
        nxt = mults[-1] if coming and len(mults) > len(past) else ""
        l1 = " · ".join(x for x in ((f"{last_m} previous" if last_m else ""),
                                     (f"{yoy} a year ago" if yoy else "")) if x)
        l1 = f"Last quarter: {l1}" if l1 else ("Last quarter not on file" if past and past[-1].get("missing") else "")
        l2 = f"Next: {nxt} ({'analysts' if cest else 'company'})" if nxt else ""
        lines = "".join(f'<p class="ec-note">{_t(x)}</p>' for x in (l1, l2) if x)
        return _chart(cols, 0.0, hi, mini=True, aria=aria, rows_below=[]) + lines
    head = f'<p class="ec-h"><b>Revenue</b>, {_t(currency)} {_t(unit)}</p>'
    rows = [("vs previous quarter", mults)]
    if any(vs_an):
        rows.append(("vs what analysts expected", vs_an))
    notes = [x for x in ((f"Latest quarter vs a year earlier: {yoy}" if yoy else ""), coming_note) if x]
    note = "".join(f'<p class="ec-note">{_t(x)}</p>' for x in notes)
    return head + _chart(cols, 0.0, hi, mini=False, aria=aria, rows_below=rows) + note


def eps_chart_html(series: dict, currency: str = "US$", company: tuple | None = None, mini: bool = False) -> str:
    """Earnings per share by quarter, from a zero line (EPS can be negative)."""
    past = [q for q in series.get("past") or [] if q.get("eps") is not None]
    coming = series.get("coming")
    if len(past) < 2:
        return ""
    if coming and _mi(coming["qe"]) - _mi(past[-1]["qe"]) > 4:
        coming = None                         # don't set an estimate beside a quarter that is not on file
    cest = coming.get("eps_est") if coming else None
    vals = [q["eps"] for q in past] + [q["eps_est"] for q in past if q.get("eps_est") is not None]
    vals += [x for x in (cest, *(company or ())) if x is not None]
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    pad = (hi - lo) * 0.12 or 1.0
    lo, hi = (lo - pad if lo < 0 else lo), hi + pad
    cols, vs_an = [], []
    for q in past:
        lab, yr = period_label(q["qe"])
        est = q.get("eps_est")
        tip = f"{lab} {yr}: EPS {q['eps']:.2f}" + (f"; analysts expected {est:.2f}" if est is not None else "")
        cols.append({"label": lab, "year": yr, "bar": q["eps"], "val": _num_label(q["eps"], 2),
                     "tick": est, "tip": tip})
        vs_an.append(_pct(q["eps"], est) if est and q["eps"] and est > 0 and q["eps"] > 0 else "")
    if coming and cest is not None:
        lab, yr = period_label(coming["qe"])
        cols.append({"label": lab, "year": yr, "coming": {"est": cest, "band": company, "whisker": None,
                     "val": f"~{_num_label(cest, 2)}"}, "tip": f"{lab} {yr} (coming): analysts expect {cest:.2f}"})
        vs_an.append("")
    aria = f"Earnings per share by quarter, {currency}: " + ", ".join(
        f"{c['label']} {c['year']} {c['val']}" for c in cols if c.get("bar") is not None)
    head = f'<p class="ec-h"><b>Earnings per share</b>, {_t(currency)}</p>'
    return head + _chart(cols, lo, hi, mini=mini, aria=aria,
                         rows_below=[] if mini else [("vs what analysts expected", vs_an)])


def block_html(charts: str, company: bool = False) -> str:
    """Key on top, then the charts, in one ``.ec-block`` ("" without charts). Both surfaces
    use it: the key comes first (owner 2026-09-29), and ``.ec-block``-scoped rules outrank
    Streamlit's markdown ``p`` reset, which zeroed the headings' top margin and set the notes
    at 16px inside the Watchlist drawer."""
    return f'<div class="ec-block">{key_html(company)}{charts}</div>' if charts else ""


def key_html(company: bool = False) -> str:
    """The chart key: what the tick and the outlined bar mean (identity is never colour-alone)."""
    items = ['<span class="ec-k-bar">reported</span>',
             '<span class="ec-k-tick">what analysts expected beforehand</span>',
             '<span class="ec-k-est">coming quarter — an estimate, not a result</span>']
    if company:
        items.append('<span class="ec-k-band">company\'s own forecast</span>')
    return '<div class="ec-key">' + "".join(items) + "</div>"
