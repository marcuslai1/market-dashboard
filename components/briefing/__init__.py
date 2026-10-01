"""Briefing-page sub-components.

Since 2026-09-29 the Briefing tab is the pulse strip, the daily briefing card and
the market-read card; ``dashboard.py`` composes them directly. ``calibration``
(the Tracker's band) and ``contrarians`` (the Watchlist's oversold-setups block)
went on 2026-10-01 with the signal labels (tag ``pre-label-removal``).
"""
from __future__ import annotations

from components.briefing.pulse import render_pulse

__all__ = [
    "render_pulse",
]
