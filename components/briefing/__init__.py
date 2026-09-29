"""Briefing-page sub-components.

Since 2026-09-29 the Briefing tab is the pulse strip, the daily briefing card and
the market-read card; ``dashboard.py`` composes them directly. ``calibration`` and
``contrarians`` live here for historical reasons but render on the Signal Tracker
and Watchlist pages.
"""
from __future__ import annotations

from components.briefing.calibration import render_calibration
from components.briefing.contrarians import render_contrarian_candidates
from components.briefing.pulse import render_pulse

__all__ = [
    "render_calibration",
    "render_contrarian_candidates",
    "render_pulse",
]
