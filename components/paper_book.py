"""Signal Tracker · Paper-book band (page-contract tier 1c).

Renders the pipeline's mechanical paper portfolio — policy ``v1_flat10``,
replay-seeded 2026-04-19, Measurement-Gate-exempt — from two exported
sources: the report's ``paper_portfolio`` summary block and
``data/paper_nav.csv`` (daily NAV + SPY/SOXX closes). The dashboard's only
arithmetic is rebasing exported series to a $10,000 display notional at
their first valid row; all measurement lives upstream
(docs/superpowers/specs/2026-07-05-paper-book-band-design.md).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.cards import render_section_head
from lib.charts import (
    CHART_ACCENT,
    CHART_LINE,
    CHART_PALETTE,
    PLOTLY_CONFIG,
    STATUS_NEG,
    STATUS_POS,
    chart_data_table,
    style_fig,
)
from lib.formatters import _escape_dollars, display_ticker

# Exported column → display series name. NAV is the hero series; SPY/SOXX are
# the benchmarks the upstream summary already compares against.
_REBASE_COLS = {"nav_units": "Paper book", "spy_close": "SPY", "soxx_close": "SOXX"}

# Display notional: curves and verdict render as dollars of a $10,000 pot
# (user request 2026-07-17 — sequential percentages don't add, dollars do;
# the book is unit/cash-based upstream, so this is pure presentation math).
NOTIONAL_START = 10_000.0


def _money(v: float) -> str:
    """$10,287 — whole dollars, thousands separator."""
    return f"${v:,.0f}"

# The headline book. Stop-rule variants (v1_trail10 / v1_nostop10) share the
# CSV since 2026-07-06 but are advisory lanes — never the default curve.
_DEFAULT_POLICY = "v1_flat10"


def select_policy(nav_df: pd.DataFrame | None, block: dict) -> pd.DataFrame:
    """Rows of *nav_df* for the policy the latest report block names.

    Without a block, falls back to the headline book (``v1_flat10``) when the
    CSV carries it, else to the sole distinct ``policy_id``. A multi-policy
    CSV with neither a block nor the headline book yields an EMPTY frame:
    side-by-side policy variants must never blend into one curve.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame()
    pid = (block or {}).get("policy_id")
    if pid is None:
        ids = nav_df["policy_id"].dropna().unique()
        if _DEFAULT_POLICY in ids:
            pid = _DEFAULT_POLICY
        elif len(ids) == 1:
            pid = ids[0]
        else:
            return pd.DataFrame()
    return nav_df[nav_df["policy_id"] == pid].sort_values("date")


def rebase_curves(df: pd.DataFrame | None) -> pd.DataFrame:
    """``date`` + one rebased-to-$10,000 column per available series.

    Each series rebases to its own first valid value (the upstream summary
    computes benchmark returns first-row→last-row the same way — this is
    presentation math, not measurement). NAV's first exported row is the
    inception seed (nav_units == INCEPTION_UNITS upstream), so the curve's
    endpoint agrees with the block's nav_return_pct. Series that are absent,
    all-NaN, or zero-based are omitted rather than plotted wrong. Base is
    ``NOTIONAL_START`` dollars (2026-07-17): sequential percentages don't
    add in readers' heads; a dollar pot compounds visibly.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], errors="coerce")})
    for col, label in _REBASE_COLS.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        valid = series.dropna()
        if valid.empty or valid.iloc[0] == 0:
            continue
        out[label] = series / valid.iloc[0] * NOTIONAL_START
    if out.columns.tolist() == ["date"]:
        return pd.DataFrame()
    return out


def verdict_bits(block: dict) -> tuple[str, str]:
    """(verdict sentence, tone) for the band's lead line.

    Tone ∈ {"pos", "neg", ""} colours the "— …the benchmark" clause. A block
    whose returns are still ``None`` (seed day / no matured session) reads
    "seeded", mirroring the upstream Telegram glance line.
    """
    nav = block.get("nav_return_pct")
    spy = block.get("spy_return_pct")
    since = f" since {block['inception']}" if block.get("inception") else ""
    if nav is None or spy is None:
        return (f"Paper book seeded{since} — first fills pending.", "")
    nav_usd = _money(NOTIONAL_START * (1 + nav / 100.0))
    spy_usd = _money(NOTIONAL_START * (1 + spy / 100.0))
    body = (f"Paper book: {_money(NOTIONAL_START)} → {nav_usd} "
            f"({nav:+.1f}%){since} vs SPY (the S&P 500) → {spy_usd} "
            f"({spy:+.1f}%)")
    if nav > spy:
        return (f"{body} — leading the benchmark.", "pos")
    if nav < spy:
        return (f"{body} — trailing the benchmark.", "neg")
    return (f"{body} — tracking the benchmark.", "")


# Trade-reason keys (upstream policy vocabulary) → plain-language chip labels
# (first-time-reader pass 2026-07-16: "ACC tranches"/"stops" were jargon).
_REASON_LABELS = {
    "buy_signal": "BUY entries",
    "accumulate_tranche": "add-on buys",
    "stop": "stop-outs (auto-sold)",
    "avoid_exit": "AVOID exits",
    "delist_exit": "delist exits",
}

# Series colours: NAV is the hero (brass); SPY the reference line at ink-3
# (CHART_LINE — ≥3:1 on --paper, same rationale as the capex band); SOXX the
# muted steel blue. None of these collide with signal tokens by design.
_SERIES_COLORS = {"Paper book": CHART_ACCENT, "SPY": CHART_LINE,
                  "SOXX": CHART_PALETTE[0]}


def _verdict_html(block: dict) -> str:
    """Band lead line — plain-English verdict first, house style."""
    text, tone = verdict_bits(block)
    color = {"pos": STATUS_POS, "neg": STATUS_NEG}.get(tone)
    head, sep, tail = text.partition(" — ")
    tail_html = ""
    if sep:
        style = f' style="color:{color};"' if color else ""
        tail_html = f'<span{style}> — {_escape_dollars(tail)}</span>'
    return f'<p class="pb-verdict">{_escape_dollars(head)}{tail_html}</p>'


def _stats_html(block: dict) -> str:
    """Stat chips: cash weight, open positions, trade counts by reason."""
    chips = []
    if block.get("cash_pct") is not None:
        chips.append((f'{block["cash_pct"]:.0f}%', "cash (not invested)"))
    if block.get("n_positions") is not None:
        chips.append((str(block["n_positions"]), "open positions"))
    for key, label in _REASON_LABELS.items():
        n = (block.get("trade_counts") or {}).get(key)
        if n:
            chips.append((str(n), label))
    if not chips:
        return ""
    body = "".join(
        f'<div class="pb-stat"><b>{_escape_dollars(v)}</b>'
        f"<span>{label}</span></div>"
        for v, label in chips
    )
    return f'<div class="pb-stats">{body}</div>'


def _banner_html(block: dict) -> str:
    """The exported caveat, verbatim — honesty inherited, never invented."""
    banner = (block.get("banner") or "").strip()
    if not banner:
        return ""
    return f'<p class="pb-banner">{_escape_dollars(banner)}</p>'


# Policy_id → compact public label (the lanes the Telegram glance abbreviates
# as "trail"/"nostop"/"wide"; the headline book itself is the flat 10% stop).
_LANE_LABELS = {"v1_flat10": "flat", "v1_trail10": "trail",
                "v1_nostop10": "no-stop", "v1_wide10": "wide"}


def _variants_html(block: dict | None) -> str:
    """Advisory stop-rule lanes, one compact line under the stats.

    Leads with the headline book's own lane, labeled "(headline)", so the
    band's lead number reconciles with the variants beside it — four unnamed
    returns invited "so which rule is the +3.5%?" (UX 2026-07-07). Numbers
    only, framed as lanes of the same book — never a ranking: the exported
    banner rendered directly beneath carries the single-regime caveat.
    Malformed entries and lanes without a return yet are skipped; without at
    least one variant lane the line is omitted entirely (the headline number
    already leads the band).
    """
    block = block or {}
    parts = []
    for v in block.get("variants") or []:
        if not isinstance(v, dict) or not v.get("policy_id"):
            continue
        nav = v.get("nav_return_pct")
        if not isinstance(nav, (int, float)):
            continue
        label = (_LANE_LABELS.get(v["policy_id"])
                 or _escape_dollars(str(v["policy_id"])))
        stops = v.get("stops")
        stop_txt = (f" · {int(stops)} stop-outs"
                    if isinstance(stops, (int, float)) else "")
        parts.append(f"<b>{label}</b> {nav:+.1f}%{stop_txt}")
    if not parts:
        return ""
    head_nav = block.get("nav_return_pct")
    if isinstance(head_nav, (int, float)):
        label = (_LANE_LABELS.get(block.get("policy_id"))
                 or _escape_dollars(str(block.get("policy_id") or "book")))
        stops = (block.get("trade_counts") or {}).get("stop")
        stop_txt = (f" · {int(stops)} stop-outs"
                    if isinstance(stops, (int, float)) else "")
        parts.insert(0, f"<b>{label}</b> {head_nav:+.1f}%{stop_txt} (headline)")
    return ('<p class="pb-variants">Stop-rule lanes: '
            + " | ".join(parts)
            + " — same book, only the stop rule differs.</p>")


def _positions_table_html(positions: list) -> str:
    """Open-positions table for the drawer. Malformed rows skipped via .get."""
    rows = ""
    for p in positions or []:
        if not isinstance(p, dict) or not p.get("ticker"):
            continue
        wt = p.get("weight_pct")
        stop = p.get("stop")
        dd = p.get("max_dd_pct")
        # Pipeline emits drawdown as a positive magnitude ("fell 8.3%");
        # render with a minus sign so it can't read as a gain.
        dd_txt = "—" if dd is None else (f"-{abs(dd):.1f}%" if dd else "0.0%")
        rows += (
            "<tr>"
            f"<td>{_escape_dollars(display_ticker(str(p['ticker'])))}</td>"
            f'<td class="num">{f"{wt:.1f}%" if wt is not None else "—"}</td>'
            f'<td class="num">{f"{stop:.2f}" if stop is not None else "—"}</td>'
            f'<td class="num">{_escape_dollars(str(p.get("tranches", "—")))}</td>'
            f'<td class="num">{dd_txt}</td>'
            "</tr>"
        )
    if not rows:
        return ""
    return (
        '<table class="ep-table"><thead><tr>'
        '<th scope="col">Name</th><th scope="col" class="num">Weight</th>'
        '<th scope="col" class="num">Stop</th>'
        '<th scope="col" class="num">Tranches</th>'
        '<th scope="col" class="num">Max drawdown</th>'
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


# Plain-language key for the positions table, rendered directly beneath it
# (first-time-reader pass 2026-07-16). Kept as one paragraph so it reads as
# small print, not a second table; reuses the .pb-banner small-italic style.
_POSITIONS_LEGEND = (
    '<p class="pb-banner">How to read this: <b>Weight</b> — the slice of the '
    "whole book held in this stock. <b>Stop</b> — the pre-set price that "
    "triggers an automatic sell if the stock falls to it. <b>Tranches</b> — "
    "how many separate purchases built the position. <b>Max drawdown</b> — "
    "the deepest fall from the stock's highest point while we've held it: "
    "the pain endured along the way, not the current profit or loss.</p>"
)


def _trades_today_html(trades: list) -> str:
    """Today's fills with their policy reasons, one line each."""
    items = ""
    for t in trades or []:
        if not isinstance(t, dict) or not t.get("ticker"):
            continue
        side = _escape_dollars(str(t.get("side", "?")).upper())
        tk = _escape_dollars(display_ticker(str(t["ticker"])))
        reason = _escape_dollars(_REASON_LABELS.get(t.get("reason"),
                                                    str(t.get("reason", ""))))
        items += f"<li><b>{side}</b> {tk} <span>({reason})</span></li>"
    if not items:
        return ""
    return f'<ul class="pb-trades">{items}</ul>'


# The chart answers exactly one question — is the book beating SPY? — so only
# those two series plot solid. SOXX's window return (±60%) set the y-range and
# flattened the book-vs-SPY gap into two overlapping lines (UX 2026-07-07);
# it stays in the rebased frame for the data-table view, with an off-chart
# note (_soxx_note_html) naming its return.
_CHART_SERIES = ("Paper book", "SPY")

# Advisory ext-exit lanes charted as DASHED curves (user decision 2026-07-17,
# entry-sizing research adoption addendum). This is a deliberate, narrow
# exception to the "variants never charted" rule of the 2026-07-05 spec:
# the exit-on-extension lanes are the live sizing/exit experiment and the
# owner asked to track the divergence visually. They stay visually
# subordinate (thin + dashed), the headline curve is unchanged, and the
# single-regime banner still renders beneath the chart. Lanes absent from
# the CSV (b30 seeds on its first post-registration pipeline run) are
# silently skipped.
_ADVISORY_CURVES = {
    "v1_tc_ext_100": "ext-exit 10/5",
    "v1_tc_ext_100_b30": "ext-exit 30/15",
}
_ADVISORY_COLORS = {"ext-exit 10/5": CHART_PALETTE[2],    # sage
                    "ext-exit 30/15": CHART_PALETTE[3]}   # dusty mauve


def advisory_curves(nav_df: pd.DataFrame | None) -> pd.DataFrame:
    """``date`` + one rebased-to-100 NAV column per advisory lane in the CSV.

    Same presentation math as ``rebase_curves`` (each lane rebases to its own
    first valid ``nav_units`` row); lanes missing from the CSV are omitted.
    Empty frame when none are present, so the band renders exactly as before.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame()
    out = None
    for pid, label in _ADVISORY_CURVES.items():
        rows = nav_df[nav_df["policy_id"] == pid].sort_values("date")
        if rows.empty or "nav_units" not in rows.columns:
            continue
        series = pd.to_numeric(rows["nav_units"], errors="coerce")
        valid = series.dropna()
        if valid.empty or valid.iloc[0] == 0:
            continue
        lane = pd.DataFrame({
            "date": pd.to_datetime(rows["date"], errors="coerce"),
            label: series / valid.iloc[0] * NOTIONAL_START,
        })
        out = lane if out is None else out.merge(lane, on="date", how="outer")
    if out is None:
        return pd.DataFrame()
    return out.sort_values("date").reset_index(drop=True)


def _nav_fig(rebased: pd.DataFrame, advisory: pd.DataFrame | None = None):
    fig = go.Figure()
    for name in [c for c in rebased.columns
                 if c != "date" and c in _CHART_SERIES]:
        fig.add_scatter(
            x=rebased["date"], y=rebased[name], mode="lines", name=name,
            line=dict(color=_SERIES_COLORS.get(name, CHART_LINE),
                      width=2.2 if name == "Paper book" else 1.4),
        )
    if advisory is not None and not advisory.empty:
        for name in [c for c in advisory.columns if c != "date"]:
            fig.add_scatter(
                x=advisory["date"], y=advisory[name], mode="lines", name=name,
                line=dict(color=_ADVISORY_COLORS.get(name, CHART_LINE),
                          width=1.2, dash="dash"),
            )
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      yaxis_title="value of $10,000 invested at start")
    return style_fig(fig)


def _advisory_note_html(advisory: pd.DataFrame) -> str:
    """One-line key for the dashed lanes, or "" when none plotted."""
    if advisory is None or advisory.empty:
        return ""
    names = [c for c in advisory.columns if c != "date"]
    if not names:
        return ""
    return ('<p class="pb-chartnote">Dashed: exit-on-extension replay lanes '
            f'({", ".join(names)} — BUY%/add-on% of the book) · '
            "hypothesis-grade, one regime · not the headline book.</p>")


def _soxx_note_html(rebased: pd.DataFrame) -> str:
    """One-line pointer to the off-chart SOXX series, or "" when absent."""
    if rebased is None or rebased.empty or "SOXX" not in rebased.columns:
        return ""
    valid = rebased["SOXX"].dropna()
    if valid.empty:
        return ""
    ret = (valid.iloc[-1] / NOTIONAL_START - 1.0) * 100.0
    return (f'<p class="pb-chartnote">SOXX {ret:+.1f}% over this window is '
            f"left off the chart so the book-vs-SPY gap stays readable — "
            f"full series in the data table.</p>")


def render_paper_book(latest_report: dict, nav_df: pd.DataFrame) -> None:
    """Tier 1c — the paper book. Corpus-scoped (the tracker's name filter
    deliberately does not touch it). Absence tiers per the spec: block+CSV →
    full band; block only → summary, no curve; CSV only → curve only; neither
    → skipped entirely (every pre-export report renders exactly as before).
    """
    block = (latest_report or {}).get("paper_portfolio") or {}
    rebased = rebase_curves(select_policy(nav_df, block))
    advisory = advisory_curves(nav_df)
    if not block and rebased.empty:
        return
    render_section_head(
        "Paper book",
        "A simulated portfolio that follows the signals by rule · "
        "no real money · exists to measure them",
    )
    if block:
        st.markdown(_verdict_html(block) + _stats_html(block),
                    unsafe_allow_html=True)
    if not rebased.empty:
        st.plotly_chart(_nav_fig(rebased, advisory), use_container_width=True,
                        config=PLOTLY_CONFIG)
        note = _soxx_note_html(rebased) + _advisory_note_html(advisory)
        if note:
            st.markdown(note, unsafe_allow_html=True)
        table = rebased
        if not advisory.empty:
            table = rebased.merge(advisory, on="date", how="left")
        chart_data_table(table)
    if block:
        st.markdown(_variants_html(block) + _banner_html(block),
                    unsafe_allow_html=True)
        positions_html = _positions_table_html(block.get("positions"))
        trades_html = _trades_today_html(block.get("trades_today"))
        if positions_html or trades_html:
            with st.expander("Positions & today's trades", expanded=False):
                if trades_html:
                    st.markdown(trades_html, unsafe_allow_html=True)
                if positions_html:
                    st.markdown(f'<div class="tk-scroll">{positions_html}</div>',
                                unsafe_allow_html=True)
                    st.markdown(_POSITIONS_LEGEND, unsafe_allow_html=True)
