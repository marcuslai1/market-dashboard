"""Tests for the Briefing earnings-scorecard band (review P1-2)."""
from components.briefing.earnings import _earnings_html, _eps_rows, _headline


def _entry(quarters, accelerating=False, accel_reason=""):
    return {"eps_trajectory": {"quarters": quarters,
                               "accelerating": accelerating,
                               "accel_reason": accel_reason}}


def test_eps_rows_collects_only_entries_with_trajectory():
    wl = {
        "MU": _entry([{"surprise_pct": 5.9}, {"surprise_pct": 21.2}]),
        "TSM": {"signal": "BUY"},                      # no eps_trajectory -> skipped
        "AMD": {"eps_trajectory": {"quarters": []}},   # empty quarters -> skipped
    }
    rows = _eps_rows(wl)
    assert [r["ticker"] for r in rows] == ["MU"]


def test_eps_rows_computes_latest_beats_and_n():
    wl = {"MU": _entry([{"surprise_pct": 5.9}, {"surprise_pct": -2.0},
                        {"surprise_pct": 21.2}])}
    (row,) = _eps_rows(wl)
    assert row["latest"] == 21.2
    assert row["n"] == 3
    assert row["beats"] == 2  # 5.9 and 21.2 are > 0; -2.0 is not


def test_eps_rows_ordered_accel_first_then_surprise_desc():
    wl = {
        "LITE": _entry([{"surprise_pct": 4.4}], accelerating=True),
        "MU": _entry([{"surprise_pct": 21.2}], accelerating=True),
        "PLTR": _entry([{"surprise_pct": 99.0}], accelerating=False),  # bigger, not accel
    }
    rows = _eps_rows(wl)
    # accelerating names first (MU 21.2 before LITE 4.4); non-accel PLTR last
    assert [r["ticker"] for r in rows] == ["MU", "LITE", "PLTR"]


def test_eps_rows_display_name_mapping():
    wl = {"000660_KS": _entry([{"surprise_pct": 41.6}], accelerating=True)}
    (row,) = _eps_rows(wl)
    assert row["ticker"] == "000660.KS"


def test_headline_counts():
    rows = [
        {"latest": 21.2, "accelerating": True},
        {"latest": 4.4, "accelerating": True},
        {"latest": -1.0, "accelerating": False},
        {"latest": 8.0, "accelerating": False},
    ]
    # 3 of 4 beat (21.2, 4.4, 8.0 > 0; -1.0 not); 2 accelerating
    assert _headline(rows) == "3 of 4 beat last quarter · 2 accelerating"


def test_headline_empty_generic():
    assert _headline([]) == "Earnings scorecard"


_WL = {
    "000660_KS": _entry(
        [{"surprise_pct": 2.5}, {"surprise_pct": 41.8},
         {"surprise_pct": 20.8}, {"surprise_pct": 41.6}],
        accelerating=True, accel_reason="EPS 17850 -> 21522 -> 56670 over 3 qtrs",
    ),
    "MU": _entry(
        [{"surprise_pct": 5.9}, {"surprise_pct": 20.7},
         {"surprise_pct": 33.2}, {"surprise_pct": 21.2}],
        accelerating=True, accel_reason="EPS 4.78 -> 12.2 -> 25.11 over 3 qtrs",
    ),
    "LITE": _entry(
        [{"surprise_pct": 8.6}, {"surprise_pct": 6.8},
         {"surprise_pct": 18.4}, {"surprise_pct": 4.4}],
        accelerating=False,
    ),
}


def test_earnings_html_full():
    out = _earnings_html(_WL)
    assert "eps-scorecard" in out
    assert "000660.KS" in out and "MU" in out and "LITE" in out
    # headline: all three latest > 0, two accelerating
    assert "3 of 3 beat last quarter · 2 accelerating" in out
    assert "eps-beat" in out          # positive surprises are green
    assert "▲" in out                 # accel marker present
    assert "EPS 4.78" in out          # accel_reason line for an accelerating name


def test_earnings_html_empty_placeholder():
    assert "No earnings data" in _earnings_html({})
    assert "No earnings data" in _earnings_html({"MU": {"signal": "BUY"}})


def test_surprise_none_tolerated():
    wl = {"MU": _entry([{"surprise_pct": None}, {"surprise_pct": 21.2}],
                       accelerating=True)}
    out = _earnings_html(wl)
    assert "—" in out                 # the None surprise renders as a dash
    assert "eps-scorecard" in out
    (row,) = _eps_rows(wl)
    assert row["latest"] == 21.2
    assert row["beats"] == 1          # only the non-None positive counts


def test_miss_colored_red():
    wl = {"MU": _entry([{"surprise_pct": -3.0}], accelerating=False)}
    out = _earnings_html(wl)
    assert "eps-miss" in out
    assert "0 of 1 beat last quarter · 0 accelerating" in out


def test_accel_reason_escaped():
    wl = {"MU": _entry([{"surprise_pct": 10.0}], accelerating=True,
                       accel_reason="<script>alert(1)</script><img src=x onerror=alert(1)>")}
    out = _earnings_html(wl)
    assert "<script>" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
