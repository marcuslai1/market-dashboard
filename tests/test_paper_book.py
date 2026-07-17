"""Paper-book band reducers + renderers (spec 2026-07-05-paper-book-band)."""
import pandas as pd

from components.paper_book import rebase_curves, select_policy, verdict_bits


def _nav_df(policy="v1_flat10"):
    return pd.DataFrame({
        "policy_id": [policy, policy],
        "date": ["2026-04-19", "2026-04-20"],
        "nav_units": [1_000_000, 1_004_500],
        "cash_units": [1_000_000, 900_000],
        "n_positions": [0, 1],
        "spy_close": [500.0, 510.0],
        "soxx_close": [200.0, 199.0],
    })


# ── select_policy ──
def test_select_policy_prefers_block_policy_id():
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("trim_on_caution")])
    out = select_policy(df, {"policy_id": "trim_on_caution"})
    assert set(out["policy_id"]) == {"trim_on_caution"}
    assert len(out) == 2


def test_select_policy_sole_id_without_block():
    out = select_policy(_nav_df(), {})
    assert len(out) == 2


def test_select_policy_multi_id_without_block_prefers_v1_flat10():
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("v1_trail10")])
    out = select_policy(df, {})            # block-less report: headline book wins
    assert set(out["policy_id"]) == {"v1_flat10"}
    assert len(out) == 2


def test_select_policy_multi_id_without_block_or_default_is_empty():
    df = pd.concat([_nav_df("v1_trail10"), _nav_df("v1_nostop10")])
    assert select_policy(df, {}).empty     # never mix variants into one curve


def test_select_policy_empty_input():
    assert select_policy(pd.DataFrame(), {}).empty
    assert select_policy(None, {"policy_id": "v1_flat10"}).empty


# ── rebase_curves ──
def test_rebase_to_notional_at_first_row():
    # Display notional is $10,000 (2026-07-17 — dollar pot instead of index-100)
    out = rebase_curves(select_policy(_nav_df(), {}))
    assert list(out.columns) == ["date", "Paper book", "SPY", "SOXX"]
    assert out["Paper book"].iloc[0] == 10_000.0
    assert round(out["Paper book"].iloc[1], 2) == 10_045.0
    assert round(out["SPY"].iloc[1], 1) == 10_200.0
    assert round(out["SOXX"].iloc[1], 1) == 9_950.0


def test_rebase_skips_series_with_no_valid_base():
    df = _nav_df()
    df["soxx_close"] = None
    out = rebase_curves(df)
    assert "SOXX" not in out.columns
    assert "Paper book" in out.columns


def test_rebase_empty_input():
    assert rebase_curves(pd.DataFrame()).empty
    assert rebase_curves(None).empty


# ── verdict_bits ──
def test_verdict_trailing():
    text, tone = verdict_bits({"nav_return_pct": 4.2, "spy_return_pct": 6.1,
                               "inception": "2026-04-19"})
    assert "+4.2%" in text and "+6.1%" in text and "2026-04-19" in text
    # dollar-pot framing (2026-07-17): $10,000 start and both endpoints
    assert "$10,000" in text and "$10,420" in text and "$10,610" in text
    assert "trailing" in text
    assert tone == "neg"


def test_verdict_leading():
    text, tone = verdict_bits({"nav_return_pct": 8.0, "spy_return_pct": 6.1})
    assert "leading" in text
    assert tone == "pos"


def test_verdict_seeded_when_returns_none():
    text, tone = verdict_bits({"nav_return_pct": None, "spy_return_pct": None,
                               "inception": "2026-04-19"})
    assert "seeded" in text
    assert tone == ""


# ── _variants_html ──
from components.paper_book import _variants_html

_VARIANTS = [
    {"policy_id": "v1_trail10", "nav_return_pct": 1.05, "cash_pct": 42.48,
     "n_positions": 7, "stops": 18},
    {"policy_id": "v1_nostop10", "nav_return_pct": 3.97, "cash_pct": 0.0,
     "n_positions": 12, "stops": 0},
    {"policy_id": "v1_wide10", "nav_return_pct": 8.31, "cash_pct": 9.55,
     "n_positions": 9, "stops": 8},
]


def test_variants_html_renders_advisory_lanes():
    html = _variants_html({"variants": _VARIANTS})
    assert 'class="pb-variants"' in html
    assert "trail" in html and "+1.1%" in html and "18 stop-outs" in html
    assert "no-stop" in html and "+4.0%" in html and "0 stop-outs" in html
    assert "<b>wide</b>" in html and "+8.3%" in html and "8 stop-outs" in html
    assert "v1_wide10" not in html            # labeled, not raw policy_id
    assert "verdict" not in html.lower()      # framing lives in the banner


def test_variants_html_skips_malformed_and_escapes_unknown_ids():
    html = _variants_html({"variants": [
        "not-a-dict", {}, {"policy_id": "v1_x", "nav_return_pct": None},
        {"policy_id": "<i>x</i>", "nav_return_pct": 2.0},
    ]})
    assert "<i>x</i>" not in html             # unknown id escaped, not raw
    assert "&lt;i&gt;x&lt;/i&gt;" in html
    assert "+2.0%" in html


def test_variants_html_empty():
    assert _variants_html(None) == ""
    assert _variants_html({}) == ""
    assert _variants_html({"variants": []}) == ""
    assert _variants_html({"variants": [{"policy_id": "v1_trail10"}]}) == ""


# ── UX review 2026-07-07: the headline book's own stop rule leads the line ──
def test_variants_html_leads_with_labeled_headline_lane():
    block = {"policy_id": "v1_flat10", "nav_return_pct": 3.52,
             "trade_counts": {"stop": 13}, "variants": _VARIANTS}
    html = _variants_html(block)
    assert "<b>flat</b> +3.5%" in html
    assert "13 stop-outs" in html
    assert "headline" in html                 # the lane is named as the book's own
    assert html.index("flat") < html.index("trail")


def test_variants_html_headline_alone_renders_nothing():
    # No variant lanes -> no line; the headline number already leads the band.
    block = {"policy_id": "v1_flat10", "nav_return_pct": 3.52,
             "trade_counts": {"stop": 13}, "variants": []}
    assert _variants_html(block) == ""


# ── UX review 2026-07-07: the chart's job is book-vs-SPY; SOXX off-chart ──
def _rebased(with_soxx=True):
    data = {"date": pd.to_datetime(["2026-04-19", "2026-04-20"]),
            "Paper book": [10_000.0, 10_350.0], "SPY": [10_000.0, 10_630.0]}
    if with_soxx:
        data["SOXX"] = [10_000.0, 16_000.0]
    return pd.DataFrame(data)


def test_nav_fig_plots_book_and_spy_only():
    from components.paper_book import _nav_fig
    names = [tr.name for tr in _nav_fig(_rebased()).data]
    assert names == ["Paper book", "SPY"]


def test_soxx_note_names_offchart_return():
    from components.paper_book import _soxx_note_html
    note = _soxx_note_html(_rebased())
    assert "SOXX" in note and "+60.0%" in note
    assert _soxx_note_html(_rebased(with_soxx=False)) == ""


# ── advisory ext-exit lanes (2026-07-17 sizing-research addendum) ──
def _adv_nav_df():
    frames = [_nav_df("v1_flat10")]
    for pid, units in (("v1_tc_ext_100", [1_000_000, 1_010_000]),
                       ("v1_tc_ext_100_b30", [1_000_000, 1_040_000])):
        f = _nav_df(pid)
        f["nav_units"] = units
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def test_advisory_curves_rebased_per_lane():
    from components.paper_book import advisory_curves
    out = advisory_curves(_adv_nav_df())
    assert list(out.columns) == ["date", "ext-exit 10/5", "ext-exit 30/15"]
    assert out["ext-exit 10/5"].iloc[0] == 10_000.0
    assert round(out["ext-exit 10/5"].iloc[1], 1) == 10_100.0
    assert round(out["ext-exit 30/15"].iloc[1], 1) == 10_400.0


def test_advisory_curves_skip_missing_lanes():
    from components.paper_book import advisory_curves
    # only the 10/5 lane in the CSV (b30 seeds on its first pipeline run)
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("v1_tc_ext_100")],
                   ignore_index=True)
    out = advisory_curves(df)
    assert list(out.columns) == ["date", "ext-exit 10/5"]
    # no advisory lanes at all → empty, band renders as before
    assert advisory_curves(_nav_df("v1_flat10")).empty
    assert advisory_curves(None).empty


def test_nav_fig_advisory_lanes_dashed_and_subordinate():
    from components.paper_book import _nav_fig, advisory_curves
    fig = _nav_fig(_rebased(), advisory_curves(_adv_nav_df()))
    by_name = {tr.name: tr for tr in fig.data}
    assert set(by_name) == {"Paper book", "SPY",
                            "ext-exit 10/5", "ext-exit 30/15"}
    for lane in ("ext-exit 10/5", "ext-exit 30/15"):
        assert by_name[lane].line.dash == "dash"
        assert by_name[lane].line.width < by_name["Paper book"].line.width


def test_advisory_note_names_lanes_and_caveat():
    from components.paper_book import _advisory_note_html, advisory_curves
    note = _advisory_note_html(advisory_curves(_adv_nav_df()))
    assert "ext-exit 10/5" in note and "ext-exit 30/15" in note
    assert "one regime" in note
    assert _advisory_note_html(pd.DataFrame()) == ""


# ── renderers ──
from components.paper_book import _positions_table_html, _stats_html, _verdict_html

_BLOCK = {
    "policy_id": "v1_flat10", "inception": "2026-04-19", "as_of": "2026-07-03",
    "nav_pct": 104.2, "cash_pct": 38.0, "n_positions": 5,
    "nav_return_pct": 4.2, "spy_return_pct": 6.1, "soxx_return_pct": 9.9,
    "trade_counts": {"buy_signal": 12, "stop": 3},
    "positions": [
        # pipeline emits drawdown as a POSITIVE magnitude (paper_portfolio.py)
        {"ticker": "NVDA", "weight_pct": 10.4, "stop": 101.5, "tranches": 1,
         "max_dd_pct": 8.3},
        {"ticker": "000660_KS", "weight_pct": 9.1, "stop": None, "tranches": 2,
         "max_dd_pct": 2.0},
    ],
    "trades_today": [{"date": "2026-07-03", "ticker": "AMD", "side": "buy",
                      "reason": "buy_signal"}],
    "banner": "Paper measurement only — single-regime window; "
              "not a performance verdict.",
}


def test_verdict_html_escapes_and_tones():
    html = _verdict_html(_BLOCK)
    assert "trailing the benchmark" in html
    assert 'class="pb-verdict"' in html


def test_stats_html_carries_cash_positions_and_reasons():
    html = _stats_html(_BLOCK)
    assert "38" in html and "5" in html
    assert "12" in html and "3" in html          # trade counts by reason


def test_positions_table_lists_rows_and_skips_malformed():
    hostile = {"ticker": "AMD", "weight_pct": 5.0, "stop": None,
               "tranches": "<b>2</b>", "max_dd_pct": None}
    weight_none = {"ticker": "INTC", "weight_pct": None, "stop": 30.0,
                   "tranches": "1", "max_dd_pct": 2.0}
    html = _positions_table_html(_BLOCK["positions"] + [hostile, weight_none,
                                                        "not-a-dict", {}])
    assert "NVDA" in html
    assert "000660.KS" in html                    # display_ticker conversion
    assert html.count("<tr>") >= 4                # malformed entries skipped
    assert "<b>2</b>" not in html                 # tranches escaped, not raw
    assert "&lt;b&gt;2&lt;/b&gt;" in html
    assert "INTC" in html                         # weight_pct None row renders
    assert "—</td>" in html                       # ...with em-dash, not a crash
    assert "-8.3%" in html                        # drawdown signed as a decline
    assert "+8.3%" not in html                    # ...never rendered as a gain


def test_positions_legend_explains_every_column():
    from components.paper_book import _POSITIONS_LEGEND
    for term in ("Weight", "Stop", "Tranches", "Max drawdown"):
        assert term in _POSITIONS_LEGEND
    assert "not the current profit" in _POSITIONS_LEGEND


def test_render_paper_book_absent_renders_nothing():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.paper_book import render_paper_book
        render_paper_book({}, pd.DataFrame())

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    assert not at.markdown                        # band skipped entirely


def test_render_paper_book_csv_only_renders_curve_only():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.paper_book import render_paper_book
        nav = pd.DataFrame({
            "policy_id": ["v1_flat10", "v1_flat10"],
            "date": ["2026-04-19", "2026-04-20"],
            "nav_units": [1_000_000, 1_004_500],
            "cash_units": [1_000_000, 900_000],
            "n_positions": [0, 1],
            "spy_close": [500.0, 510.0],
            "soxx_close": [200.0, 199.0],
        })
        render_paper_book({}, nav)   # report predates the block

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "Paper book" in joined                 # section head + curve…
    assert "benchmark" not in joined              # …but no verdict line
    assert "Paper measurement" not in joined      # …and no invented banner


def test_render_paper_book_block_only_renders_summary():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.paper_book import render_paper_book
        block = {"policy_id": "v1_flat10", "inception": "2026-04-19",
                 "cash_pct": 38.0, "n_positions": 1, "nav_return_pct": 4.2,
                 "spy_return_pct": 6.1, "trade_counts": {},
                 "positions": [], "trades_today": [],
                 "variants": [{"policy_id": "v1_trail10",
                               "nav_return_pct": 1.05, "stops": 18}],
                 "banner": "Paper measurement only."}
        render_paper_book({"paper_portfolio": block}, pd.DataFrame())

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "Paper book" in joined
    assert "trailing the benchmark" in joined
    assert "Paper measurement only." in joined
    assert "trail" in joined and "18 stop-outs" in joined   # advisory lanes line


# ── trade history (spec 2026-07-17-paper-trade-history) ──
from components.paper_book import (
    _drawer_title,
    _history_verdict_html,
    _trade_history_html,
    select_trades,
    trade_dollars_factor,
    trade_rows,
)


def _trades_df(policy="v1_flat10"):
    return pd.DataFrame({
        "policy_id": [policy] * 3,
        "ticker": ["AMD", "000660_KS", "NVDA"],
        "entry_date": ["2026-04-20", "2026-05-02", "2026-04-22"],
        "avg_entry_price": [203.43, 210000.0, 174.40],
        "tranches": [1, 1, 2],
        "exit_date": ["2026-05-15", "2026-06-10", "2026-06-03"],
        "exit_price": [188.10, 189000.0, 216.10],
        "exit_reason": ["stop", "delist_exit", "avoid_exit"],
        "pnl_pct": [-7.5, -10.0, 23.9],
        "pnl_units": [-7500, -10000, 24100],
    })


# ── select_trades ──
def test_select_trades_prefers_block_policy_and_sorts_newest_first():
    df = pd.concat([_trades_df("v1_flat10"), _trades_df("v1_trail10")])
    out = select_trades(df, {"policy_id": "v1_flat10"})
    assert set(out["policy_id"]) == {"v1_flat10"}
    assert list(out["ticker"]) == ["000660_KS", "NVDA", "AMD"]  # newest exit first


def test_select_trades_policy_fallbacks_match_nav_rules():
    assert len(select_trades(_trades_df("v1_trail10"), {})) == 3   # sole id
    multi = pd.concat([_trades_df("v1_trail10"), _trades_df("v1_nostop10")])
    assert select_trades(multi, {}).empty          # never blend variants
    both = pd.concat([_trades_df("v1_flat10"), _trades_df("v1_trail10")])
    out = select_trades(both, {})                  # headline book wins
    assert set(out["policy_id"]) == {"v1_flat10"}
    assert select_trades(pd.DataFrame(), {}).empty
    assert select_trades(None, {}).empty


# ── trade_dollars_factor ──
def test_trade_dollars_factor_matches_nav_rebase():
    assert trade_dollars_factor(_nav_df(), {}) == 10_000.0 / 1_000_000
    assert trade_dollars_factor(pd.DataFrame(), {}) is None
    assert trade_dollars_factor(None, {}) is None


# ── trade_rows ──
def test_trade_rows_formats_dates_prices_and_dollars():
    rows = trade_rows(select_trades(_trades_df(), {}), factor=0.01,
                      as_of_year=2026)
    assert [r["ticker"] for r in rows] == ["000660.KS", "NVDA", "AMD"]
    nvda = rows[1]
    # prices bare (no $) — non-USD listings would mislabel the currency
    assert nvda["bought"].startswith("Apr 22 @ 174.40")
    assert "2 buys" in nvda["bought"]              # multi-tranche suffix
    assert "avg" in nvda["bought"]
    assert nvda["sold"] == "Jun 3 @ 216.10"
    assert nvda["why"] == "AVOID exit"
    assert nvda["dollars"] == 241.0
    assert nvda["pct"] == 23.9
    amd = rows[2]
    assert "buys" not in amd["bought"]             # single tranche, no suffix
    assert amd["why"] == "stop-out (auto-sold)"
    assert rows[0]["why"] == "delisted"
    # live pipeline vocabulary (2026-07-17 export): caution_exit is labeled too
    from components.paper_book import _EXIT_LABELS
    assert _EXIT_LABELS["caution_exit"] == "CAUTION exit"
    assert rows[0]["dollars"] == -100.0


def test_trade_rows_year_shown_when_it_differs():
    df = _trades_df()
    rows = trade_rows(select_trades(df, {}), factor=0.01, as_of_year=2027)
    assert any("2026" in r["bought"] for r in rows)


def test_trade_rows_skips_malformed_and_survives_missing_fields():
    df = _trades_df()
    df.loc[0, "ticker"] = None                     # no ticker → skipped
    df.loc[1, "pnl_pct"] = None
    df.loc[1, "pnl_units"] = None                  # no P&L at all → skipped
    df.loc[2, "entry_date"] = "not-a-date"         # bad date → em-dash, kept
    rows = trade_rows(select_trades(df, {}), factor=0.01, as_of_year=2026)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"
    assert rows[0]["bought"].startswith("—")


def test_trade_rows_percent_only_without_factor():
    rows = trade_rows(select_trades(_trades_df(), {}), factor=None,
                      as_of_year=2026)
    assert all(r["dollars"] is None for r in rows)
    assert rows[1]["pct"] == 23.9


# ── _trade_history_html / _history_verdict_html ──
def test_trade_history_html_renders_table():
    rows = trade_rows(select_trades(_trades_df(), {}), factor=0.01,
                      as_of_year=2026)
    html = _trade_history_html(rows)
    for head in ("Name", "Bought", "Sold", "Why sold", "Profit"):
        assert head in html
    assert "NVDA" in html and "000660.KS" in html
    assert "+&#36;241 (+23.9%)" in html            # dollars escaped, not LaTeX
    assert "stop-out (auto-sold)" in html
    assert _trade_history_html([]) == ""


def test_history_verdict_counts_and_pot_total():
    rows = trade_rows(select_trades(_trades_df(), {}), factor=0.01,
                      as_of_year=2026)
    html = _history_verdict_html(rows)
    assert "3 completed trades" in html
    assert "1 made money" in html and "2 lost" in html
    assert "&#36;66" in html                       # -75 + 241 - 100 = +66
    assert _history_verdict_html([]) == ""


def test_history_verdict_omits_pot_total_without_dollars():
    rows = trade_rows(select_trades(_trades_df(), {}), factor=None,
                      as_of_year=2026)
    html = _history_verdict_html(rows)
    assert "1 made money" in html
    assert "&#36;" not in html                     # no invented dollars


def test_drawer_title_switches_only_with_history():
    assert _drawer_title(True) == "Positions & trade history"
    assert _drawer_title(False) == "Positions & today's trades"


# ── open positions: optional P&L-so-far columns ──
def test_positions_table_gains_pnl_columns_when_exported():
    positions = [
        {"ticker": "NVDA", "weight_pct": 10.4, "stop": 101.5, "tranches": 1,
         "max_dd_pct": 8.3, "entry_date": "2026-05-02", "pnl_pct": 6.3,
         "pnl_units": 6300},
        {"ticker": "AMD", "weight_pct": 5.0, "stop": None, "tranches": 1,
         "max_dd_pct": None},                      # no new fields → em-dashes
    ]
    html = _positions_table_html(positions, factor=0.01, as_of_year=2026)
    assert "Bought" in html and "P&amp;L so far" in html
    assert "May 2" in html
    assert "+&#36;63 (+6.3%)" in html
    assert html.count("—") >= 2                    # AMD's new cells stay honest


def test_positions_table_unchanged_without_new_fields():
    html = _positions_table_html(_BLOCK["positions"], factor=0.01,
                                 as_of_year=2026)
    assert html == _positions_table_html(_BLOCK["positions"])
    assert "P&amp;L" not in html                   # byte-identical absence tier


# ── render integration ──
def test_render_paper_book_shows_history_in_drawer():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.paper_book import render_paper_book
        nav = pd.DataFrame({
            "policy_id": ["v1_flat10", "v1_flat10"],
            "date": ["2026-04-19", "2026-04-20"],
            "nav_units": [1_000_000, 1_004_500],
            "cash_units": [1_000_000, 900_000],
            "n_positions": [0, 1],
            "spy_close": [500.0, 510.0],
            "soxx_close": [200.0, 199.0],
        })
        trades = pd.DataFrame({
            "policy_id": ["v1_flat10"],
            "ticker": ["NVDA"],
            "entry_date": ["2026-04-22"],
            "avg_entry_price": [174.40],
            "tranches": [2],
            "exit_date": ["2026-06-03"],
            "exit_price": [216.10],
            "exit_reason": ["stop"],
            "pnl_pct": [23.9],
            "pnl_units": [24_100],
        })
        block = {"policy_id": "v1_flat10", "inception": "2026-04-19",
                 "as_of": "2026-07-17", "cash_pct": 38.0, "n_positions": 0,
                 "nav_return_pct": 4.2, "spy_return_pct": 6.1,
                 "trade_counts": {"stop": 1}, "positions": [],
                 "trades_today": [], "variants": [], "banner": "Paper only."}
        render_paper_book({"paper_portfolio": block}, nav, trades)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "1 completed trade" in joined
    assert "NVDA" in joined and "stop-out (auto-sold)" in joined
    assert "+&#36;241 (+23.9%)" in joined          # units × the NAV rebase factor


def test_render_paper_book_history_without_block_still_shows():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.paper_book import render_paper_book
        trades = pd.DataFrame({
            "policy_id": ["v1_flat10"],
            "ticker": ["NVDA"],
            "entry_date": ["2026-04-22"],
            "avg_entry_price": [174.40],
            "tranches": [1],
            "exit_date": ["2026-06-03"],
            "exit_price": [216.10],
            "exit_reason": ["stop"],
            "pnl_pct": [23.9],
            "pnl_units": [24_100],
        })
        render_paper_book({}, pd.DataFrame(), trades)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "NVDA" in joined
    assert "+23.9%" in joined                      # percent-only: no NAV factor
    assert "&#36;" not in joined or "+&#36;241" not in joined


def test_render_paper_book_without_trades_is_unchanged():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.paper_book import render_paper_book
        block = {"policy_id": "v1_flat10", "inception": "2026-04-19",
                 "cash_pct": 38.0, "n_positions": 1, "nav_return_pct": 4.2,
                 "spy_return_pct": 6.1, "trade_counts": {},
                 "positions": [{"ticker": "NVDA", "weight_pct": 10.0,
                                "stop": 101.5, "tranches": 1,
                                "max_dd_pct": 8.3}],
                 "trades_today": [], "variants": [], "banner": "Paper only."}
        render_paper_book({"paper_portfolio": block}, pd.DataFrame(), None)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "completed trade" not in joined         # no history, no verdict line
    assert "P&amp;L so far" not in joined          # positions table as today
