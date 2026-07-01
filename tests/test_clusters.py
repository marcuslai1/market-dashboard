"""Tests for the Briefing cluster band (review P1-2)."""
from components.briefing.clusters import (
    _clusters_html,
    _extension_breadth,
    _norm,
    _signal_mix,
)


def test_norm_dot_to_underscore():
    assert _norm("D05.SI") == "D05_SI"
    assert _norm("000660.KS") == "000660_KS"


def test_signal_mix_orders_best_to_worst():
    wl = {"A": {"signal": "AVOID"}, "B": {"signal": "WATCH"}, "C": {"signal": "WATCH"}}
    # WATCH ranks above AVOID in SIGNAL_ORDER, so it comes first.
    assert _signal_mix(["A", "B", "C"], wl) == [("WATCH", 2), ("AVOID", 1)]


def test_signal_mix_buckets_null_and_missing_last():
    wl = {"A": {"signal": "HOLD"}, "B": {"signal": None}}
    # "C" is absent from the watchlist -> also counts toward the "—" bucket.
    assert _signal_mix(["A", "B", "C"], wl) == [("HOLD", 1), ("—", 2)]


def test_extension_breadth_counts_blocked_normalized():
    er = {"blocked_tickers": ["D05_SI", "000660_KS"]}
    assert _extension_breadth(["D05.SI", "O39.SI", "000660.KS"], er) == (2, 3)


def test_extension_breadth_none_without_regime():
    assert _extension_breadth(["D05.SI"], None) is None
    assert _extension_breadth(["D05.SI"], {}) is None


_WL = {
    "D05.SI": {"signal": "HOLD", "price": 47.0, "currency": "SGD", "chg_pct": -0.3},
    "O39.SI": {"signal": "WATCH", "price": 17.0, "currency": "SGD"},
}
_CLUSTERS = {
    "singapore": {
        "tickers": ["D05.SI", "O39.SI"],
        "summary": "Banks near overbought.",
        "thesis_status": "Structurally impaired",
        "key_development": "UOB upgraded to WATCH.",
        "data_anchors": {
            "D05_SI": {"vs_sma50_pct": 6.47, "rsi_14": 61.5},
            "O39_SI": {"vs_sma50_pct": 6.07, "rsi_14": 60.3},
        },
    }
}


def test_renders_name_summary_thesis_dev():
    out = _clusters_html(_CLUSTERS, _WL)
    assert "Singapore" in out            # title-cased key
    assert "Banks near overbought." in out
    assert "Structurally impaired" in out
    assert "UOB upgraded to WATCH." in out


def test_renders_at_a_glance_counts():
    out = _clusters_html(_CLUSTERS, _WL)
    assert "1&nbsp;WATCH" in out
    assert "1&nbsp;HOLD" in out


def test_extension_breadth_chip_rendered():
    out = _clusters_html(_CLUSTERS, _WL, {"blocked_tickers": ["D05_SI"]})
    assert "1/2&nbsp;ext." in out


def test_anchor_row_uses_normalized_key():
    out = _clusters_html(_CLUSTERS, _WL)
    assert "+6.5%" in out    # D05_SI anchor vs_sma50_pct 6.47 -> +6.5%
    assert "62" in out       # rsi_14 61.5 -> "62" at 0 decimals


def test_empty_clusters_placeholder():
    assert "No cluster breakdown" in _clusters_html({}, _WL)


def test_missing_data_anchors_no_table_no_raise():
    c = {"x": {"tickers": ["D05.SI"], "summary": "S"}}
    out = _clusters_html(c, _WL)
    assert "ep-table" not in out
    assert "S" in out


def test_ticker_missing_from_watchlist_degrades_gracefully():
    c = {"x": {"tickers": ["ZZZ"], "summary": "S",
               "data_anchors": {"ZZZ": {"vs_sma50_pct": 1.0, "rsi_14": 50}}}}
    out = _clusters_html(c, {})   # empty watchlist -> no KeyError
    assert "ep-table" in out      # anchor row still renders (no signal pill)
    assert "50" in out


def test_prose_is_escaped():
    c = {"x": {"tickers": [],
               "summary": "<script>alert(1)</script>",
               "thesis_status": "<img src=x onerror=alert(1)>",
               "key_development": '"><script>evil</script>'}}
    out = _clusters_html(c, {})
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
