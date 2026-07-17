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


def _policy_for(df: pd.DataFrame, block: dict) -> str | None:
    """The policy_id the band should render from *df*, or None.

    Block-named policy first; without a block, the headline book
    (``v1_flat10``) when the frame carries it, else the sole distinct
    ``policy_id``. Multi-policy with neither → None: side-by-side policy
    variants must never blend into one view.
    """
    pid = (block or {}).get("policy_id")
    if pid is None:
        ids = df["policy_id"].dropna().unique()
        if _DEFAULT_POLICY in ids:
            pid = _DEFAULT_POLICY
        elif len(ids) == 1:
            pid = ids[0]
        else:
            return None
    return pid


def select_policy(nav_df: pd.DataFrame | None, block: dict) -> pd.DataFrame:
    """Rows of *nav_df* for the policy the latest report block names.

    Selection rule in ``_policy_for``; empty frame when no policy resolves.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame()
    pid = _policy_for(nav_df, block)
    if pid is None:
        return pd.DataFrame()
    return nav_df[nav_df["policy_id"] == pid].sort_values("date")


def select_trades(trades_df: pd.DataFrame | None, block: dict) -> pd.DataFrame:
    """Completed round-trips for the band's policy, newest exit first.

    Same selection rule as the NAV curve (``_policy_for``), so advisory-lane
    trades in the CSV stay invisible unless the block ever names such a lane.
    """
    if (trades_df is None or trades_df.empty
            or "policy_id" not in trades_df.columns):
        return pd.DataFrame()
    pid = _policy_for(trades_df, block)
    if pid is None:
        return pd.DataFrame()
    rows = trades_df[trades_df["policy_id"] == pid].copy()
    if "exit_date" in rows.columns:
        rows["_exit"] = pd.to_datetime(rows["exit_date"], errors="coerce")
        rows = rows.sort_values("_exit", ascending=False).drop(columns="_exit")
    return rows


def trade_dollars_factor(nav_df: pd.DataFrame | None,
                         block: dict) -> float | None:
    """Dollars-of-the-pot per book unit, or None when unavailable.

    ``NOTIONAL_START / first valid nav_units`` of the selected policy — the
    identical rebase factor the NAV curve uses, so a trade's exported
    ``pnl_units`` converts to the same dollars the curve shows. No factor →
    the history renders percent-only rather than inventing dollars.
    """
    rows = select_policy(nav_df, block)
    if rows.empty or "nav_units" not in rows.columns:
        return None
    valid = pd.to_numeric(rows["nav_units"], errors="coerce").dropna()
    if valid.empty or valid.iloc[0] == 0:
        return None
    return NOTIONAL_START / valid.iloc[0]


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


# Exit-reason keys → singular plain-language labels for the history's
# "Why sold" column (the chip map above is plural, for counts).
_EXIT_LABELS = {
    "stop": "stop-out (auto-sold)",
    "avoid_exit": "AVOID exit",
    "delist_exit": "delisted",
}


def _fmt_trade_date(val, as_of_year: int | None = None) -> str:
    """``May 2`` — year appended only when it differs from the as-of year
    (or when no as-of year is known). Unparseable → em-dash."""
    d = pd.to_datetime(val, errors="coerce")
    if pd.isna(d):
        return "—"
    txt = f"{d:%b} {d.day}"
    if as_of_year is None or d.year != as_of_year:
        txt += f", {d.year}"
    return txt


def _num_or_none(val) -> float | None:
    """float(val), or None for missing/NaN/non-numeric."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def trade_rows(df: pd.DataFrame | None, factor: float | None = None,
               as_of_year: int | None = None) -> list[dict]:
    """Display rows for the completed-trades table, from ``select_trades``.

    Each row: ``ticker`` (display form), ``bought``/``sold`` (date @ price,
    with an ``avg · N buys`` suffix for multi-tranche entries), ``why``
    (labeled exit reason), ``dollars`` (pnl_units × *factor*, None without a
    factor) and ``pct`` (exported return on cost). Rows without a ticker, or
    with nothing honest to show as profit, are skipped; a bad date degrades
    to an em-dash rather than dropping an otherwise-complete trade.
    """
    rows: list[dict] = []
    if df is None or df.empty:
        return rows
    for _, r in df.iterrows():
        ticker = r.get("ticker")
        if not isinstance(ticker, str) or not ticker.strip():
            continue
        pct = _num_or_none(r.get("pnl_pct"))
        units = _num_or_none(r.get("pnl_units"))
        dollars = units * factor if units is not None and factor else None
        if pct is None and dollars is None:
            continue
        # Prices render bare (no $), matching the positions table's Stop
        # column: the book holds non-USD listings (e.g. 000660.KS trades in
        # KRW), so a dollar sign would mislabel the currency.
        bought = _fmt_trade_date(r.get("entry_date"), as_of_year)
        entry_px = _num_or_none(r.get("avg_entry_price"))
        if entry_px is not None:
            bought += f" @ {entry_px:,.2f}"
        tranches = _num_or_none(r.get("tranches"))
        if tranches is not None and tranches >= 2:
            bought += f" avg · {int(tranches)} buys"
        sold = _fmt_trade_date(r.get("exit_date"), as_of_year)
        exit_px = _num_or_none(r.get("exit_price"))
        if exit_px is not None:
            sold += f" @ {exit_px:,.2f}"
        reason = r.get("exit_reason")
        why = _EXIT_LABELS.get(reason, "" if pd.isna(reason) else str(reason))
        rows.append({"ticker": display_ticker(ticker), "bought": bought,
                     "sold": sold, "why": why, "dollars": dollars,
                     "pct": pct})
    return rows


def _signed_money(v: float) -> str:
    """+$241 / -$75 — signed whole dollars."""
    sign = "+" if v > 0 else "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"


def _profit_html(dollars: float | None, pct: float | None) -> str:
    """``+$241 (+23.9%)`` colored by sign; percent- or dollar-only when
    that's all the data supports; em-dash when neither exists."""
    if dollars is not None and pct is not None:
        txt = f"{_signed_money(dollars)} ({pct:+.1f}%)"
    elif dollars is not None:
        txt = _signed_money(dollars)
    elif pct is not None:
        txt = f"{pct:+.1f}%"
    else:
        return "—"
    val = dollars if dollars is not None else pct
    color = STATUS_POS if val > 0 else STATUS_NEG if val < 0 else None
    style = f' style="color:{color};"' if color else ""
    return f"<span{style}>{_escape_dollars(txt)}</span>"


def _drawer_title(has_history: bool) -> str:
    """The drawer earns its new name only once history data exists, so the
    pre-export corpus renders byte-identical to today."""
    return ("Positions & trade history" if has_history
            else "Positions & today's trades")


def _history_verdict_html(rows: list[dict]) -> str:
    """Plain-English lead line above the completed-trades table.

    Counts winners/losers by the sign of the exported per-trade P&L and sums
    the pot dollars — display aggregation of exported values, inside the
    band's math budget. The pot total is omitted unless every row carries
    dollars: a partial sum would misread as the whole story.
    """
    if not rows:
        return ""

    def _sign(r: dict) -> float:
        v = r["pct"] if r["pct"] is not None else r["dollars"]
        return v or 0.0

    wins = sum(1 for r in rows if _sign(r) > 0)
    losses = sum(1 for r in rows if _sign(r) < 0)
    flat = len(rows) - wins - losses
    word = "trade" if len(rows) == 1 else "trades"
    text = f"{len(rows)} completed {word} — {wins} made money, {losses} lost"
    if flat:
        text += f", {flat} broke even"
    if all(r["dollars"] is not None for r in rows):
        total = sum(r["dollars"] for r in rows)
        if total > 0:
            text += f"; together they added {_signed_money(total)} to the pot"
        elif total < 0:
            text += (f"; together they took {_signed_money(total)} "
                     "from the pot")
        else:
            text += "; together they netted out flat"
    return f'<p class="pb-history-lead">{_escape_dollars(text)}.</p>'


def _trade_history_html(rows: list[dict]) -> str:
    """Completed round-trips table (newest exit first), or "" when empty."""
    body = ""
    for r in rows:
        body += (
            "<tr>"
            f"<td>{_escape_dollars(r['ticker'])}</td>"
            f"<td>{_escape_dollars(r['bought'])}</td>"
            f"<td>{_escape_dollars(r['sold'])}</td>"
            f"<td>{_escape_dollars(r['why'])}</td>"
            f'<td class="num">{_profit_html(r["dollars"], r["pct"])}</td>'
            "</tr>"
        )
    if not body:
        return ""
    return (
        '<table class="ep-table"><thead><tr>'
        '<th scope="col">Name</th><th scope="col">Bought</th>'
        '<th scope="col">Sold</th><th scope="col">Why sold</th>'
        '<th scope="col" class="num">Profit</th>'
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


# Plain-language key for the history table, same voice as the positions
# legend. &#36; keeps the literal dollar sign out of Streamlit's LaTeX path.
_HISTORY_LEGEND = (
    '<p class="pb-banner">How to read this: each row is one completed trade, '
    "newest first. <b>Bought / Sold</b> — the fill dates and prices (avg — "
    "the average price when several buys built the position). <b>Why "
    "sold</b> — the rule that triggered the sale; every exit is mechanical, "
    "never a judgment call. <b>Profit</b> — what the trade added to or took "
    "from the &#36;10,000 pot, with the return on the money put in.</p>"
)


def _has_position_pnl(positions: list) -> bool:
    """True when any position carries the optional entry/P&L export fields
    (spec 2026-07-17-paper-trade-history); gates the extra columns+legend."""
    return any(
        isinstance(p, dict) and (p.get("entry_date")
                                 or p.get("pnl_pct") is not None
                                 or p.get("pnl_units") is not None)
        for p in positions or []
    )


def _positions_table_html(positions: list, factor: float | None = None,
                          as_of_year: int | None = None) -> str:
    """Open-positions table for the drawer. Malformed rows skipped via .get.

    Gains Bought and P&L-so-far columns only when at least one position
    carries the optional export fields — the pre-export block renders
    byte-identical to today.
    """
    with_pnl = _has_position_pnl(positions)
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
        bought_cell = pnl_cell = ""
        if with_pnl:
            bought = ("—" if not p.get("entry_date")
                      else _fmt_trade_date(p["entry_date"], as_of_year))
            units = _num_or_none(p.get("pnl_units"))
            dollars = units * factor if units is not None and factor else None
            bought_cell = f"<td>{_escape_dollars(bought)}</td>"
            pnl_cell = (f'<td class="num">'
                        f'{_profit_html(dollars, _num_or_none(p.get("pnl_pct")))}'
                        "</td>")
        rows += (
            "<tr>"
            f"<td>{_escape_dollars(display_ticker(str(p['ticker'])))}</td>"
            f"{bought_cell}"
            f'<td class="num">{f"{wt:.1f}%" if wt is not None else "—"}</td>'
            f'<td class="num">{f"{stop:.2f}" if stop is not None else "—"}</td>'
            f'<td class="num">{_escape_dollars(str(p.get("tranches", "—")))}</td>'
            f'<td class="num">{dd_txt}</td>'
            f"{pnl_cell}"
            "</tr>"
        )
    if not rows:
        return ""
    bought_head = '<th scope="col">Bought</th>' if with_pnl else ""
    pnl_head = ('<th scope="col" class="num">P&amp;L so far</th>'
                if with_pnl else "")
    return (
        '<table class="ep-table"><thead><tr>'
        f'<th scope="col">Name</th>{bought_head}'
        '<th scope="col" class="num">Weight</th>'
        '<th scope="col" class="num">Stop</th>'
        '<th scope="col" class="num">Tranches</th>'
        '<th scope="col" class="num">Max drawdown</th>'
        f"{pnl_head}"
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

# Appended to the legend only when the optional export fields render.
_POSITIONS_PNL_LEGEND = (
    '<p class="pb-banner"><b>Bought</b> — the day the position was first '
    "purchased. <b>P&amp;L so far</b> — what the position has made or lost "
    "since purchase, in dollars of the &#36;10,000 pot; unrealized until "
    "sold.</p>"
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


def render_paper_book(latest_report: dict, nav_df: pd.DataFrame,
                      trades_df: pd.DataFrame | None = None) -> None:
    """Tier 1c — the paper book. Corpus-scoped (the tracker's name filter
    deliberately does not touch it). Absence tiers per the specs: block+CSV →
    full band; block only → summary, no curve; CSV only → curve only; neither
    (and no trade history) → skipped entirely, so every pre-export report
    renders exactly as before. *trades_df* (``data/paper_trades.csv``, spec
    2026-07-17-paper-trade-history) adds the completed-trades history to the
    drawer; absent → drawer title and contents byte-identical to today.
    """
    block = (latest_report or {}).get("paper_portfolio") or {}
    rebased = rebase_curves(select_policy(nav_df, block))
    advisory = advisory_curves(nav_df)
    factor = trade_dollars_factor(nav_df, block)
    as_of = pd.to_datetime(block.get("as_of"), errors="coerce")
    as_of_year = None if pd.isna(as_of) else as_of.year
    history_rows = trade_rows(select_trades(trades_df, block), factor,
                              as_of_year)
    history_html = _trade_history_html(history_rows)
    if not block and rebased.empty and not history_html:
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
    positions_html = _positions_table_html(block.get("positions"), factor,
                                           as_of_year)
    trades_html = _trades_today_html(block.get("trades_today"))
    if positions_html or trades_html or history_html:
        with st.expander(_drawer_title(bool(history_html)), expanded=False):
            if trades_html:
                st.markdown(trades_html, unsafe_allow_html=True)
            if positions_html:
                st.markdown(f'<div class="tk-scroll">{positions_html}</div>',
                            unsafe_allow_html=True)
                legend = _POSITIONS_LEGEND
                if _has_position_pnl(block.get("positions")):
                    legend += _POSITIONS_PNL_LEGEND
                st.markdown(legend, unsafe_allow_html=True)
            if history_html:
                st.markdown(_history_verdict_html(history_rows),
                            unsafe_allow_html=True)
                st.markdown(f'<div class="tk-scroll">{history_html}</div>',
                            unsafe_allow_html=True)
                st.markdown(_HISTORY_LEGEND, unsafe_allow_html=True)
