"""Tests for the watchlist summary-row builder.

Facts only since 2026-10-01 (MarketReport spec 2026-10-01-info-only-watchlist,
O6): seven cells — Ticker (+ cluster) · Last · Δ · 5 d · 1 mo · vs 50-day · RSI ·
Earnings. A report that still carries signal labels renders the same row as one
that does not.

Missing numerics must render a bare em-dash — `_fmt_num(None)` already yields
"—", but a cell that appends its unit unconditionally prints "—%" (UX review
2026-07-07, seen live on CBRS's vs-50-day cell).
"""
import re

from components.watchlist.row import earnings_cell_html, render_ticker_details_html

#: A pre-cutover entry, carrying every label key the row used to render.
LABELLED = {
    "signal": "CAUTION", "raw_signal": "CAUTION", "prev_signal": "WATCH",
    "caution_source": "hard_block",
    "entry_block": "BLOCKED: +10.8% above 50-day SMA (>5% hard block).",
    "entry_block_reader": "Entry blocked: price is 10.8% above its 50-day average.",
    "risk_reward": {"ratio": 2.6, "ratio_label": "2.6:1"},
    "accumulate_gates": {"all_mechanical_pass": False, "earnings_days_until": 47},
    "writeup": {"headline": "Extended", "what_to_do": "Wait for a pullback."},
    "price": 990.0, "currency": "USD", "chg_pct": 1.2, "5d_pct": 3.4,
    "1mo_pct": 9.0, "vs_sma50_pct": 11.0, "rsi_14": 77,
}
#: The same facts in the post-cutover shape: no label keys at all.
LABEL_FREE = {k: v for k, v in LABELLED.items()
              if k in {"price", "currency", "chg_pct", "5d_pct", "1mo_pct",
                       "vs_sma50_pct", "rsi_14"}}
LABEL_FREE["next_earnings"] = {"date": "2026-11-17", "days_until": 47, "status": "scheduled"}


def _summary(html: str) -> str:
    return html.split("<summary>", 1)[1].split("</summary>", 1)[0]


def test_row_has_seven_cells_in_the_spec_order():
    s = _summary(render_ticker_details_html("MU", LABELLED, report_date="2026-10-01"))
    classes = re.findall(r'^<div class="([\w-]+)|</div><div class="([\w-]+)', s)
    top = [a or b for a, b in classes]
    assert top[:1] == ["tk-tick"]
    for cls in ("tk-last", "tk-5d", "tk-1mo", "tk-ext", "tk-rsi", "tk-earn"):
        assert f'class="{cls}' in s, cls


def test_a_labelled_report_renders_no_label():
    html = render_ticker_details_html("MU", LABELLED, report_date="2026-10-01")
    for gone in ("sig-pill", "data-signal", "CAUTION", "tk-rr", "2.6:1", "tk-changed",
                 "tk-sig-days", "ENTRY BLOCK", "Entry blocked", "Wait for a pullback"):
        assert gone not in html, gone


def test_both_report_shapes_render_the_same_row():
    a = _summary(render_ticker_details_html("MU", LABELLED, report_date="2026-10-01"))
    b = _summary(render_ticker_details_html("MU", LABEL_FREE, report_date="2026-10-01"))
    assert a == b


def test_missing_pct_cells_render_bare_dash():
    html = render_ticker_details_html("CBRS", {"price": 192.01})
    assert "—%" not in html
    assert "—" in html                      # the placeholder itself survives


def test_present_pct_cells_keep_sign_and_unit():
    d = {"price": 195.55, "chg_pct": 0.59, "5d_pct": 2.31, "1mo_pct": -8.9,
         "vs_sma50_pct": -6.7}
    html = render_ticker_details_html("NVDA", d)
    assert "+0.59%" in html
    assert "+2.3%" in html
    assert "-8.9%" in html
    assert "-6.7%" in html


def test_returns_keep_the_price_direction_colour():
    s = _summary(render_ticker_details_html("NVDA", {"5d_pct": 2.0, "1mo_pct": -3.0}))
    assert 'class="tk-5d up"' in s
    assert 'class="tk-1mo down"' in s


def test_rsi_cell_is_uncoloured_at_any_reading():
    for rsi in (12, 55, 88):
        s = _summary(render_ticker_details_html("NVDA", {"rsi_14": rsi}))
        assert f'<div class="tk-rsi">{rsi}</div>' in s
        assert "data-zone" not in s


def test_missing_price_renders_dash_without_currency_prefix():
    html = render_ticker_details_html("NVDA", {})
    assert "$—" not in html


def test_extended_session_row_gets_tag():
    d = {"price": 208.0, "chg_pct": -1.4, "live_session": "PRE"}
    html = render_ticker_details_html("NVDA", d)
    assert 'class="ext-tag"' in html
    assert ">PRE</span>" in html


def test_regular_session_row_has_no_tag():
    html = render_ticker_details_html("NVDA", {"price": 210.96, "chg_pct": 0.19})
    assert "ext-tag" not in html


def test_ticker_cell_carries_the_cluster_as_a_sub_line():
    html = render_ticker_details_html("NVDA", {"price": 210.0})
    assert '<div class="tk-tick-cluster">Semis</div>' in html


def test_the_reports_own_cluster_wins_over_the_catalog():
    html = render_ticker_details_html("NVDA", {"cluster": "Accelerators"})
    assert '<div class="tk-tick-cluster">Accelerators</div>' in html


def test_row_carries_the_gauge():
    html = render_ticker_details_html("MU", {"vs_sma50_pct": 11.0})
    assert "tk-ext-track" in html
    assert "data-tone" not in html


# ── Earnings cell ──
def test_earnings_cell_dates_a_day_count_from_the_report_date():
    html = earnings_cell_html({"accumulate_gates": {"earnings_days_until": 47}}, "2026-10-01")
    assert '<div class="tk-earn-date">17 Nov</div>' in html
    assert '<div class="tk-earn-sub">in 47 d</div>' in html


def test_earnings_cell_reads_the_post_cutover_field():
    d = {"next_earnings": {"date": "2026-11-17", "days_until": 47, "status": "scheduled"}}
    assert "17 Nov" in earnings_cell_html(d, None)


def test_earnings_cell_says_reported_the_morning_after():
    d = {"pre_earnings_band": {"earnings_date": "2026-09-30", "days_until": -1,
                               "temporal_status": "released_overnight"}}
    html = earnings_cell_html(d, "2026-10-01")
    assert "30 Sep" in html and "reported" in html


def test_earnings_cell_without_a_date_is_a_bare_dash():
    assert '<div class="tk-earn-date">—</div>' in earnings_cell_html({}, "2026-10-01")


def test_earnings_cell_names_an_unreadable_calendar():
    d = {"accumulate_gates": {"earnings_days_until": None, "abstained": [
        {"gate": "g5_no_earnings_7d",
         "reason": "earnings calendar unavailable — proximity unverifiable"}]}}
    html = earnings_cell_html(d, "2026-10-01")
    assert "n/a" in html and "no calendar" in html


def test_earnings_cell_carries_no_colour():
    html = earnings_cell_html({"accumulate_gates": {"earnings_days_until": 2}}, "2026-10-01")
    assert "style=" not in html and " up" not in html and " down" not in html
