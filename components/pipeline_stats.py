"""Pipeline Stats page: cost, tokens, prompt cache, article volume."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.cards import render_section_head
from lib.data_loader import load_pipeline_stats, load_token_usage


def render_pipeline_stats_page(reports: dict) -> None:
    """Render the Pipeline Stats page.

    Args:
        reports: filtered reports dict (only used to gate the empty state).
    """
    st.title("Pipeline Statistics")
    token_df = load_token_usage()

    if token_df.empty:
        st.warning("No pipeline data available yet.")
        st.stop()

    render_section_head("Cost & Tokens", "API spend and runtime per report")

    # ── Cost & timing overview ──
    st.subheader("API Usage Over Time")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=token_df["date"], y=token_df["token_count"],
        name="Tokens", marker_color="#3b82f6",
    ))
    fig.update_layout(
        yaxis_title="Token Count", height=300,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, width="stretch")

    # Generation time
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=token_df["date"], y=token_df["generation_time_seconds"],
        mode="lines+markers", name="Gen Time",
        line=dict(color="#f59e0b", width=2),
    ))
    fig2.update_layout(
        yaxis_title="Seconds", height=250,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig2, width="stretch")

    # Summary stats
    cols = st.columns(4)
    cols[0].metric("Total Reports", len(token_df))
    cols[1].metric("Avg Tokens", f"{token_df['token_count'].mean():,.0f}")
    cols[2].metric("Avg Gen Time", f"{token_df['generation_time_seconds'].mean():.0f}s")
    cols[3].metric("Model", token_df["model_used"].iloc[-1] if len(token_df) else "—")

    # ── API Cost (authoritative — read from pipeline_stats.computed_cost_usd) ──
    # Pre-2026-05-05 rows used Sonnet+Haiku rates and overstate spend by ~10x.
    # Post-cutover rows are cache-aware DeepSeek v4 Pro. We render both ranges
    # so the step-change is visible rather than silently averaging across them.
    st.subheader("API Cost")
    ps_for_cost = load_pipeline_stats()
    cost_df = ps_for_cost.dropna(subset=["computed_cost_usd"]).sort_values("date").copy()
    if cost_df.empty:
        st.info("No cost data available — pipeline_stats.computed_cost_usd is empty.")
    else:
        cost_df["cost_usd"] = cost_df["computed_cost_usd"].astype(float)
        cost_df["cumulative_cost"] = cost_df["cost_usd"].cumsum()
        cost_df["cost_7d_avg"] = cost_df["cost_usd"].rolling(7, min_periods=1).mean()

        cutover_str = "2026-05-05"
        cutover = pd.Timestamp(cutover_str)
        post = cost_df[cost_df["date"] >= cutover]
        pre = cost_df[cost_df["date"] < cutover]

        cost_cols = st.columns(4)
        cost_cols[0].metric(
            "Total (post-cutover)",
            f"${post['cost_usd'].sum():.2f}" if not post.empty else "—",
        )
        cost_cols[1].metric(
            "Avg / run (post)",
            f"${post['cost_usd'].mean():.4f}" if not post.empty else "—",
        )
        cost_cols[2].metric(
            "Latest run",
            f"${cost_df['cost_usd'].iloc[-1]:.4f}",
        )
        cost_cols[3].metric(
            "Pre-cutover total",
            f"${pre['cost_usd'].sum():.2f}" if not pre.empty else "—",
            help="Sonnet+Haiku pricing constants — overstated ~10x. Kept for history.",
        )

        st.caption(
            "Pre-2026-05-05 rows used Sonnet+Haiku rates (overstated ~10x). "
            "Post-cutover rows reflect cache-aware DeepSeek v4 Pro spend "
            "($0.27 input miss / $0.07 input hit / $1.10 output per MTok)."
        )

        fig_cost = go.Figure()
        if not pre.empty:
            fig_cost.add_trace(go.Bar(
                x=pre["date"], y=pre["cost_usd"],
                name="Pre-cutover (Sonnet+Haiku)",
                marker_color="#6b7280", opacity=0.5,
            ))
        if not post.empty:
            fig_cost.add_trace(go.Bar(
                x=post["date"], y=post["cost_usd"],
                name="Post-cutover (DeepSeek)",
                marker_color="#3b82f6", opacity=0.85,
            ))
        fig_cost.add_trace(go.Scatter(
            x=cost_df["date"], y=cost_df["cost_7d_avg"],
            mode="lines", name="7d avg",
            line=dict(color="#f59e0b", width=2),
        ))
        # Plotly's add_vline annotation midpoint does sum(X)/len(X) which
        # blows up on pd.Timestamp; pass the date as a millisecond epoch
        # so the math works. The visual is identical.
        cutover_ms = int(cutover.timestamp() * 1000)
        fig_cost.add_vline(
            x=cutover_ms, line=dict(color="#ef4444", dash="dash", width=1),
            annotation_text="DeepSeek cutover",
            annotation_position="top right",
        )
        fig_cost.update_layout(
            yaxis_title="Cost (USD)", height=260,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_cost, width="stretch")

        # Cumulative cost
        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=cost_df["date"], y=cost_df["cumulative_cost"],
            mode="lines+markers", name="Cumulative",
            line=dict(color="#22c55e", width=2),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.1)",
        ))
        fig_cum.update_layout(
            yaxis_title="Cumulative Cost (USD)", height=200,
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_cum, width="stretch")

    # ── Prompt Cache Telemetry ──
    st.subheader("Prompt Cache")
    cache_df = ps_for_cost.copy()
    has_cache_data = (
        "cache_hit_tokens" in cache_df.columns
        and "cache_miss_tokens" in cache_df.columns
        and ((cache_df["cache_hit_tokens"].fillna(0)
              + cache_df["cache_miss_tokens"].fillna(0)) > 0).any()
    )
    if not has_cache_data:
        st.info(
            "Cache telemetry will appear after the next pipeline run. "
            "DeepSeek's automatic prefix cache is read from `response.usage` "
            "and stored in `pipeline_stats.cache_hit_tokens` / `cache_miss_tokens`."
        )
    else:
        cdf = cache_df.dropna(
            subset=["cache_hit_tokens", "cache_miss_tokens"], how="all"
        ).copy()
        cdf["cache_hit_tokens"] = cdf["cache_hit_tokens"].fillna(0)
        cdf["cache_miss_tokens"] = cdf["cache_miss_tokens"].fillna(0)
        cdf["total_input"] = cdf["cache_hit_tokens"] + cdf["cache_miss_tokens"]
        cdf = cdf[cdf["total_input"] > 0].sort_values("date")
        cdf["hit_ratio"] = cdf["cache_hit_tokens"] / cdf["total_input"]
        # Savings: hit tokens cost $0.07/MTok instead of $0.27/MTok — $0.20/MTok saved.
        cdf["savings_usd"] = cdf["cache_hit_tokens"] * (0.27 - 0.07) / 1_000_000

        latest = cdf.iloc[-1]
        avg_ratio = cdf["hit_ratio"].mean()
        total_savings = cdf["savings_usd"].sum()

        cc_cols = st.columns(4)
        cc_cols[0].metric("Latest hit ratio", f"{latest['hit_ratio']:.1%}")
        cc_cols[1].metric("Avg hit ratio", f"{avg_ratio:.1%}")
        cc_cols[2].metric(
            "Latest hit tokens",
            f"{int(latest['cache_hit_tokens']):,}",
            help="Cached input tokens billed at $0.07/MTok instead of $0.27/MTok.",
        )
        cc_cols[3].metric(
            "Cumulative savings",
            f"${total_savings:.4f}",
            help="Versus billing all input as cache miss ($0.27/MTok).",
        )

        fig_cache = go.Figure()
        fig_cache.add_trace(go.Bar(
            x=cdf["date"], y=cdf["cache_hit_tokens"],
            name="Cache hit", marker_color="#22c55e",
        ))
        fig_cache.add_trace(go.Bar(
            x=cdf["date"], y=cdf["cache_miss_tokens"],
            name="Cache miss", marker_color="#ef4444",
        ))
        fig_cache.update_layout(
            barmode="stack",
            yaxis_title="Input tokens",
            height=240,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_cache, width="stretch")

        st.caption(
            "If hit ratio sits near 0%, the user prompt's first dynamic block "
            "is breaking the prefix immediately — reorder static blocks "
            "(catalysts JSON, portfolio_count_directive, field-contracts, "
            "crisis_block) above the data_json block to extend the cacheable "
            "prefix. Savings figures assume a flat $0.20/MTok delta."
        )

    render_section_head("Pipeline Volume", "Articles ingested and prompt size")

    # ── Articles Fed to Prompt ──
    st.subheader("Articles Fed to Prompt")
    ps_df = load_pipeline_stats()
    if ps_df.empty:
        st.info("No pipeline stats recorded yet.")
    else:
        # Article count metrics
        art_cols = st.columns(4)
        art_cols[0].metric("Avg Tavily Fetched", f"{ps_df['articles_fetched'].mean():.0f}")
        art_cols[1].metric("Avg Tavily After Filter", f"{ps_df['articles_after_filter'].mean():.0f}")
        art_cols[2].metric("Avg Blocked", f"{ps_df['articles_blocked'].mean():.0f}")
        # yfinance may be null for older rows
        yf_col = ps_df["yfinance_articles"].dropna()
        art_cols[3].metric("Avg yFinance", f"{yf_col.mean():.0f}" if len(yf_col) else "—")

        # Article count chart — stacked by source
        fig_art = go.Figure()
        fig_art.add_trace(go.Bar(
            x=ps_df["date"], y=ps_df["articles_after_filter"],
            name="Tavily", marker_color="#3b82f6",
        ))
        if ps_df["yfinance_articles"].notna().any():
            fig_art.add_trace(go.Bar(
                x=ps_df["date"], y=ps_df["yfinance_articles"],
                name="yFinance", marker_color="#f59e0b",
            ))
        fig_art.update_layout(
            barmode="stack",
            yaxis_title="Article Count", height=300,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_art, width="stretch")

        # ── Prompt Size Breakdown ──
        has_breakdown = ps_df["total_prompt_chars"].notna().any()
        if has_breakdown:
            st.subheader("Prompt Size Breakdown")
            # Latest run metrics
            latest = ps_df.dropna(subset=["total_prompt_chars"]).iloc[-1] if has_breakdown else None
            if latest is not None:
                pb_cols = st.columns(5)
                pb_cols[0].metric("System Prompt", f"{latest['system_prompt_chars']:,.0f} chars")
                pb_cols[1].metric("Watchlist Data", f"{latest['watchlist_data_chars']:,.0f} chars")
                pb_cols[2].metric("yFinance News", f"{latest['yfinance_chars']:,.0f} chars")
                pb_cols[3].metric("Tavily News", f"{latest['tavily_chars']:,.0f} chars")
                pb_cols[4].metric("Memory", f"{latest['memory_chars']:,.0f} chars")

            # Stacked area chart over time
            breakdown_df = ps_df.dropna(subset=["total_prompt_chars"])
            if len(breakdown_df) > 0:
                fig_pb = go.Figure()
                components = [
                    ("system_prompt_chars", "System Prompt", "#6366f1"),
                    ("watchlist_data_chars", "Watchlist Data", "#3b82f6"),
                    ("yfinance_chars", "yFinance News", "#f59e0b"),
                    ("tavily_chars", "Tavily News", "#22c55e"),
                    ("memory_chars", "Memory", "#ec4899"),
                ]
                for col, name, color in components:
                    fig_pb.add_trace(go.Bar(
                        x=breakdown_df["date"], y=breakdown_df[col],
                        name=name, marker_color=color,
                    ))
                fig_pb.update_layout(
                    barmode="stack",
                    yaxis_title="Chars", height=300,
                    margin=dict(l=0, r=0, t=30, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_pb, width="stretch")
