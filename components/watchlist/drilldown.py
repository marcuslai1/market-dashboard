"""Watchlist drill-down detail HTML builder.

Pure HTML-string generation — no Streamlit calls. The output is intended to be
embedded inside a ``<details>`` element rendered by ``components.watchlist.row``.
"""
from __future__ import annotations

from lib.catalog import CLUSTER_MAP
from lib.formatters import _escape_dollars, _fmt_num, _sign


def _drilldown_section_html(title: str) -> str:
    return f'<div class="dd-section">{title}</div>'


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


def render_drilldown_detail_html(tk: str, d: dict) -> str:
    """HTML-string version of _render_drilldown_detail — returns one block of HTML
    suitable for embedding inside a <details> element. No Streamlit calls."""
    ccy = d.get("currency", "USD")
    pfx = "S$" if ccy == "SGD" else "$"
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
        "hard_block": ("Mechanical hard block", "#ef4444"),
        "claude_override": ("Judgment override", "#f59e0b"),
        "base_scorer": ("Soft caution (base scorer)", "#f59e0b"),
        "rr_gate_fail": ("R:R gate failed", "#ef4444"),
        "catalyst_override": ("Catalyst override", "#3498db"),
        "rcp_terminal": ("RCP terminal", "#ef4444"),
        "fragility_single_leg": ("Fragility gate — single leg", "#f59e0b"),
        "avoid_source_missing": ("AVOID unsourced", "#f59e0b"),
    }
    status_chips: list[str] = []
    if caution_source and signal not in {"BUY", "HOLD"}:
        label, color = cs_labels.get(
            caution_source, (caution_source, "#9ca3af")
        )
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.10em;text-transform:uppercase;'
            f'background:rgba(255,255,255,0.05);color:{color};'
            f'padding:3px 8px;border-radius:3px;">'
            f'{label} · {caution_source}</span>'
        )
    if momentum_warn:
        reason_str = "; ".join(momentum_reasons) if momentum_reasons else "tape diverging"
        status_chips.append(
            f'<span style="font-family:var(--mono);font-size:10.5px;'
            f'letter-spacing:0.06em;background:rgba(245,158,11,0.16);'
            f'color:#fbb454;padding:3px 8px;border-radius:3px;">'
            f'momentum_warn · {_escape_dollars(reason_str)}</span>'
        )
    if status_chips:
        parts.append(
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">'
            + "".join(status_chips) + '</div>'
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
            "gap_day": "#ef4444",
            "cooling_off": "#f59e0b",
            "graduation_watch": "#3b82f6",
            "path_a_confirmed": "#22c55e",
            "path_b_confirmed": "#22c55e",
            "failed": "#6b7280",
            "expired": "#6b7280",
            "invalidated": "#6b7280",
        }
        rcp_color = _rcp_phase_colors.get(rcp_phase, "#9ca3af")
        rcp_phase_label = rcp_phase.replace("_", " ").title()
        sessions_note = (
            f"  ·  {rcp_sessions} sessions since gap" if rcp_sessions is not None else ""
        )
        parts.append(_drilldown_section_html("Regime Change Pending"))
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
                _rcp_metrics.append(("Path A graduation", f"{pfx}{_fmt_num(rcp_path_a, 2)}"))
            if rcp_path_b is not None:
                _rcp_metrics.append(("Path B graduation", f"{pfx}{_fmt_num(rcp_path_b, 2)}"))
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
                '<div class="dd-line" style="color:#6b7280;font-size:12px;">'
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
            if c_url:
                head_html += (
                    f' <a href="{c_url}" target="_blank" '
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
                 f"{pfx}{_fmt_num(c_rr_inv, 2)}" if c_rr_inv else (
                     f"{pfx}{_fmt_num(c_pre_price, 2)}" if c_pre_price else "—")),
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
    rr_label = rr_obj.get("ratio_label", "")
    rr_quality = rr_obj.get("rr_quality", "")

    has_rr = any(v is not None for v in [upside_target, invalidation, structural, wide_stop])
    if has_rr:
        parts.append(_drilldown_section_html("Risk & Reward"))
        if upside_target is not None:
            line = f"<strong>Upside target.</strong> {pfx}{_fmt_num(upside_target, 2)}"
            if upside_pct is not None:
                line += f" (+{_fmt_num(upside_pct, 1)}%)"
            if upside_reason:
                line += f" — {_escape_dollars(upside_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        if invalidation is not None:
            line = f"<strong>Invalidation.</strong> {pfx}{_fmt_num(invalidation, 2)}"
            if inv_pct is not None:
                line += f" (-{_fmt_num(inv_pct, 1)}%)"
            if invalidation_reason:
                line += f" — {_escape_dollars(invalidation_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        rr_metrics = [
            ("Headline R:R", f"{rr_label} ({rr_quality})" if rr_label else "—"),
            ("Wide-stop R:R", f"{_fmt_num(wide_stop, 2)}:1" if wide_stop else "—"),
            (
                "Structural support",
                f"{pfx}{_fmt_num(structural, 2)} (-{_fmt_num(struct_pct, 1)}%)"
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
                bg, fg, mark = "rgba(34,197,94,0.18)", "#22c55e", "✓"
            elif gate_val is False:
                bg, fg, mark = "rgba(239,68,68,0.18)", "#ef4444", "✗"
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
            "#22c55e" if all_pass is True
            else "#ef4444" if all_pass is False
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
            "priced_for_perfection": "#ef4444",
            "low_bar_underdog": "#22c55e",
            "neutral": "#9ca3af",
        }.get(archetype, "#9ca3af")
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
                f'<strong>Bull case.</strong> {pfx}{_fmt_num(impl_up, 2)} '
                f'({_sign(avg_up)}{_fmt_num(avg_up, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_dn is not None and impl_lo is not None:
            parts.append(
                f'<div class="dd-line">'
                f'<strong>Bear case.</strong> {pfx}{_fmt_num(impl_lo, 2)} '
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

    parts.append(_drilldown_section_html("Technicals"))
    drawdown_3mo = d.get("drawdown_3mo_pct")
    tech_metrics = [
        ("vs 50-day", f"{_sign(vs50)}{_fmt_num(vs50, 1)}%" if vs50 is not None else "—"),
        ("vs 200-day", f"{_sign(vs200)}{_fmt_num(vs200, 1)}%" if vs200 is not None else "—"),
        ("SMA50",
         f"{pfx}{_fmt_num(sma50, 2)} ({sma_status})" if sma50 else "—"),
        ("Days above SMA50", str(days_above) if days_above is not None else "—"),
        ("RSI (14d)", f"{_fmt_num(rsi, 0)} {rsi_zone}" if rsi else "—"),
        ("Volume signal",
         f"{vol_sig} ({_fmt_num(vol_ratio, 2)}x)" if vol_sig else "—"),
        ("5-day return",
         f"{_sign(chg5)}{_fmt_num(chg5, 1)}%" if chg5 is not None else "—"),
        ("1-month return",
         f"{_sign(m1)}{_fmt_num(m1, 1)}%" if m1 is not None else "—"),
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
                + ", ".join(f"{pfx}{_fmt_num(s, 2)}" for s in supports)
                + '</div>'
            )
        if resistances:
            parts.append(
                '<div class="dd-line"><strong>Resistance:</strong> '
                + ", ".join(f"{pfx}{_fmt_num(r, 2)}" for r in resistances)
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
        ("Analyst consensus",
         f"{rec} ({n_analysts})" if rec and n_analysts else (rec or "—")),
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
                '<div class="dd-line" style="color:#f59e0b;font-size:12.5px;">'
                'Single-leg fragility gate triggered — signal capped to WATCH.</div>'
            )
        leg_color = "#ef4444" if is_fragility else "#22c55e"
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
            if _av_url:
                _cite_html += (
                    f' <a href="{_av_url}" target="_blank" '
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
            if _ern_url:
                _ern_html += (
                    f' <a href="{_ern_url}" target="_blank" '
                    f'style="color:var(--ink-3);font-family:var(--mono);font-size:11px;">[link]</a>'
                )
            _ern_html += '</div>'
            parts.append(_ern_html)

    return "".join(parts)
