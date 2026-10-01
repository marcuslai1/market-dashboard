"""Session-state bootstrap for the Streamlit dashboard.

Centralizes default values for cross-page state so individual components
don't reach into st.session_state directly. The first-mount flag
(``has_mounted`` / ``is_first_mount`` / ``mark_mounted``) went 2026-10-01: it
gated the Watchlist's one-shot signal flash, which went with the labels.
"""
from __future__ import annotations

import streamlit as st


def init_session_state() -> None:
    """Initialize default keys. Idempotent — safe to call on every rerun."""
    if "density" not in st.session_state:
        st.session_state.density = "relaxed"
