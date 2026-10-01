"""Test-injectable 'today' so visual-regression baselines can pin the render date.

Production leaves TEST_DATE unset, so ``today()`` is exactly ``datetime.date.today()``.
The visual-regression harness sets ``TEST_DATE=YYYY-MM-DD`` to freeze the render
date, keeping the committed pixel baselines of today-anchored, date-filtered
pages stable as the wall clock advances. No page is date-filtered since
2026-10-01 (the Signal Tracker and its sidebar date range went with the labels;
pipeline-stats, scenario-log and report-comparison went 2026-09-29), so nothing
reads it today; it stays as the visual harness's frozen-clock seam. A guarded,
test-only date seam — no logic change.
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
