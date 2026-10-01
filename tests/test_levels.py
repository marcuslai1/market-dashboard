"""lib.levels — the drill-down's price ladder (MarketReport spec
2026-10-01-info-only-watchlist §3: levels without ratio / stop / target).

The pipeline back-fills an empty support / resistance side with an SMA or with
price × 0.8 / 0.9 (supports), × 1.05 / 1.15 (resistances) — ``pipeline/indicators.py``
``ensure_*_zones``. Those must never print as a support or resistance.
"""
from lib.levels import level_ladder, observed_zones


def test_observed_zones_pass_real_levels_through_nearest_first():
    d = {"price": 228.38, "support_zones": [198.43, 208.08],
         "resistance_zones": [235.25, 229.88], "sma50": 217.23, "sma200": 199.81}
    assert observed_zones(d) == ([208.08, 198.43], [229.88, 235.25])


def test_synthetic_resistance_pair_is_dropped():
    # AMD, 2026-10-01: 611.76 × 1.05 = 642.35, × 1.15 = 703.52.
    d = {"price": 611.76, "support_zones": [496.75, 461.71],
         "resistance_zones": [642.35, 703.52]}
    assert observed_zones(d) == ([496.75, 461.71], [])


def test_synthetic_support_pair_is_dropped():
    p = 50.0
    d = {"price": p, "support_zones": [round(p * 0.8, 2), round(p * 0.9, 2)]}
    assert observed_zones(d)[0] == []


def test_synthetic_pair_is_detected_after_a_live_price_overlay():
    # The overlay moves `price`; the pair's own ratio still gives it away.
    d = {"price": 640.0, "resistance_zones": [642.35, 703.52]}
    assert observed_zones(d)[1] == []


def test_a_level_that_is_just_the_sma_is_dropped():
    d = {"price": 100.0, "sma50": 104.37, "sma200": 90.12,
         "resistance_zones": [104.37], "support_zones": [90.12, 95.5]}
    assert observed_zones(d) == ([95.5], [])


def test_a_real_pair_near_the_synthetic_ratio_survives():
    # 0.8 / 0.9 = 0.8889; a real pair a few cents off the multiple is kept.
    d = {"support_zones": [80.30, 90.0]}
    assert observed_zones(d)[0] == [90.0, 80.30]


def test_ladder_sorts_high_to_low_and_measures_from_the_last_price():
    d = {"price": 100.0, "support_zones": [95.0], "resistance_zones": [110.0],
         "sma50": 98.0, "sma200": 80.0}
    rungs = level_ladder(d)
    assert [(r.kind, r.price) for r in rungs] == [
        ("resistance", 110.0), ("last", 100.0), ("sma50", 98.0),
        ("support", 95.0), ("sma200", 80.0)]
    assert round(rungs[0].pct, 6) == 10.0
    assert rungs[1].pct is None
    assert round(rungs[-1].pct, 6) == -20.0


def test_ladder_without_a_price_has_no_last_rung_and_no_distances():
    rungs = level_ladder({"sma50": 98.0})
    assert [r.kind for r in rungs] == ["sma50"]
    assert rungs[0].pct is None


def test_ladder_is_empty_without_any_level():
    assert level_ladder({"price": 100.0}) == []


def test_non_numeric_levels_are_ignored():
    d = {"price": 10.0, "support_zones": ["9.5", None, 9.0], "sma50": True}
    assert [r.price for r in level_ladder(d)] == [10.0, 9.0]
