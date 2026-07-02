"""
=============================================================================
core/session.py
=============================================================================
Centralised Streamlit session-state initialisation.
All keys used across the app are declared here so they are always available
before any widget tries to read them.
=============================================================================
"""

import streamlit as st


def init_session_state() -> None:
    """
    Initialise every session-state key with a safe default value.
    Idempotent – safe to call on every rerun.
    """

    defaults: dict = {
        # ── Pipeline state ───────────────────────────────────────────────
        "pipeline_running": False,       # True while the pipeline is active
        "pipeline_done": False,          # True after the pipeline completes
        "pipeline_error": None,          # Stores an error message string if fatal

        # ── Scan / filter results ────────────────────────────────────────
        "all_videos": [],                # Raw list of video metadata dicts
        "qualified_videos": [],          # Videos that pass the view threshold

        # ── Per-video processing results ─────────────────────────────────
        "processed_results": [],         # List of ProcessedVideo dicts
        "current_video_index": 0,        # Index being processed right now

        # ── UI helpers ───────────────────────────────────────────────────
        "log_messages": [],              # List of log strings for the console
        "output_dir": "",                # Resolved output directory path
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
