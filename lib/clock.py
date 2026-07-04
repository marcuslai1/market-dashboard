"""Test-injectable 'today' so visual-regression baselines can pin the render date.

Production leaves TEST_DATE unset, so ``today()`` is exactly ``datetime.date.today()``.
The visual-regression harness sets ``TEST_DATE=YYYY-MM-DD`` to freeze the render
date, keeping the committed pixel baselines of the today-anchored, date-filtered
pages (signal-tracker, pipeline-stats, scenario-log, report-comparison) stable as
the wall clock advances. This is a guarded, test-only date seam — no signal or
logic change.
"""
from __future__ import annotations

import os
from datetime import date


def today() -> date:
    """``date.today()``, unless ``TEST_DATE=YYYY-MM-DD`` is set (visual-regression
    freeze). A malformed TEST_DATE raises ValueError via ``date.fromisoformat`` —
    fail loud rather than silently render the wrong window."""
    override = os.environ.get("TEST_DATE")
    return date.fromisoformat(override) if override else date.today()
