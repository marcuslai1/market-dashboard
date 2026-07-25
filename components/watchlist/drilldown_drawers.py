"""The drill-down's three collapsed drawers — the material only an auditor wants.

The shipped drill-down stacked fifteen undifferentiated sections, so a reader who
opened a row got everything at once and no floor. The 2026-07-25 redesign keeps
every block but sorts them by who needs them: the consequential facts stay in the
card (``drilldown.py``), and these three drawers hold the rest, collapsed.

* **Earnings** — the pre-print setup band and the quarter-on-quarter history.
* **Risk & reward detail** — the prose exits, the three R:R figures, key levels.
* **Pipeline detail** — ACCUMULATE gates, Regime Change Pending, catalyst
  context, the AVOID citation, the earnings headline.

Raw ``<details>`` rather than ``st.expander``: these live *inside* a
markdown-injected ``<details>``, where a Streamlit expander cannot go. Nested
``<details>`` is valid HTML and the drill-down already relies on
``unsafe_allow_html``.

A drawer whose every block is absent does not render at all, so a thin report
does not sprout three empty summaries.
"""
from __future__ import annotations

from components.watchlist.earnings_history import _earnings_history_html
from lib.charts import (
    ACCENT_LINK,
    STATUS_MUTED,
    STATUS_NEG,
    STATUS_NEUTRAL,
    STATUS_POS,
)
from lib.formatters import _escape_dollars, _fmt_num, _safe_href, _sign

#: Gate conditions, data-quality warnings and falsifiers all take terracotta.
#: Amber is WATCH's hue and red is CAUTION's — a *reason* for a rating must not
#: wear the rating's colour, or the reader reads two verdicts where there is one.
STRESS = "var(--stress)"


def _drilldown_section_html(title: str) -> str:
    return f'<div class="dd-section">{title}</div>'


def _drilldown_metrics_html(items: list[tuple]) -> str:
    """Metric grid. Items are ``(label, value)`` or ``(label, value, colour)``.

    The optional third element tints the VALUE — use the price up/down palette
    for directional figures (an "avg down move" should read as a down move) or
    the data palette; never a signal hue, which belongs only on pills and rails.
    """
    visible = [it for it in items if it[1] not in (None, "", "—")]
    if not visible:
        return ""
    cells = ""
    for item in visible:
        label, value = item[0], item[1]
        colour = item[2] if len(item) > 2 else ""
        style = f' style="color:{colour};"' if colour else ""
        cells += (
            f'<div class="dd-metric"><div class="lbl">{label}</div>'
            f'<div class="val"{style}>{value}</div></div>'
        )
    return f'<div class="dd-metric-grid">{cells}</div>'


def _drawer(summary: str, body: str) -> str:
    """One collapsed drawer, or "" when nothing inside it populated."""
    if not body:
        return ""
    return (
        f'<details class="dd-drawer"><summary>{summary}</summary>'
        f'<div class="dd-drawer-body">{body}</div></details>'
    )


# ── Earnings ──────────────────────────────────────────────────────────────────

def _earnings_body_html(d: dict, price_fn, earnings_hist) -> str:
    """Pre-print setup band, then the quarter-on-quarter history beneath it.

    "Here is the setup for the coming print" → "here are the last eight quarters'
    beat/miss and revenue". Both are silent when their data is absent.
    """
    parts: list[str] = []
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
        # Health axis, not signals: the archetype characterises the SETUP, so it
        # takes the data palette (brass = neutral, terracotta = stressed) rather
        # than a BUY/CAUTION hue. "Neutral" was grey and read as absent.
        archetype_color = {
            "priced_for_perfection": STRESS,
            "low_bar_underdog": "var(--up)",
            "neutral": "var(--brass)",
        }.get(archetype, "var(--brass)")
        label = (
            f"Earnings setup — {temporal_phrase}" if temporal_phrase
            else "Earnings setup"
        )
        parts.append(_drilldown_section_html(label))
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
                f'<strong style="color:var(--up);">Bull case.</strong> '
                f'{price_fn(impl_up)} '
                f'({_sign(avg_up)}{_fmt_num(avg_up, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_dn is not None and impl_lo is not None:
            parts.append(
                f'<div class="dd-line">'
                f'<strong style="color:var(--down);">Bear case.</strong> '
                f'{price_fn(impl_lo)} '
                f'({_fmt_num(avg_dn, 1)}% avg of {n_priors} priors)'
                f'</div>'
            )
        if avg_up is None and avg_dn is not None:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'All {n_priors} priors moved down — no symmetric bull-side '
                f'reference.</div>'
            )
        if avg_dn is None and avg_up is not None:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
                f'All {n_priors} priors moved up — no symmetric bear-side '
                f'reference.</div>'
            )
        # Directional figures carry the price up/down palette so an "avg down
        # move" reads as a down move; the date/countdown stay neutral.
        parts.append(_drilldown_metrics_html([
            ("Earnings date", earn_date),
            ("Days until", str(days_until) if days_until is not None else "—"),
            ("Avg up move",
             f"{_sign(avg_up)}{_fmt_num(avg_up, 1)}%" if avg_up is not None else "—",
             "var(--up)"),
            ("Avg down move",
             f"{_fmt_num(avg_dn, 1)}%" if avg_dn is not None else "—",
             "var(--down)"),
            ("Max up move",
             f"{_sign(max_up)}{_fmt_num(max_up, 1)}%" if max_up is not None else "—",
             "var(--up)"),
            ("Max down move",
             f"{_fmt_num(max_dn, 1)}%" if max_dn is not None else "—",
             "var(--down)"),
        ]))

    eh = _earnings_history_html(earnings_hist) if earnings_hist else ""
    if eh:
        parts.append(_drilldown_section_html("Earnings history"))
        parts.append(eh)
    return "".join(parts)


# ── Risk & reward detail ──────────────────────────────────────────────────────

def _rr_body_html(d: dict, price_fn) -> str:
    """The prose exits, the three R:R figures, and the key-level zones.

    The card's levels plate already states the numbers you act on; this is the
    working behind them — why the target is where it is, and what the ratio looks
    like with a deeper stop.
    """
    rr_obj = d.get("risk_reward") or {}
    parts: list[str] = []

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
        # Newer reports carry the same deeper-stop ratio under `sizing_rr` (R:R
        # sized to structural support). Surface it here so the corrective
        # "wide-stop" number isn't blank for tight-invalidation names — exactly
        # where it matters and the headline R:R is distorted (UX-BR-2/WL-1/TM-1).
        wide_stop = (rr_obj.get("sizing_rr") or {}).get("ratio")
    rr_label = rr_obj.get("ratio_label", "")
    rr_quality = rr_obj.get("rr_quality", "")

    if any(v is not None for v in (upside_target, invalidation, structural, wide_stop)):
        parts.append(_drilldown_section_html("Risk &amp; reward"))
        if upside_target is not None:
            line = (f'<strong style="color:var(--up);">Upside target.</strong> '
                    f'{price_fn(upside_target)}')
            if upside_pct is not None:
                line += f" (+{_fmt_num(upside_pct, 1)}%)"
            if upside_reason:
                line += f" — {_escape_dollars(upside_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        if invalidation is not None:
            line = (f'<strong style="color:var(--down);">Invalidation.</strong> '
                    f'{price_fn(invalidation)}')
            if inv_pct is not None:
                line += f" (-{_fmt_num(inv_pct, 1)}%)"
            if invalidation_reason:
                line += f" — {_escape_dollars(invalidation_reason)}"
            parts.append(f'<div class="dd-line">{line}</div>')
        # A distorted headline (too-tight stop inflating the ratio) is flagged on
        # the stat itself — the row and the levels plate already show the
        # corrected sizing R:R, so an unmarked 22.5:1 here read as a
        # contradiction.
        qual_bits = [
            b for b in (rr_quality,
                        "tight-stop distorted" if rr_obj.get("rr_distorted") else "")
            if b
        ]
        qual = f" ({' · '.join(qual_bits)})" if qual_bits else ""
        # R:R ratios are computed data, so they take the brass data tone; the
        # structural-support level is a downside price, so it takes --down.
        parts.append(_drilldown_metrics_html([
            ("Headline R:R", f"{rr_label}{qual}" if rr_label else "—", "var(--brass)"),
            ("Wide-stop R:R",
             f"{_fmt_num(wide_stop, 2)}:1" if wide_stop else "—", "var(--brass)"),
            ("Structural support",
             f"{price_fn(structural)} (-{_fmt_num(struct_pct, 1)}%)"
             if structural else "—",
             "var(--down)"),
        ]))

    supports = d.get("support_zones") or []
    resistances = d.get("resistance_zones") or []
    if supports or resistances:
        parts.append(_drilldown_section_html("Key Levels"))
        if supports:
            parts.append(
                '<div class="dd-line"><strong>Support:</strong> '
                + ", ".join(price_fn(s) for s in supports)
                + '</div>'
            )
        if resistances:
            parts.append(
                '<div class="dd-line"><strong>Resistance:</strong> '
                + ", ".join(price_fn(r) for r in resistances)
                + '</div>'
            )
    return "".join(parts)


# ── Pipeline detail ───────────────────────────────────────────────────────────

_GATE_LABELS = {
    "g1_signal_eligible": "Signal eligible",
    "g2_rr_above_2": "R:R ≥ 2.0",
    "g3_rr_observed": "R:R observed",
    "g5_no_earnings_7d": "No earnings ≤7d",
    "g6_vix_ok": "VIX &lt; 30",
    "g8_rr_robust": "R:R robust",
}

_TERMINAL_PHASES = {"failed", "expired", "invalidated"}

_RCP_PHASE_COLORS = {
    "gap_day": STATUS_NEG,
    "cooling_off": STRESS,
    "graduation_watch": ACCENT_LINK,
    "path_a_confirmed": STATUS_POS,
    "path_b_confirmed": STATUS_POS,
    "failed": STATUS_MUTED,
    "expired": STATUS_MUTED,
    "invalidated": STATUS_MUTED,
}


def _gates_html(d: dict) -> str:
    """The six mechanical ACCUMULATE gates, pass/fail/unknown.

    Always rendered when the report carries them, so a reader can see why a name
    does or doesn't qualify. ✓/✗ glyphs carry the state as well as the colour.
    """
    gates = d.get("accumulate_gates") or {}
    if not gates:
        return ""
    chips: list[str] = []
    for gkey, glabel in _GATE_LABELS.items():
        val = gates.get(gkey)
        if val is True:
            bg, fg, mark = "rgba(34,197,94,0.18)", STATUS_POS, "✓"
        elif val is False:
            bg, fg, mark = "rgba(239,68,68,0.18)", STATUS_NEG, "✗"
        else:
            bg, fg, mark = "rgba(255,255,255,0.05)", "var(--ink-3)", "—"
        chips.append(
            f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'background:{bg};color:{fg};padding:4px 9px;border-radius:3px;'
            f'font-family:var(--mono);font-size:11px;font-weight:600;'
            f'letter-spacing:0.04em;">'
            f'<span style="font-size:13px;">{mark}</span>{glabel}</span>'
        )
    all_pass = gates.get("all_mechanical_pass")
    summary_color = (
        STATUS_POS if all_pass is True
        else STRESS if all_pass is False
        else "var(--ink-3)"
    )
    summary_text = (
        "All mechanical gates pass — Claude judgment determines ACCUMULATE"
        if all_pass is True
        else "One or more mechanical gates fail — ACCUMULATE blocked"
        if all_pass is False
        else "Gate status unknown"
    )
    parts = [
        _drilldown_section_html("ACCUMULATE gates"),
        '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">'
        + "".join(chips) + '</div>',
        f'<div class="dd-line" style="color:{summary_color};font-size:12.5px;">'
        f'{summary_text}</div>',
    ]
    # Abstained gates — couldn't be evaluated on incomplete data (NOT the same as
    # a failed gate). Listed so a degraded run reads honestly.
    abstained = gates.get("abstained") or []
    items = "".join(
        f'<div class="dd-line" style="color:var(--ink-3);font-size:12px;">'
        f'· <strong>{_escape_dollars(str(a.get("gate", "")))}</strong> '
        f'not evaluated — {_escape_dollars(str(a.get("reason", "")))}</div>'
        for a in abstained if isinstance(a, dict)
    )
    if items:
        parts.append(
            '<div style="margin-top:6px;">'
            '<div style="font-family:var(--mono);font-size:10px;'
            'letter-spacing:0.08em;text-transform:uppercase;'
            'color:var(--ink-3);margin-bottom:4px;">Abstained gates</div>'
            f'{items}</div>'
        )
    return "".join(parts)


def _rcp_html(d: dict, price_fn) -> str:
    """Regime Change Pending — a step-function move reset the chart.

    The one-line gloss is load-bearing: this was the least self-explanatory block
    on the site (casual-reader review 2026-07-12), because phase chips and
    "sessions since gap" mean nothing without the rule they belong to.
    """
    rcp = d.get("rcp_state")
    if not rcp:
        return ""
    phase = rcp.get("current_phase", "")
    sessions = rcp.get("sessions_since_gap")
    terminal_outcome = rcp.get("terminal_outcome", "")
    path_a = rcp.get("path_a_level")
    path_b = rcp.get("path_b_level")
    color = _RCP_PHASE_COLORS.get(phase, STATUS_NEUTRAL)
    sessions_note = (
        f"  ·  {sessions} sessions since gap" if sessions is not None else ""
    )
    parts = [
        _drilldown_section_html("Regime Change Pending"),
        '<div class="dd-line" style="color:var(--ink-3);font-size:12px;'
        'line-height:1.5;">A single-session move of 10%+ on real news reset '
        'this chart — old trend anchors like the 50-day average no longer '
        'apply. The name re-qualifies only by proving the new level: holding '
        'a retest (Path A) or breaking above the post-gap range (Path B) '
        'within 60 sessions.</div>',
        f'<div class="dd-line">'
        f'<span style="font-family:var(--mono);font-size:11px;'
        f'letter-spacing:0.10em;text-transform:uppercase;'
        f'background:rgba(255,255,255,0.05);color:{color};'
        f'padding:3px 8px;border-radius:3px;font-weight:600;">'
        f'{phase.replace("_", " ").title()}</span>'
        f'<span style="color:var(--ink-3);font-size:12px;">{sessions_note}</span>'
        f'</div>',
    ]
    if phase not in _TERMINAL_PHASES:
        metrics: list[tuple[str, str]] = []
        if path_a is not None:
            metrics.append(("Path A graduation", price_fn(path_a)))
        if path_b is not None:
            metrics.append(("Path B graduation", price_fn(path_b)))
        if sessions is not None:
            metrics.append(("Sessions remaining", str(max(0, 60 - sessions))))
        if metrics:
            parts.append(_drilldown_metrics_html(metrics))
    else:
        if terminal_outcome:
            parts.append(
                f'<div class="dd-line" style="color:var(--ink-3);'
                f'font-style:italic;">{_escape_dollars(terminal_outcome)}</div>'
            )
        parts.append(
            f'<div class="dd-line" style="color:{STATUS_MUTED};font-size:12px;">'
            'New step-function catalyst required before re-entry.</div>'
        )
    return "".join(parts)


def _catalyst_html(d: dict, price_fn) -> str:
    """Catalyst context.

    As of 2026-05-30 the catalyst path is narrative-only: the pipeline emits
    facts (catalyst_event/source/date) with ``narrative_only=True`` and no longer
    produces catalyst_rr / position_tier / extension relaxation. Legacy reports
    (pre-2026-05-30) carry the old entry-path shape; this renders both, and the
    R:R / tier framing appears only when those legacy fields are present.
    """
    catalyst = d.get("catalyst") or {}
    if not catalyst:
        return ""
    narrative_only = bool(catalyst.get("narrative_only"))
    c_rr = d.get("catalyst_rr") or catalyst.get("catalyst_rr") or {}
    c_tier = (d.get("catalyst_position_tier")
              or catalyst.get("catalyst_position_tier") or {})
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
    parts = [_drilldown_section_html(title)]
    if c_headline:
        head = (
            f'<div class="dd-line"><strong>'
            f'{_escape_dollars(c_type) or "Catalyst"}.</strong> '
            f'{_escape_dollars(c_headline)}'
        )
        if c_source:
            head += (f' <span style="color:var(--ink-3);">'
                     f'— {_escape_dollars(c_source)}</span>')
        href = _safe_href(c_url)
        if href:
            head += (
                f' <a href="{href}" target="_blank" rel="noopener noreferrer" '
                f'style="color:var(--ink-3);font-family:var(--mono);'
                f'font-size:11px;">[link]</a>'
            )
        parts.append(head + '</div>')
    metrics = [("Catalyst date", c_date or "—")]
    if is_entry_path:
        metrics += [
            ("Catalyst R:R", f"{_fmt_num(c_rr_ratio, 2)}:1" if c_rr_ratio else "—"),
            ("Gap-fill invalidation",
             price_fn(c_rr_inv) if c_rr_inv else (
                 price_fn(c_pre_price) if c_pre_price else "—")),
            ("Position tier",
             f"{c_tier_name} ({_fmt_num(c_max_size, 0)}% max)"
             if c_tier_name and c_max_size is not None else (c_tier_name or "—")),
        ]
    else:
        metrics.append(
            ("Signal impact", "Context only — does not change the signal")
        )
    parts.append(_drilldown_metrics_html(metrics))
    return "".join(parts)


def _avoid_source_html(d: dict) -> str:
    """The citation behind an AVOID — a rating we refuse to make unsourced."""
    src = d.get("avoid_source")
    if not isinstance(src, dict):
        return ""
    pub = src.get("publication", "")
    frag = src.get("headline_fragment", "")
    date = src.get("date", "")
    url = src.get("url", "")
    if not (pub or frag):
        return ""
    bits: list[str] = []
    if pub:
        bits.append(f'<strong>{_escape_dollars(pub)}</strong>')
    if frag:
        bits.append(f'"{_escape_dollars(frag)}"')
    if date:
        bits.append(f'<span style="color:var(--ink-3);">{_escape_dollars(date)}</span>')
    cite = " · ".join(bits)
    href = _safe_href(url)
    if href:
        cite += (
            f' <a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="color:var(--ink-3);font-family:var(--mono);'
            f'font-size:11px;">[link]</a>'
        )
    return (_drilldown_section_html("Avoid source")
            + f'<div class="dd-line">{cite}</div>')


def _earnings_result_html(d: dict) -> str:
    """The headline that reported the print, when the news carried one."""
    ern = d.get("earnings_results_in_news")
    if not isinstance(ern, dict):
        return ""
    headline = ern.get("headline", "")
    if not headline:
        return ""
    html = f'<div class="dd-line">"{_escape_dollars(headline)}"'
    source = ern.get("source", "")
    if source:
        html += f' <span style="color:var(--ink-3);">— {_escape_dollars(source)}</span>'
    href = _safe_href(ern.get("url", ""))
    if href:
        html += (
            f' <a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="color:var(--ink-3);font-family:var(--mono);'
            f'font-size:11px;">[link]</a>'
        )
    return _drilldown_section_html("Earnings result") + html + '</div>'


def _pipeline_body_html(d: dict, price_fn) -> str:
    return "".join((
        _gates_html(d),
        _rcp_html(d, price_fn),
        _catalyst_html(d, price_fn),
        _avoid_source_html(d),
        _earnings_result_html(d),
    ))


# ── Public entry point ────────────────────────────────────────────────────────

def render_drawers_html(d: dict, price_fn, earnings_hist=None) -> str:
    """The three drawers, in audit order. Empty ones are omitted entirely.

    ``price_fn`` is the caller's currency-aware price formatter, passed in rather
    than rebuilt so KRW names format the same here as in the card above.
    """
    return "".join((
        _drawer("Earnings", _earnings_body_html(d, price_fn, earnings_hist)),
        _drawer("Risk &amp; reward detail", _rr_body_html(d, price_fn)),
        _drawer("Pipeline detail", _pipeline_body_html(d, price_fn)),
    ))
