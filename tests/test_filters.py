"""Tests for lib.filters date-range filtering."""
from datetime import date

import pandas as pd

from lib.filters import filter_prices, filter_reports


def test_filter_reports_inclusive_boundaries():
    reports = {"2026-01-01": 1, "2026-01-15": 2, "2026-01-31": 3, "2026-02-01": 4}
    out = filter_reports(reports, date(2026, 1, 1), date(2026, 1, 31))
    assert set(out) == {"2026-01-01", "2026-01-15", "2026-01-31"}


def test_filter_reports_skips_non_iso_keys():
    reports = {"2026-01-10": 1, "not-a-date": 2}
    out = filter_reports(reports, date(2026, 1, 1), date(2026, 1, 31))
    assert set(out) == {"2026-01-10"}


def test_filter_prices_inclusive_and_empty_passthrough():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2025-12-31", "2026-01-01", "2026-01-31", "2026-02-02"]),
        "ticker": ["A"] * 4,
    })
    out = filter_prices(df, date(2026, 1, 1), date(2026, 1, 31))
    assert list(out["date"].dt.date.astype(str)) == ["2026-01-01", "2026-01-31"]
    assert filter_prices(pd.DataFrame(), date(2026, 1, 1), date(2026, 1, 31)).empty
