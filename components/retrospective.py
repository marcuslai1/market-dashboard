"""Retrospective page: monthly "what we called / what happened" narrative digest.

(MarketReport capability-gap survey 2026-07-19, item #8). Derives one-sentence
verdicts from the pipeline's exported call ledger (data/signal_log.csv).
Verdicts are frozen to each call's own 5/10/20-session outcome window — never
re-marked to the latest price — so a finished month's story never changes
afterwards. Retired tickers deliberately stay in: the page is about what we
*said*, and dropping bad old calls would be survivorship bias (deliberate
divergence from the Watchlist's RETIRED_TICKERS filter).

The page answers one question — did the calls work? — and is ordered
caveat → time control → verdict → evidence → method, so the limitation leads and
no figure is read unqualified. The scoreboard computes the verdict the old layout
left to the reader ("9 resolved · 6 went our way" → "67%"), and always prints the
arithmetic under it so the percentage is never a bare assertion.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.paper_book import select_policy
from lib.cards import render_section_head
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


def month_label_short(key: str) -> str:
    """'2026-07' -> 'Jul 2026' — the segment label (CSS uppercases it).

    Short so the whole archive stays on one row: the segmented control exists to
    keep the time axis visible, which a wrapped strip starts to undo.
    """
    return pd.Timestamp(f"{key}-01").strftime("%b %Y")


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


def hit_rate(digest: dict) -> float | None:
    """Percent of *resolved* calls that went our way; None when none have.

    The denominator is deliberately ``n_resolved``, not ``n_calls`` — a call
    whose 20-session window is still open has no verdict to average in. That is
    also the one thing a hit rate can quietly lie about, which is why the
    scoreboard prints the arithmetic and puts the open count in the bar beside it.
    """
    n = digest["n_resolved"]
    return None if not n else digest["n_worked"] / n * 100.0


def banner_text(calibration_insights: dict | None) -> str:
    """The honesty banner: the pipeline's own confidence_banner verbatim when
    present, else a fixed single-regime caution. Never empty — the spec
    requires every month to render under it."""
    banner = ((calibration_insights or {}).get("confidence_banner") or "").strip()
    return banner or _FALLBACK_BANNER


def paper_month_stats(nav_df: pd.DataFrame, block: dict, month: str) -> dict | None:
    """Paper-book month move as numbers, or None when the month has no NAV read.

    ``{"month_name": "June", "nav_pct": 3.0, "spy_pct": 2.0, "soxx_pct": 2.5}``
    — a benchmark key is None when its column has no usable pair.

    Baseline = last NAV at-or-before month start (the seed month, with no prior
    row, measures from its first in-month observation). Uses the same
    ``select_policy`` rule as the Paper Book band so both surfaces always
    describe the same headline lane.
    """
    rows = select_policy(nav_df if nav_df is not None else pd.DataFrame(), block or {})
    if rows.empty:
        return None
    rows = rows.assign(_d=pd.to_datetime(rows["date"], errors="coerce")).dropna(subset=["_d"])
    keys = rows["_d"].dt.strftime("%Y-%m")
    in_month = rows[keys == month]
    if in_month.empty:
        return None
    before = rows[keys < month]
    base = before.iloc[-1] if not before.empty else in_month.iloc[0]
    end = in_month.iloc[-1]

    out: dict = {"month_name": pd.Timestamp(f"{month}-01").strftime("%B")}
    for col, key in [("nav_units", "nav_pct"), ("spy_close", "spy_pct"),
                     ("soxx_close", "soxx_pct")]:
        b = pd.to_numeric(base.get(col), errors="coerce")
        e = pd.to_numeric(end.get(col), errors="coerce")
        out[key] = None if (pd.isna(b) or pd.isna(e) or b == 0) else (e - b) / b * 100
    # No NAV read means no paper read at all: the benchmarks alone say nothing
    # about whether following the calls made money.
    return None if out["nav_pct"] is None else out


_ICONS = {"worked": "✓", "failed": "✗", "pending": "⏳"}
_GROUP_HEADS = [("worked", "What worked"), ("failed", "What didn't"),
                ("pending", "Too early to judge")]


def _price(v) -> str:
    """'&#36;203.43' — entity dollar so Streamlit never parses LaTeX."""
    if v is None or pd.isna(v):
        return "—"
    return f"&#36;{float(v):,.2f}"


def month_scoreboard_html(digest: dict, stats: dict | None) -> str:
    """The month's verdict, its composition, and the paper-book consequence.

    Three panels in one blueprint frame: three readings of the same month, not
    three subjects. The hit rate is the loudest element because a percentage is
    the answer to the question the page asks. The bar beside it carries the
    unresolved slice the hit rate structurally cannot show — together they are
    honest in a way either alone isn't. The paper return is the cross-check that
    stops either number being taken for the whole story.
    """
    n_calls = digest["n_calls"]
    n_res = digest["n_resolved"]
    n_worked = digest["n_worked"]
    n_failed = len(digest["groups"]["failed"])
    n_open = len(digest["groups"]["pending"])

    pct = hit_rate(digest)
    # With nothing resolved there is no percentage to print, and a dash in the
    # figure slot reads as a stray rule rather than a missing value — so the
    # empty state says what it means in words, in the muted ramp, and the
    # sub-line carries the detail instead of repeating it. data-empty lets CSS
    # step it out of the 48px brass treatment reserved for real readings.
    if pct is None:
        hit, empty_attr = "No verdict yet", ' data-empty="1"'
        arith = (f"all {n_calls} calls are still inside their 20-session windows"
                 if n_calls != 1 else
                 "its 20-session window hasn't closed yet")
    else:
        hit, empty_attr = f"{pct:.0f}%", ""
        noun = "call" if n_res == 1 else "calls"
        arith = f"{n_worked} of {n_res} resolved {noun} went our way"

    segs = ""
    for key, n in (("worked", n_worked), ("failed", n_failed), ("open", n_open)):
        if n:
            segs += (f'<span class="rb-seg" data-seg="{key}" '
                     f'style="width:{n / n_calls * 100:.1f}%;"></span>')
    # The bar is decorative markup, so it carries its own reading for anyone on
    # a screen reader.
    bar = (f'<div class="rb-bar" role="img" aria-label="{n_worked} worked, '
           f'{n_failed} failed, {n_open} still open of {n_calls} calls">'
           f'{segs}</div>') if segs else ""

    counts = "".join(
        f'<div class="rb-count"><b>{v}</b><span>{lbl}</span></div>'
        for v, lbl in ((n_calls, "New calls"), (n_res, "Resolved"), (n_open, "Still open"))
    )

    if stats:
        paper_val, paper_empty = f"{stats['nav_pct']:+.1f}%", ""
        bench = " / ".join(
            f"{lbl} {stats[k]:+.1f}%"
            for k, lbl in (("spy_pct", "SPY"), ("soxx_pct", "SOXX"))
            if stats.get(k) is not None
        )
        paper_sub = f"vs {bench}" if bench else "no benchmark read this month"
    else:
        # Same treatment as an unresolved hit rate: say it, don't draw a dash.
        paper_val, paper_empty = "Not measured", ' data-empty="1"'
        paper_sub = "no paper-book rows this month"

    return (
        '<div class="retro-board blueprint">'
        '<i class="corner tl"></i><i class="corner tr"></i>'
        '<i class="corner bl"></i><i class="corner br"></i>'
        '<div class="rb-panel rb-verdict">'
        f'<div class="rb-eyebrow">{month_label(digest["month"])} · hit rate</div>'
        f'<div class="rb-hit"{empty_attr}>{hit}</div>'
        f'<div class="rb-arith">{arith}</div>'
        '</div>'
        '<div class="rb-panel rb-comp">'
        '<div class="rb-eyebrow">Composition</div>'
        f'{bar}'
        f'<div class="rb-counts">{counts}</div>'
        '</div>'
        '<div class="rb-panel rb-paper">'
        '<div class="rb-eyebrow">Paper book</div>'
        f'<div class="rb-paper-val"{paper_empty}>{paper_val}</div>'
        f'<div class="rb-vs">{_escape_dollars(paper_sub)}</div>'
        '</div>'
        '</div>'
    )


def call_item_html(row, bucket: str, outcome: str) -> str:
    """One verdict row: rail · glyph · pill · TICKER @ entry — outcome · date.

    The pill keeps the full signal treatment while the rail and glyph state the
    outcome, so a CAUTION call that worked reads as an amber pill on a green
    rail — the rating and the result, each in its own colour system. Target/stop
    levels sit on a quiet second line rather than inline, where they used to
    interrupt the outcome sentence mid-read.
    """
    tk = _escape_dollars(display_ticker(str(row["ticker"])))
    levels = ""
    if row["signal"] in _LONG:
        bits = []
        if pd.notna(row.get("upside_target")):
            bits.append(f"target {_price(row['upside_target'])}")
        if pd.notna(row.get("invalidation")):
            bits.append(f"stop {_price(row['invalidation'])}")
        if bits:
            levels = f'<div class="retro-levels">{" · ".join(bits)}</div>'
    return (
        f'<div class="retro-item" data-bucket="{bucket}">'
        f'<span class="retro-icon">{_ICONS[bucket]}</span>'
        f'<span class="retro-pill">{_signal_pill_html(row["signal"], small=True)}</span>'
        f'<div class="retro-main">'
        f'<div class="retro-line"><b>{tk}</b> '
        f'<span class="retro-entry">@ {_price(row.get("entry_price"))}</span> '
        f'<span class="retro-outcome">— {_escape_dollars(outcome)}</span></div>'
        f'{levels}'
        f'</div>'
        f'<span class="retro-date">{row["date"].strftime("%b %d")}</span>'
        f'</div>'
    )


def digest_html(digest: dict, stats: dict | None) -> str:
    """Scoreboard + the three verdict groups for one month.

    Empty groups are omitted: a month with nothing pending should not render an
    empty "Too early to judge" head.
    """
    board = month_scoreboard_html(digest, stats) if digest["n_calls"] else ""
    groups = ""
    for key, title in _GROUP_HEADS:
        items = digest["groups"][key]
        if not items:
            continue
        body = "".join(call_item_html(r, key, o) for r, o in items)
        groups += (f'<div class="retro-group" data-bucket="{key}">'
                   f'<div class="retro-group-head"><h2>{_escape_dollars(title)}</h2>'
                   f'<span class="retro-group-n">{len(items)}</span></div>'
                   f'{body}</div>')
    if not groups:
        groups = '<div class="retro-empty">No calls this month.</div>'
    return board + groups


# Exactly two phrases carry bold, because they are the two facts that change how
# every row above is read: outcomes are absolute (the benchmark-relative view is
# elsewhere), and nothing is dropped from the record. Bolding by what breaks
# comprehension if missed, never by keyword.
_METHOD_NOTE = (
    "Outcomes are <b>raw price direction</b> over each call's own 20-session "
    "window — not benchmark-relative; the alpha view lives on the Briefing's "
    "Signal Calibration band. WATCH and HOLD aren't scored here "
    "(non-directional). <b>Retired names stay on the record</b> — dropping old "
    "calls would flatter it."
)

# The page's own legend, at the foot: where a reader confused by an
# amber-pill-on-green-rail row goes looking for the rule.
_FOOTER_RULES = ("Signal pills keep the rating · rails state the outcome",
                 "Verdicts frozen to each call's own window")


def render_retrospective_page(latest_report: dict, log_df: pd.DataFrame,
                              nav_df: pd.DataFrame) -> None:
    """Retrospective page — monthly narrative digest of calls vs outcomes.

    Deliberately NOT clipped by the sidebar date filter: the month picker is
    this page's own time control and the archive should always be complete.
    """
    # masthead=True is the shared 2px full-strength rule + 30px/600 head (the
    # Signal Tracker's peer sections use the same variant). This page had its own
    # copy of that treatment until the shared variant landed; one device, one
    # implementation — "a top-level document surface" should not be spelled two
    # different ways.
    render_section_head(
        "Retrospective",
        "What we called, and what actually happened — month by month",
        masthead=True,
    )

    # The caveat comes before any number. After a 67% hit rate it would be a
    # disclaimer; ahead of it, it is a precondition for reading.
    banner = _escape_dollars(banner_text((latest_report or {}).get("calibration_insights")))
    st.markdown(
        f'<div class="retro-banner"><span class="retro-warn">⚠</span>'
        f'<p>{banner}</p></div>',
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
    pick, note = st.columns([0.62, 0.38], vertical_alignment="bottom")
    with pick:
        sel = st.radio("Month", months, index=0, format_func=month_label_short,
                       horizontal=True, key="retro_month")
    with note:
        # "In progress" is data-derived (latest month in the ledger), never
        # wall-clock — the visual baselines freeze TEST_DATE. Inline beside the
        # control because it qualifies selecting *this* month, not the page.
        if sel == months[0]:
            st.markdown(
                f'<div class="retro-inprogress">{month_label(sel)} still in '
                'progress · open calls await their 20-session mark</div>',
                unsafe_allow_html=True,
            )

    digest = build_month_digest(calls, sel)
    stats = paper_month_stats(nav_df, (latest_report or {}).get("paper_portfolio") or {}, sel)
    st.markdown(digest_html(digest, stats), unsafe_allow_html=True)

    st.markdown(f'<p class="retro-method">{_METHOD_NOTE}</p>', unsafe_allow_html=True)
    st.markdown(
        '<div class="retro-footer">'
        + "".join(f"<span>{r}</span>" for r in _FOOTER_RULES)
        + '</div>',
        unsafe_allow_html=True,
    )
