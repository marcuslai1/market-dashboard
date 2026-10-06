"""Tests for the watchlist drill-down card — facts only since 2026-10-01.

MarketReport spec 2026-10-01-info-only-watchlist §8 (O6): header (no pill) →
data-health chips → levels | technicals | valuation → the Earnings drawer →
news & context. The entry-block card, the writeup verdict, the caution-source
chip, the trigger / target / invalidation / R:R plate, the R:R drawer and the
pipeline-detail drawer are gone for EVERY report date: an old report keeps
those keys in its JSON and nothing here reads them.
"""
from components.watchlist.drilldown import fact_text, render_drilldown_detail_html

#: A pre-cutover MU entry carrying every label surface the card used to render.
_MU = {
    "signal": "CAUTION",
    "caution_source": "hard_block",
    "momentum_warn": True, "momentum_warn_reasons": ["close < SMA10"],
    "price": 990.0,
    "currency": "USD",
    "chg_pct": 1.25,
    "entry_block": "BLOCKED: 5-day change +16.1% (>10% momentum chase block).",
    "entry_block_reader": "Entry blocked: up 16.1% in five sessions.",
    "reentry_zone": {"level": "$952.20", "source": "sma50"},
    "risk_reward": {
        "invalidation": 952.2, "upside_target": 1089.12,
        "ratio": 2.6, "ratio_label": "2.6:1",
        "upside_pct": 10.0, "downside_pct": 3.8,
    },
    "writeup": {
        "headline": "An 11.3% surge reclaims the 50-day.",
        "prior_period_delta_narrative": "Rating held from yesterday.",
        "what_to_do": "Wait for the move to settle.",
        "thesis_break_condition": "A close back below the 50-day.",
        "entry_block": "BLOCKED: 5-day change +16.1% (>10% momentum chase block).",
    },
    "support_legs": ["HBM sold out", "Pricing power", "Capex discipline"],
    "accumulate_gates": {"g1_signal_eligible": True, "all_mechanical_pass": False,
                         "earnings_days_until": 47},
    "rcp_state": {"current_phase": "cooling_off", "sessions_since_gap": 3},
    "avoid_source": {"publication": "Reuters", "headline_fragment": "x"},
    "news_sentiment_skew": "bullish",
    "premarket": {"phrase": "Up 2% pre-market", "pm_chg_pct": 2.0},
    "pre_earnings_band": {"earnings_date": "2026-08-01", "days_until": 7,
                          "setup_archetype": "priced_for_perfection",
                          "setup_rationale": "extended and overbought",
                          "n_priors": 4, "avg_up_pct": 11.1, "avg_down_pct": -2.8,
                          "implied_upper": 1100.0, "implied_lower": 962.3},
    "support_zones": [952.2, 900.0], "resistance_zones": [1089.12, 1150.0],
    "sma50": 940.0, "sma200": 800.0,
    "rsi_14": 61.0, "vs_sma50_pct": 5.3,
}


def _html(d=None, **kw):
    return render_drilldown_detail_html("MU", dict(_MU, **(d or {})), **kw)


# ── No label surface, on any report shape ──
def test_a_labelled_report_shows_no_label_surface():
    html = _html()
    for gone in ("sig-pill", "data-signal", "CAUTION", "ENTRY BLOCK", "Entry blocked",
                 "dd-verdict", "An 11.3% surge", "Wait for the move", "Rating held",
                 "Mechanical hard block", "Momentum warning", "dd-levels", "Trigger",
                 "Invalidation", "Target", "2.6:1", "R:R", "Risk &amp; reward",
                 "Pipeline detail", "ACCUMULATE", "Regime Change Pending", "Reuters",
                 "Thesis pillars", "HBM sold out", "Thesis break", "news · bullish",
                 "Up 2% pre-market", "Priced for perfection", "extended and overbought",
                 "$952.20"):
        assert gone not in html, gone


def test_header_is_identity_price_and_change_without_a_pill():
    html = _html()
    head = html.split('<div class="dd-head">', 1)[1].split('<div class="dd-cols', 1)[0]
    assert ">MU<" in head and ">Semis<" in head
    assert "&#36;990.00" in head and "+1.25%" in head


def test_card_order_is_levels_technicals_valuation_drawer_news():
    html = _html({"thesis_highlights": ["HBM is sold out through 2027"],
                  "valuation": {"forward_pe": 12.0}})
    order = [html.index(x) for x in ('>Levels<', '>Technicals<', '>Valuation<',
                                      'class="dd-drawer"', '>News &amp; context<')]
    assert order == sorted(order)


def test_card_has_one_neutral_rail_and_one_drawer():
    html = _html()
    assert html.startswith('<div class="dd-card">')
    assert html.count('<details class="dd-drawer">') == 1
    assert "<summary>Earnings</summary>" in html


# ── Levels ladder ──
def test_ladder_lists_levels_high_to_low_with_the_last_price():
    html = _html()
    ladder = html.split('class="dd-ladder"', 1)[1].split("</div></div><div class", 1)[0]
    labels = [s.split("</span>")[0] for s in ladder.split('class="dd-rung-lbl">')[1:]]
    # 1150 · 1089.12 · last 990 · 952.20 · SMA50 940 · 900 · SMA200 800
    assert labels == ["Resistance", "Resistance", "Last", "Support", "50-day avg",
                      "Support", "200-day avg"]
    assert "+10.0%" in ladder           # 1,089.12 is 10.0% above 990
    assert "-3.8%" in ladder            # 952.20 is 3.8% below


def test_ladder_drops_synthetic_fallback_levels():
    # AMD 10-01: two "resistances" at exactly price x 1.05 / x 1.15.
    d = {"price": 611.76, "resistance_zones": [642.35, 703.52],
         "support_zones": [496.75, 461.71], "sma50": 560.0, "sma200": 400.0}
    html = render_drilldown_detail_html("AMD", d)
    assert "Resistance" not in html
    assert "642.35" not in html and "703.52" not in html
    assert "496.75" in html


def test_ladder_is_uncoloured():
    ladder = _html().split('class="dd-ladder"', 1)[1].split('class="dd-eyebrow">Technicals', 1)[0]
    assert "style=" not in ladder and " up" not in ladder and " down" not in ladder


def test_no_levels_no_ladder():
    assert ">Levels<" not in render_drilldown_detail_html("MU", {"price": 1.0})


# ── Technicals ──
def test_technicals_print_numbers_without_zone_words():
    d = {"rsi_14": 77, "rsi_zone": "overbought", "vol_ratio": 1.42,
         "volume_signal": "confirmed", "sma50_rising": True, "days_above_sma50": 12}
    html = render_drilldown_detail_html("NVDA", d)
    assert "RSI (14-session)" in html and ">77<" in html
    assert "1.42× 10-session avg" in html
    assert ">rising<" in html and ">12<" in html
    assert "overbought" not in html and "confirmed" not in html


def test_sma50_not_rising_is_not_called_declining():
    html = render_drilldown_detail_html("NVDA", {"sma50_rising": False})
    assert ">not rising<" in html and "declining" not in html


def test_vs_cluster_rows_render_signed_values():
    d = {"vs_cluster_chg_pct": 1.21, "vs_cluster_5d_pct": -14.55, "vs_cluster_1mo_pct": 3.0}
    html = render_drilldown_detail_html("NVDA", d)
    assert "vs cluster · day" in html and "+1.21%" in html
    assert "-14.6%" in html and "+3.0%" in html


def test_vs_cluster_absent_renders_no_row():
    assert "vs cluster" not in render_drilldown_detail_html("NVDA", {})


# ── Valuation ──
def test_consensus_is_labelled_as_the_sourced_third_party_figure():
    d = {"valuation": {"forward_pe": 15.3,
                       "analyst_consensus": {"recommendation": "strong_buy",
                                             "num_analysts": 58}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Sell-side consensus (Yahoo)" in html
    assert "Strong buy · 58 analysts" in html
    assert "strong_buy" not in html


def test_consensus_none_renders_no_row():
    d = {"valuation": {"forward_pe": 15.3,
                       "analyst_consensus": {"recommendation": "none", "num_analysts": 4}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Sell-side consensus" not in html


def test_cluster_median_pe_without_a_delta_drops_the_parenthetical():
    html = render_drilldown_detail_html("CRWV", {"valuation": {"cluster_median_pe": 25.6}})
    assert "25.6x" in html
    assert "—%" not in html
    assert "(" not in html.split("25.6x")[1][:6]


def test_cluster_median_pe_with_a_delta_keeps_it():
    d = {"valuation": {"cluster_median_pe": 25.6, "pe_vs_cluster_pct": -37.0}}
    assert "25.6x (-37%)" in render_drilldown_detail_html("CRWV", d)


def test_forward_pe_names_its_fiscal_year_when_the_report_carries_one():
    d = {"valuation": {"forward_pe": 14.7, "forward_pe_fy_end": "2028-01-31"}}
    assert "14.7x · FY to Jan 2028" in render_drilldown_detail_html("NVDA", d)


def test_forward_pe_without_a_fiscal_year_is_unchanged():
    html = render_drilldown_detail_html("MU", {"valuation": {"forward_pe": 5.3}})
    assert "5.3x" in html and "FY to" not in html


def test_foreign_reporter_hides_mixed_currency_pb_and_fcf_on_old_reports():
    # 2026-10-01 shape: Yahoo's P/B divides a USD price by EUR book value.
    d = {"valuation": {"forward_pe": 30.8, "price_to_book": 1557.82, "fcf_yield_pct": 1.2}}
    html = render_drilldown_detail_html("ASML", d)
    assert "1557" not in html and "Price / Book" not in html and "FCF yield" not in html
    assert "30.8x" in html


def test_home_currency_name_keeps_pb_and_fcf():
    d = {"valuation": {"price_to_book": 24.08, "fcf_yield_pct": 0.76}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "24.08x" in html and "+0.76%" in html


def test_eps_growth_rows_say_which_is_the_estimate():
    d = {"valuation": {"eps_growth_next_fy_pct": 68.5,
                       "analyst_consensus": {"earnings_growth_pct": 127.8}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Est. EPS growth, next FY" in html and "+68.5%" in html
    assert "EPS growth, last quarter y/y" in html and "+127.8%" in html


def test_old_report_without_the_next_fy_figure_shows_no_estimate_row():
    d = {"valuation": {"analyst_consensus": {"earnings_growth_pct": 127.8}}}
    html = render_drilldown_detail_html("NVDA", d)
    assert "Est. EPS growth" not in html and "last quarter y/y" in html


def test_revenue_rows_show_the_last_quarter_then_both_estimates():
    """Pipeline 2026-10-06: analysts' sales growth this FY and next, beside the last quarter's."""
    d = {"valuation": {"revenue_growth_pct": 379.3, "revenue_growth_this_fy_pct": 106.4,
                       "revenue_growth_next_fy_pct": 14.3}}
    html = render_drilldown_detail_html("MU", d)
    q = html.index("Revenue growth, last quarter y/y")
    assert q < html.index("Est. revenue growth, this FY") < html.index("Est. revenue growth, next FY")
    assert "+379.3%" in html and "+106.4%" in html and "+14.3%" in html


def test_old_report_shows_no_revenue_estimate_rows():
    html = render_drilldown_detail_html("MU", {"valuation": {"revenue_growth_pct": 379.3}})
    assert "Est. revenue growth" not in html and "Revenue growth, last quarter y/y" in html


def test_a_missing_revenue_estimate_side_drops_alone():
    html = render_drilldown_detail_html("CBRS", {"valuation": {"revenue_growth_next_fy_pct": 232.7}})
    assert "Est. revenue growth, next FY" in html and "this FY" not in html


# ── Data-health chips ──
def test_clean_name_has_no_chips():
    assert "dd-chips" not in render_drilldown_detail_html("NVDA", {"price": 1.0})


def test_data_anomaly_keeps_the_fact_and_drops_the_label_sentence():
    d = {"data_anomaly": "price_source_conflict: fast_info prev_close $13.18 vs history "
                         "$11.73 diverge by 11.0%. Signal suppressed. | insufficient_history=40",
         "price_source_conflict": True}
    html = render_drilldown_detail_html("NVTS", d)
    assert "diverge by 11.0%." in html
    assert "insufficient history = 40" in html
    assert "Signal suppressed" not in html
    assert html.count('class="dd-chip"') == 1        # the conflict is not chipped twice


def test_sma50_warning_loses_its_entry_advice():
    d = {"sma50_warning": "SMA50 is 28% below price — pullback to SMA50 would require a "
                          "crash-level move. Use shorter-term support levels for entry "
                          "guidance instead."}
    html = render_drilldown_detail_html("AXTI", d)
    assert "SMA50 is 28% below price" in html
    assert "entry" not in html.lower().split("dd-chips", 1)[1]


def test_stale_and_freshness_notes_render_as_chips():
    d = {"stale_session": True, "stale_session_note": "No new session since 2026-09-23.",
         "data_freshness_note": "technicals through 2026-09-29: behind"}
    html = render_drilldown_detail_html("000660_KS", d)
    assert "No new session" in html and "Data freshness" in html


def test_fact_text_keeps_ordinary_words_that_contain_label_letters():
    assert fact_text("Market closed: holiday/weekend.") == "Market closed: holiday/weekend."
    assert fact_text("Signal suppressed.") == ""


# ── Earnings drawer ──
def test_earnings_drawer_states_the_next_report_date():
    d = {"accumulate_gates": {"earnings_days_until": 47}}
    html = render_drilldown_detail_html("NVDA", d, report_date="2026-10-01")
    assert "Next report." in html and "17 Nov 2026 · in 47 d" in html


def test_band_renders_reactions_without_the_archetype():
    html = _html()
    assert "Past earnings reactions" in html
    assert "Average up move." in html and "Average down move." in html
    assert "Bull case" not in html and "Bear case" not in html


def test_earnings_result_headline_lives_in_the_drawer():
    html = _html({"earnings_results_in_news": {"headline": "beat", "source": "Wire"}})
    drawer = html.split('<details class="dd-drawer">', 1)[1].split("</details>", 1)[0]
    assert '"beat"' in drawer


# ── News & context ──
def test_thesis_highlights_render_each_bullet():
    d = {"thesis_highlights": ["SK Hynix dominates HBM3E with >50% share",
                               "ADR/China delisting risk is a standing consideration"]}
    html = render_drilldown_detail_html("000660_KS", d)
    assert "Thesis highlights" in html
    assert "SK Hynix dominates HBM3E with &gt;50% share" in html
    assert "ADR/China delisting risk is a standing consideration" in html


def test_thesis_highlights_empty_or_blank_items_stay_silent():
    html = render_drilldown_detail_html("NVDA", {"thesis_highlights": ["", "  "]})
    assert "Thesis highlights" not in html and "News &amp; context" not in html


def test_thesis_highlights_escape_dollars_and_markup():
    d = {"thesis_highlights": ["~45% of MSFT $625B RPO is OpenAI-linked <risk>"]}
    html = render_drilldown_detail_html("MSFT", d)
    assert "&#36;625B" in html
    assert "<risk>" not in html and "&lt;risk&gt;" in html


# ── Recent news (spec S2: watchlist[<key>].recent_news) ──
_NEWS = [
    {"title": "Micron beats on HBM", "publisher": "Reuters", "date": "2026-10-01",
     "link": "https://example.com/mu-beat"},
    {"title": "Memory prices firm", "publisher": "Bloomberg", "date": "2026-09-30",
     "link": None},
]


def test_recent_news_renders_title_link_publisher_and_date_in_order():
    html = render_drilldown_detail_html("MU", {"recent_news": _NEWS})
    assert ">Recent news<" in html and "News &amp; context" in html
    assert ('<a class="dd-news-title" href="https://example.com/mu-beat" target="_blank" '
            'rel="noopener noreferrer">Micron beats on HBM</a>') in html
    assert "Reuters · 1 Oct" in html and "Bloomberg · 30 Sep" in html
    assert html.index("Micron beats") < html.index("Memory prices firm")


def test_recent_news_without_a_link_is_plain_text():
    html = render_drilldown_detail_html("MU", {"recent_news": [_NEWS[1]]})
    assert '<span class="dd-news-title">Memory prices firm</span>' in html
    assert "<a " not in html.split(">Recent news<", 1)[1]


def test_recent_news_absent_or_empty_renders_nothing():
    for value in (None, [], "", {"title": "x"}, [{"title": ""}, {"publisher": "Reuters"}, "x"]):
        html = render_drilldown_detail_html("D05_SI", {"recent_news": value})
        assert "Recent news" not in html and "News &amp; context" not in html, value


def test_recent_news_comes_first_in_news_and_context():
    html = render_drilldown_detail_html("MU", {
        "recent_news": _NEWS,
        "thesis_highlights": ["HBM is sold out through 2027"],
        "catalyst": {"catalyst_event": "HBM contract"},
    })
    order = [html.index(x) for x in (">Recent news<", ">Thesis highlights<", ">Catalyst<")]
    assert order == sorted(order)


def test_recent_news_is_capped():
    many = [{"title": f"Headline {i}", "publisher": "P", "date": "2026-09-30"} for i in range(9)]
    html = render_drilldown_detail_html("MU", {"recent_news": many})
    assert html.count('class="dd-news-item"') == 5


def test_recent_news_odd_date_renders_verbatim_and_missing_meta_drops():
    html = render_drilldown_detail_html("MU", {"recent_news": [
        {"title": "A", "publisher": "", "date": "yesterday"},
        {"title": "B"},
    ]})
    assert '<div class="dd-news-meta">yesterday</div>' in html
    assert html.count('class="dd-news-meta"') == 1

def test_catalyst_renders_facts_only():
    d = {"catalyst": {"catalyst_type": "contract_win", "catalyst_event": "HBM contract",
                      "catalyst_source": "Reuters", "catalyst_date": "2026-09-25",
                      "narrative_only": True,
                      "catalyst_rr": {"ratio": 3.0}, "catalyst_position_tier": {"tier": "T1"}}}
    html = render_drilldown_detail_html("MU", d)
    assert "Contract win." in html and "HBM contract" in html
    assert "Reuters" in html and "2026-09-25" in html
    for gone in ("Catalyst R:R", "Position tier", "Signal impact", "does not change the signal"):
        assert gone not in html


# ── Earnings history — quarter-on-quarter expected vs actual (2026-07-24) ──
def _eh_rows():
    """Newest-first records like the CSV export; NaN mimics empty CSV cells."""
    nan = float("nan")
    return [
        {"fiscal_label": "2026-Q3", "quarter_end": "2026-07-31",
         "eps_estimate": 2.08, "eps_actual": nan, "eps_surprise_pct": nan,
         "revenue_estimate": 91.82e9, "revenue_actual": nan,
         "revenue_yoy_pct": nan, "gross_margin_pct": nan, "operating_margin_pct": nan},
        {"fiscal_label": "2026-Q2", "quarter_end": "2026-04-30",
         "eps_estimate": 1.77, "eps_actual": 1.87, "eps_surprise_pct": 5.6,
         "revenue_estimate": nan, "revenue_actual": 81.615e9,
         "revenue_yoy_pct": 85.2, "gross_margin_pct": 74.9, "operating_margin_pct": 65.6},
        {"fiscal_label": "2026-Q1", "quarter_end": "2026-01-31",
         "eps_estimate": 1.54, "eps_actual": 1.62, "eps_surprise_pct": -3.1,
         "revenue_estimate": nan, "revenue_actual": 68.127e9,
         "revenue_yoy_pct": nan, "gross_margin_pct": nan, "operating_margin_pct": nan},
    ]


def test_earnings_history_renders_section_and_table():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert "Earnings history" in html
    assert "2026-Q2" in html and "1.87" in html
    assert "81.61B" in html


def test_earnings_history_absent_is_silent():
    assert "Earnings history" not in render_drilldown_detail_html("NVDA", {})
    assert "Earnings history" not in render_drilldown_detail_html("NVDA", {}, earnings_hist=[])


def test_earnings_history_beat_and_miss_encoding():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert 'class="eps-beat">▲ +5.6%' in html
    assert 'class="eps-miss">▼ -3.1%' in html


def test_earnings_history_coming_quarter_snapshot():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert "upcoming" in html
    assert "91.82B" in html and ">est<" in html


def test_earnings_history_missing_margins_render_dash():
    html = render_drilldown_detail_html("NVDA", {}, earnings_hist=_eh_rows())
    assert "74.9%" in html
