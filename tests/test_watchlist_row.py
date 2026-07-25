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


# ── redesign 2026-07-25: seven cells, two-line ticker, visible R:R qualifier ──
def test_ticker_cell_carries_the_cluster_as_a_sub_line():
    # Cluster stopped being a column: it is context you want while looking at a
    # name, not an axis you scan — and it was eating 100px of a fixed grid.
    html = render_ticker_details_html("NVDA", {"signal": "WATCH", "price": 210.0})
    assert "tk-tick-cluster" in html


def test_changed_row_gets_the_steel_dot():
    html = render_ticker_details_html(
        "MU", {"signal": "CAUTION", "price": 990.0}, signal_changed=True
    )
    assert "tk-changed" in html
    assert 'data-signal-changed="true"' in html   # the first-mount flash survives


def test_unchanged_row_has_no_dot():
    html = render_ticker_details_html("MU", {"signal": "CAUTION", "price": 990.0})
    assert "tk-changed" not in html


def test_row_carries_the_extension_gauge():
    html = render_ticker_details_html(
        "MU", {"signal": "CAUTION", "price": 990.0, "vs_sma50_pct": 11.0}
    )
    assert "tk-ext-track" in html
    assert 'data-tone="over"' in html


def test_rsi_is_flagged_hot_at_seventy_and_cold_at_thirty():
    hot = render_ticker_details_html("D05.SI", {"signal": "CAUTION", "rsi_14": 77})
    cold = render_ticker_details_html("CRWV", {"signal": "CAUTION", "rsi_14": 28})
    mid = render_ticker_details_html("NVDA", {"signal": "WATCH", "rsi_14": 55})
    assert 'data-zone="hot"' in hot
    assert 'data-zone="cold"' in cold
    assert 'data-zone=""' in mid


def test_missing_rsi_is_not_flagged_cold():
    # An absent reading is not an oversold one.
    html = render_ticker_details_html("NVDA", {"signal": "WATCH"})
    assert 'data-zone=""' in html


def test_adjusted_rr_qualifier_is_visible_text_not_only_a_title():
    # Shipped code hid this in a title attribute — invisible on touch, and it is
    # the difference between a 1.5:1 that clears the gate and one that doesn't.
    d = {
        "signal": "CAUTION",
        "risk_reward": {
            "ratio": 22.5, "ratio_label": "22.5:1", "rr_distorted": True,
            "sizing_rr": {"ratio": 1.49, "ratio_label": "1.49:1"},
        },
    }
    html = render_ticker_details_html("MU", d)
    assert "tight-stop adj." in html
    assert "1.49:1" in html
    assert "22.5:1" in html      # raw headline survives on the title


def test_unadjusted_rr_has_no_qualifier_line():
    d = {"signal": "WATCH", "risk_reward": {"ratio": 2.6, "ratio_label": "2.6:1"}}
    assert "tight-stop adj." not in render_ticker_details_html("NVDA", d)
