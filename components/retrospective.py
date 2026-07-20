"""Retrospective page: monthly "what we called / what happened" narrative digest.

Spec: docs/superpowers/specs/2026-07-20-reader-retrospective-design.md
(MarketReport capability-gap survey 2026-07-19, item #8). Derives one-sentence
verdicts from the pipeline's exported call ledger (data/signal_log.csv).
Verdicts are frozen to each call's own 5/10/20-session outcome window — never
re-marked to the latest price — so a finished month's story never changes
afterwards. Retired tickers deliberately stay in: the page is about what we
*said*, and dropping bad old calls would be survivorship bias (deliberate
divergence from the Watchlist's RETIRED_TICKERS filter).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.paper_book import select_policy
from lib.cards import render_section_head
from lib.charts import STATUS_NEG, STATUS_POS
from lib.formatters import _escape_dollars, display_ticker
from lib.pills import _signal_pill_html

_FALLBACK_BANNER = (
    "Track record spans mostly a single market regime — read these verdicts "
    "as provisional, not proven."
)

_DIRECTIONAL = ("BUY", "ACCUMULATE", "CAUTION", "AVOID")
_LONG = ("BUY", "ACCUMULATE")


def dedupe_calls(log_df: pd.DataFrame) -> pd.DataFrame:
    """One row per *call*: the first row of each consecutive same-signal run
    per ticker, then directional calls only.

    The log repeats a signal daily while it stands; a HOLD/WATCH day between
    two ACCUMULATE days breaks the run (two distinct calls) — the same streak
    rule ``compute_signal_accuracy`` uses on the report corpus.
    """
    if log_df is None or log_df.empty or "signal" not in log_df.columns:
        return pd.DataFrame()
    df = log_df[log_df["signal"].notna()].sort_values(["ticker", "date"])
    first_of_run = df["signal"] != df.groupby("ticker")["signal"].shift()
    calls = df[first_of_run]
    return calls[calls["signal"].isin(_DIRECTIONAL)].reset_index(drop=True)


def _flag(row, col: str) -> bool:
    """True when a 0/1/NaN hit-flag cell is exactly 1."""
    v = row.get(col)
    try:
        return pd.notna(v) and float(v) == 1.0
    except (TypeError, ValueError):
        return False


def _pct_sfx(ret) -> str:
    return f" ({ret:+.1f}%)" if ret is not None else ""


def classify_call(row) -> tuple[str, str]:
    """(bucket, plain-text outcome) for one deduped call row.

    bucket: "worked" | "failed" | "pending". Right/wrong mirrors the Signal
    Tracker scorecard exactly — long calls are right when price rose (>0),
    CAUTION/AVOID right when it fell or went nowhere (<=0) — so the two pages
    can never disagree on a verdict. Only the call's own window is consulted
    (hit flags + 20-session return); no re-marking to the latest price.
    """
    ret = row.get("return_20d")
    ret = None if ret is None or pd.isna(ret) else float(ret)

    if row["signal"] in _LONG:
        hit_up = _flag(row, "hit_upside_target")
        hit_stop = _flag(row, "hit_invalidation")
        if hit_up and hit_stop:
            if ret is None:
                return "pending", ("hit both its target and its stop — verdict pending "
                                   "the 20-session mark")
            bucket = "worked" if ret > 0 else "failed"
            return bucket, (f"hit both its target and its stop inside the window — "
                            f"finished {ret:+.1f}% after 20 sessions")
        if hit_up:
            return "worked", f"hit its target inside 20 sessions{_pct_sfx(ret)}"
        if hit_stop:
            return "failed", f"stopped out{_pct_sfx(ret)}"
        if ret is None:
            return "pending", "too early to judge"
        if ret > 0:
            return "worked", f"up {ret:+.1f}% after 20 sessions"
        return "failed", f"down {ret:+.1f}% after 20 sessions"

    # CAUTION / AVOID — a drop (or nothing) proves the call right
    if ret is None:
        return "pending", "too early to judge"
    if ret == 0:
        return "worked", "went nowhere — staying out cost nothing"
    if ret < 0:
        return "worked", f"fell {abs(ret):.1f}% — staying out was right"
    return "failed", f"rallied {ret:+.1f}% instead"


def month_label(key: str) -> str:
    """'2026-07' -> 'July 2026'."""
    return pd.Timestamp(f"{key}-01").strftime("%B %Y")


def build_month_digest(calls: pd.DataFrame, month: str) -> dict:
    """Classified calls + headline stats for one 'YYYY-MM' month."""
    rows = calls[calls["date"].dt.strftime("%Y-%m") == month].sort_values("date")
    groups: dict[str, list] = {"worked": [], "failed": [], "pending": []}
    for _, row in rows.iterrows():
        bucket, outcome = classify_call(row)
        groups[bucket].append((row, outcome))
    resolved = len(groups["worked"]) + len(groups["failed"])
    return {"month": month, "n_calls": len(rows), "n_resolved": resolved,
            "n_worked": len(groups["worked"]), "groups": groups}


def banner_text(calibration_insights: dict | None) -> str:
    """The honesty banner: the pipeline's own confidence_banner verbatim when
    present, else a fixed single-regime caution. Never empty — the spec
    requires every month to render under it."""
    banner = ((calibration_insights or {}).get("confidence_banner") or "").strip()
    return banner or _FALLBACK_BANNER


def paper_month_line(nav_df: pd.DataFrame, block: dict, month: str) -> str:
    """One-line paper-book month read, or '' when the month has no NAV rows.

    Baseline = last NAV at-or-before month start (the seed month, with no
    prior row, measures from its first in-month observation). Uses the same
    ``select_policy`` rule as the Paper Book band so both surfaces always
    describe the same headline lane.
    """
    rows = select_policy(nav_df if nav_df is not None else pd.DataFrame(), block or {})
    if rows.empty:
        return ""
    rows = rows.assign(_d=pd.to_datetime(rows["date"], errors="coerce")).dropna(subset=["_d"])
    keys = rows["_d"].dt.strftime("%Y-%m")
    in_month = rows[keys == month]
    if in_month.empty:
        return ""
    before = rows[keys < month]
    base = before.iloc[-1] if not before.empty else in_month.iloc[0]
    end = in_month.iloc[-1]

    mon_name = pd.Timestamp(f"{month}-01").strftime("%B")
    bits = []
    for col, label in [("nav_units", None), ("spy_close", "SPY"), ("soxx_close", "SOXX")]:
        b = pd.to_numeric(base.get(col), errors="coerce")
        e = pd.to_numeric(end.get(col), errors="coerce")
        if pd.isna(b) or pd.isna(e) or b == 0:
            if label is None:
                return ""  # no NAV read -> no line at all
            continue
        pct = (e - b) / b * 100
        bits.append(f"{pct:+.1f}% in {mon_name}" if label is None else f"{label} {pct:+.1f}%")
    line = f"Paper book: {bits[0]}"
    if len(bits) > 1:
        line += " vs " + " · ".join(bits[1:])
    return line


_ICONS = {"worked": "✓", "failed": "✗", "pending": "⏳"}
_GROUP_HEADS = [("worked", "What worked"), ("failed", "What didn't"),
                ("pending", "Too early to judge")]


def _price(v) -> str:
    """'&#36;203.43' — entity dollar so Streamlit never parses LaTeX."""
    if v is None or pd.isna(v):
        return "—"
    return f"&#36;{float(v):,.2f}"


def call_item_html(row, bucket: str, outcome: str) -> str:
    """One verdict line: icon · pill · TICKER @ entry (levels) — outcome · date."""
    icon_col = {"worked": STATUS_POS, "failed": STATUS_NEG}.get(bucket, "var(--ink-3)")
    tk = _escape_dollars(display_ticker(str(row["ticker"])))
    levels = ""
    if row["signal"] in _LONG:
        bits = []
        if pd.notna(row.get("upside_target")):
            bits.append(f"target {_price(row['upside_target'])}")
        if pd.notna(row.get("invalidation")):
            bits.append(f"stop {_price(row['invalidation'])}")
        if bits:
            levels = f' <span class="retro-levels">({", ".join(bits)})</span>'
    return (
        f'<div class="retro-item" data-bucket="{bucket}">'
        f'<span class="retro-icon" style="color:{icon_col};">{_ICONS[bucket]}</span>'
        f'<div class="retro-body">'
        f'{_signal_pill_html(row["signal"], small=True)} '
        f'<b>{tk}</b> @ {_price(row.get("entry_price"))}{levels}'
        f'<span class="retro-outcome">— {_escape_dollars(outcome)}</span>'
        f'<span class="retro-date">{row["date"].strftime("%b %d")}</span>'
        f'</div></div>'
    )


def digest_html(digest: dict, paper_line: str) -> str:
    """Headline + paper line + the three groups for one month (empty groups omitted)."""
    head = (f'<div class="retro-headline"><b>{month_label(digest["month"])}</b> — '
            f'{digest["n_calls"]} new calls · {digest["n_resolved"]} resolved · '
            f'{digest["n_worked"]} went our way</div>')
    paper = (f'<div class="retro-paper">{_escape_dollars(paper_line)}</div>'
             if paper_line else "")
    groups = ""
    for key, title in _GROUP_HEADS:
        items = digest["groups"][key]
        if not items:
            continue
        body = "".join(call_item_html(r, key, o) for r, o in items)
        groups += (f'<div class="retro-group"><div class="retro-group-title">'
                   f'{_escape_dollars(title)} · {len(items)}</div>{body}</div>')
    if not groups:
        groups = '<div class="retro-group retro-empty">No calls this month.</div>'
    return head + paper + groups


def render_retrospective_page(latest_report: dict, log_df: pd.DataFrame,
                              nav_df: pd.DataFrame) -> None:
    """Retrospective page — monthly narrative digest of calls vs outcomes.

    Deliberately NOT clipped by the sidebar date filter: the month picker is
    this page's own time control and the archive should always be complete.
    """
    render_section_head(
        "Retrospective",
        "What we called, and what actually happened — month by month",
    )
    banner = _escape_dollars(banner_text((latest_report or {}).get("calibration_insights")))
    st.markdown(
        f'<div class="briefing-banner" data-tone="warn">⚠ {banner}</div>',
        unsafe_allow_html=True,
    )

    calls = dedupe_calls(log_df)
    if calls.empty:
        st.caption(
            "No calls logged yet — this page fills in as the pipeline's call "
            "ledger (signal_log.csv) accumulates."
        )
        return

    months = sorted(calls["date"].dt.strftime("%Y-%m").unique(), reverse=True)
    sel = st.selectbox("Month", months, index=0, format_func=month_label,
                       key="retro_month")

    # "In progress" is data-derived (latest month in the ledger), never
    # wall-clock — the visual baselines freeze TEST_DATE.
    if sel == months[0]:
        st.caption(
            f"{month_label(sel)} is still in progress — recent calls sit in "
            '"Too early to judge" until their 20-session window closes.'
        )

    digest = build_month_digest(calls, sel)
    paper = paper_month_line(nav_df, (latest_report or {}).get("paper_portfolio") or {}, sel)
    st.markdown(digest_html(digest, paper), unsafe_allow_html=True)

    st.caption(
        "Outcomes are **raw price direction** over each call's own 20-session "
        "window — not benchmark-relative; the alpha view lives on the "
        "Briefing's Signal Calibration band. WATCH and HOLD aren't scored "
        "here (non-directional). Retired names stay on the record — dropping "
        "old calls would flatter it."
    )
