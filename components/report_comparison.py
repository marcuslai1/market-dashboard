"""Report Comparison page: multi-day trend + pairwise diff between two dates."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from components.scenario_log import _get_probs
from lib.cards import render_section_head
from lib.catalog import SIGNAL_BULLISHNESS
from lib.formatters import (
    _escape_attr,
    _escape_dollars,
    _legacy_rationale_from,
    _price_str,
    display_ticker,
)
from lib.pills import _signal_pill_html

# ── Editorial table helpers ──────────────────────────────────────────────────
# The diff tables used to render as bare st.dataframe grids: signals shown as
# uncolored text, Direction uncolored, Rationale truncated. On the one page
# about signal *changes* that dropped all the color scent the rest of the app
# relies on. These build the same rows as editorial HTML tables (reusing the
# .ep-table look) with signal pills + colour-coded direction/deltas instead.

_DIRECTION_STYLE = {
    "upgrade": ("▲", "var(--buy)"),       # ▲
    "downgrade": ("▼", "var(--caution)"),  # ▼
    "new": ("＋", "var(--accumulate)"),     # ＋
    "removed": ("−", "var(--ink-3)"),      # −
}


def _clip_rationale(text: str, limit: int = 150) -> str:
    """Cap a rationale for the diff table at a WORD boundary with an ellipsis.

    The old bare ``[:150]`` slice cut mid-word ("improved to 2.4:1. Close
    $1815… sinc") and read as a rendering bug rather than a deliberate cap.
    """
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    return f"{clipped} …"


def _sig_cell(sig: str) -> str:
    if not sig or sig == "—":
        return '<span style="color:var(--ink-3);">—</span>'
    return _signal_pill_html(sig, small=True)


def _dir_cell(direction: str) -> str:
    arrow, col = _DIRECTION_STYLE.get(direction, ("", "var(--ink-2)"))
    return f'<span style="color:{col};font-weight:600;">{arrow} {direction}</span>'


def _delta_cell(s: str) -> str:
    """Colour a pre-formatted +/- change string ('+1.3%', '-2.0pp', '—')."""
    if not s or s == "—":
        return '<span style="color:var(--ink-3);">—</span>'
    t = s.strip()
    # A zero magnitude ('+0.0') is no change — keep it neutral, not green.
    try:
        is_zero = float(t.lstrip("+-").rstrip("%pP ")) == 0.0
    except ValueError:
        is_zero = False
    cls = "flat" if is_zero else "down" if t.startswith("-") else "up" if t.startswith("+") else "flat"
    return f'<span class="{cls}">{s}</span>'


def _stat_tile(label: str, value: str, color: str = "var(--ink)") -> str:
    """One editorial stat tile mirroring the themed st.metric look, but with a
    colour-able value. st.metric forces its value to --ink, so the Upgrades /
    Downgrades / Net counts couldn't carry the green-up · red-down scent the
    rest of this page (see _DIRECTION_STYLE) already relies on."""
    return (
        '<div style="background:var(--paper-2);border:1px solid var(--rule);padding:12px 14px;">'
        '<div style="font-family:var(--mono);font-size:10px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:var(--ink-3);">{label}</div>'
        '<div style="font-family:var(--serif);font-size:1.6rem;font-weight:500;'
        f'color:{color};margin-top:2px;">{value}</div>'
        '</div>'
    )


def _editorial_table(headers: list[str], rows: list[list[str]],
                     num_cols: set[int] | None = None,
                     wide_cols: set[int] | None = None) -> str:
    """Render an editorial HTML table (reuses the .ep-table styling).

    ``num_cols`` are column indices to right-align + nowrap (the .num class).
    ``wide_cols`` are prose columns that span the full card width on phones.
    On phones the .stack-m table reflows each row into a card of label-over-
    value pairs (labels via ``data-l``), so the diff reads on one screen
    instead of swiping sideways (owner request 2026-07-17).
    """
    num_cols = num_cols or set()
    wide_cols = wide_cols or set()

    def _cls(i: int) -> str:
        parts = (["num"] if i in num_cols else []) + (["span2"] if i in wide_cols else [])
        return f' class="{" ".join(parts)}"' if parts else ""

    head = "".join(f'<th scope="col"{_cls(i)}>{h}</th>' for i, h in enumerate(headers))
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            f'<td{_cls(i)} data-l="{_escape_attr(headers[i])}">{c}</td>'
            for i, c in enumerate(r)
        ) + "</tr>"
    return (
        '<div class="tk-scroll"><table class="ep-table cmp-table stack-m">'
        f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def render_report_comparison_page(reports: dict) -> None:
    """Render the Report Comparison page.

    Args:
        reports: filtered reports dict (date-keyed).
    """
    st.title("Report Comparison")
    if len(reports) < 2:
        st.warning("Need at least 2 reports to compare.")
        st.stop()

    dates = sorted(reports.keys(), reverse=True)

    render_section_head("Multi-Day Trend", "How posture and signals shifted across a window")
    window_options = {3: "3 days", 5: "5 days", 7: "7 days", 14: "14 days", 30: "30 days"}
    window = st.select_slider(
        "Show changes over last", options=list(window_options.keys()),
        value=7, format_func=lambda x: window_options[x], key="trend_window"
    )

    sorted_dates_asc = sorted(reports.keys())
    if len(sorted_dates_asc) >= 2:
        # Find the oldest report within the window
        latest_date = sorted_dates_asc[-1]
        cutoff = (date.fromisoformat(latest_date) - timedelta(days=window)).isoformat()
        window_dates = [d for d in sorted_dates_asc if d >= cutoff]

        if len(window_dates) >= 2:
            start_date = window_dates[0]
            end_date = window_dates[-1]
            rpt_start = reports[start_date]
            rpt_end = reports[end_date]
            wl_start = rpt_start.get("watchlist", {})
            wl_end = rpt_end.get("watchlist", {})

            trend_changes = []
            upgrades = 0
            downgrades = 0
            all_tks = sorted(set(wl_start) | set(wl_end))

            for tk in all_tks:
                sig_s = wl_start.get(tk, {}).get("signal", "—")
                sig_e = wl_end.get(tk, {}).get("signal", "—")
                if sig_s == sig_e:
                    continue
                r_s = SIGNAL_BULLISHNESS.get(sig_s, 0)
                r_e = SIGNAL_BULLISHNESS.get(sig_e, 0)
                direction = "upgrade" if r_e > r_s else "downgrade"
                if sig_s == "—":
                    direction = "new"
                elif sig_e == "—":
                    direction = "removed"
                if direction == "upgrade":
                    upgrades += 1
                elif direction == "downgrade":
                    downgrades += 1

                # Price change over window
                price_s = wl_start.get(tk, {}).get("price")
                price_e = wl_end.get(tk, {}).get("price")
                price_chg = ""
                if price_s and price_e:
                    price_chg = f"{(price_e - price_s) / price_s * 100:+.1f}%"

                trend_changes.append({
                    "Ticker": tk,
                    f"Signal ({start_date})": sig_s,
                    f"Signal ({end_date})": sig_e,
                    "Direction": direction,
                    "Price Chg": price_chg or "—",
                })

            # Check for volatile tickers (changed signal more than once in window)
            volatile_tickers = []
            for tk in all_tks:
                signal_changes = 0
                prev_sig = None
                for wd in window_dates:
                    sig = reports[wd].get("watchlist", {}).get(tk, {}).get("signal")
                    if sig and sig != prev_sig and prev_sig is not None:
                        signal_changes += 1
                    if sig:
                        prev_sig = sig
                if signal_changes >= 2:
                    volatile_tickers.append((tk, signal_changes))

            # Summary stats
            net = upgrades - downgrades
            net_label = f"net {'+' if net >= 0 else ''}{net}"
            # Colour the counts like the direction cells below: green upgrades,
            # red downgrades, net by sign. A zero count stays neutral (0
            # downgrades is good news, not red; 0 upgrades isn't green).
            up_color = "var(--buy)" if upgrades > 0 else "var(--ink)"
            dn_color = "var(--caution)" if downgrades > 0 else "var(--ink)"
            net_color = ("var(--buy)" if net > 0
                         else "var(--caution)" if net < 0 else "var(--ink)")
            st.markdown(
                '<div style="display:grid;'
                'grid-template-columns:repeat(auto-fit,minmax(140px,1fr));'
                'gap:16px;margin-bottom:10px;">'
                + _stat_tile("Upgrades", str(upgrades), up_color)
                + _stat_tile("Downgrades", str(downgrades), dn_color)
                + _stat_tile("Net", net_label, net_color)
                + '</div>',
                unsafe_allow_html=True,
            )

            if volatile_tickers:
                volatile_str = ", ".join(f"**{display_ticker(tk)}** ({n}x)" for tk, n in sorted(volatile_tickers, key=lambda x: -x[1]))
                st.caption(f"Volatile signals: {volatile_str}")

            if trend_changes:
                h = ["Ticker", f"Signal ({start_date})", f"Signal ({end_date})",
                     "Direction", "Price Chg"]
                rows = [
                    [_escape_dollars(display_ticker(tc["Ticker"])), _sig_cell(tc[h[1]]), _sig_cell(tc[h[2]]),
                     _dir_cell(tc["Direction"]), _delta_cell(tc["Price Chg"])]
                    for tc in trend_changes
                ]
                st.markdown(_editorial_table(h, rows, num_cols={4}), unsafe_allow_html=True)
            else:
                st.caption(f"No signal changes in the last {window_options[window]}.")

            # Scenario probability drift over window
            st.markdown("**Scenario Drift**")

            probs_s = _get_probs(rpt_start)
            probs_e = _get_probs(rpt_end)
            sc_all = sorted(set(probs_s) | set(probs_e))

            drift_rows = []
            for sc_name in sc_all:
                p_s_str, mid_s = probs_s.get(sc_name, ("—", None))
                p_e_str, mid_e = probs_e.get(sc_name, ("—", None))
                drift_val = (mid_e - mid_s) if (mid_s is not None and mid_e is not None) else None
                drift_rows.append({
                    "Scenario": sc_name.replace("_", " ").title(),
                    f"Prob ({start_date})": p_s_str,
                    f"Prob ({end_date})": p_e_str,
                    "Drift (pp)": f"{drift_val:+.1f}" if drift_val is not None else "—",
                    "_abs_drift": abs(drift_val) if drift_val is not None else 0,
                })
            if drift_rows:
                drift_sorted = sorted(drift_rows, key=lambda r: r["_abs_drift"], reverse=True)
                h = ["Scenario", f"Prob ({start_date})", f"Prob ({end_date})", "Drift (pp)"]
                rows = [
                    [dr["Scenario"], dr[h[1]], dr[h[2]], _delta_cell(dr["Drift (pp)"])]
                    for dr in drift_sorted
                ]
                st.markdown(_editorial_table(h, rows, num_cols={1, 2, 3}), unsafe_allow_html=True)
        else:
            st.caption(f"Only 1 report in the last {window_options[window]} — need at least 2.")

    st.divider()

    render_section_head("Pairwise Comparison", "Side-by-side diff between any two dates")
    ccols = st.columns(2)
    with ccols[0]:
        date_a = st.selectbox("Report A (older)", dates[1:], index=0, key="cmp_a")
    with ccols[1]:
        date_b = st.selectbox("Report B (newer)", dates, index=0, key="cmp_b")

    if date_a == date_b:
        st.info("Select two different dates to compare.")
        st.stop()

    rpt_a = reports[date_a]
    rpt_b = reports[date_b]
    wl_a = rpt_a.get("watchlist", {})
    wl_b = rpt_b.get("watchlist", {})

    # ── Signal Changes ──
    st.subheader("Signal Changes")
    sig_changes = []
    all_tickers = sorted(set(wl_a) | set(wl_b))
    for tk in all_tickers:
        sig_a = wl_a.get(tk, {}).get("signal", "—")
        sig_b = wl_b.get(tk, {}).get("signal", "—")
        if sig_a != sig_b:
            r_a = SIGNAL_BULLISHNESS.get(sig_a, 0)
            r_b = SIGNAL_BULLISHNESS.get(sig_b, 0)
            direction = "upgrade" if r_b > r_a else "downgrade"
            if sig_a == "—":
                direction = "new"
            elif sig_b == "—":
                direction = "removed"
            sig_changes.append({
                "Ticker": tk,
                f"Signal ({date_a})": sig_a,
                f"Signal ({date_b})": sig_b,
                "Direction": direction,
                "Rationale": _clip_rationale(_legacy_rationale_from(wl_b.get(tk, {}))),
            })

    if sig_changes:
        h = ["Ticker", f"Signal ({date_a})", f"Signal ({date_b})", "Direction", "Rationale"]
        rows = [
            [_escape_dollars(display_ticker(sc["Ticker"])), _sig_cell(sc[h[1]]), _sig_cell(sc[h[2]]),
             _dir_cell(sc["Direction"]),
             f'<span style="color:var(--ink-3);">{_escape_dollars(sc["Rationale"])}</span>']
            for sc in sig_changes
        ]
        st.markdown(_editorial_table(h, rows, wide_cols={4}), unsafe_allow_html=True)
    else:
        st.caption("No signal changes between these dates.")

    # ── Probability Drift ──
    st.subheader("Scenario Probability Drift")
    probs_a = _get_probs(rpt_a)
    probs_b = _get_probs(rpt_b)
    sc_all = sorted(set(probs_a) | set(probs_b))

    prob_rows = []
    for sc_name in sc_all:
        p_a_str, mid_a = probs_a.get(sc_name, ("—", None))
        p_b_str, mid_b = probs_b.get(sc_name, ("—", None))
        drift = None
        if mid_a is not None and mid_b is not None:
            drift = mid_b - mid_a
        label = sc_name.replace("_", " ").title()
        prob_rows.append({
            "Scenario": label,
            f"Prob ({date_a})": p_a_str,
            f"Prob ({date_b})": p_b_str,
            "Drift (pp)": f"{drift:+.1f}" if drift is not None else "—",
        })
    if prob_rows:
        h = ["Scenario", f"Prob ({date_a})", f"Prob ({date_b})", "Drift (pp)"]
        rows = [
            [pr["Scenario"], pr[h[1]], pr[h[2]], _delta_cell(pr["Drift (pp)"])]
            for pr in prob_rows
        ]
        st.markdown(_editorial_table(h, rows, num_cols={1, 2, 3}), unsafe_allow_html=True)

    # ── Interconnected Stocks Diff ──
    st.subheader("Interconnected Stocks Diff")
    inter_a = {s.get("ticker", s.get("name", "?")) for s in rpt_a.get("interconnected", [])}
    inter_b = {s.get("ticker", s.get("name", "?")) for s in rpt_b.get("interconnected", [])}
    added = inter_b - inter_a
    removed = inter_a - inter_b
    if added:
        st.markdown(f"**Added:** {', '.join(sorted(added))}")
    if removed:
        st.markdown(f"**Removed:** {', '.join(sorted(removed))}")
    if not added and not removed:
        st.caption("No changes to interconnected stocks.")

    # ── Key Metric Shifts ──
    st.subheader("Key Metric Shifts")
    metric_rows = []
    for tk in all_tickers:
        da = wl_a.get(tk, {})
        db = wl_b.get(tk, {})
        price_a = da.get("price")
        price_b = db.get("price")
        rsi_a = da.get("rsi_14")
        rsi_b = db.get("rsi_14")
        vs50_a = da.get("vs_sma50_pct")
        vs50_b = db.get("vs_sma50_pct")

        # Only show tickers with meaningful changes
        if price_a is None and price_b is None:
            continue

        price_chg = ""
        if price_a and price_b:
            pct = (price_b - price_a) / price_a * 100
            price_chg = f"{pct:+.2f}%"

        rsi_chg = ""
        if rsi_a is not None and rsi_b is not None:
            rsi_chg = f"{rsi_b - rsi_a:+.1f}"

        vs50_chg = ""
        if vs50_a is not None and vs50_b is not None:
            vs50_chg = f"{vs50_b - vs50_a:+.1f}pp"

        curr_a = da.get("currency", "USD")
        curr_b = db.get("currency", "USD")
        metric_rows.append({
            "Ticker": tk,
            f"Price ({date_a})": _price_str(price_a, curr_a) if price_a else "—",
            f"Price ({date_b})": _price_str(price_b, curr_b) if price_b else "—",
            "Price Chg": price_chg or "—",
            "RSI Chg": rsi_chg or "—",
            "vs SMA50 Chg": vs50_chg or "—",
        })
    if metric_rows:
        h = ["Ticker", f"Price ({date_a})", f"Price ({date_b})",
             "Price Chg", "RSI Chg", "vs SMA50 Chg"]
        rows = [
            [_escape_dollars(display_ticker(m["Ticker"])), m[h[1]], m[h[2]], _delta_cell(m["Price Chg"]),
             _delta_cell(m["RSI Chg"]), _delta_cell(m["vs SMA50 Chg"])]
            for m in metric_rows
        ]
        st.markdown(_editorial_table(h, rows, num_cols={1, 2, 3, 4, 5}), unsafe_allow_html=True)
