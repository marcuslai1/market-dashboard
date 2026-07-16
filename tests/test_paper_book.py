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
def test_rebase_to_100_at_first_row():
    out = rebase_curves(select_policy(_nav_df(), {}))
    assert list(out.columns) == ["date", "Paper book", "SPY", "SOXX"]
    assert out["Paper book"].iloc[0] == 100.0
    assert round(out["Paper book"].iloc[1], 2) == 100.45
    assert round(out["SPY"].iloc[1], 1) == 102.0
    assert round(out["SOXX"].iloc[1], 1) == 99.5


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
    assert "trail" in html and "+1.1%" in html and "18 stops" in html
    assert "no-stop" in html and "+4.0%" in html and "0 stops" in html
    assert "<b>wide</b>" in html and "+8.3%" in html and "8 stops" in html
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
    assert "13 stops" in html
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
            "Paper book": [100.0, 103.5], "SPY": [100.0, 106.3]}
    if with_soxx:
        data["SOXX"] = [100.0, 160.0]
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
    assert "trail" in joined and "18 stops" in joined   # advisory lanes line
