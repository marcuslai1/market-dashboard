"""Tests for lib.clock — the TEST_DATE-injectable ``today()`` seam.

The core faithfulness property: when TEST_DATE is UNSET, ``lib.clock.today()``
must be byte-for-byte identical to ``datetime.date.today()`` (production is
unchanged; the freeze is a test-only affordance). The other tests prove the
override activates only under the env var and fails loud on a bad value.
"""
from datetime import date

import pytest

from lib.clock import today


def test_today_frozen_when_test_date_set(monkeypatch):
    """TEST_DATE=YYYY-MM-DD -> today() returns exactly that date."""
    monkeypatch.setenv("TEST_DATE", "2026-08-01")
    assert today() == date(2026, 8, 1)


def test_today_returns_date_type_when_frozen(monkeypatch):
    """The frozen value is a real datetime.date (not a str), so arithmetic
    like ``today() - timedelta(days=30)`` keeps working downstream."""
    monkeypatch.setenv("TEST_DATE", "2026-07-04")
    result = today()
    assert isinstance(result, date)
    assert result == date(2026, 7, 4)


def test_today_faithful_to_stdlib_when_unset(monkeypatch):
    """Faithfulness: unset TEST_DATE -> today() == datetime.date.today().

    This guards production behavior — the seam must be invisible when the env
    var is absent.
    """
    monkeypatch.delenv("TEST_DATE", raising=False)
    assert today() == date.today()


def test_today_ignores_empty_test_date(monkeypatch):
    """An empty string is falsy -> treated as unset, not as a malformed date."""
    monkeypatch.setenv("TEST_DATE", "")
    assert today() == date.today()


def test_today_raises_on_malformed_test_date(monkeypatch):
    """A non-ISO TEST_DATE fails loud (fromisoformat raises ValueError) rather
    than silently rendering the wrong window."""
    monkeypatch.setenv("TEST_DATE", "not-a-date")
    with pytest.raises(ValueError):
        today()
