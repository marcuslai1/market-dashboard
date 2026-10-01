"""The vs 50-day gauge — the Watchlist's one visual (spec 2026-07-25 §8).

The scale is FIXED at ±EXT_MAX for every row: a shared scale is what makes the
bars comparable down the page. Since 2026-10-01 the gauge is untinted (MarketReport
spec 2026-10-01-info-only-watchlist §8): no terracotta at the old ±10% entry-block
threshold and no up/down colour on the number.
"""
from components.watchlist.gauge import EXT_MAX, extension_gauge_html


def test_missing_value_renders_bare_dash_and_no_track():
    html = extension_gauge_html(None)
    assert "—" in html
    assert "—%" not in html
    assert "tk-ext-track" not in html


def test_positive_grows_right_from_centre():
    html = extension_gauge_html(10.0)
    assert "left:50%" in html
    assert "right:50%" not in html


def test_negative_grows_left_from_centre():
    html = extension_gauge_html(-10.0)
    assert "right:50%" in html
    assert "left:50%" not in html


def test_full_scale_fills_exactly_half_the_track():
    # ±EXT_MAX is the widest a bar may be: half the track, from the centre out.
    assert "width:50.00%" in extension_gauge_html(EXT_MAX)


def test_half_scale_fills_a_quarter():
    assert "width:25.00%" in extension_gauge_html(EXT_MAX / 2)


def test_value_past_the_scale_is_clamped_not_overflowed():
    clamped = extension_gauge_html(-40.0)
    assert "width:50.00%" in clamped
    # …and still prints its true value, so clamping never hides the number.
    assert "-40.0%" in clamped


def test_no_threshold_tone_at_any_distance():
    for v in (0.5, 9.9, 10.0, 25.0, -10.0, -30.0):
        assert "data-tone" not in extension_gauge_html(v)


def test_number_is_uncoloured():
    assert '<div class="tk-ext-num">+4.0%</div>' in extension_gauge_html(4.0)
    assert '<div class="tk-ext-num">-4.0%</div>' in extension_gauge_html(-4.0)


def test_zero_renders_a_track_with_no_fill_width():
    html = extension_gauge_html(0.0)
    assert "tk-ext-track" in html
    assert "width:0.00%" in html


def test_zero_line_is_drawn_inside_every_track():
    # Steel structural reference mark, over-tall so a crossing bar can't hide it.
    assert "tk-ext-zero" in extension_gauge_html(4.0)
