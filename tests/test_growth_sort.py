"""The Watchlist's experimental growth sort (owner 2026-10-06; MarketReport PIPELINE_FEATURES §125).

Default order unchanged; the control sorts by two-year or latest-quarter sales growth; the
sorted view shows a growth line per row; numbers only — no rank, no growth type, no colour.
"""
import glob
import json
import re

import pytest
from streamlit.testing.v1 import AppTest

from components.watchlist.growth import (
    ORDER_CLUSTERS,
    ORDER_QUARTER,
    ORDER_TWO_YEAR,
    ORDERS,
    SORT_FIELD,
    growth_by_key,
    growth_line_html,
    sorted_footer_html,
    sorted_grid_html,
    sorted_rows,
    sortline_html,
)
from components.watchlist.row import render_ticker_details_html

GROWTH = {
    "_meta": {"as_of": "2026-10-06", "aliases": {"SKHY": "000660.KS"}},
    "000660.KS": {"avg2y": 133.9, "latest_q": 256.8, "latest_quarter_end": "2026-06-30",
                  "om_ya": 41.4, "om_now": 76.3},
    "AXTI": {"avg2y": 128.4, "latest_q": 164.8, "latest_quarter_end": "2026-06-30",
             "om_ya": -37.5, "om_now": 21.9},
    "NOK": {"avg2y": 5.6, "latest_q": 8.4, "latest_quarter_end": "2026-06-30",
            "om_ya": 3.3, "om_now": -1.0},
    "MU": {"avg2y": 54.0, "latest_q": 346.0, "latest_quarter_end": "2026-05-31",
           "om_ya": 20.0, "om_now": 60.0},
}


def _row(tk, d, **kw):
    return f"<row {tk}|{kw.get('growth_html', '')}>"


def test_orders_default_to_clusters_and_each_sort_names_its_figure():
    assert ORDERS[0] == ORDER_CLUSTERS
    assert SORT_FIELD == {ORDER_TWO_YEAR: "avg2y", ORDER_QUARTER: "latest_q"}
    assert ORDER_CLUSTERS not in SORT_FIELD


def test_growth_by_key_uses_report_keys_and_aliases():
    m = growth_by_key(GROWTH)
    assert m["000660_KS"] is m["SKHY"]
    assert "000660.KS" not in m and "_meta" not in m
    assert growth_by_key(None) == {} and growth_by_key([]) == {}


def test_sorted_rows_fastest_first_missing_last_a_to_z():
    wl = {"NOK": {}, "AXTI": {}, "ZZZ": {}, "AAA": {}, "000660_KS": {}, "MU": {}}
    m = growth_by_key(GROWTH)
    assert [t for t, _ in sorted_rows(wl, m, "avg2y")] == ["000660_KS", "AXTI", "MU", "NOK", "AAA", "ZZZ"]
    assert [t for t, _ in sorted_rows(wl, m, "latest_q")] == ["MU", "000660_KS", "AXTI", "NOK", "AAA", "ZZZ"]


def test_sorted_rows_ignore_nan_and_bool():
    m = {"A": {"avg2y": float("nan")}, "B": {"avg2y": True}, "C": {"avg2y": 1.0}}
    assert [t for t, _ in sorted_rows({"A": {}, "B": {}, "C": {}}, m, "avg2y")] == ["C", "A", "B"]


def test_growth_line_shows_both_figures_the_quarter_and_the_margin_swing():
    line = growth_line_html(GROWTH["AXTI"], "avg2y")
    assert line.startswith('<div class="tk-growth">')
    assert "2-year average <b>+128%</b> a year" in line
    assert "latest quarter +165% (quarter to Jun 2026)" in line
    assert "operating margin -38% → 22%" in line
    q = growth_line_html(GROWTH["AXTI"], "latest_q")
    assert "latest quarter <b>+165%</b>" in q and "<b>+128%</b>" not in q


def test_growth_line_without_figures_says_so():
    assert "no figures on file" in growth_line_html(None, "avg2y")
    assert "no figures on file" in growth_line_html({"latest_quarter_end": "2026-06-30"}, "avg2y")


def test_sortline_states_basis_age_and_that_it_is_not_a_pick_list():
    s = sortline_html("avg2y", "2026-10-06")
    assert 'class="tk-sortline tk-sortline-exp"' in s
    for phrase in ("Experimental", "analysts' forecast", "names without a figure last",
                   "not the share price", "not a pick list", "figures as of 6 Oct 2026"):
        assert phrase in s, phrase
    assert "quarters end on different dates" in sortline_html("latest_q", None)
    assert "figures as of" not in sortline_html("latest_q", None)


def test_sorted_grid_is_one_blob_without_cluster_headers():
    m = growth_by_key(GROWTH)
    rows = sorted_rows({"NOK": {}, "AXTI": {}}, m, "avg2y")
    html = sorted_grid_html(rows, m, "avg2y", {}, _row)
    assert html.startswith('<div class="tk-scroll"') and html.endswith("</div>")
    assert 'class="tk-group"' not in html
    assert html.index("<row AXTI|") < html.index("<row NOK|")
    assert html.count('class="tk-growth"') == 2


def test_the_real_row_puts_the_growth_line_inside_the_summary_last():
    html = render_ticker_details_html("AXTI", {"price": 86.66, "chg_pct": 0.9},
                                      growth_html='<div class="tk-growth">x</div>')
    summary = html[html.index("<summary>"):html.index("</summary>")]
    assert summary.endswith('<div class="tk-growth">x</div>')
    plain = render_ticker_details_html("AXTI", {"price": 86.66, "chg_pct": 0.9})
    assert "tk-growth" not in plain


def test_nothing_ranks_labels_or_colours():
    m = growth_by_key(GROWTH)
    rows = sorted_rows({t: {} for t in ("NOK", "AXTI", "MU")}, m, "avg2y")
    text = (sorted_grid_html(rows, m, "avg2y", {}, _row) + sortline_html("avg2y", "2026-10-06")
            + sorted_footer_html(3) + "".join(growth_line_html(v, "avg2y") for v in m.values()))
    for word in ("Inflection", "Fast grower", "Stalwart", "Slow grower", "Cyclical", "Turnaround",
                 "hypergrowth", "#1", "rank", "BUY", "WATCH", "tone-pos", "tone-neg", "pos", "neg"):
        assert word not in text, word
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", text)
    assert "3 names · experimental sort by sales growth" in sorted_footer_html(3)


def test_the_css_keeps_the_growth_line_in_neutral_ink():
    with open("assets/theme.css", encoding="utf-8") as fh:
        css = fh.read()
    block = css[css.index("Experimental growth sort (2026-10-06)"):]
    block = block[:block.index(".tk-growth b")]
    assert "grid-column: 1 / -1" in block
    assert "--tone" not in block and "--color-text-3" in block


def test_the_published_file_covers_the_report_watchlist():
    """data/growth.json (MarketReport growth_types.py publish) has a figure entry for every
    name on the newest report, aliases included."""
    files = sorted(glob.glob("data/morning_report_*.json"))
    if not files or not glob.glob("data/growth.json"):
        pytest.skip("no report or growth data checked out")
    with open(files[-1], encoding="utf-8") as fh:
        wl = json.load(fh).get("watchlist", {})
    with open("data/growth.json", encoding="utf-8") as fh:
        m = growth_by_key(json.load(fh))
    assert set(wl) <= set(m), sorted(set(wl) - set(m))


# --- the page --------------------------------------------------------------------------------------------------


def _watchlist_app():
    """Boot ONLY the Watchlist grid on the newest report. ASCII-only source."""
    import glob
    import json

    from components.watchlist import render_watchlist

    files = sorted(glob.glob("data/morning_report_*.json"))
    with open(files[-1], encoding="utf-8") as fh:
        report = json.load(fh)
    render_watchlist(report.get("watchlist", {}),
                     report_date=(report.get("meta") or {}).get("report_date"))


def _boot():
    if not glob.glob("data/morning_report_*.json") or not glob.glob("data/growth.json"):
        pytest.skip("no report or growth data checked out")
    at = AppTest.from_function(_watchlist_app, default_timeout=60)
    at.run()
    assert not at.exception, f"boot: {[e.value for e in at.exception]}"
    return at


def test_the_page_defaults_to_the_cluster_order():
    at = _boot()
    assert at.radio(key="wl_order").value == ORDER_CLUSTERS
    blob = " ".join(str(m.value) for m in at.markdown)
    assert 'class="tk-group"' in blob and "tk-growth" not in blob


@pytest.mark.parametrize("order", [ORDER_TWO_YEAR, ORDER_QUARTER])
def test_each_sort_reorders_the_rows_and_adds_the_growth_lines(order):
    at = _boot()
    at.radio(key="wl_order").set_value(order).run()
    assert not at.exception, f"{order}: {[e.value for e in at.exception]}"
    blob = " ".join(str(m.value) for m in at.markdown)
    assert 'class="tk-group"' not in blob
    assert "tk-sortline-exp" in blob and "experimental sort by sales growth" in blob
    grid = next(str(m.value) for m in at.markdown if 'class="tk-scroll"' in str(m.value))
    assert grid.count('class="tk-growth"') == grid.count('class="tk-details"') > 0
