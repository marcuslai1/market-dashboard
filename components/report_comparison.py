"""Report Comparison page: multi-day trend + pairwise diff between two dates."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from lib.cards import render_section_head
from lib.formatters import _legacy_rationale_from

from components.scenario_log import _get_probs


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
    st.subheader("Multi-Day Trend Summary")
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

            signal_rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
            trend_changes = []
            upgrades = 0
            downgrades = 0
            all_tks = sorted(set(wl_start) | set(wl_end))

            for tk in all_tks:
                sig_s = wl_start.get(tk, {}).get("signal", "—")
                sig_e = wl_end.get(tk, {}).get("signal", "—")
                if sig_s == sig_e:
                    continue
                r_s = signal_rank.get(sig_s, 0)
                r_e = signal_rank.get(sig_e, 0)
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
            tcols = st.columns(3)
            tcols[0].metric("Upgrades", upgrades)
            tcols[1].metric("Downgrades", downgrades)
            tcols[2].metric("Net", net_label)

            if volatile_tickers:
                volatile_str = ", ".join(f"**{tk}** ({n}x)" for tk, n in sorted(volatile_tickers, key=lambda x: -x[1]))
                st.caption(f"Volatile signals: {volatile_str}")

            if trend_changes:
                st.dataframe(pd.DataFrame(trend_changes), width="stretch", hide_index=True)
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
                drift_df = pd.DataFrame(drift_rows).sort_values("_abs_drift", ascending=False)
                st.dataframe(drift_df.drop(columns=["_abs_drift"]), width="stretch", hide_index=True)
        else:
            st.caption(f"Only 1 report in the last {window_options[window]} — need at least 2.")

    st.divider()

    render_section_head("Pairwise Comparison", "Side-by-side diff between any two dates")
    st.subheader("Pairwise Comparison")
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
    signal_rank = {"BUY": 5, "ACCUMULATE": 4, "WATCH": 3, "HOLD": 2, "CAUTION": 1}
    sig_changes = []
    all_tickers = sorted(set(wl_a) | set(wl_b))
    for tk in all_tickers:
        sig_a = wl_a.get(tk, {}).get("signal", "—")
        sig_b = wl_b.get(tk, {}).get("signal", "—")
        if sig_a != sig_b:
            r_a = signal_rank.get(sig_a, 0)
            r_b = signal_rank.get(sig_b, 0)
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
                "Rationale": _legacy_rationale_from(wl_b.get(tk, {}))[:150],
            })

    if sig_changes:
        df_sc = pd.DataFrame(sig_changes)
        # Color-code direction
        st.dataframe(df_sc, width="stretch", hide_index=True)
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
        st.dataframe(pd.DataFrame(prob_rows), width="stretch", hide_index=True)

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
        pfx = "S$" if curr_b == "SGD" or curr_a == "SGD" else "$"
        metric_rows.append({
            "Ticker": tk,
            f"Price ({date_a})": f"{pfx}{price_a:,.2f}" if price_a else "—",
            f"Price ({date_b})": f"{pfx}{price_b:,.2f}" if price_b else "—",
            "Price Chg": price_chg or "—",
            "RSI Chg": rsi_chg or "—",
            "vs SMA50 Chg": vs50_chg or "—",
        })
    if metric_rows:
        st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)
