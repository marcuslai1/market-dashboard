"""Signal Tracker · Paper-book band (page-contract tier 1c).

Renders the pipeline's mechanical paper portfolio — policy ``v1_flat10``,
replay-seeded 2026-04-19, Measurement-Gate-exempt — from two exported
sources: the report's ``paper_portfolio`` summary block and
``data/paper_nav.csv`` (daily NAV + SPY/SOXX closes). The dashboard's only
arithmetic is rebasing exported series to a $100,000 display notional at
their first valid row; all measurement lives upstream.
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.cards import render_section_head
from lib.charts import (
    CHART_ACCENT,
    CHART_ACCENT_SOFT,
    CHART_LINE,
    CHART_MUTED,
    CHART_PALETTE,
    PLOTLY_CONFIG,
    STATUS_NEG,
    STATUS_POS,
    chart_data_table,
    style_fig,
)
from lib.formatters import _escape_dollars, display_ticker
from lib.paper_metrics import scorecard as _scorecard_rows

# Exported column → display series name. NAV is the hero series; SPY/SOXX are
# the benchmarks the upstream summary already compares against.
_REBASE_COLS = {"nav_units": "Paper book", "spy_close": "SPY", "soxx_close": "SOXX"}

# Display notional: curves and verdict render as dollars of a $100,000 pot
# (user request 2026-07-17 — sequential percentages don't add, dollars do;
# the book is unit/cash-based upstream, so this is pure presentation math).
# $100k rather than $10k (same-day follow-up): positions display in WHOLE
# shares, and a $10k pot rounds a 10% stake of a $1,400 stock to zero.
NOTIONAL_START = 100_000.0


def _money(v: float) -> str:
    """$10,287 — whole dollars, thousands separator."""
    return f"${v:,.0f}"

# The headline book. Stop-rule variants (v1_trail10 / v1_nostop10) share the
# CSV since 2026-07-06 but are advisory lanes — never the default curve.
# The DEFAULT strategy the band headlines (owner decision 2026-08-27, pipeline
# spec 2026-08-27-paper-stop-exit-cross-design addenda e/f): the wide
# structural stop with the extension-or-thesis exit at 15%/7.5% sizing.
# The pipeline's report block still names v1_flat10 (the frozen-stop control
# the regime-turn playbook's falsification read is defined against, and the
# Telegram glance's headline) — this band deliberately does NOT follow the
# block's policy_id any more: the control is charted as the muted "legacy
# control" line instead. Falls back to the block's policy, then the legacy
# default, when the CSV predates the default lane.
# 2026-08-28 (owner decisions, pipeline spec 2026-08-28-paper-v2-starter-
# default): the headline is the v2 STARTER default — the report's own
# ACCUMULATE semantics (one starter per episode, only a BUY tops up), small/
# mid caps at half size, idle cash in T-bills, IBKR Pro costs. The previous
# v1 default (persistence adds, no sleeve, no fees) is charted as a dashed
# comparator so the reader can see what the semantics change cost; the v1
# ext-only challenger stays dashed too. Every registered iteration is listed
# in the scorecard (owner request: "show all possible iterations").
_HEADLINE_POLICY = "v2_starter_b15_tb_fees"
_PREV_DEFAULT_POLICY = "v1_wide_extthesis_100_b15"
_CHALLENGER_POLICY = "v1_wide_ext_100_b12"
_LEGACY_POLICY = "v1_flat10"
_DEFAULT_POLICY = _LEGACY_POLICY          # legacy name kept for callers/tests


def _policy_for(df: pd.DataFrame, block: dict) -> str | None:
    """The policy_id the band should render from *df*, or None.

    An explicitly block-named policy always wins (per-lane callers pass
    ``{"policy_id": pid}``); without one, the default strategy when the frame
    carries it, else the legacy control, else the sole distinct
    ``policy_id``. Multi-policy with none of those → None: side-by-side
    policy variants must never blend into one view. ``headline_block``
    resolves the band's own headline through this same rule.
    """
    pid = (block or {}).get("policy_id")
    if pid is not None:
        return pid
    ids = set(df["policy_id"].dropna().unique())
    if _HEADLINE_POLICY in ids:
        return _HEADLINE_POLICY
    if _PREV_DEFAULT_POLICY in ids:       # CSV predates the v2 default (08-28)
        return _PREV_DEFAULT_POLICY
    if _LEGACY_POLICY in ids:
        return _LEGACY_POLICY
    if len(ids) == 1:
        return next(iter(ids))
    return None


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
    return _newest_exit_first(trades_df[trades_df["policy_id"] == pid])


def _newest_exit_first(rows: pd.DataFrame) -> pd.DataFrame:
    rows = rows.copy()
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
    """``date`` + one rebased-to-notional column per available series.

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


def _human_date(value) -> str:
    """'2026-04-19' → '19 Apr 2026'; anything unparseable passes through."""
    if not value:
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return f"{parsed.day} {parsed.strftime('%b')} {parsed.year}"


def verdict_bits(block: dict) -> tuple[str, str]:
    """(verdict sentence, tone) for the band's lead line.

    A full sentence rather than a stat row, and verdict-first: the conclusion is
    the last clause. Tone ∈ {"pos", "neg", ""} colours it. No "Paper book:"
    prefix — the section head above already says so. A block whose returns are
    still ``None`` (seed day / no matured session) reads "seeded", mirroring the
    upstream Telegram glance line.
    """
    nav = block.get("nav_return_pct")
    spy = block.get("spy_return_pct")
    since = f" since {_human_date(block['inception'])}" if block.get("inception") else ""
    if nav is None or spy is None:
        return (f"Paper book seeded{since} — first fills pending.", "")
    nav_usd = _money(NOTIONAL_START * (1 + nav / 100.0))
    spy_usd = _money(NOTIONAL_START * (1 + spy / 100.0))
    body = (f"{_money(NOTIONAL_START)} → {nav_usd} ({nav:+.1f}%){since}, "
            f"against SPY at {spy_usd} ({spy:+.1f}%)")
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


# The verdict clause by branch. "Trailing" is a trust limitation on the book's
# own performance → terracotta, never the CAUTION hue; "leading" takes the same
# market-direction system the two returns use; "tracking" makes no reading.
_VERDICT_CLAUSE_COLOR = {"pos": "var(--up)", "neg": "var(--stress)"}

# _escape_dollars has already turned "$" into "&#36;" by the time these run.
_MONEY_RE = re.compile(r"&#36;[\d,]+")
_RET_RE = re.compile(r"\(([-+]\d+\.\d)%\)")


def headline_block(nav_df: pd.DataFrame | None, block: dict) -> dict:
    """The block the verdict line reads from: the DEFAULT lane's own numbers
    computed from the CSV (nav_return_pct / spy_return_pct / inception),
    not the pipeline block's (which describes the legacy control). Falls
    back to the exported block when the CSV can't resolve the lane."""
    pid = None
    if nav_df is not None and not nav_df.empty and "policy_id" in nav_df.columns:
        pid = _policy_for(nav_df, {})       # ignore the block's (legacy) policy_id
    if pid is None:
        return dict(block or {})
    rows = _scorecard_rows(nav_df, None, None, [pid])
    if not rows:
        return dict(block or {})
    r = rows[0]
    spy = (r.get("spy") or {}).get("ret_pct")
    return {
        "policy_id": pid,
        "nav_return_pct": r.get("ret_pct"),
        "spy_return_pct": spy,
        "inception": r.get("since") or (block or {}).get("inception"),
        "as_of": r.get("as_of") or (block or {}).get("as_of"),
    }


def _verdict_html(block: dict) -> str:
    """Band lead line — a full sentence, the conclusion last and the only
    coloured words.

    The two returns carry market direction (the delta system, deliberately
    distinct from the signal palette); the money reads as a value; the clause
    carries the reading.
    """
    text, tone = verdict_bits(block)
    head, sep, tail = text.partition(" — ")
    head = _escape_dollars(head)
    head = _MONEY_RE.sub(lambda m: f'<span class="pb-val">{m.group(0)}</span>', head)
    head = _RET_RE.sub(
        lambda m: '<span class="pb-ret" style="color:'
                  + ("var(--up)" if m.group(1).startswith("+") else "var(--down)")
                  + f'">({m.group(1)}%)</span>',
        head,
    )
    tail_html = ""
    if sep:
        color = _VERDICT_CLAUSE_COLOR.get(tone)
        style = f' style="color:{color};"' if color else ""
        tail_html = f'<span class="pb-clause"{style}> — {_escape_dollars(tail)}</span>'
    return f'<p class="pb-verdict">{head}{tail_html}</p>'


# Strategy scorecard lanes (2026-08-27): role labels are the reader's
# contract — which line is the default, which is the challenger, and which
# is the old book kept only as the control. Order = display order.
_SCORECARD_LANES = [
    # Each row answers a question that is still OPEN (owner cut 2026-08-28:
    # "surely some aren't relevant any more"). Settled lanes live in
    # _SCORECARD_ARCHIVE and render inside a collapsed drawer — they keep
    # accruing upstream for their pre-registered reads; only the display moves.
    ("v2_starter_b15_tb_fees", "Default", "v2 starter · wide stop · exit on extension or thesis · 15/7.5 · small/mid ×½ · T-bill · IBKR fees"),
    ("v2_starter_b15_tb_fees_mcstop", "Twin · small/mid headline stop", "mechanism test: the tighter headline stop on small/mid names"),
    ("v2_starter_b15_regime_fees", "Twin · regime sleeve", "mechanism test: idle cash in SOXX while the regime is trend-up, T-bills otherwise"),
    ("v2_starter_b15_tb_fees_full", "Twin · small/mid full size", "tier control: is half-size doing anything?"),
    ("v2_starter_b15_all", "Theoretical · 0% borrow", "every signal funded at full size, cash may go negative at zero cost"),
    ("v1_wide_extthesis_100_b15", "Previous default (v1)", "same rules with adds on persistence — what the starter semantics cost"),
    ("v1_wide_ext_100_b12", "Challenger (v1)", "extension exit only · 12/6 — do the model's thesis downgrades add anything?"),
    ("v1_wide_extthesis_100_b15_lc", "v1 · large caps only", "never opens a small/mid name — the exclude answer to the tier question"),
    ("v1_flat10", "Control", "the original frozen SMA50-stop book · hold through CAUTION"),
]
# Settled iterations — measured, kept for the record, rendered collapsed.
_SCORECARD_ARCHIVE = [
    ("v2_starter_b15_tb_fees_mc67", "v2 · small/mid 10/5", "third point on the tier line (monotone with full and half)"),
    ("v2_starter_b15_spy_fees", "v2 · SPY sleeve", "idle cash in SPY — +5 pp is benchmark beta relabelled"),
    ("v2_starter_b15", "v2 · bare", "no sleeve, no fees — the sleeve/fees effect is ~0.5 pp"),
    ("v1_wide_extthesis_100_b15_rot", "v1 · rotate weakest", "moot under starter semantics — the cash cap never binds"),
    ("v1_wide_extthesis_100_b15_rot_top20", "v1 · sell +20% gainers", "banked R up, NAV down — profit-taking rule, not supported"),
    ("v1_wide_extthesis_100_b15_rot_ow", "v1 · trim to target", "between the two above; one funded trade, a loser"),
    ("v1_wide_extthesis_100_b15_spy", "v1 + SPY sleeve", "idle cash in SPY"),
    ("v1_wide_extthesis_100_b15_fees", "v1 + IBKR fees", "commissions, taxes, FX, slippage ≈ 0.15%"),
    ("v1_wide_extthesis_100", "v1 · 10/5", "same rules, smaller sizing — idles ~60% of the pot"),
    ("v1_wide_ext_100", "v1 ext-only · 10/5", "challenger rules, smaller sizing"),
]
_SCORECARD_ROLE_CLASS = {"Default": "pb-role-default",
                         "Previous default (v1)": "pb-role-challenger",
                         "Challenger (v1)": "pb-role-challenger"}


# What each scorecard column means, in one plain sentence, plus the scale a
# reader can judge the number against. Rendered as a click-to-open popover
# on each column header (works on touch too, so no separate glossary).
_METRIC_HELP = {
    "NAV": ("How much the $100,000 pot has grown.",
            "Read it against SPY on the same window: above SPY = beat the market."),
    "Sharpe": ("Return per unit of wobble — how smooth the growth was.",
               "Under 1 weak · 1–2 good · 2–3 strong · over 3 exceptional (short windows flatter it)."),
    "Max DD": ("The worst peak-to-trough fall on the way — what you would have had to sit through.",
               "Under −5% mild · −5 to −10% normal for a stock book · beyond −15% painful."),
    "Win": ("Share of closed trades that made money.",
            "50–65% is typical for a trend book; on its own it says little — read it with expectancy."),
    "Expectancy": ("Average profit per $1 risked at the stop, over all closed trades (R-multiples).",
                   "Below 0 losing · +0.3R decent · +0.5R strong · +0.8R excellent."),
    "Exit-rule R": ("The same, only for trades the sell rule closed.",
                    "Should sit well above +1R — the rule is meant to bank the winners."),
    "Stop R": ("The same, only for trades the stop closed.",
               "−1R means the stop did exactly its job; worse than −1R = gap-downs through it."),
    "Stop drag": ("What all the stop-outs cost together, as % of the pot.",
                  "Smaller is better · −2 to −3% is normal here · the old book ran −6%."),
    "Cash idle": ("Average share of the pot sitting in cash, not in stocks.",
                  "High = signals are scarce; the cash-sleeve lane parks it in SPY instead."),
    "Fees": ("Commissions, taxes and FX on closed trades, as % of the pot.",
             "Under 0.3% over four months is immaterial; slippage sits in the fill prices."),
    "β SOXX": ("How much the book moves with the semiconductor index — whole pot / per invested dollar.",
               "1.0 = it is the index. Low over one window can be exit timing and cash, not skill: descriptive, not proof."),
    "Worst pos": ("The deepest fall any currently held name has taken from its peak while held.",
                  "The pain the portfolio drawdown hides — a wide stop means sitting through −15 to −25% on single names."),
}


def help_tip(text: str, label: str = "What this means") -> str:
    """A click-to-open "?" popover. Built on <details>, which Streamlit's
    sanitiser keeps (the watchlist drawers use it), so it opens on click and
    on keyboard, and needs no JavaScript. A title attribute alone only shows
    after a long hover and never on click/touch (owner report 2026-08-27)."""
    body = _escape_dollars(text)
    return (f'<details class="pb-tip"><summary aria-label="{label}">?</summary>'
            f'<div class="pb-tip-body">{body}</div></details>')


def _th(name: str) -> str:
    what, scale = _METRIC_HELP.get(name, ("", ""))
    tip = f"<b>{_escape_dollars(what)}</b><br>{_escape_dollars(scale)}"
    return (f'<th>{_escape_dollars(name)}'
            f'<details class="pb-tip"><summary aria-label="What {_escape_dollars(name)} means">?</summary>'
            f'<div class="pb-tip-body">{tip}</div></details></th>')


def _fmt_pct(v, plus=True, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:+.{d}f}%" if plus else f"{v:.{d}f}%"


def _fmt_r(v, n=None):
    if v is None:
        return "—"
    s = f"{v:+.2f}R"
    return f"{s} <small>n={n}</small>" if n else s


def _fmt_num(v, d=2):
    return "—" if v is None else f"{v:.{d}f}"


def _fmt_beta(port, invested):
    if port is None:
        return "—"
    s = f"{port:.2f}"
    return f"{s} <small>/ {invested:.2f}</small>" if invested is not None else s


def scorecard_html(nav_df, trades_df, positions_df, lanes=None,
                   benchmarks: bool = True) -> str:
    """The metrics the book is judged on, one row per lane + SPY/SOXX.
    ``lanes`` defaults to the open-question set; the archive drawer passes
    _SCORECARD_ARCHIVE with ``benchmarks=False``."""
    lanes = _SCORECARD_LANES if lanes is None else lanes
    rows = _scorecard_rows(nav_df, trades_df, positions_df,
                           [pid for pid, _r, _d in lanes])
    if not rows:
        return ""
    meta = {pid: (role, desc) for pid, role, desc in lanes}
    spy = next((r.get("spy") for r in rows if r.get("spy")), None) if benchmarks else None
    soxx = next((r.get("soxx") for r in rows if r.get("soxx")), None) if benchmarks else None
    head = ("<tr><th>Lane</th>" + "".join(_th(n) for n in (
        "NAV", "Sharpe", "Max DD", "Worst pos", "β SOXX", "Win", "Expectancy",
        "Exit-rule R", "Stop R", "Stop drag", "Cash idle", "Fees")) + "</tr>")
    body = ""
    for r in rows:
        role, desc = meta[r["policy_id"]]
        by = r.get("by_reason") or {}
        ex, stp = by.get("exit_rule") or {}, by.get("stop") or {}
        cls = _SCORECARD_ROLE_CLASS.get(role, "")
        body += (
            f'<tr class="{cls}"><td class="pb-sc-lane"><b>{_escape_dollars(role)}</b>'
            f'<small>{_escape_dollars(desc)}</small></td>'
            f'<td>{_fmt_pct(r.get("ret_pct"))}</td>'
            f'<td>{_fmt_num(r.get("sharpe"))}</td>'
            f'<td>{_fmt_pct(r.get("max_dd_pct"))}</td>'
            f'<td>{_fmt_pct(r.get("worst_open_dd_pct"))}</td>'
            f'<td>{_fmt_beta(r.get("beta_soxx"), r.get("beta_soxx_invested"))}</td>'
            f'<td>{_fmt_pct(r.get("win_rate_pct"), plus=False, d=0)}</td>'
            f'<td>{_fmt_r(r.get("expectancy_r"), r.get("n_r"))}</td>'
            f'<td>{_fmt_r(ex.get("mean_r"), ex.get("n"))}</td>'
            f'<td>{_fmt_r(stp.get("mean_r"), stp.get("n"))}</td>'
            f'<td>{_fmt_pct(r.get("stop_drag_pct"), d=2)}</td>'
            f'<td>{_fmt_pct(r.get("avg_cash_pct"), plus=False, d=0)}</td>'
            f'<td>{_fmt_pct(r.get("fees_pct"), plus=False, d=2) if r.get("fees_pct") is not None else "—"}</td>'
            "</tr>"
        )
    if spy:
        body += (
            '<tr class="pb-role-bench"><td class="pb-sc-lane"><b>SPY</b>'
            "<small>benchmark · same window</small></td>"
            f'<td>{_fmt_pct(spy.get("ret_pct"))}</td>'
            f'<td>{_fmt_num(spy.get("sharpe"))}</td>'
            f'<td>{_fmt_pct(spy.get("max_dd_pct"))}</td>'
            + "<td>—</td>" * 9 + "</tr>"
        )
    if soxx:
        body += (
            '<tr class="pb-role-bench"><td class="pb-sc-lane"><b>SOXX</b>'
            "<small>semis index · the factor most names load on</small></td>"
            f'<td>{_fmt_pct(soxx.get("ret_pct"))}</td>'
            f'<td>{_fmt_num(soxx.get("sharpe"))}</td>'
            f'<td>{_fmt_pct(soxx.get("max_dd_pct"))}</td>'
            "<td>—</td><td>1.00</td>" + "<td>—</td>" * 7 + "</tr>"
        )
    return (
        '<p class="pb-lane-eyebrow">Strategy scorecard '
        '<span class="pb-eyebrow-hint">click ? on a column for what it means</span></p>'
        f'<div class="tk-scroll"><table class="pb-scorecard">{head}{body}</table></div>'
    )


# ── Why the default strategy is built this way (2026-08-27) ───────────────
# Collapsed by default. Each line: what is used · why · the number behind it.
# Numbers are the 2026-08-27 read (pipeline spec 2026-08-27-paper-stop-exit-
# cross-design + addenda); refresh them when the pre-registered read lands.
_RATIONALE = [
    ("Entries — the report's own BUY / ACCUMULATE signals, bought at that day's close; a fill that already sits under its own stop is refused.",
     "Entry quality was never the problem: ACCUMULATE names beat SPY by +2.3 pts over the "
     "next 10 sessions, and the AVOID / CAUTION calls are the best-calibrated thing in the "
     "system (AVOID names −9.7 pts vs SPY at 30 sessions)."),
    ("Stop at the nearest structural support, not at the 50-day line.",
     "The 50-day stop sat a median 2.3% under entry, fired within 20 sessions on half of all "
     "fills, never once closed a winner (0 of 16), and 3 in 4 of the names it sold were higher "
     "ten sessions later. It cost about 6% of the pot in the book that used it. The wider stop "
     "fires a quarter as often and the names it sells keep falling (−8 pts vs SPY afterwards)."),
    ("Sell when a name stretches too far above its 50-day trend, or when the report breaks the thesis.",
     "The only two exits whose sales were later vindicated: extension exits made +12% of the "
     "pot with the names −15 pts vs SPY afterwards; thesis exits won every time. RSI and "
     "valuation triggers lost money, and the 'any' trigger that blends them in did worse than "
     "either good one alone."),
    ("15% per name, built 7.5% a day on ACCUMULATE.",
     "This rulebook's drawdown barely moves with size (−5.2% at 10/5 → −6.7% at 15/7.5) "
     "because the thesis exit leaves early; Sharpe keeps rising to 15/7.5. 20/10 would mean "
     "five names in a book where 17 of 33 share one factor."),
    ("Cash waits for the next signal.",
     "Signals are scarce, so ~42% of the pot idles on average — the book's main drag. The "
     "'cash sleeve' lane parks idle cash in SPY (+5 pts over the window at no extra drawdown); "
     "a T-bill version is the safe variant. Neither is the default yet."),
    ("Fees are modelled from IBKR's live schedule.",
     "Venue commissions, the Korean sell tax, FX conversion and half-spread slippage: about "
     "0.6% of the pot over four months, two-thirds of it on the nine foreign names. Immaterial."),
    ("What is not proven yet.",
     "Two regime segments, ~20 closed trades a lane, no bear market. The comparison against "
     "the old stop was pre-registered before the numbers were read and lands ~8 Sep 2026; "
     "until then this is a paper book, not a verdict."),
]


def strategy_rationale_html() -> str:
    items = "".join(
        f'<li><b>{_escape_dollars(what)}</b><br>'
        f'<span class="pb-why">{_escape_dollars(why)}</span></li>'
        for what, why in _RATIONALE
    )
    return f'<ul class="pb-rationale">{items}</ul>'


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
    # All neutral: these are inputs, not verdicts. Colouring them would imply
    # 15 stop-outs is "bad" when it is simply how many there were.
    body = "".join(
        f'<div class="stat-tick"><b>{_escape_dollars(v)}</b>'
        f"<span>{label}</span></div>"
        for v, label in chips
    )
    # Column count follows the chips: 5 on today's data, up to 7 when the
    # AVOID / delist exit reasons are present.
    return (f'<div class="hair-grid pb-stats" '
            f'style="grid-template-columns:repeat({len(chips)},1fr);">{body}</div>')


_BAND_BANNER = ("Paper only · 90 sessions · carried by a handful of AI-hardware "
                "names · ~15 trades a lane · not a track record · next read ~8 Sep 2026")
_BAND_BANNER_FULL = (
    "Paper measurement only. Ninety sessions, one trending segment and one "
    "choppy one since 22 Jul; about 15 closed trades a lane. Half of the "
    "return comes from three names and most of the beat over SPY from the "
    "August AI-hardware run — 17 of the 33 names share that factor, so the "
    "book holds ~3–4 real bets, not 9. The cash constraint hid only one "
    "trade (a loser), so the per-trade numbers are not sizing luck; whether "
    "they hold on new names in a different tape is what the pre-registered "
    "read around 8 Sep 2026 tests. Not a performance verdict."
)


def _banner_html(block: dict) -> str:
    """The band's caveat, one line; the full version on hover. Since
    2026-08-27 the dashboard owns this copy (the exported block's banner
    describes the legacy control's window)."""
    return (f'<p class="pb-banner">{_escape_dollars(_BAND_BANNER)}'
            f'{help_tip(_BAND_BANNER_FULL, "Full caveat")}</p>')


# Policy_id → compact public label (the lanes the Telegram glance abbreviates
# as "trail"/"nostop"/"wide"; the headline book itself is the flat 10% stop).
_LANE_LABELS = {"v1_flat10": "flat", "v1_trail10": "trail",
                "v1_nostop10": "no-stop", "v1_wide10": "wide",
                "v1_ladder10": "ladder",
                # still in the surfaced variants array (it is the control
                # for the pipeline's pre-registered stop x exit read) but no
                # longer a charted lane since 2026-08-27
                "v1_tc_ext_100": "ext-exit 10/5",
                "v1_wide_ext_100": "wide+ext 10/5",
                "v1_wide_extthesis_100": "wide+extthesis 10/5",
                "v1_wide_extthesis_100_b15": "v1 default · wide+extthesis 15/7.5",
                "v2_starter_b15_tb_fees": "default · v2 starter",
                "v2_starter_b15_tb_fees_mc67": "v2 · small/mid 10/5",
                "v2_starter_b15_tb_fees_full": "v2 · small/mid full",
                "v2_starter_b15_tb_fees_mcstop": "v2 · small/mid headline stop",
                "v2_starter_b15_regime_fees": "v2 · regime sleeve",
                "v2_starter_b15_spy_fees": "v2 · SPY sleeve",
                "v2_starter_b15": "v2 · bare",
                "v2_starter_b15_all": "v2 · 0% borrow"}


def _lane_label(policy_id: str) -> str:
    """Reader label for a lane, falling back through every map we own.

    The exported ``variants`` array is not limited to the four stop-rule lanes —
    the ext-exit replays appear there too, and those already have labels in
    ``_ADVISORY_CURVES`` (used by the chart legend). Consulting both keeps a raw
    policy_id off the page; in the lane grid an unlabelled id sits as a cell
    title beside four clean ones, which is far louder than it was mid-sentence.
    Unknown ids still fall through to the escaped id rather than being dropped.
    """
    return (_LANE_LABELS.get(policy_id)
            or _ADVISORY_CURVES.get(policy_id)
            or _escape_dollars(str(policy_id)))


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
    lanes = []
    for v in block.get("variants") or []:
        if not isinstance(v, dict) or not v.get("policy_id"):
            continue
        nav = v.get("nav_return_pct")
        if not isinstance(nav, (int, float)):
            continue
        label = _lane_label(v["policy_id"])
        lanes.append((label, nav, v.get("stops"), False))
    if not lanes:
        return ""
    head_nav = block.get("nav_return_pct")
    if isinstance(head_nav, (int, float)):
        label = _lane_label(block.get("policy_id") or "book")
        stops = (block.get("trade_counts") or {}).get("stop")
        lanes.insert(0, (label, head_nav, stops, True))

    cells = ""
    for label, nav, stops, is_head in lanes:
        stop_txt = (f'<span class="pb-lane-stops">{int(stops)} stop-outs</span>'
                    if isinstance(stops, (int, float)) else "")
        # Steel rail + the word: without it a reader cannot tell which of these
        # numbers is the real book, and the best-looking lane reads as the
        # headline result. Never a ranking — the exported banner below carries
        # the caveat.
        flag = ' data-flag="1"' if is_head else ""
        suffix = ' <span class="pb-lane-head">· headline</span>' if is_head else ""
        cells += (
            f'<div class="pb-lane"{flag}>'
            f'<div class="pb-lane-label">{label}{suffix}</div>'
            f'<div class="pb-lane-ret">{nav:+.1f}%</div>'
            f"{stop_txt}</div>"
        )
    return (
        '<p class="pb-lane-eyebrow">Stop-rule lanes — same book, only the stop '
        "rule differs</p>"
        f'<div class="hair-grid pb-lanes" '
        f'style="grid-template-columns:repeat({len(lanes)},1fr);">{cells}</div>'
    )


# Exit-reason keys → singular plain-language labels for the history's
# "Why sold" column (the chip map above is plural, for counts).
_EXIT_LABELS = {
    "stop": "stop-out (auto-sold)",
    "avoid_exit": "AVOID exit",
    "caution_exit": "CAUTION exit",
    "delist_exit": "delisted",
    "margin_call": "forced sale (margin)",
    "rotation_exit": "rotated out for a new signal",
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
               as_of_year: int | None = None,
               labels: dict | None = None) -> list[dict]:
    """Display rows for the completed-trades table, from ``select_trades``.

    Each row: ``ticker`` (display form), ``bought``/``sold`` (date @ price,
    with an ``avg · N buys`` suffix for multi-tranche entries), ``why``
    (labeled exit reason), ``dollars`` (pnl_units × *factor*, None without a
    factor) and ``pct`` (exported return on cost). Rows without a ticker, or
    with nothing honest to show as profit, are skipped; a bad date degrades
    to an em-dash rather than dropping an otherwise-complete trade.
    """
    rows: list[dict] = []
    labels = _EXIT_LABELS if labels is None else labels
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
        why = labels.get(reason, "" if pd.isna(reason) else str(reason))
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
            f'<td data-l="Bought">{_escape_dollars(r["bought"])}</td>'
            f'<td data-l="Sold">{_escape_dollars(r["sold"])}</td>'
            f'<td data-l="Why sold">{_escape_dollars(r["why"])}</td>'
            f'<td class="num" data-l="Profit">{_profit_html(r["dollars"], r["pct"])}</td>'
            "</tr>"
        )
    if not body:
        return ""
    # .stack-m: phones reflow each trade into a labeled card (data-l labels)
    # instead of swiping a 5-column table sideways (owner request 2026-07-17).
    return (
        '<table class="ep-table stack-m"><thead><tr>'
        '<th scope="col">Name</th><th scope="col">Bought</th>'
        '<th scope="col">Sold</th><th scope="col">Why sold</th>'
        '<th scope="col" class="num">Profit</th>'
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def select_positions(positions_df: pd.DataFrame | None,
                     block: dict) -> pd.DataFrame:
    """Open positions for the band's policy — same rule as the NAV curve."""
    if (positions_df is None or positions_df.empty
            or "policy_id" not in positions_df.columns):
        return pd.DataFrame()
    pid = _policy_for(positions_df, block)
    if pid is None:
        return pd.DataFrame()
    return positions_df[positions_df["policy_id"] == pid]


def position_rows(df: pd.DataFrame | None, factor: float | None = None,
                  as_of_year: int | None = None) -> list[dict]:
    """Display rows for the shares/cost-basis positions table.

    WHOLE shares (user decision 2026-07-17): the pot's fractional stake
    (book qty × *factor*, the NAV curve's own rebase) rounds to the nearest
    whole share — spending a touch more or less than the measured stake —
    and never below one share of a held position. ``cost`` = shares × the
    position's per-share USD cost basis (``invested_units/qty``, which
    carries the fx actually paid), ``value`` = shares × native last close ×
    the carried fx, so cost/value/P&L are exactly what those whole shares
    are worth in pot dollars. Prices (``bought``/``now``/stop) stay native,
    matching the trades table. Rows without a ticker or share count are
    skipped; a missing mark degrades to a cost-only row rather than
    inventing a value.
    """
    rows: list[dict] = []
    if df is None or df.empty:
        return rows
    for _, r in df.iterrows():
        ticker = r.get("ticker")
        qty = _num_or_none(r.get("qty"))
        if not isinstance(ticker, str) or not ticker.strip() or not qty:
            continue
        bought = _fmt_trade_date(r.get("entry_date"), as_of_year)
        entry_px = _num_or_none(r.get("avg_entry_price"))
        if entry_px is not None:
            bought += f" @ {entry_px:,.2f}"
        tranches = _num_or_none(r.get("tranches"))
        if tranches is not None and tranches >= 2:
            bought += f" avg · {int(tranches)} buys"
        last_close = _num_or_none(r.get("last_close"))
        fx = _num_or_none(r.get("fx_rate"))
        fx = 1.0 if fx is None else fx
        invested = _num_or_none(r.get("invested_units"))
        # per-share USD cost = invested/qty — the pot scaling cancels, so
        # shares × it is the pot cost of exactly those whole shares
        shares = max(1, round(qty * factor)) if factor else max(1, round(qty))
        cost = shares * invested / qty if invested and factor else None
        value = (shares * last_close * fx
                 if last_close is not None and factor else None)
        dollars = pct = None
        if cost and value is not None:
            dollars = value - cost
            pct = (value / cost - 1) * 100.0
        stop = _num_or_none(r.get("stop_price"))
        dd = _num_or_none(r.get("max_dd_pct"))
        # drawdown is a positive magnitude upstream; sign it as a decline
        dd_txt = "—" if dd is None else (f"-{abs(dd):.1f}%" if dd else "0.0%")
        rows.append({
            "ticker": display_ticker(ticker),
            "shares": f"{shares:,}",
            "bought": bought,
            "now": f"{last_close:,.2f}" if last_close is not None else "—",
            "stop": f"{stop:,.2f}" if stop is not None else "—",
            "dd": dd_txt,
            "cost": cost, "value": value,
            "dollars": dollars, "pct": pct,
        })
    return rows


def _positions_v2_table_html(rows: list[dict]) -> str:
    """Shares / cost-basis / marks positions table, or "" when empty."""
    body = ""
    for r in rows:
        if r["cost"] is not None and r["value"] is not None:
            cv = _escape_dollars(f"${r['cost']:,.0f} → ${r['value']:,.0f}")
        elif r["cost"] is not None:
            cv = _escape_dollars(f"${r['cost']:,.0f} → —")
        else:
            cv = "—"
        body += (
            "<tr>"
            f"<td>{_escape_dollars(r['ticker'])}</td>"
            f'<td class="num" data-l="Shares">{_escape_dollars(r["shares"])}</td>'
            f'<td data-l="Bought">{_escape_dollars(r["bought"])}</td>'
            f'<td class="num" data-l="Now">{_escape_dollars(r["now"])}</td>'
            f'<td class="num" data-l="Cost → value">{cv}</td>'
            f'<td class="num" data-l="P&amp;L so far">{_profit_html(r["dollars"], r["pct"])}</td>'
            f'<td class="num" data-l="Stop">{_escape_dollars(r["stop"])}</td>'
            f'<td class="num" data-l="Max drawdown">{r["dd"]}</td>'
            "</tr>"
        )
    if not body:
        return ""
    # .stack-m: phones reflow each position into a labeled card (data-l
    # labels) instead of swiping an 8-column table sideways.
    return (
        '<table class="ep-table stack-m"><thead><tr>'
        '<th scope="col">Name</th><th scope="col" class="num">Shares</th>'
        '<th scope="col">Bought</th><th scope="col" class="num">Now</th>'
        '<th scope="col" class="num">Cost → value</th>'
        '<th scope="col" class="num">P&amp;L so far</th>'
        '<th scope="col" class="num">Stop</th>'
        '<th scope="col" class="num">Max drawdown</th>'
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


_POSITIONS_V2_LEGEND = (
    '<p class="pb-banner">How to read this: <b>Shares</b> — whole shares '
    "the &#36;100,000 pot's stake buys, rounded to the nearest share "
    "(spending a touch more or less than the measured stake — so the table "
    "can differ from the pot line by a share's worth). <b>Bought</b> — "
    "first purchase date @ average fill price, in the stock's own currency "
    "(avg — several buys built the position). <b>Now</b> — the latest "
    "close, same currency. <b>Cost → value</b> — pot dollars those shares "
    "cost → what they're worth at that close. <b>P&amp;L so far</b> — the "
    "difference; unrealized until sold. <b>Stop</b> — the pre-set price "
    "that triggers an automatic sell. <b>Max drawdown</b> — the deepest "
    "fall from the stock's highest point while held: pain along the way, "
    "not the current profit.</p>"
)


def lane_cash_html(nav_df: pd.DataFrame | None, pid: str,
                   n_open: int) -> str:
    """One-line pot status for a book: pot now, cash, open-position count.

    All from the book's own NAV tail × its own rebase factor — the exact
    numbers its curve compounds to; nothing re-derived.
    """
    rows = select_policy(nav_df, {"policy_id": pid})
    factor = trade_dollars_factor(nav_df, {"policy_id": pid})
    if rows.empty or not factor or "nav_units" not in rows.columns:
        return ""
    last = rows.iloc[-1]
    nav = _num_or_none(last.get("nav_units"))
    cash = _num_or_none(last.get("cash_units"))
    if not nav or cash is None:
        return ""
    word = "position" if n_open == 1 else "positions"
    txt = (f"Pot now {_money(nav * factor)} · cash {_money(cash * factor)} "
           f"({cash / nav * 100:.0f}%) · {n_open} open {word}")
    return f'<p class="pb-lane-cash">{_escape_dollars(txt)}</p>'


# Advisory lanes' history (spec addendum 2026-07-17; lanes swapped
# 2026-08-27) — the same scoped allowlist as the dashed curves. A
# caution_exit is the lane's own exit rule firing, so it's labeled as the
# behaviour it represents — per lane, because the hybrid's rule fires on
# EITHER an extension or a thesis-break CAUTION and the export carries only
# the reason, not the bucket.
_EXT_EXIT_LABELS = {**_EXIT_LABELS, "caution_exit": "sold on extension"}
_LANE_EXIT_LABELS = {
    "v1_wide_ext_100": _EXT_EXIT_LABELS,
    "v1_wide_ext_100_b12": _EXT_EXIT_LABELS,
    "v1_wide_extthesis_100": {**_EXIT_LABELS,
                              "caution_exit": "sold on extension / thesis"},
    "v1_wide_extthesis_100_b15": {**_EXIT_LABELS,
                                  "caution_exit": "sold on extension / thesis"},
}

_EXT_HISTORY_CAVEAT = (
    '<p class="pb-banner">The dashed line on the chart, trade by trade. '
    "<b>Challenger</b>: the same wide stop as the default, exits on "
    "extension only, 12%/6% sizing — its own &#36;100,000 pot. "
    "Hypothesis-grade · not the default book.</p>"
)


def _lane_of(df: pd.DataFrame | None, pid: str) -> pd.DataFrame:
    """Rows of *df* for one policy_id; empty frame when unusable."""
    if df is None or df.empty or "policy_id" not in df.columns:
        return pd.DataFrame()
    return df[df["policy_id"] == pid]


def ext_lane_views(nav_df: pd.DataFrame | None,
                   trades_df: pd.DataFrame | None,
                   positions_df: pd.DataFrame | None = None,
                   as_of_year: int | None = None) -> list[tuple]:
    """(label, policy_id, position rows, trade rows) per charted advisory
    lane with any data — the ``_ADVISORY_CURVES`` allowlist, nothing else.
    Each lane's dollars use its OWN NAV rebase factor (the pot its dashed
    curve plots); lanes absent from both CSVs are skipped silently."""
    out: list[tuple] = []
    for pid, label in _ADVISORY_CURVES.items():
        lane_t = _lane_of(trades_df, pid)
        lane_p = _lane_of(positions_df, pid)
        if lane_t.empty and lane_p.empty:
            continue
        factor = trade_dollars_factor(nav_df, {"policy_id": pid})
        t_rows = trade_rows(_newest_exit_first(lane_t), factor, as_of_year,
                            labels=_LANE_EXIT_LABELS.get(pid, _EXT_EXIT_LABELS))
        p_rows = position_rows(lane_p, factor, as_of_year)
        if t_rows or p_rows:
            out.append((label, pid, p_rows, t_rows))
    return out


def ext_exit_history(nav_df: pd.DataFrame | None,
                     trades_df: pd.DataFrame | None,
                     as_of_year: int | None = None) -> list[tuple[str, list]]:
    """(lane label, completed-trade rows) — trades-only view of
    ``ext_lane_views``, kept for its narrower contract."""
    return [(label, t_rows)
            for label, _pid, _p_rows, t_rows
            in ext_lane_views(nav_df, trades_df, None, as_of_year) if t_rows]


def _lane_heading_html(label: str, rows: list[dict]) -> str:
    """Lane name + its exit-reason mix, e.g. "12 × stop-out · 3 × sold on
    extension" — the selling-behaviour contrast at a glance."""
    mix = Counter(r["why"] for r in rows if r.get("why"))
    mix_txt = " · ".join(f"{n} × {why}" for why, n in mix.most_common())
    head = f"<b>{_escape_dollars(label)}</b>"
    if mix_txt:
        head += f" — {_escape_dollars(mix_txt)}"
    return f'<p class="pb-lane-head">{head}</p>'


# Plain-language key for the history table, same voice as the positions
# legend. &#36; keeps the literal dollar sign out of Streamlit's LaTeX path.
_HISTORY_LEGEND = (
    '<p class="pb-banner">How to read this: each row is one completed trade, '
    "newest first. <b>Bought / Sold</b> — the fill dates and prices (avg — "
    "the average price when several buys built the position). <b>Why "
    "sold</b> — the rule that triggered the sale; every exit is mechanical, "
    "never a judgment call. <b>Profit</b> — what the trade added to or took "
    "from the &#36;100,000 pot, with the return on the money put in.</p>"
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
            bought_cell = f'<td data-l="Bought">{_escape_dollars(bought)}</td>'
            pnl_cell = (f'<td class="num" data-l="P&amp;L so far">'
                        f'{_profit_html(dollars, _num_or_none(p.get("pnl_pct")))}'
                        "</td>")
        rows += (
            "<tr>"
            f"<td>{_escape_dollars(display_ticker(str(p['ticker'])))}</td>"
            f"{bought_cell}"
            f'<td class="num" data-l="Weight">{f"{wt:.1f}%" if wt is not None else "—"}</td>'
            f'<td class="num" data-l="Stop">{f"{stop:.2f}" if stop is not None else "—"}</td>'
            f'<td class="num" data-l="Tranches">{_escape_dollars(str(p.get("tranches", "—")))}</td>'
            f'<td class="num" data-l="Max drawdown">{dd_txt}</td>'
            f"{pnl_cell}"
            "</tr>"
        )
    if not rows:
        return ""
    bought_head = '<th scope="col">Bought</th>' if with_pnl else ""
    pnl_head = ('<th scope="col" class="num">P&amp;L so far</th>'
                if with_pnl else "")
    # .stack-m: phones reflow each position into a labeled card.
    return (
        '<table class="ep-table stack-m"><thead><tr>'
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
    "since purchase, in dollars of the &#36;100,000 pot; unrealized until "
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


# Book, SPY and SOXX plot solid. SOXX was held off the chart from 2026-07-07
# (its ±60% window return flattened the book-vs-SPY gap) and restored on
# 2026-08-27 (owner call): the surfaced lanes now sit within a few points of
# SOXX, and after the external review SOXX is the benchmark the book must
# be read against — hiding it would flatter the SPY comparison.
_CHART_SERIES = ("Paper book", "SPY", "SOXX")

# Advisory ext-exit lanes charted as DASHED curves (user decision 2026-07-17,
# entry-sizing research adoption addendum). This is a deliberate, narrow
# exception to the "variants never charted" rule of the 2026-07-05 spec:
# the exit-on-extension lanes are the live sizing/exit experiment and the
# owner asked to track the divergence visually. They stay visually
# subordinate (thin + dashed), the headline curve is unchanged, and the
# single-regime banner still renders beneath the chart. Lanes absent from
# the CSV (b30 seeds on its first post-registration pipeline run) are
# silently skipped.
# 2026-08-27 (stop x exit cross, pipeline spec 2026-08-27-paper-stop-exit-
# cross-design addendum e, user decision): the two charted lanes are now the
# wide-stop contenders — same entries, same wide structural stop, differing
# only in the exit trigger. The frozen-stop ext-exit lanes (10/5, 30/15)
# stay in the CSV but are no longer charted: the 30/15 lead read as cash
# deployment, not a sizing edge, and the 10/5 lane is the control the
# contenders are measured against in the pipeline's pre-registered read.
# 2026-08-27 (f/g, owner decision): the headline curve is the DEFAULT
# strategy (v1_wide_extthesis_100_b15, see _HEADLINE_POLICY) and the one
# dashed lane is the CHALLENGER (wide+ext 12/6). The original frozen-stop
# book (v1_flat10) is NOT charted any more — measured the weakest lane on
# every metric; the pipeline still accrues it as the regime-turn playbook's
# control, which needs no chart.
_ADVISORY_CURVES = {
    _PREV_DEFAULT_POLICY: "Previous default · v1 wide+extthesis 15/7.5",
    _CHALLENGER_POLICY: "Challenger · wide+ext 12/6",
}
_ADVISORY_DASH = {"Previous default · v1 wide+extthesis 15/7.5": "dash",
                  "Challenger · wide+ext 12/6": "dash"}
# Reader-facing name for the solid line (the series key stays "Paper book"
# for every downstream table/test contract).
_HEADLINE_LEGEND = "Default · v2 starter 15/7.5 · T-bill · fees"
# One neutral, one brass-tinted — variants of the subject and the benchmark, not
# two more categories. Two arbitrary palette hues (the old sage / dusty mauve)
# read as new series with meanings of their own. The tint is dimmed rather than
# CHART_ACCENT itself: a replay must never be mistaken for the book.
_ADVISORY_COLORS = {"Previous default · v1 wide+extthesis 15/7.5": CHART_ACCENT_SOFT,
                    "Challenger · wide+ext 12/6": CHART_ACCENT_SOFT}


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


# Series widths — hierarchy by weight, not just hue. A reader who knows nothing
# can still tell which line is the point.
_W_SUBJECT, _W_BENCH, _W_REPLAY = 2.4, 1.6, 1.4

# System milestones drawn on the NAV chart (owner request 2026-08-04): the
# dates the machine itself changed materially, so a kink in the curve can be
# read against what we did to it. Hand-curated (date, chart label, key text) —
# add sparingly: the labels share one strip and three is near the collision
# ceiling. Dates: 05-05 is the same cutover Pipeline Stats annotates; 05-30 is
# the measured-alpha severance; 07-05 is when live accrual replaced the
# replay seed AND the quant-patterns adoption wave landed.
_MILESTONES = [
    ("2026-05-05", "DeepSeek swap",
     "analysis engine switched Claude Sonnet → DeepSeek"),
    ("2026-05-30", "Catalyst cut",
     "catalyst entry path severed from live signals on measured "
     "negative alpha"),
    ("2026-07-05", "Quant patterns",
     "paper book goes live (earlier curve is replay-seeded) + "
     "quant-patterns adoption wave"),
]


def milestone_marks(rebased: pd.DataFrame | None) -> list[tuple]:
    """(date, label, key text) for each milestone inside the chart's span.

    Off-window milestones drop silently — a mark floating past the curve's
    edge would stretch the x-axis and imply data that isn't plotted.
    """
    if rebased is None or rebased.empty or "date" not in rebased.columns:
        return []
    dates = pd.to_datetime(rebased["date"], errors="coerce").dropna()
    if dates.empty:
        return []
    lo, hi = dates.min(), dates.max()
    return [(d, label, key) for iso, label, key in _MILESTONES
            if lo <= (d := pd.to_datetime(iso)) <= hi]


def _milestone_note_html(marks: list[tuple]) -> str:
    """One-line key for the milestone marks, or "" when none plotted.

    Same voice and class as the SOXX/advisory notes; neutral ink throughout —
    these are records of what changed, never verdicts on whether it helped.
    """
    if not marks:
        return ""
    parts = " · ".join(
        f"<b>{d.day} {d:%b}</b> {_escape_dollars(key)}"
        for d, _label, key in marks
    )
    return f'<p class="pb-chartnote">Marks — {parts}.</p>'


def _legend_swatch(color: str, width: float, dash: bool) -> str:
    """An 18px rule at the series' real width and dash pattern.

    Actual line samples rather than colour squares, so the legend and the plot
    use identical encoding — the dashes say "hypothetical" before the caption is
    read. non-scaling-stroke keeps a hairline a hairline as the SVG stretches.
    """
    dash_attr = ("" if not dash else
                 ' stroke-dasharray="1.5 2.5"' if dash == "dot" else
                 ' stroke-dasharray="4 3"')
    return (
        '<svg class="pb-swatch" viewBox="0 0 18 6" width="18" height="6" '
        'aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" '
        f'stroke="{color}" stroke-width="{width}"{dash_attr} '
        'vector-effect="non-scaling-stroke"/></svg>'
    )


def _chart_head_html(rebased: pd.DataFrame,
                     advisory: pd.DataFrame | None) -> str:
    """Header row for the chart card: steel axis eyebrow left, legend right.

    Also carries the four blueprint registration marks, which position against
    the bordered container the chart sits in.
    """
    entries = []
    for name in [c for c in rebased.columns if c != "date" and c in _CHART_SERIES]:
        width = _W_SUBJECT if name == "Paper book" else _W_BENCH
        shown = _HEADLINE_LEGEND if name == "Paper book" else name
        entries.append((shown, _SERIES_COLORS.get(name, CHART_LINE), width, False))
    if advisory is not None and not advisory.empty:
        for name in [c for c in advisory.columns if c != "date"]:
            entries.append((name, _ADVISORY_COLORS.get(name, CHART_LINE),
                            _W_REPLAY, _ADVISORY_DASH.get(name, "dash")))
    legend = "".join(
        f'<span class="pb-legend-item">{_legend_swatch(color, width, dash)}'
        f"{_escape_dollars(name)}</span>"
        for name, color, width, dash in entries
    )
    # Escaped: a raw "$" in injected markdown is read as a LaTeX delimiter.
    axis = _escape_dollars(f"Value of {_money(NOTIONAL_START)} invested at start")
    return (
        '<i class="corner tl"></i><i class="corner tr"></i>'
        '<i class="corner bl"></i><i class="corner br"></i>'
        '<div class="pb-chart-head">'
        f'<span class="eyebrow">{axis}</span>'
        f'<span class="pb-legend">{legend}</span>'
        "</div>"
    )


def _nav_fig(rebased: pd.DataFrame, advisory: pd.DataFrame | None = None):
    """The NAV plot as a line drawing: no axis box, no filled plot area, and no
    Plotly legend — the header row above carries it, with real line samples."""
    fig = go.Figure()
    for name in [c for c in rebased.columns
                 if c != "date" and c in _CHART_SERIES]:
        fig.add_scatter(
            x=rebased["date"], y=rebased[name], mode="lines", name=name,
            line=dict(color=_SERIES_COLORS.get(name, CHART_LINE),
                      width=_W_SUBJECT if name == "Paper book" else _W_BENCH),
        )
    if advisory is not None and not advisory.empty:
        for name in [c for c in advisory.columns if c != "date"]:
            fig.add_scatter(
                x=advisory["date"], y=advisory[name], mode="lines", name=name,
                line=dict(color=_ADVISORY_COLORS.get(name, CHART_LINE),
                          width=_W_REPLAY,
                          dash=_ADVISORY_DASH.get(name, "dash")),
            )
    marks = milestone_marks(rebased)
    for d, label, _key in marks:
        # Dotted hairline in ink-4: a record on the paper, visually beneath
        # every plotted series. Labels live in the top margin strip (t=20)
        # so they never collide with the curves; a mark past 70% of the span
        # anchors right so its label can't clip off the chart edge.
        fig.add_shape(type="line", xref="x", yref="paper",
                      x0=d, x1=d, y0=0, y1=1,
                      line=dict(color=CHART_MUTED, width=1, dash="dot"))
        lo, hi = rebased["date"].min(), rebased["date"].max()
        frac = (d - lo) / (hi - lo) if hi > lo else 0.0
        right = frac > 0.7
        fig.add_annotation(x=d, y=1.0, yref="paper", yanchor="bottom",
                           xanchor="right" if right else "left",
                           xshift=-3 if right else 3,
                           text=label, showarrow=False,
                           font=dict(size=9, color=CHART_LINE))
    fig.update_layout(height=260,
                      margin=dict(l=0, r=0, t=20 if marks else 6, b=0),
                      showlegend=False)
    fig.update_xaxes(showline=False, zeroline=False)
    fig.update_yaxes(showline=False, zeroline=False, title=None)
    return style_fig(fig)


def _advisory_note_html(advisory: pd.DataFrame) -> str:
    """One-line key for the dashed lanes, or "" when none plotted."""
    if advisory is None or advisory.empty:
        return ""
    names = [c for c in advisory.columns if c != "date"]
    if not names:
        return ""
    # Terracotta on the limitation only — it marks a trust limit, never a rating.
    return ('<p class="pb-chartnote">Solid: the default strategy. Dashed: the '
            f'previous default and the challenger ({", ".join(names)} — BUY%/add-on% of the pot) · '
            '<span class="lim">hypothesis-grade, two regime segments</span> · '
            "not the default book.</p>")


def chart_notes_compact(rebased: pd.DataFrame, advisory: pd.DataFrame | None,
                        marks: list[tuple]) -> str:
    """One line under the chart; the detail rides on hover."""
    bits = ['<b>Solid</b> default']
    if advisory is not None and not advisory.empty and len(advisory.columns) > 1:
        bits.append("<b>dashed</b> previous default / challenger")
    if rebased is not None and "SOXX" in getattr(rebased, "columns", []):
        valid = rebased["SOXX"].dropna()
        if not valid.empty:
            ret = (valid.iloc[-1] / NOTIONAL_START - 1.0) * 100.0
            bits.append(f'SOXX <span class="val">{ret:+.1f}%</span> — the factor most names load on')
    tip = ""
    if marks:
        tip = "Dotted marks — " + " · ".join(
            f"{d.day} {d:%b}: {key}" for d, _label, key in marks)
        bits.append('dotted marks = system changes' + help_tip(tip, "What the marks are"))
    return f'<p class="pb-chartnote">{" · ".join(bits)}</p>'


def _soxx_note_html(rebased: pd.DataFrame) -> str:
    """One-line SOXX return note, or "" when absent (SOXX has plotted on the
    chart since 2026-08-27; kept for callers that want the number alone)."""
    if rebased is None or rebased.empty or "SOXX" not in rebased.columns:
        return ""
    valid = rebased["SOXX"].dropna()
    if valid.empty:
        return ""
    ret = (valid.iloc[-1] / NOTIONAL_START - 1.0) * 100.0
    # Brass on the figure: a measurement. The exclusion is disclosed rather than
    # silent — a +32% series would flatten the gap the chart exists to show.
    return (f'<p class="pb-chartnote">SOXX <span class="val">{ret:+.1f}%</span> '
            f"over this window — the semiconductor index most names load on.</p>")


def render_paper_book(latest_report: dict, nav_df: pd.DataFrame,
                      trades_df: pd.DataFrame | None = None,
                      positions_df: pd.DataFrame | None = None,
                      prices_df: pd.DataFrame | None = None) -> None:
    """Tier 1c — the paper book. Corpus-scoped (the tracker's name filter
    deliberately does not touch it). Absence tiers per the specs: block+CSV →
    full band; block only → summary, no curve; CSV only → curve only; neither
    (and no trade history) → skipped entirely, so every pre-export report
    renders exactly as before. *trades_df* (``data/paper_trades.csv``) adds
    the completed-trades history; *positions_df* (``data/paper_positions.csv``,
    addendum 2) upgrades the open-positions table to the shares/cost-basis
    view and adds per-lane pot/cash lines; either absent → the earlier
    rendering, unchanged.
    """
    raw_block = (latest_report or {}).get("paper_portfolio") or {}
    # The band headlines the DEFAULT lane from the CSV; the exported block
    # (the legacy control's numbers) is only a fallback / as_of source.
    block = headline_block(nav_df, raw_block) if raw_block or (
        nav_df is not None and not nav_df.empty) else {}
    rebased = rebase_curves(select_policy(nav_df, block))
    advisory = advisory_curves(nav_df)
    factor = trade_dollars_factor(nav_df, block)
    as_of = pd.to_datetime(block.get("as_of"), errors="coerce")
    as_of_year = None if pd.isna(as_of) else as_of.year
    history_rows = trade_rows(select_trades(trades_df, block), factor,
                              as_of_year)
    history_html = _trade_history_html(history_rows)
    pos_v2_rows = position_rows(select_positions(positions_df, block),
                                factor, as_of_year)
    ext_lanes = ext_lane_views(nav_df, trades_df, positions_df, as_of_year)
    if (not block and rebased.empty and not history_html and not ext_lanes
            and not pos_v2_rows):
        return
    render_section_head(
        "Paper book",
        "A simulated portfolio that follows the signals by rule · "
        "no real money · exists to measure them",
        masthead=True,
    )
    if block:
        st.markdown(_verdict_html(block), unsafe_allow_html=True)
    # The reasoning behind the default, collapsed: what is used, why, and
    # the number behind each choice. The band itself stays numbers-first.
    if block or (nav_df is not None and not nav_df.empty):
        with st.expander("Why the default strategy is built this way",
                         expanded=False):
            st.markdown(strategy_rationale_html(), unsafe_allow_html=True)
    chart_table = None
    if not rebased.empty:
        # st.container(border=True) is the only wrapper a Plotly element can sit
        # inside; the tracker-scoped CSS turns it into the blueprint frame, and
        # the injected corner marks position against it.
        with st.container(border=True):
            st.markdown(_chart_head_html(rebased, advisory),
                        unsafe_allow_html=True)
            st.plotly_chart(_nav_fig(rebased, advisory),
                            use_container_width=True, config=PLOTLY_CONFIG)
        st.markdown(chart_notes_compact(rebased, advisory,
                                        milestone_marks(rebased)),
                    unsafe_allow_html=True)
        # Held back rather than rendered here: the raw frame is the band's
        # lowest-priority door and renders after every other drawer (see the
        # end of this function).
        chart_table = rebased
        if not advisory.empty:
            chart_table = rebased.merge(advisory, on="date", how="left")
    sc = scorecard_html(nav_df, trades_df, positions_df)
    if sc or block:
        st.markdown(sc + _banner_html(block), unsafe_allow_html=True)
    # Settled iterations, collapsed: the record without the noise.
    archive = scorecard_html(nav_df, trades_df, positions_df,
                             lanes=_SCORECARD_ARCHIVE, benchmarks=False)
    if archive:
        with st.expander(f"All registered iterations — {len(_SCORECARD_ARCHIVE)} "
                         "settled lanes (measured, kept for the record)",
                         expanded=False):
            st.markdown(archive, unsafe_allow_html=True)
    if pos_v2_rows:
        # positions CSV present → the shares/cost-basis view supersedes the
        # block table (addendum 2); the block stays the fallback contract.
        positions_html = _positions_v2_table_html(pos_v2_rows)
    else:
        positions_html = _positions_table_html(block.get("positions"), factor,
                                               as_of_year)
    # trades_today belongs to the exported (legacy-control) block, not the
    # default lane — never shown under the default's drawer.
    trades_html = ""
    if positions_html or trades_html or history_html:
        with st.expander(_drawer_title(bool(history_html)), expanded=False):
            if trades_html:
                st.markdown(trades_html, unsafe_allow_html=True)
            if positions_html:
                if pos_v2_rows:
                    pid = _policy_for(positions_df, block)
                    st.markdown(lane_cash_html(nav_df, pid,
                                               len(pos_v2_rows)),
                                unsafe_allow_html=True)
                st.markdown(f'<div class="tk-scroll">{positions_html}</div>',
                            unsafe_allow_html=True)
                if pos_v2_rows:
                    st.markdown(_POSITIONS_V2_LEGEND, unsafe_allow_html=True)
                else:
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
    if ext_lanes:
        with st.expander("Challenger — trade history", expanded=False):
            st.markdown(_EXT_HISTORY_CAVEAT, unsafe_allow_html=True)
            any_pos = any_trades = False
            for label, pid, p_rows, t_rows in ext_lanes:
                st.markdown(_lane_heading_html(label, t_rows),
                            unsafe_allow_html=True)
                if p_rows:
                    any_pos = True
                    st.markdown(lane_cash_html(nav_df, pid, len(p_rows)),
                                unsafe_allow_html=True)
                    st.markdown('<div class="tk-scroll">'
                                f"{_positions_v2_table_html(p_rows)}</div>",
                                unsafe_allow_html=True)
                if t_rows:
                    any_trades = True
                    st.markdown(_history_verdict_html(t_rows),
                                unsafe_allow_html=True)
                    st.markdown('<div class="tk-scroll">'
                                f"{_trade_history_html(t_rows)}</div>",
                                unsafe_allow_html=True)
            if any_pos:
                st.markdown(_POSITIONS_V2_LEGEND, unsafe_allow_html=True)
            if any_trades:
                st.markdown(_HISTORY_LEGEND, unsafe_allow_html=True)
    # Last door on the band (owner call 2026-08-27b): the raw chart frame is
    # a screen-reader / data-parity fallback almost nobody opens, so it sits
    # below every drawer a reader might actually want.
    if chart_table is not None:
        chart_data_table(chart_table)
