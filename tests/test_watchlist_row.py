"""Tests for the watchlist summary-row builder (UX review 2026-07-07).

Missing numerics must render a bare em-dash — `_fmt_num(None)` already yields
"—", but the row cells append their unit unconditionally, so a None percent
printed as "—%" (seen live on CBRS's vs-50-day cell).
"""
from components.watchlist.row import render_ticker_details_html


def test_missing_pct_cells_render_bare_dash():
    html = render_ticker_details_html("CBRS", {"signal": "CAUTION", "price": 192.01})
    assert "—%" not in html
    assert "—" in html                      # the placeholder itself survives


def test_present_pct_cells_keep_sign_and_unit():
    d = {"signal": "WATCH", "price": 195.55, "chg_pct": 0.59,
         "1mo_pct": -8.9, "vs_sma50_pct": -6.7}
    html = render_ticker_details_html("NVDA", d)
    assert "+0.59%" in html
    assert "-8.9%" in html
    assert "-6.7%" in html


def test_missing_price_renders_dash_without_currency_prefix():
    html = render_ticker_details_html("NVDA", {"signal": "HOLD"})
    assert "$—" not in html


def test_extended_session_row_gets_tag():
    d = {"signal": "WATCH", "price": 208.0, "chg_pct": -1.4, "live_session": "PRE"}
    html = render_ticker_details_html("NVDA", d)
    assert 'class="ext-tag"' in html
    assert ">PRE</span>" in html


def test_regular_session_row_has_no_tag():
    d = {"signal": "WATCH", "price": 210.96, "chg_pct": 0.19}
    html = render_ticker_details_html("NVDA", d)
    assert "ext-tag" not in html


# ── entry_block_reader preference (F2, 2026-07-18 reader eval) ──
def test_entry_block_reader_preferred_when_present():
    d = {
        "signal": "CAUTION",
        "entry_block": "BLOCKED: +10.8% above 50-day SMA (>5% hard block).",
        "entry_block_reader": "Entry blocked: price is 10.8% above its "
                              "50-day average.",
        "writeup": {"entry_block": "BLOCKED: +10.8% above 50-day SMA "
                                   "(>5% hard block)."},
    }
    html = render_ticker_details_html("MU", d)
    assert "price is 10.8% above its 50-day average" in html
    # Raw string survives as the hover title for grep-ability.
    assert "BLOCKED: +10.8%" in html


def test_entry_block_raw_fallback_for_old_reports():
    d = {
        "signal": "CAUTION",
        "entry_block": "BLOCKED: RSI 72 (>65 hard block).",
        "writeup": {"entry_block": "BLOCKED: RSI 72 (>65 hard block)."},
    }
    html = render_ticker_details_html("MU", d)
    assert "BLOCKED: RSI 72" in html
