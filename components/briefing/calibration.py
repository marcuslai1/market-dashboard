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

import streamlit as st

from lib.cards import render_section_head
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
    """True when a signal_performance bucket is single-regime or thin.

    Sample-size honesty: when the pipeline exports its own ``thin`` flag
    (alpha-n floor AND ≥5 independent episodes — commit 5dc0fa3 upstream),
    that flag replaces the local ``n < _MIN_MATURED_N`` floor; older reports
    keep the local heuristic. ``single_regime`` stays a gate in both paths —
    regime coverage is orthogonal to sample size, and a single-regime cell
    reading "decision-grade" would contradict the pipeline's own banner.
    """
    if not perf:
        return True
    if perf.get("single_regime"):
        return True
    if "thin" in perf:
        return bool(perf["thin"])
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
            "n_episodes": perf.get("n_episodes"),
            "ep_mean": perf.get("alpha_episode_mean_10d"),
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


def _decayed_full_line(decayed_full: dict | None) -> str:
    """One-line full-corpus decayed+shrunk view — the honest "no 60d cliff" α.

    Built from ``signal_performance_decayed_full`` (upstream 2934f47): episodes
    over the FULL corpus with old outcomes faded by half-life and thin cells
    shrunk toward the skeptical prior (0% α / 50% hit) — a small-episode signal
    SHOULD read muted here. Shows the shrunk α per signal in SIGNAL_ORDER; the
    decayed-only intermediates stay unshown (one honest number beats two
    near-duplicates). Returns "" when the report predates the fields, so
    pre-adoption markup is unchanged. Same pre-cutover pooling caveat as
    ``taxonomy_discrimination.full_corpus``. Plain text — the caller escapes it.
    """
    df = decayed_full or {}
    bits = []
    for sig in SIGNAL_ORDER:
        cell = df.get(sig)
        if not cell:
            continue
        ep = cell.get("n_episodes")
        ep_txt = f" ({int(ep)} ep)" if ep is not None else ""
        bits.append(f"{sig} {_pct(cell.get('alpha_shrunk_10d'))}{ep_txt}")
    if not bits:
        return ""
    return f"Full corpus, decayed + shrunk α/10d: {' · '.join(bits)}"


def _decay_knobs_caption(decay_shrinkage: dict | None) -> str:
    """Short caveat bit naming the decay/shrinkage knobs, or "" when absent.

    Anchors the full-corpus line's numbers to the knobs that produced them
    (``decay_shrinkage``, additive upstream field); the Terminology page
    carries the full definitions, so this stays telegraphic.
    """
    ds = decay_shrinkage or {}
    bits = []
    halflife = ds.get("halflife_days")
    if halflife is not None:
        bits.append(f"decay half-life {int(halflife)}d")
    strength = ds.get("strength")
    if strength is not None:
        min_ep = ds.get("min_sample")
        tail = f" (min {int(min_ep)} ep)" if min_ep is not None else ""
        bits.append(f"shrinkage {strength:g}{tail}")
    return " · ".join(bits)


def _scorecard_table_html(rows: list) -> str:
    """A .ep-table of signal → today-count, n, win%, avg-10d, alpha.

    When any row carries the pipeline's episode fields, the sample cell
    becomes "n · Nep" (overlapping daily rows can't pose as independent
    observations) and an α/ep column shows the one-episode-one-vote mean.
    Field-absent corpora render exactly the pre-adoption markup. Low-
    confidence rows carry ``data-lowconf="1"`` for CSS muting. Returns ''
    when there are no rows.
    """
    if not rows:
        return ""
    has_ep = any(r["n_episodes"] is not None for r in rows)
    trs = []
    for r in rows:
        lc = ' data-lowconf="1"' if r["low_conf"] else ""
        win = f'{_fmt_num(r["win"], 0)}%' if r["win"] is not None else "—"
        n_cell = _fmt_num(r["n"], 0)
        if has_ep and r["n_episodes"] is not None:
            n_cell = f'{n_cell} · {int(r["n_episodes"])} ep'
        ep_td = (f'<td class="num" data-l="alpha/ep">{_pct(r["ep_mean"])}</td>'
                 if has_ep else "")
        trs.append(
            f"<tr{lc}><td>{_signal_pill_html(r['signal'], small=True)}</td>"
            f'<td class="num" data-l="Today">{r["today"]}</td>'
            f'<td class="num" data-l="n">{n_cell}</td>'
            f'<td class="num" data-l="Win">{win}</td>'
            f'<td class="num" data-l="Avg 10d">{_pct(r["avg"])}</td>'
            f'<td class="num" data-l="alpha">{_pct(r["alpha"])}</td>{ep_td}</tr>'
        )
    # α headers ride in a .lc span: .ep-table th uppercases text, and Greek α
    # capitalizes to Α — pixel-identical to Latin "A" (UX 2026-07-07).
    # The phone data-l labels are ALSO uppercased (stack-m ::before), so they
    # spell out "alpha" instead of carrying the glyph.
    ep_th = '<th class="num"><span class="lc">α/ep</span></th>' if has_ep else ""
    return (
        '<div class="tk-scroll"><table class="ep-table cal-scorecard stack-m">'
        '<thead><tr><th>Signal</th><th class="num">Today</th>'
        '<th class="num">n</th><th class="num">Win</th>'
        f'<th class="num">Avg 10d</th><th class="num"><span class="lc">α</span></th>{ep_th}</tr></thead>'
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
            # Point-of-use gloss for the confidence word (casual-reader
            # review 2026-07-12) — the full caveat still lives in the body.
            if row["low_conf"]:
                conf = "low-confidence"
                conf_tip = "Thin sample or single market regime — treat as provisional."
            else:
                conf = "decision-grade"
                conf_tip = (
                    "Enough matured calls across two or more market regimes "
                    "to lean on this number."
                )
            n = counts[dominant]
            names = "name" if n == 1 else "names"
            return (
                '<span class="cal-headline">'
                f"{_signal_pill_html(dominant, small=True)}"
                f'<span class="cal-head-txt">most common today ({n}&nbsp;{names}) · '
                f'{_pct(row["alpha"])} α / 10d · '
                f'<span class="cal-conf" title="{conf_tip}">{conf}</span></span></span>'
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

    fc_line = _decayed_full_line(ci.get("signal_performance_decayed_full"))
    if fc_line:
        parts.append(f'<p class="cal-fullcorpus">{_escape_dollars(fc_line)}</p>')

    tax_line = _taxonomy_line(ci.get("taxonomy_discrimination"))
    if tax_line:
        parts.append(f'<p class="cal-taxonomy">{_escape_dollars(tax_line)}</p>')

    banner = (ci.get("confidence_banner") or "").strip()
    window = _window_caption(ci.get("data_window"))
    knobs = _decay_knobs_caption(ci.get("decay_shrinkage"))
    if banner or window or knobs:
        caveat_bits = []
        if banner:
            caveat_bits.append(_escape_dollars(banner))
        if window:
            caveat_bits.append(window)  # dates already escaped inside
        if knobs:
            caveat_bits.append(_escape_dollars(knobs))
        parts.append(f'<p class="cal-caveat">{"&nbsp; ".join(caveat_bits)}</p>')

    parts.append("</div>")
    return f'<details class="cal-band cal-details">{"".join(parts)}</details>'


def render_calibration(calibration_insights: dict | None, watchlist: dict) -> None:
    """Briefing signal-calibration band — the pipeline's signal-accuracy
    self-assessment (review P1-2).

    Silent when the report carries no ``calibration_insights`` (older reports /
    the ~56% without it); on the latest report it is present.
    """
    ci = calibration_insights or {}
    if not ci.get("signal_performance"):
        return
    render_section_head("Signal Calibration", "How today's signals have actually performed")
    st.markdown(
        _calibration_html(ci, watchlist),
        unsafe_allow_html=True,
    )
