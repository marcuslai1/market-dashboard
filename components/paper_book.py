"""Signal Tracker · Paper-book band (page-contract tier 1c).

Renders the pipeline's mechanical paper portfolio — policy ``v1_flat10``,
replay-seeded 2026-04-19, Measurement-Gate-exempt — from two exported
sources: the report's ``paper_portfolio`` summary block and
``data/paper_nav.csv`` (daily NAV + SPY/SOXX closes). The dashboard's only
arithmetic is rebasing exported series to 100 at their first valid row;
all measurement lives upstream
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


def select_policy(nav_df: pd.DataFrame | None, block: dict) -> pd.DataFrame:
    """Rows of *nav_df* for the policy the latest report block names.

    Without a block, falls back to the sole distinct ``policy_id`` — but a
    multi-policy CSV with no block to disambiguate yields an EMPTY frame:
    side-by-side policy variants must never blend into one curve.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame()
    pid = (block or {}).get("policy_id")
    if pid is None:
        ids = nav_df["policy_id"].dropna().unique()
        if len(ids) != 1:
            return pd.DataFrame()
        pid = ids[0]
    return nav_df[nav_df["policy_id"] == pid].sort_values("date")


def rebase_curves(df: pd.DataFrame | None) -> pd.DataFrame:
    """``date`` + one rebased-to-100 column per available series.

    Each series rebases to its own first valid value (the upstream summary
    computes benchmark returns first-row→last-row the same way — this is
    presentation math, not measurement). Series that are absent, all-NaN, or
    zero-based are omitted rather than plotted wrong.
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
        out[label] = series / valid.iloc[0] * 100.0
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
    body = f"Paper book {nav:+.1f}%{since} vs SPY {spy:+.1f}%"
    if nav > spy:
        return (f"{body} — leading the benchmark.", "pos")
    if nav < spy:
        return (f"{body} — trailing the benchmark.", "neg")
    return (f"{body} — tracking the benchmark.", "")


# Trade-reason keys (upstream policy vocabulary) → compact chip labels.
_REASON_LABELS = {
    "buy_signal": "BUY entries",
    "accumulate_tranche": "ACC tranches",
    "stop": "stops",
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
        chips.append((f'{block["cash_pct"]:.0f}%', "cash"))
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


def _positions_table_html(positions: list) -> str:
    """Open-positions table for the drawer. Malformed rows skipped via .get."""
    rows = ""
    for p in positions or []:
        if not isinstance(p, dict) or not p.get("ticker"):
            continue
        stop = p.get("stop")
        dd = p.get("max_dd_pct")
        rows += (
            "<tr>"
            f"<td>{_escape_dollars(display_ticker(str(p['ticker'])))}</td>"
            f'<td class="num">{p.get("weight_pct", 0):.1f}%</td>'
            f'<td class="num">{f"{stop:.2f}" if stop is not None else "—"}</td>'
            f'<td class="num">{_escape_dollars(str(p.get("tranches", "—")))}</td>'
            f'<td class="num">{f"{dd:+.1f}%" if dd is not None else "—"}</td>'
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


def _nav_fig(rebased: pd.DataFrame):
    fig = go.Figure()
    for name in [c for c in rebased.columns if c != "date"]:
        fig.add_scatter(
            x=rebased["date"], y=rebased[name], mode="lines", name=name,
            line=dict(color=_SERIES_COLORS.get(name, CHART_LINE),
                      width=2.2 if name == "Paper book" else 1.4),
        )
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      yaxis_title="rebased · inception = 100")
    return style_fig(fig)


def render_paper_book(latest_report: dict, nav_df: pd.DataFrame) -> None:
    """Tier 1c — the paper book. Corpus-scoped (the tracker's name filter
    deliberately does not touch it). Absence tiers per the spec: block+CSV →
    full band; block only → summary, no curve; CSV only → curve only; neither
    → skipped entirely (every pre-export report renders exactly as before).
    """
    block = (latest_report or {}).get("paper_portfolio") or {}
    rebased = rebase_curves(select_policy(nav_df, block))
    if not block and rebased.empty:
        return
    render_section_head(
        "Paper book",
        "The signals traded mechanically · measured by the pipeline",
    )
    if block:
        st.markdown(_verdict_html(block) + _stats_html(block),
                    unsafe_allow_html=True)
    if not rebased.empty:
        st.plotly_chart(_nav_fig(rebased), use_container_width=True,
                        config=PLOTLY_CONFIG)
        chart_data_table(rebased)
    if block:
        st.markdown(_banner_html(block), unsafe_allow_html=True)
        positions_html = _positions_table_html(block.get("positions"))
        trades_html = _trades_today_html(block.get("trades_today"))
        if positions_html or trades_html:
            with st.expander("Positions & today's trades", expanded=False):
                if trades_html:
                    st.markdown(trades_html, unsafe_allow_html=True)
                if positions_html:
                    st.markdown(f'<div class="tk-scroll">{positions_html}</div>',
                                unsafe_allow_html=True)
