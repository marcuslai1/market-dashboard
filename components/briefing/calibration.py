"""Briefing · Signal-calibration band.

Surfaces ``calibration_insights`` — the pipeline's own signal-accuracy
self-assessment (per-signal win-rate / alpha, taxonomy ordering, confidence
caveat), present in ~44% of reports and rendered nowhere (review finding P1-2).
Confidence-gated (honest about the block's own "not yet decision-grade" caveat —
every bucket is single-regime today) and anchored to today's live signals so a
glance answers "how much should I trust the signals I'm acting on today?".
"""
from __future__ import annotations

from collections import Counter

from lib.catalog import SIGNAL_ORDER
from lib.formatters import _escape_dollars, _fmt_num, _sign
from lib.pills import _signal_pill_html

# Small-sample floor for a proportion: buckets with fewer than this many matured
# observations are treated as low-confidence regardless of regime coverage.
_MIN_MATURED_N = 30


def _today_signal_counts(watchlist: dict) -> Counter:
    """Count truthy signals across today's watchlist entries.

    Null / absent signals are skipped — they are not actionable and would only
    dilute the "dominant signal today" headline.
    """
    counts: Counter = Counter()
    for entry in (watchlist or {}).values():
        sig = (entry or {}).get("signal")
        if sig:
            counts[sig] += 1
    return counts


def _is_low_confidence(perf: dict) -> bool:
    """True when a signal_performance bucket is single-regime or thin-n.

    The block self-flags every bucket single_regime today, so this honestly
    gates the whole card as low-confidence. ``_MIN_MATURED_N`` catches thin
    samples once multiple regimes have accumulated.
    """
    if not perf:
        return True
    if perf.get("single_regime"):
        return True
    return (perf.get("n_matured_10d") or 0) < _MIN_MATURED_N


def _scorecard_rows(signal_performance: dict, today_counts) -> list:
    """Ordered scorecard rows for every bucket present in *signal_performance*.

    Rows follow SIGNAL_ORDER (best→worst) so BUY/ACCUMULATE lead even at zero
    current exposure. Each row carries today's exposure count and a
    low-confidence flag.
    """
    sp = signal_performance or {}
    counts = today_counts or {}
    rows = []
    for sig in SIGNAL_ORDER:
        perf = sp.get(sig)
        if not perf:
            continue
        rows.append({
            "signal": sig,
            "today": int(counts.get(sig, 0)),
            "n": perf.get("n_matured_10d"),
            "win": perf.get("win_rate_pct"),
            "avg": perf.get("avg_return_10d"),
            "alpha": perf.get("alpha_10d"),
            "low_conf": _is_low_confidence(perf),
        })
    return rows


def _taxonomy_line(taxonomy: dict) -> str:
    """One-line "do better signals produce better outcomes?" verdict.

    Built from the *full_corpus* ordering (the *in_window* block is usually
    empty / INSUFFICIENT on the short lookback). Returns "" when unavailable so
    the caller omits the line. Plain text — the caller escapes it.
    """
    fc = (taxonomy or {}).get("full_corpus") or {}
    ordering = (fc.get("observed_ordering_str") or "").strip()
    if not ordering:
        return ""
    mono = (fc.get("monotonic") or "").strip().upper()
    mono_txt = {
        "YES": "monotonic",
        "PARTIAL": "partially monotonic",
        "NO": "not monotonic",
        "INSUFFICIENT": "insufficient data",
    }.get(mono, mono.lower())
    tail = f" · {mono_txt}" if mono_txt else ""
    return f"Signal ordering (full corpus): {ordering}{tail}"


def _pct(value, decimals: int = 1) -> str:
    """Signed percentage like '+2.7%' / '-3.0%', or '—' when missing."""
    if value is None:
        return "—"
    return f"{_sign(value)}{_fmt_num(value, decimals)}%"


def _window_caption(data_window: dict) -> str:
    """'60-day window · 2026-05-02 – 2026-07-01' from data_window, or ''.

    ISO dates are shown as-is (robust + cross-platform); month-name humanizing
    is a deferred cosmetic nicety.
    """
    dw = data_window or {}
    days = dw.get("lookback_days")
    frm = dw.get("from")
    to = dw.get("to")
    bits = []
    if days:
        bits.append(f"{_fmt_num(days, 0)}-day window")
    if frm and to:
        bits.append(f"{_escape_dollars(str(frm))} – {_escape_dollars(str(to))}")
    return " · ".join(bits)


def _scorecard_table_html(rows: list) -> str:
    """A .ep-table of signal → today-count, n, win%, avg-10d, alpha.

    Low-confidence rows carry ``data-lowconf="1"`` for CSS muting. Returns ''
    when there are no rows.
    """
    if not rows:
        return ""
    trs = []
    for r in rows:
        lc = ' data-lowconf="1"' if r["low_conf"] else ""
        win = f'{_fmt_num(r["win"], 0)}%' if r["win"] is not None else "—"
        trs.append(
            f"<tr{lc}><td>{_signal_pill_html(r['signal'], small=True)}</td>"
            f'<td class="num">{r["today"]}</td>'
            f'<td class="num">{_fmt_num(r["n"], 0)}</td>'
            f'<td class="num">{win}</td>'
            f'<td class="num">{_pct(r["avg"])}</td>'
            f'<td class="num">{_pct(r["alpha"])}</td></tr>'
        )
    return (
        '<div class="tk-scroll"><table class="ep-table cal-scorecard">'
        '<thead><tr><th>Signal</th><th class="num">Today</th>'
        '<th class="num">n</th><th class="num">Win</th>'
        '<th class="num">Avg 10d</th><th class="num">α</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )


def _headline_html(rows: list, today_counts) -> str:
    """Collapsed-row headline anchored to today's dominant signal.

    Names the most common current signal (ties broken by SIGNAL_ORDER,
    best-first), its 10d alpha, and its confidence state. Falls back to a
    generic label when that signal has no scorecard row.
    """
    counts = today_counts or {}
    if counts:
        order = {s: i for i, s in enumerate(SIGNAL_ORDER)}
        dominant = sorted(counts, key=lambda s: (-counts[s], order.get(s, 99)))[0]
        row = next((r for r in rows if r["signal"] == dominant), None)
        if row is not None:
            conf = "low-confidence" if row["low_conf"] else "decision-grade"
            n = counts[dominant]
            names = "name" if n == 1 else "names"
            return (
                '<span class="cal-headline">'
                f"{_signal_pill_html(dominant, small=True)}"
                f'<span class="cal-head-txt">most common today ({n}&nbsp;{names}) · '
                f'{_pct(row["alpha"])} α / 10d · '
                f'<span class="cal-conf">{conf}</span></span></span>'
            )
    return '<span class="cal-headline cal-head-txt">Signal calibration · 60-day window</span>'


def _calibration_html(calibration_insights: dict, watchlist: dict) -> str:
    """Full calibration band HTML, or a muted placeholder when empty."""
    ci = calibration_insights or {}
    sp = ci.get("signal_performance") or {}
    if not sp:
        return '<div class="cal-band cal-empty">No calibration data in this report.</div>'

    today = _today_signal_counts(watchlist)
    rows = _scorecard_rows(sp, today)

    parts = [
        f'<summary class="cal-summary">{_headline_html(rows, today)}</summary>',
        '<div class="cal-body">',
        _scorecard_table_html(rows),
    ]

    tax_line = _taxonomy_line(ci.get("taxonomy_discrimination"))
    if tax_line:
        parts.append(f'<p class="cal-taxonomy">{_escape_dollars(tax_line)}</p>')

    banner = (ci.get("confidence_banner") or "").strip()
    window = _window_caption(ci.get("data_window"))
    if banner or window:
        caveat_bits = []
        if banner:
            caveat_bits.append(_escape_dollars(banner))
        if window:
            caveat_bits.append(window)  # dates already escaped inside
        parts.append(f'<p class="cal-caveat">{"&nbsp; ".join(caveat_bits)}</p>')

    parts.append("</div>")
    return f'<details class="cal-band cal-details">{"".join(parts)}</details>'
