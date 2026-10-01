"""Earnings trajectory charts — revenue and EPS by quarter, analysts vs what happened.

Owner 2026-09-29: the numbers alone ("41.5 → 51.4") hide the shape; a chart shows the
speed-up and the expected slowdown at a glance. Two forms from one series builder:

- ``revenue_chart_html`` — solid bars = reported quarters, a dashed-outline bar = the
  coming quarter (analysts' estimate; the company's own forecast as a band when known),
  a neutral hairline on each past bar = what analysts expected beforehand, with its number
  beside it, and a "vs previous quarter" growth row (+21.7%, +74.9%, ~+23.9%; a % to one decimal,
  not the first ship's 1.7×) so the speed-up is a number.
  The rows form a table: on a wide chart the title and row labels share a left gutter; on a
  narrow one the labels stack and a "what analysts expected" row carries the estimates. On a
  roomy chart (≥ 860px) the two comparisons move onto the plot and their rows step aside: the
  result vs analysts beside the analysts' number (12.8 +6%), the growth between the two
  quarter labels it compares (Sep–Nov — +74.9% — Dec–Feb).
- ``eps_chart_html`` — same grammar for earnings per share, drawn from a zero line
  because EPS can be negative, with a "what happened: above (+) or below (−) analysts" row.
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

# The two analyst rows under the axis. Owner 2026-09-30: "what analysts expected" over "vs what
# analysts expected" read as analysts against analysts — the second row is the RESULT against
# them, so it says so. It names analysts itself because a 600–860px chart shows it alone.
_EST_ROW = "what analysts expected"
_BEAT_ROW = "what happened: above (+) or below (−) analysts"


# Revenue is in the REPORTING currency, which for five US-listed names is not the USD they
# trade in (TSMC reports TWD, ASML and Nokia EUR, WeRide RMB, SK hynix KRW). EPS for TSM,
# SK hynix and Nokia is Yahoo's per-ADR figure in USD and ASML's is EUR (checked 2026-10-02
# against the home listings: TSM 4.31 = 2330.TW 27.25 TWD x 5 / FX; SKHY 9.06 = 000660.KS
# 131,478 KRW / 10 / FX; NOK 0.08 vs NOKIA.HE EUR 0.07; ASML = ASML.AS). WeRide's actuals and
# estimates do not reconcile to one unit, so its chart says whose units they are instead.
_SUFFIX_REPORTING = {"_KS": "KRW", "_SI": "SGD", "_DE": "EUR", "_PA": "EUR"}
_REVENUE_CCY = {"TSM": "TWD", "ASML": "EUR", "NOK": "EUR", "WRD": "RMB", "SKHY": "KRW"}
_EPS_CCY = {"TSM": "US$ per ADR", "ASML": "EUR", "NOK": "US$ per ADR",
            "WRD": "Yahoo Finance units", "SKHY": "US$ per ADR"}


def reports_in_foreign_currency(key: str) -> bool:
    """A US listing whose company reports in another currency. Yahoo divides its
    US-dollar price by home-currency book value and cash flow, so P/B and FCF yield
    are mixed-currency for these names on every report date."""
    return key in _REVENUE_CCY


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
    """Bar label to the data's own precision: up to 3 decimals, trailing zeros trimmed (41.456,
    23.86, 8.87). Owner 2026-09-29, "11.2 to 11.3 is 0.8?": at one decimal 11.315 printed as
    11.3 and 11.22 as 11.2, so the one-decimal % beside them could not be checked."""
    s = _num_label(v, 3)
    return s.rstrip("0").rstrip(".")


def _shown(v, scale: float = 1.0, nd: int = 3):
    """``v`` as its label prints it (display units, ``nd`` decimals). Every % on a chart is
    worked from these, so it checks out against the numbers beside it."""
    return None if v is None else round(v / scale, nd)


def _pct(cur, ref) -> str:
    """cur vs ref as a % to one decimal ('+5.8%'; owner 2026-09-29: whole numbers hid the
    difference between +21% and +22%). ``+ 0.0`` turns a rounded −0.0 into +0.0."""
    if cur is None or ref is None or ref == 0:
        return ""
    return f"{round((cur / ref - 1) * 100, 1) + 0.0:+,.1f}%".replace("-", "−")


def _growth(cur, prev) -> str:
    """cur vs prev as a % ('+74.9%', '−14.9%'; owner 2026-09-29: a % rather than '1.7×').
    prev is None when the quarter before is not on file — no figure then, never one across a
    gap; none across a zero or negative quarter either."""
    if cur is None or prev is None or prev <= 0 or cur <= 0:
        return ""
    return _pct(cur, prev)


def _growth_tip(frm: str, to: str, cur, prev, how: str = "") -> str:
    """Hover text for a growth label: 'Sep–Nov 2025 → Dec–Feb 2026: +74.9%'."""
    g = _growth(cur, prev)
    return f"{frm} → {to}{' (' + how + ')' if how else ''}: {g}" if g else ""


def _pos(v: float, lo: float, hi: float) -> float:
    return (v - lo) / (hi - lo) * 100 if hi > lo else 0.0


def _chart(cols: list[dict], lo: float, hi: float, *, mini: bool, aria: str, rows_below: list,
           head: str = "") -> str:
    """cols: [{label, year, bar, tick, tip, beat, growth, coming: {est, band, whisker}}]; values
    already scaled. ``beat`` rides beside the estimate's number and ``growth`` (a ``_growth``
    string, vs the column before) sits between the two quarter labels — both drawn only on a
    roomy chart (theme.css), where the rows marked ``ec-row-onplot`` step aside.
    ``head`` = the title; inside ``.ec`` so a wide chart can set it in the label gutter."""
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
            tp = _pos(c["tick"], lo, hi)
            inner += f'<span class="ec-tick" style="bottom:{tp:.2f}%"></span>'
            if c.get("tick_val"):                            # the estimate's number beside its line (wide only)
                beat = f'<b class="ec-tvb">{_t(c["beat"])}</b>' if c.get("beat") else ""
                inner += f'<span class="ec-tv" style="bottom:{tp:.2f}%">{_t(c["tick_val"])}{beat}</span>'
        if c.get("missing"):
            inner += '<span class="ec-miss">not on file</span>' if not mini else '<span class="ec-miss">·</span>'
        grow = ""
        if c.get("growth") and not mini:
            grow = f'<span class="ec-g" title="{_t(c.get("growth_tip", ""))}">{_t(c["growth"])}</span>'
        lab = "" if mini else f'<span class="ec-x">{grow}{_t(c["label"])}<small>{_t(c["year"])}</small></span>'
        axis = f'<span class="ec-zero" style="bottom:{zero:.2f}%"></span>'
        body += (f'<div class="ec-col{" ec-coming" if cm else ""}" title="{_t(c.get("tip", ""))}">'
                 f'<div class="ec-plot">{axis}{inner}</div>{lab}</div>')
    # A table under the axis: row label in a left gutter on a wide chart, above its row on a
    # narrow one (theme.css container query); an empty cell is a dash, never a hole.
    rows = "".join(
        f'<div class="ec-row{" " + cls[0] if cls else ""}"><span class="ec-rh">{_t(h)}</span>'
        + "".join(f'<span class="ec-rc">{_t(v)}</span>' if v else '<span class="ec-rc ec-na">–</span>'
                  for v in vals) + "</div>"
        for h, vals, *cls in rows_below if any(vals))
    return (f'<div class="ec{" ec-mini" if mini else ""}" role="img" aria-label="{_t(aria)}" '
            f'style="--ec-n:{len(cols)}">{head}<div class="ec-cols">{body}</div>{rows}</div>')


def _head(what: str, unit: str) -> str:
    """'<b>Revenue</b>, US$ billions' — the comma drops and the unit takes its own line when the
    title sits in a wide chart's gutter."""
    return (f'<p class="ec-h"><b>{_t(what)}</b><span class="ec-hc">, </span>'
            f'<span class="ec-hu">{_t(unit)}</span></p>')


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
    cv = _shown(cest, scale) if cest else None                            # the coming estimate, as printed
    cols, grows, vs_an, ests = [], [], [], []
    prev, prev_lab = None, ""
    for q in past:
        lab, yr = period_label(q["qe"])
        if q.get("missing"):
            cols.append({"label": lab, "year": yr, "missing": True, "tip": f"{lab} {yr}: not on file"})
            grows.append("")
            vs_an.append("")
            ests.append("")
            prev = None
            continue
        est = q.get("rev_est")
        rv = _shown(q["rev"], scale)
        ev = _shown(est, scale) if est else None
        tip = f"{lab} {yr}: revenue {currency} {_val_label(rv)} {unit}"
        if est:
            tip += f"; analysts expected {_val_label(ev)} ({q.get('rev_est_src') or 'source not recorded'})"
        g = _growth(rv, prev)
        cols.append({"label": lab, "year": yr, "bar": q["rev"] / scale, "val": _val_label(rv),
                     "tick": est / scale if est else None, "tick_val": _val_label(ev) if est else "",
                     "beat": _pct(rv, ev), "tip": tip, "growth": g,
                     "growth_tip": _growth_tip(prev_lab, f"{lab} {yr}", rv, prev)})
        grows.append(g)
        vs_an.append(_pct(rv, ev))
        ests.append(_val_label(ev) if est else "")
        prev, prev_lab = rv, f"{lab} {yr}"
    coming_note = ""
    if coming and (cest or company):
        lab, yr = period_label(coming["qe"])
        band = tuple(x / scale for x in company) if company else None
        wh = tuple(x / scale for x in whisker) if whisker else None
        co = _shown(sum(company) / 2, scale) if company else None           # the forecast's midpoint
        tip = f"{lab} {yr} (coming): analysts expect {_val_label(cv)} {unit}" if cest else f"{lab} {yr} (coming)"
        if company:
            tip += f"; company forecast {_val_label(_shown(company[0], scale))}–{_val_label(_shown(company[1], scale))}"
        g_an = _growth(cv, prev)
        g_co = _growth(co, prev)
        g = "~" + (g_an or g_co) if (g_an or g_co) else ""
        cols.append({"label": lab, "year": yr, "coming": {"est": cest / scale if cest else None, "band": band,
                     "whisker": wh, "val": f"~{_val_label(cv)}" if cest else ""}, "tip": tip,
                     "growth": g, "growth_tip": _growth_tip(prev_lab, f"{lab} {yr}", cv or co, prev,
                                                             "analysts expect" if g_an else "company forecast")})
        grows.append(g)
        vs_an.append("")
        ests.append("")
        parts = []
        if g_an:
            parts.append(f"analysts ~{g_an}")
        if g_co:
            parts.append(f"company forecast ~{g_co}")
        coming_note = ("Coming quarter vs the last: " + " · ".join(parts)) if parts else ""
    on_file = [q for q in past if not q.get("missing")]
    yoy = ""
    if on_file:
        last = on_file[-1]
        ago = next((q for q in on_file if _mi(last["qe"]) - _mi(q["qe"]) == 12), None)
        if ago:
            yoy = _growth(_shown(last["rev"], scale), _shown(ago["rev"], scale))
    aria = (f"Revenue by quarter, {currency} {unit}: " + ", ".join(
        f"{c['label']} {c['year']} {c['val']}" for c in cols if c.get("bar") is not None)
        + (f"; coming quarter analysts expect {_val_label(cv)}" if cest else ""))
    if mini:
        last_g = grows[len(past) - 1] if past and not past[-1].get("missing") else ""
        nxt = grows[-1] if coming and len(grows) > len(past) else ""
        l1 = " · ".join(x for x in ((f"{last_g} vs the one before" if last_g else ""),
                                     (f"{yoy} vs a year ago" if yoy else "")) if x)
        l1 = f"Last quarter: {l1}" if l1 else ("Last quarter not on file" if past and past[-1].get("missing") else "")
        l2 = f"Next: {nxt} ({'analysts' if cest else 'company'})" if nxt else ""
        lines = "".join(f'<p class="ec-note">{_t(x)}</p>' for x in (l1, l2) if x)
        return _chart(cols, 0.0, hi, mini=True, aria=aria, rows_below=[]) + lines
    head = _head("Revenue", f"{currency} {unit}".strip())
    rows = [("vs previous quarter", grows, "ec-row-onplot")]             # between the quarter labels when roomy
    if any(vs_an):
        rows.append((_EST_ROW, ests, "ec-row-narrow"))     # on the chart when it is wide
        rows.append((_BEAT_ROW, vs_an, "ec-row-onplot"))   # beside that number when roomy
    notes = [x for x in ((f"Latest quarter vs a year earlier: {yoy}" if yoy else ""), coming_note) if x]
    note = "".join(f'<p class="ec-note">{_t(x)}</p>' for x in notes)
    return _chart(cols, 0.0, hi, mini=False, aria=aria, rows_below=rows, head=head) + note


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
    cols, vs_an, ests = [], [], []
    for q in past:
        lab, yr = period_label(q["qe"])
        est = q.get("eps_est")
        tip = f"{lab} {yr}: EPS {q['eps']:.2f}" + (f"; analysts expected {est:.2f}" if est is not None else "")
        rv, ev = _shown(q["eps"], nd=2), _shown(est, nd=2)                 # as printed, 2 decimals
        beat = _pct(rv, ev) if ev and rv and ev > 0 and rv > 0 else ""
        cols.append({"label": lab, "year": yr, "bar": q["eps"], "val": _num_label(q["eps"], 2),
                     "tick": est, "tick_val": _num_label(est, 2) if est is not None else "", "beat": beat,
                     "tip": tip})
        vs_an.append(beat)
        ests.append(_num_label(est, 2) if est is not None else "")
    if coming and cest is not None:
        lab, yr = period_label(coming["qe"])
        cols.append({"label": lab, "year": yr, "coming": {"est": cest, "band": company, "whisker": None,
                     "val": f"~{_num_label(cest, 2)}"}, "tip": f"{lab} {yr} (coming): analysts expect {cest:.2f}"})
        vs_an.append("")
        ests.append("")
    aria = f"Earnings per share by quarter, {currency}: " + ", ".join(
        f"{c['label']} {c['year']} {c['val']}" for c in cols if c.get("bar") is not None)
    head = _head("Earnings per share", currency)
    rows = [] if mini else [(_EST_ROW, ests, "ec-row-narrow"), (_BEAT_ROW, vs_an, "ec-row-onplot")]
    return _chart(cols, lo, hi, mini=mini, aria=aria, rows_below=rows, head=head)


def block_html(charts: str, company: bool = False) -> str:
    """Key on top, then the charts, in one ``.ec-block`` ("" without charts). Both surfaces
    use it: the key comes first (owner 2026-09-29), and ``.ec-block``-scoped rules outrank
    Streamlit's markdown ``p`` reset, which zeroed the headings' top margin and set the notes
    at 16px inside the Watchlist drawer."""
    if not charts:
        return ""
    key = key_html(company, beat='class="ec-tvb"' in charts, growth='class="ec-g"' in charts)
    return f'<div class="ec-block">{key}{charts}</div>'


def key_html(company: bool = False, beat: bool = False, growth: bool = False) -> str:
    """The chart key: what the tick and the outlined bar mean (identity is never colour-alone).
    ``beat`` / ``growth`` add entries for the on-plot numbers, shown only on a roomy chart."""
    items = ['<span class="ec-k-bar">reported</span>',
             '<span class="ec-k-tick">what analysts expected beforehand</span>',
             '<span class="ec-k-est">coming quarter — an estimate, not a result</span>']
    if company:
        items.append('<span class="ec-k-band">company\'s own forecast</span>')
    if beat:
        items.append('<span class="ec-k-beat">beside the line: what happened, above (+) or below (−) analysts</span>')
    if growth:
        items.append('<span class="ec-k-g">between quarters: revenue vs the quarter before</span>')
    return '<div class="ec-key">' + "".join(items) + "</div>"
