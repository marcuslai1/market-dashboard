"""The Watchlist grid builders — the fixed display order (MarketReport spec
2026-10-01-info-only-watchlist §4, O1) and the facts-only table chrome.

The rule: cluster groups, largest first, then by name; names A–Z by display
ticker; retired names excluded. A report that stamps ``cluster`` on every entry
(post-cutover) is already in that order and is rendered as it comes.
"""
import glob
import json

import pytest

from components.watchlist.grid import (
    OTHER_CLUSTER,
    build_grid_html,
    column_header_html,
    footer_html,
    group_header_html,
    method_note_html,
    ordered_groups,
)


def _row(tk, d, **kw):
    return f"<row {tk}>"


def test_groups_go_largest_first_then_by_name():
    wl = {"MSFT": {}, "NVDA": {}, "AMD": {}, "D05_SI": {}, "AMZN": {}, "LITE": {}}
    names = [c for c, _ in ordered_groups(wl)]
    # Semis 2, BigTech 2 (tie → by name), then the singletons by name.
    assert names == ["BigTech", "Semis", "AI Optics", "SG Banks"]


def test_names_are_alphabetical_by_display_ticker_inside_a_group():
    wl = {"TSM": {}, "000660_KS": {}, "SOI_PA": {}, "AMD": {}, "SNDK": {}}
    (_, rows), = ordered_groups(wl)
    assert [tk for tk, _ in rows] == ["000660_KS", "AMD", "SNDK", "SOI_PA", "TSM"]


def test_order_ignores_every_daily_quantity():
    wl = {"NVDA": {"1mo_pct": -20, "signal": "CAUTION"},
          "AMD": {"1mo_pct": 30, "signal": "BUY"}}
    (_, rows), = ordered_groups(wl)
    assert [tk for tk, _ in rows] == ["AMD", "NVDA"]


def test_retired_names_are_excluded():
    wl = {"NVDA": {}, "COHR": {}}
    assert [tk for _, rows in ordered_groups(wl) for tk, _ in rows] == ["NVDA"]


def test_an_unknown_ticker_lands_in_other_last_even_when_larger():
    wl = {"ZZZ1": {}, "ZZZ2": {}, "ZZZ3": {}, "NVDA": {}}
    names = [c for c, _ in ordered_groups(wl)]
    assert names == ["Semis", OTHER_CLUSTER]


def test_a_stamped_report_keeps_its_own_order():
    # Post-cutover the pipeline's display_order writes the order and the cluster;
    # the dashboard renders it as is rather than re-deriving it.
    wl = {"B": {"cluster": "Two"}, "A": {"cluster": "Two"}, "C": {"cluster": "One"}}
    groups = ordered_groups(wl)
    assert [(c, [tk for tk, _ in rows]) for c, rows in groups] == [
        ("Two", ["B", "A"]), ("One", ["C"])]


def test_a_partly_stamped_report_falls_back_to_the_rule():
    wl = {"NVDA": {"cluster": "Semis"}, "AMZN": {}}
    assert [c for c, _ in ordered_groups(wl)] == ["BigTech", "Semis"]


def test_the_latest_report_matches_the_spec_order():
    files = sorted(glob.glob("data/morning_report_*.json"))
    if not files:
        pytest.skip("no report data checked out")
    with open(files[-1], encoding="utf-8") as fh:
        wl = json.load(fh).get("watchlist", {})
    groups = ordered_groups(wl)
    sizes = [len(rows) for _, rows in groups]
    assert sizes == sorted(sizes, reverse=True)
    for _, rows in groups:
        keys = [tk.replace("_", ".") for tk, _ in rows]
        assert keys == sorted(keys)


def test_column_header_is_the_seven_fact_columns():
    html = column_header_html()
    for label in ("Ticker", "Last · Δ", "5 d", "1 mo", "vs 50-day", "RSI", "Earnings"):
        assert f">{label}</div>" in html
    for gone in ("Signal", "R:R"):
        assert gone not in html


def test_group_header_is_neutral_ink():
    html = group_header_html("Semis", 14)
    assert ">Semis<" in html and ">14<" in html
    assert "style=" not in html and "tk-group-dot" not in html


def test_grid_is_one_blob_with_a_header_per_group():
    groups = ordered_groups({"NVDA": {}, "AMD": {}, "MSFT": {}})
    html = build_grid_html(groups, {}, _row, report_date="2026-10-01")
    assert html.startswith('<div class="tk-scroll"')
    assert html.count('class="tk-group"') == 2
    assert "<row AMD><row NVDA>" in html


def test_method_note_and_footer_make_no_rating_claim():
    text = method_note_html() + footer_html(33, 11)
    assert "33 names in 11 groups" in text
    for gone in ("signal", "R:R", "block", "terracotta"):
        assert gone not in text
