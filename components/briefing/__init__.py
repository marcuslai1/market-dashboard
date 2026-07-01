"""Briefing-page sub-components.

Each section of the Briefing tab is a standalone module under
``components.briefing`` exporting a single ``render_*`` entry point. ``dashboard.py``
composes them directly (interleaving the crisis flag, live-price caption, catalyst
playbook, contrarians, and methodology footer), so there is no shared orchestrator.
"""
from __future__ import annotations

from components.briefing.action_card import render_action_card
from components.briefing.catalyst_playbook import render_catalyst_playbook
from components.briefing.changes import render_changes
from components.briefing.clusters import render_clusters
from components.briefing.contrarians import render_contrarian_candidates
from components.briefing.pulse import render_pulse

__all__ = [
    "render_action_card",
    "render_catalyst_playbook",
    "render_changes",
    "render_clusters",
    "render_contrarian_candidates",
    "render_pulse",
]
