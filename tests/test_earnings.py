"""Tests for the Briefing earnings-scorecard band (review P1-2)."""
from components.briefing.earnings import _eps_rows, _headline


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
