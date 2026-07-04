"""Tests for lib.formatters escaping + currency helpers.

Covers the escaping contract (attribute escaping + href sanitisation) and the
currency-aware price prefix/decimals, which the many hand-built HTML sinks rely
on.
"""
from lib.formatters import (
    _ccy_decimals,
    _ccy_prefix,
    _escape_attr,
    _price_str,
    _safe_href,
    display_ticker,
    rr_display,
)


# ── Attribute escaping ──
def test_escape_attr_neutralizes_quotes_and_angles():
    out = _escape_attr('a" onmouseover="x')
    assert '"' not in out
    assert "&quot;" in out


def test_escape_attr_handles_none_and_empty():
    assert _escape_attr(None) == ""
    assert _escape_attr("") == ""


# ── href sanitisation ──
def test_safe_href_passes_https():
    url = "https://www.reuters.com/business/x-2026-06-24/"
    assert _safe_href(url) == url


def test_safe_href_passes_http():
    assert _safe_href("http://example.com") == "http://example.com"


def test_safe_href_rejects_javascript_scheme():
    assert _safe_href("javascript:alert(1)") == ""


def test_safe_href_rejects_data_scheme():
    assert _safe_href("data:text/html,<script>") == ""


def test_safe_href_escapes_attribute_breakout():
    out = _safe_href('https://a.com/"><script>')
    assert '"' not in out
    assert "<" not in out


def test_safe_href_handles_none_and_empty():
    assert _safe_href(None) == ""
    assert _safe_href("") == ""


# ── Currency prefix (HTML-safe: $ neutralised for Streamlit LaTeX) ──
def test_ccy_prefix_known_currencies():
    assert _ccy_prefix("USD") == "&#36;"
    assert _ccy_prefix("SGD") == "S&#36;"
    assert _ccy_prefix("EUR") == "€"
    assert _ccy_prefix("KRW") == "₩"
    assert _ccy_prefix("TWD") == "NT&#36;"


def test_ccy_prefix_unknown_defaults_to_dollar():
    assert _ccy_prefix("XYZ") == "&#36;"
    assert _ccy_prefix(None) == "&#36;"


# ── Currency decimals (zero-decimal currencies) ──
def test_ccy_decimals_zero_decimal_currencies():
    assert _ccy_decimals("KRW") == 0
    assert _ccy_decimals("JPY") == 0


def test_ccy_decimals_default_two():
    assert _ccy_decimals("USD") == 2
    assert _ccy_decimals("SGD") == 2
    assert _ccy_decimals("EUR") == 2


# ── Full price string ──
def test_price_str_krw_no_decimals_correct_symbol():
    out = _price_str(2_560_000, "KRW")
    assert out == "₩2,560,000"


def test_price_str_sgd_two_decimals():
    assert _price_str(2300.5, "SGD") == "S&#36;2,300.50"


def test_price_str_none_is_dash():
    assert _price_str(None, "USD") == "—"


# ── Ticker display form ──
def test_display_ticker_uses_override_map():
    # Overrides carry the glyphs a plain replace can't restore (= ^ -).
    assert display_ticker("CL_F") == "CL=F"
    assert display_ticker("VIX") == "^VIX"
    assert display_ticker("DX_Y_NYB") == "DX-Y.NYB"


def test_display_ticker_restores_dots_for_unmapped_keys():
    # TICKER_DISPLAY is sparse: plain underscore-for-dot names aren't listed,
    # so the raw .get(tk, tk) pattern used to leak `000660_KS` into the UI.
    assert display_ticker("000660_KS") == "000660.KS"


def test_display_ticker_plain_ticker_unchanged():
    assert display_ticker("NVDA") == "NVDA"


# ── Risk:reward display — distorted-headline correction (UX-BR-2) ──
def test_rr_display_prefers_sizing_rr_when_distorted():
    rr = {"ratio_label": "46.5:1", "ratio": 46.5, "rr_distorted": True,
          "sizing_rr": {"ratio": 4.4, "ratio_label": "4.4:1"}}
    label, ratio, adjusted = rr_display(rr)
    assert label == "4.4:1"
    assert ratio == 4.4
    assert adjusted is True


def test_rr_display_passes_through_normal_rr():
    label, ratio, adjusted = rr_display({"ratio_label": "2.4:1", "ratio": 2.4})
    assert (label, ratio, adjusted) == ("2.4:1", 2.4, False)


def test_rr_display_distorted_without_sizing_keeps_headline():
    # Flagged distorted but no sizing_rr supplied → keep the headline, unadjusted.
    label, ratio, adjusted = rr_display({"ratio_label": "9.0:1", "ratio": 9.0,
                                         "rr_distorted": True})
    assert (label, ratio, adjusted) == ("9.0:1", 9.0, False)


def test_rr_display_empty_is_safe():
    assert rr_display(None) == ("", 0.0, False)
    assert rr_display({}) == ("", 0.0, False)
