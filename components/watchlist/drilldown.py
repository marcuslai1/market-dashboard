"""Watchlist drill-down detail HTML builder.

Pure HTML-string generation — no Streamlit calls. The output is intended to be
embedded inside a ``<details>`` element rendered by ``components.watchlist.row``.
"""
from __future__ import annotations

from lib.catalog import CLUSTER_MAP
from lib.charts import (
    ACCENT_LINK,
    STATUS_INFO,
    STATUS_MUTED,
    STATUS_NEG,
    STATUS_NEUTRAL,
    STATUS_POS,
    STATUS_WARN,
    STATUS_WARN_SOFT,
)
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _escape_dollars,
    _fmt_num,
    _safe_href,
    _sign,
)


def _drilldown_section_html(title: str) -> str:
    return f'<div class="dd-section">{title}</div>'


def _consensus_str(rec, n_analysts) -> str:
    """Human form of yfinance's snake_case recommendation, or '—'.

    'strong_buy (58)' read as a raw field leak; 'none' is yfinance's literal
    no-coverage sentinel, not a rating (UX 2026-07-07).
    """
    if not rec or str(rec).lower() == "none":
        return "—"
    label = str(rec).replace("_", " ").strip().capitalize()
    if n_analysts:
        return f"{label} · {int(n_analysts)} analysts"
    return label


def _drilldown_metrics_html(items: list[tuple[str, str]]) -> str:
    visible = [(label, value) for label, value in items if value not in (None, "", "—")]
    if not visible:
        return ""
    cells = "".join(
        f'<div class="dd-metric"><div class="lbl">{label}</div>'
        f'<div class="val">{value}</div></div>'
        for label, value in visible
    )
    return f'<div class="dd-metric-grid">{cells}</div>'


# ── Earnings history (quarter-on-quarter expected vs actual) ──────────────────

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


def render_drilldown_detail_html(tk: str, d: dict, earnings_hist=None) -> str:
    """HTML-string version of _render_drilldown_detail — returns one block of HTML
    suitable for embedding inside a <details> element. No Streamlit calls.

    ``earnings_hist`` (optional) is the ticker's ``earnings_history`` records
    (newest quarter first) for the quarter-on-quarter expected-vs-actual table;
    the caller loads + filters the CSV so this stays Streamlit-free."""
    ccy = d.get("currency", "USD")
    pfx = _ccy_prefix(ccy)
    dec = _ccy_decimals(ccy)

    def _p(v) -> str:
        """Currency-prefixed price with the right decimal count for this ticker."""
        return f"{pfx}{_fmt_num(v, dec)}"

    val = d.get("valuation", {}) or {}
    rr_obj = d.get("risk_reward", {}) or {}
    sma50 = d.get("sma50")
    sma50_rising = d.get("sma50_rising")
    sma_status = (
        "rising" if sma50_rising is True
        else "declining" if sma50_rising is False
        else "—"
    )
    days_above = d.get("days_above_sma50")
    rsi = d.get("rsi_14")
    rsi_zone = d.get("rsi_zone", "")
    vol_sig = d.get("volume_signal", "")
    vol_ratio = d.get("vol_ratio")
    chg5 = d.get("5d_pct")
    m1 = d.get("1mo_pct")
    vs50 = d.get("vs_sma50_pct")
    vs200 = d.get("vs_sma200_pct")

    parts: list[str] = []

    # ── Status strip (caution_source + momentum_warn) ──
    # Compact, visible without expanding any section. Shown only when there's
    # something worth flagging — silent on clean BUY/HOLD with no advisories.
    caution_source = d.get("caution_source")
    momentum_warn = d.get("momentum_warn")
    momentum_reasons = d.get("momentum_warn_reasons") or []
    signal = d.get("signal", "")
    cs_labels = {
        "hard_block": ("Mechanical hard block", STATUS_NEG),
        "claude_override": ("Judgment override", STATUS_WARN),
        "base_scorer": ("Soft caution (base scorer)", STATUS_WARN),
        "rr_gate_fail": ("R:R gate failed", STATUS_NEG),
        "catalyst_override": ("Catalyst override", STATUS_INFO),
        "rcp_terminal": ("RCP terminal", STATUS_NEG),
        "fragility_single_leg": ("Fragility gate — single leg", STATUS_WARN),
        "avoid_source_missing": ("AVOID unsourced", STATUS_WARN),
    }
    status_chips: list[str] = []
    if caution_source and signal not in {"BUY", "HOLD"}:
        # Mapped ids show the plain-English label alone — repeating the raw id
        # beside it leaked pipeline vocabulary into the UI (UX 2026-07-07).
        # Unmapped ids fall back to the raw id: it is the only label we have.
        label, color = cs_labels.get(
            caution_source, (caution_source, STATUS_NEUTRAL)
        )
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.10em;text-transform:uppercase;'
            f'background:rgba(255,255,255,0.05);color:{color};'
            f'padding:3px 8px;border-radius:3px;">'
            f'{label}</span>'
        )
    if momentum_warn:
        # Plain-English label; the reason strings stay verbatim — they are
        # report data (thresholds included), only the chrome is ours.
        reason_str = "; ".join(momentum_reasons) if momentum_reasons else "tape diverging"
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.06em;background:rgba(245,158,11,0.16);'
            f'color:{STATUS_WARN_SOFT};padding:3px 8px;border-radius:3px;">'
            f'Momentum warning · {_escape_dollars(reason_str)}</span>'
        )
    data_anomaly = d.get("data_anomaly")
    if data_anomaly:
        _anom = str(data_anomaly).replace("_", " ").replace("=", " = ")
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.06em;background:rgba(245,158,11,0.16);'
            f'color:{STATUS_WARN_SOFT};padding:3px 8px;border-radius:3px;">'
            f'data anomaly · {_escape_dollars(_anom)}</span>'
        )
    # News-sentiment skew chip (P1-2 slice) — the pipeline's per-name read of
    # the day's headlines, colored by lean. Absent on ~half the corpus → silent.
    _skew = d.get("news_sentiment_skew")
    _skew_colors = {
        "bullish": STATUS_POS,
        "bearish": STATUS_NEG,
        "mixed": STATUS_WARN,
        "neutral": STATUS_NEUTRAL,
    }
    if _skew in _skew_colors:
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.10em;text-transform:uppercase;'
            f'background:rgba(255,255,255,0.05);color:{_skew_colors[_skew]};'
            f'padding:3px 8px;border-radius:3px;">news · {_skew}</span>'
        )
    # Premarket chip (P1-2 slice) — the pipeline-authored phrase captured at
    # report generation ("premarket -0.9% vs prior close"), colored by the
    # move's sign. Snapshot-time context, deliberately not a live quote.
    _pm_phrase = (d.get("premarket") or {}).get("phrase")
    if _pm_phrase:
        _pm_chg = (d.get("premarket") or {}).get("pm_chg_pct")
        _pm_color = (
            STATUS_POS if (_pm_chg or 0) > 0
            else STATUS_NEG if (_pm_chg or 0) < 0
            else STATUS_NEUTRAL
        )
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.06em;background:rgba(255,255,255,0.05);'
            f'color:{_pm_color};padding:3px 8px;border-radius:3px;">'
            f'{_escape_dollars(_pm_phrase)}</span>'
        )
    if status_chips:
        parts.append(
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">'
            + "".join(status_chips) + '</div>'
        )

    # ── Thesis break condition ──
    # Pipeline-injected single sentence: what would invalidate the thesis.
    # High-signal exit guidance — surfaced near the top of the drill-down.
    thesis_break = (d.get("writeup") or {}).get("thesis_break_condition")
    if thesis_break:
        parts.append(_drilldown_section_html("Thesis break condition"))
        parts.append(
            f'<div class="dd-line" style="color:var(--ink-2);">'
            f'{_escape_dollars(thesis_break)}</div>'
        )

    # ── RCP state ──
    rcp = d.get("rcp_state")
    if rcp:
        rcp_phase = rcp.get("current_phase", "")
        rcp_sessions = rcp.get("sessions_since_gap")
        rcp_terminal_outcome = rcp.get("terminal_outcome", "")
        rcp_path_a = rcp.get("path_a_level")
        rcp_path_b = rcp.get("path_b_level")
        _TERMINAL_PHASES = {"failed", "expired", "invalidated"}
        _rcp_phase_colors = {
            "gap_day": STATUS_NEG,
            "cooling_off": STATUS_WARN,
            "graduation_watch": ACCENT_LINK,
            "path_a_confirmed": STATUS_POS,
            "path_b_confirmed": STATUS_POS,
            "failed": STATUS_MUTED,
            "expired": STATUS_MUTED,
            "invalidated": STATUS_MUTED,
        }
        rcp_color = _rcp_phase_colors.get(rcp_phase, STATUS_NEUTRAL)
        rcp_phase_label = rcp_phase.replace("_", " ").title()
        sessions_note = (
            f"  ·  {rcp_sessions} sessions since gap" if rcp_sessions is not None else ""
        )
        parts.append(_drilldown_section_html("Regime Change Pending"))
        # One-line gloss: this was the least self-explanatory block on the
        # site (casual-reader review 2026-07-12) — phase chips and "sessions
        # since gap" meant nothing without the rule they belong to.
        parts.append(
            '<div class="dd-line" style="color:var(--ink-3);font-size:12px;'
            'line-height:1.5;">A single-session move of 10%+ on real news reset '
            'this chart — old trend anchors like the 50-day average no longer '
            'apply. The name re-qualifies only by proving the new level: holding '
            'a retest (Path A) or breaking above the post-gap range (Path B) '
            'within 60 sessions.</div>'
        )
        parts.append(
            f'<div class="dd-line">'
            f'<span style="font-family:var(--mono);font-size:11px;letter-spacing:0.10em;'
            f'text-transform:uppercase;background:rgba(255,255,255,0.05);color:{rcp_color};'
            f'padding:3px 8px;border-radius:3px;font-weight:600;">{rcp_phase_label}</span>'
            f'<span style="color:var(--ink-3);font-size:12px;">{sessions_note}</span>'
            f'</div>'
        )
        if rcp_phase not in _TERMINAL_PHASES:
            _rcp_metrics: list[tuple[str, str]] = []
            if rcp_path_a is not None:
                _rcp_metrics.append(("Path A graduation", _p(rcp_path_a)))
            if rcp_path_b is not None:
                _rcp_metrics.append(("Path B graduation", _p(rcp_path_b)))
            if rcp_sessions is not None:
                _rcp_metrics.append(("Sessions remaining", str(max(0, 60 - rcp_sessions))))
            if _rcp_metrics:
                parts.append(_drilldown_metrics_html(_rcp_metrics))
        else:
            if rcp_terminal_outcome:
                parts.append(
                    f'<div class="dd-line" style="color:var(--ink-3);font-style:italic;">'
                    f'{_escape_dollars(rcp_terminal_outcome)}</div>'
                )
            parts.append(
                f'<div class="dd-line" style="color:{STATUS_MUTED};font-size:12px;">'
                'New step-function catalyst required before re-entry.</div>'
            )

    # ── Catalyst block ──
    # As of 2026-05-30 the catalyst path is narrative-only: the pipeline
    # emits facts (catalyst_event/source/date) with narrative_only=True and
    # no longer produces catalyst_rr / position_tier / extension relaxation.
    # Legacy reports (pre-2026-05-30) carry the old entry-path shape; this
    # block renders both — R:R / tier / paper-trade framing appear only when
    # the legacy fields are actually present.
    catalyst = d.get("catalyst") or {}
    if catalyst:
        narrative_only = bool(catalyst.get("narrative_only"))
        c_rr = d.get("catalyst_rr") or catalyst.get("catalyst_rr") or {}
        c_tier = d.get("catalyst_position_tier") or catalyst.get("catalyst_position_tier") or {}
        c_type = catalyst.get("type") or catalyst.get("catalyst_type") or ""
        c_headline = (catalyst.get("catalyst_event") or catalyst.get("headline")
                      or catalyst.get("description") or "")
        c_source = catalyst.get("catalyst_source") or catalyst.get("source") or ""
        c_url = catalyst.get("url") or ""
        c_date = (catalyst.get("catalyst_date") or catalyst.get("date")
                  or catalyst.get("event_date") or "")
        c_pre_price = catalyst.get("pre_catalyst_close")
        c_rr_ratio = c_rr.get("ratio") or c_rr.get("ratio_raw")
        c_rr_inv = c_rr.get("invalidation")
        c_tier_name = c_tier.get("tier") or ""
        c_max_size = c_tier.get("max_size_pct")
        is_entry_path = bool(c_rr_ratio or c_tier_name)

        title = ("Catalyst context · narrative only"
                 if narrative_only or not is_entry_path
                 else "Catalyst entry path · paper trade only")
        parts.append(_drilldown_section_html(title))
        if c_headline:
            head_html = (
                f'<div class="dd-line"><strong>{_escape_dollars(c_type) or "Catalyst"}.</strong> '
                f'{_escape_dollars(c_headline)}'
            )
            if c_source:
                head_html += f' <span style="color:var(--ink-3);">— {_escape_dollars(c_source)}</span>'
            _c_href = _safe_href(c_url)
            if _c_href:
                head_html += (
                    f' <a href="{_c_href}" target="_blank" rel="noopener noreferrer" '
                    f'style="color:var(--ink-3);font-family:var(--mono);'
                    f'font-size:11px;">[link]</a>'
                )
            head_html += '</div>'
            parts.append(head_html)
        cat_metrics = [("Catalyst date", c_date or "—")]
        # Entry-path numerics are legacy-only; show them solely when present.
        if is_entry_path:
            cat_metrics += [
                ("Catalyst R:R", f"{_fmt_num(c_rr_ratio, 2)}:1" if c_rr_ratio else "—"),
                ("Gap-fill invalidation",
                 _p(c_rr_inv) if c_rr_inv else (
                     _p(c_pre_price) if c_pre_price else "—")),
                ("Position tier",
                 f"{c_tier_name} ({_fmt_num(c_max_size, 0)}% max)"
                 if c_tier_name and c_max_size is not None else (c_tier_name or "—")),
            ]
        else:
            cat_metrics.append(("Signal impact", "Context only — does not change the signal"))
        parts.append(_drilldown_metrics_html(cat_metrics))

    upside_target = rr_obj.get("upside_target")
    upside_pct = rr_obj.get("upside_pct")
    upside_reason = rr_obj.get("upside_reason", "")
    invalidation = rr_obj.get("invalidation")
    invalidation_reason = rr_obj.get("invalidation_reason", "")
    inv_pct = rr_obj.get("downside_pct")
    structural = rr_obj.get("structural_support")
    struct_pct = rr_obj.get("structural_support_pct")
    wide_stop = rr_obj.get("wide_stop_rr")
    if wide_stop is None:
        # Newer reports carry the same deeper-stop ratio under `sizing_rr`
        # (R:R sized to structural support). Surface it here so the corrective
        # "wide-stop" number isn't blank for tight-invalidation names — exactly
        # where it matters and the headline R:R is distorted (UX-BR-2/WL-1/TM-1).
        wide_stop = (rr_obj.get("sizing_rr") or {}).get("ratio")
    rr_label = rr_obj.get("ratio_label", "")
    rr_quality = rr_obj.get("rr_quality", "")

    has_rr = any(v is not None for v in [upside_target, invalidation, structural, wide_stop])
    if has_rr:
        parts.append(_drilldown_section_html("Risk & Reward"))
        if upside_target is not None:
            line = f"<strong>Upside target.</strong> {_p(upside_target)}"
            if upside_pct is not None:
                line += f" (+{_fmt_num(upside_pct, 1)}%)"
            if upside_reason:
                line += f" — {_escape_dollars(upside_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        if invalidation is not None:
            line = f"<strong>Invalidation.</strong> {_p(invalidation)}"
            if inv_pct is not None:
                line += f" (-{_fmt_num(inv_pct, 1)}%)"
            if invalidation_reason:
                line += f" — {_escape_dollars(invalidation_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        # A distorted headline (too-tight stop inflating the ratio) is flagged
        # on the stat itself — the row/action card already show the corrected
        # sizing R:R, so an unmarked 22.5:1 here read as a contradiction.
        _rr_qual_bits = [b for b in (rr_quality,
                                     "tight-stop distorted" if rr_obj.get("rr_distorted") else "")
                         if b]
        _rr_qual = f" ({' · '.join(_rr_qual_bits)})" if _rr_qual_bits else ""
        rr_metrics = [
            ("Headline R:R", f"{rr_label}{_rr_qual}" if rr_label else "—"),
            ("Wide-stop R:R", f"{_fmt_num(wide_stop, 2)}:1" if wide_stop else "—"),
            (
                "Structural support",
                f"{_p(structural)} (-{_fmt_num(struct_pct, 1)}%)"
                if structural else "—",
            ),
        ]
        parts.append(_drilldown_metrics_html(rr_metrics))

    # ── ACCUMULATE Gates ──
    # The 6 mechanical gates the pipeline pre-computes for every ticker.
    # Always rendered so readers can see why a name does or doesn't qualify.
    gates = d.get("accumulate_gates") or {}
    if gates:
        gate_labels = {
            "g1_signal_eligible": "Signal eligible",
            "g2_rr_above_2": "R:R ≥ 2.0",
            "g3_rr_observed": "R:R observed",
            "g5_no_earnings_7d": "No earnings ≤7d",
            "g6_vix_ok": "VIX < 30",
            "g8_rr_robust": "R:R robust",
        }
        all_pass = gates.get("all_mechanical_pass")
        chip_html_list: list[str] = []
        for gkey, glabel in gate_labels.items():
            gate_val = gates.get(gkey)
            if gate_val is True:
                bg, fg, mark = "rgba(34,197,94,0.18)", STATUS_POS, "✓"
            elif gate_val is False:
                bg, fg, mark = "rgba(239,68,68,0.18)", STATUS_NEG, "✗"
            else:
                bg, fg, mark = "rgba(255,255,255,0.05)", "var(--ink-3)", "—"
            chip_html_list.append(
                f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'background:{bg};color:{fg};padding:4px 9px;border-radius:3px;'
                f'font-family:var(--mono);font-size:11px;font-weight:600;'
                f'letter-spacing:0.04em;">'
                f'<span style="font-size:13px;">{mark}</span>{glabel}</span>'
            )
        summary_color = (
            STATUS_POS if all_pass is True
            else STATUS_NEG if all_pass is False
            else "var(--ink-3)"
        )
        summary_text = (
            "All mechanical gates pass — Claude judgment determines ACCUMULATE"
            if all_pass is True
            else "One or more mechanical gates fail — ACCUMULATE blocked"
            if all_pass is False
            else "Gate status unknown"
        )
        parts.append(_drilldown_section_html("ACCUMULATE gates"))
        parts.append(
            '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">'
            + "".join(chip_html_list) + '</div>'
        )
        parts.append(
            f'<div class="dd-line" style="color:{summary_color};font-size:12.5px;">'
            f'{summary_text}</div>'
        )
        # Abstained gates — couldn't be evaluated on incomplete data (NOT the
        # same as a failed gate). Listed so a degraded run reads honestly.
        _abstained = gates.get("abstained") or []
        if _abstained:
            _ab_items = "".join(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'· <strong>{_escape_dollars(str(a.get("gate", "")))}</strong> '
                f'not evaluated — {_escape_dollars(str(a.get("reason", "")))}</div>'
                for a in _abstained if isinstance(a, dict)
            )
            if _ab_items:
                parts.append(
                    '<div style="margin-top:6px;">'
                    '<div style="font-family:var(--mono);font-size:10px;'
                    'letter-spacing:0.08em;text-transform:uppercase;'
                    'color:var(--ink-3);margin-bottom:4px;">Abstained gates</div>'
                    f'{_ab_items}</div>'
                )

    band = d.get("pre_earnings_band") or {}
    if band:
        days_until = band.get("days_until")
        earn_date = band.get("earnings_date") or "—"
        temporal_phrase = band.get("temporal_phrase") or ""
        n_priors = band.get("n_priors")
        avg_up = band.get("avg_up_pct")
        avg_dn = band.get("avg_down_pct")
        max_up = band.get("max_up_pct")
        max_dn = band.get("max_down_pct")
        impl_up = band.get("implied_upper")
        impl_lo = band.get("implied_lower")
        archetype = band.get("setup_archetype")
        rationale = band.get("setup_rationale") or ""
        archetype_pretty = {
            "priced_for_perfection": "Priced for perfection",
            "low_bar_underdog": "Low bar / underdog",
            "neutral": "Neutral",
        }.get(archetype, archetype or "—")
        archetype_color = {
            "priced_for_perfection": STATUS_NEG,
            "low_bar_underdog": STATUS_POS,
            "neutral": STATUS_NEUTRAL,
        }.get(archetype, STATUS_NEUTRAL)
        section_label = f"Earnings setup — {temporal_phrase}" if temporal_phrase else "Earnings setup"
        parts.append(_drilldown_section_html(section_label))
        if archetype:
            parts.append(
                f'<div class="dd-line">'
                f'<strong style="color:{archetype_color};">{archetype_pretty}</strong>'
                f' — {_escape_dollars(rationale)}'
                f'</div>'
            )
        # Implied bull / bear from prior-print averages.
        if avg_up is not None and impl_up is not None:
            parts.append(
                f'<div class="dd-line">'
                f'<strong>Bull case.</strong> {_p(impl_up)} '
                f'({_sign(avg_up)}{_fmt_num(avg_up, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_dn is not None and impl_lo is not None:
            parts.append(
                f'<div class="dd-line">'
                f'<strong>Bear case.</strong> {_p(impl_lo)} '
                f'({_fmt_num(avg_dn, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_up is None and avg_dn is not None:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'All {n_priors} priors moved down — no symmetric bull-side reference.'
                f'</div>'
            )
        if avg_dn is None and avg_up is not None:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'All {n_priors} priors moved up — no symmetric bear-side reference.'
                f'</div>'
            )
        band_metrics = [
            ("Earnings date", earn_date),
            ("Days until", str(days_until) if days_until is not None else "—"),
            (
                "Avg up move",
                f"{_sign(avg_up)}{_fmt_num(avg_up, 1)}%" if avg_up is not None else "—",
            ),
            (
                "Avg down move",
                f"{_fmt_num(avg_dn, 1)}%" if avg_dn is not None else "—",
            ),
            (
                "Max up move",
                f"{_sign(max_up)}{_fmt_num(max_up, 1)}%" if max_up is not None else "—",
            ),
            (
                "Max down move",
                f"{_fmt_num(max_dn, 1)}%" if max_dn is not None else "—",
            ),
        ]
        parts.append(_drilldown_metrics_html(band_metrics))

    # ── Earnings history (quarter-on-quarter expected vs actual) ──
    # Sits right after the pre-earnings setup: "here's the setup for the coming
    # print" → "here's the last 8 quarters' beat/miss + revenue." Data comes
    # from the separate earnings_history.csv, threaded in by the caller (this
    # module stays Streamlit-free). Silent when the ticker has no rows.
    _eh_section = _earnings_history_html(earnings_hist) if earnings_hist else ""
    if _eh_section:
        parts.append(_drilldown_section_html("Earnings history"))
        parts.append(_eh_section)

    # ── Thesis highlights ──
    # Pipeline-emitted guardrail bullets that matched the day's news (~5/29 names);
    # e.g. MSFT "~45% of $625B RPO is OpenAI-linked". Surfaced as an amber-bordered
    # list above Technicals — closes the one live surfacing gap (2026-07-04).
    _thesis_highlights = [
        str(b).strip() for b in (d.get("thesis_highlights") or []) if b and str(b).strip()
    ]
    if _thesis_highlights:
        parts.append(_drilldown_section_html("Thesis highlights"))
        for _hl in _thesis_highlights:
            parts.append(
                f'<div class="dd-line" style="border-left:2px solid {STATUS_WARN};'
                f'padding-left:10px;margin:0 0 6px;color:var(--ink-2);">'
                f'{_escape_dollars(_hl)}</div>'
            )

    parts.append(_drilldown_section_html("Technicals"))
    drawdown_3mo = d.get("drawdown_3mo_pct")
    vs_cluster = d.get("vs_cluster_chg_pct")
    tech_metrics = [
        ("vs 50-day", f"{_sign(vs50)}{_fmt_num(vs50, 1)}%" if vs50 is not None else "—"),
        ("vs 200-day", f"{_sign(vs200)}{_fmt_num(vs200, 1)}%" if vs200 is not None else "—"),
        ("SMA50",
         f"{_p(sma50)} ({sma_status})" if sma50 else "—"),
        ("Days above SMA50", str(days_above) if days_above is not None else "—"),
        ("RSI (14d)", f"{_fmt_num(rsi, 0)} {rsi_zone}" if rsi else "—"),
        ("Volume signal",
         f"{vol_sig} ({_fmt_num(vol_ratio, 2)}x)" if vol_sig else "—"),
        ("5-day return",
         f"{_sign(chg5)}{_fmt_num(chg5, 1)}%" if chg5 is not None else "—"),
        ("1-month return",
         f"{_sign(m1)}{_fmt_num(m1, 1)}%" if m1 is not None else "—"),
        # P1-2 slice: the day's move relative to the cluster median — the
        # pipeline's relative-strength read, rendered nowhere until 2026-07-02.
        ("vs cluster (1d)",
         f"{_sign(vs_cluster)}{_fmt_num(vs_cluster, 2)}%" if vs_cluster is not None else "—"),
        ("3mo drawdown",
         f"{_fmt_num(drawdown_3mo, 1)}%" if drawdown_3mo is not None else "—"),
    ]
    parts.append(_drilldown_metrics_html(tech_metrics))

    supports = d.get("support_zones") or []
    resistances = d.get("resistance_zones") or []
    if supports or resistances:
        parts.append(_drilldown_section_html("Key Levels"))
        if supports:
            parts.append(
                '<div class="dd-line"><strong>Support:</strong> '
                + ", ".join(_p(s) for s in supports)
                + '</div>'
            )
        if resistances:
            parts.append(
                '<div class="dd-line"><strong>Resistance:</strong> '
                + ", ".join(_p(r) for r in resistances)
                + '</div>'
            )

    fpe = val.get("forward_pe")
    peg = val.get("peg_ratio")
    rev_g = val.get("revenue_growth_pct")
    cluster_med_pe = val.get("cluster_median_pe")
    pe_vs_cluster = val.get("pe_vs_cluster_pct")
    fcf_y = val.get("fcf_yield_pct")
    div_y = val.get("dividend_yield_pct")
    pb = val.get("price_to_book")
    consensus = (val.get("analyst_consensus") or {})
    rec = consensus.get("recommendation", "")
    n_analysts = consensus.get("num_analysts")
    eps_g = consensus.get("earnings_growth_pct")

    val_metrics = [
        ("Cluster", CLUSTER_MAP.get(tk, "—")),
        ("Forward P/E", f"{_fmt_num(fpe, 1)}x" if fpe else "—"),
        ("Cluster median P/E",
         f"{_fmt_num(cluster_med_pe, 1)}x ({_sign(pe_vs_cluster)}{_fmt_num(pe_vs_cluster, 0)}%)"
         if cluster_med_pe else "—"),
        ("PEG", _fmt_num(peg, 2)),
        ("Revenue growth",
         f"{_sign(rev_g)}{_fmt_num(rev_g, 1)}%" if rev_g is not None else "—"),
        ("FCF yield", f"{_sign(fcf_y)}{_fmt_num(fcf_y, 2)}%" if fcf_y is not None else "—"),
        ("Dividend yield", f"{_fmt_num(div_y, 2)}%" if div_y else "—"),
        ("Price / Book", f"{_fmt_num(pb, 2)}x" if pb else "—"),
        ("Analyst consensus", _consensus_str(rec, n_analysts)),
        ("Est. EPS growth",
         f"{_sign(eps_g)}{_fmt_num(eps_g, 1)}%" if eps_g is not None else "—"),
    ]
    parts.append(_drilldown_section_html("Valuation"))
    parts.append(_drilldown_metrics_html(val_metrics))

    # ── Thesis pillars (support_legs) ──
    support_legs = d.get("support_legs")
    if support_legs is not None:
        is_fragility = d.get("caution_source") == "fragility_single_leg"
        parts.append(_drilldown_section_html("Thesis pillars"))
        if is_fragility:
            parts.append(
                f'<div class="dd-line" style="color:{STATUS_WARN};font-size:12.5px;">'
                'Single-leg fragility gate triggered — signal capped to WATCH.</div>'
            )
        leg_color = STATUS_NEG if is_fragility else STATUS_POS
        for _leg in (support_legs or []):
            parts.append(
                f'<div class="dd-line" style="display:flex;align-items:baseline;gap:8px;">'
                f'<span style="color:{leg_color};font-size:14px;flex-shrink:0;">·</span>'
                f'<span>{_escape_dollars(str(_leg))}</span>'
                f'</div>'
            )

    # ── Avoid source citation ──
    avoid_source = d.get("avoid_source")
    if avoid_source and isinstance(avoid_source, dict):
        _av_pub = avoid_source.get("publication", "")
        _av_frag = avoid_source.get("headline_fragment", "")
        _av_date = avoid_source.get("date", "")
        _av_url = avoid_source.get("url", "")
        if _av_pub or _av_frag:
            parts.append(_drilldown_section_html("Avoid source"))
            _cite_parts: list[str] = []
            if _av_pub:
                _cite_parts.append(f'<strong>{_escape_dollars(_av_pub)}</strong>')
            if _av_frag:
                _cite_parts.append(f'"{_escape_dollars(_av_frag)}"')
            if _av_date:
                _cite_parts.append(
                    f'<span style="color:var(--ink-3);">{_escape_dollars(_av_date)}</span>'
                )
            _cite_html = " · ".join(_cite_parts)
            _av_href = _safe_href(_av_url)
            if _av_href:
                _cite_html += (
                    f' <a href="{_av_href}" target="_blank" rel="noopener noreferrer" '
                    f'style="color:var(--ink-3);font-family:var(--mono);font-size:11px;">[link]</a>'
                )
            parts.append(f'<div class="dd-line">{_cite_html}</div>')

    # ── Earnings results in news ──
    ern = d.get("earnings_results_in_news")
    if ern and isinstance(ern, dict):
        _ern_headline = ern.get("headline", "")
        _ern_source = ern.get("source", "")
        _ern_url = ern.get("url", "")
        if _ern_headline:
            parts.append(_drilldown_section_html("Earnings result"))
            _ern_html = f'<div class="dd-line">"{_escape_dollars(_ern_headline)}"'
            if _ern_source:
                _ern_html += (
                    f' <span style="color:var(--ink-3);">— {_escape_dollars(_ern_source)}</span>'
                )
            _ern_href = _safe_href(_ern_url)
            if _ern_href:
                _ern_html += (
                    f' <a href="{_ern_href}" target="_blank" rel="noopener noreferrer" '
                    f'style="color:var(--ink-3);font-family:var(--mono);font-size:11px;">[link]</a>'
                )
            _ern_html += '</div>'
            parts.append(_ern_html)

    return "".join(parts)
