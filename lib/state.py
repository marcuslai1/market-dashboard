"""Session-state bootstrap for the Streamlit dashboard.

Centralizes default values for cross-page state so individual components
don't reach into st.session_state directly. The has_mounted flag gates
first-mount-only animations (signal-flash, severity-pulse) so they don't
replay on every Streamlit script rerun.
"""
from __future__ import annotations

import streamlit as st


def init_session_state() -> None:
    """Initialize default keys. Idempotent — safe to call on every rerun."""
    if "has_mounted" not in st.session_state:
        st.session_state.has_mounted = False
    if "density" not in st.session_state:
        st.session_state.density = "relaxed"


def is_first_mount() -> bool:
    """True on the very first script run of the session, False thereafter.

    Use this to decide whether to emit data-first-mount="true" on a wrapper
    so CSS keyframes fire once. Must be called BEFORE mark_mounted().
    """
    return not st.session_state.get("has_mounted", False)


def mark_mounted() -> None:
    """Flip has_mounted to True. Call at the END of the script (post-render).

    On the next rerun, is_first_mount() returns False — animations stay
    dormant. Calling this mid-script is safe but defeats the purpose.
    """
    st.session_state.has_mounted = True
