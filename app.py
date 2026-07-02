"""
=============================================================================
YouTube Channel Video & Transcript Downloader
=============================================================================
Main Streamlit application entry point.
Orchestrates the UI layout, state management, and pipeline coordination.
=============================================================================
"""

import streamlit as st
import os
import sys

# ---------------------------------------------------------------------------
# Page configuration — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="YT Channel Downloader",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Local module imports
# ---------------------------------------------------------------------------
from ui.sidebar import render_sidebar
from ui.dashboard import render_dashboard
from ui.styles import inject_custom_css
from core.session import init_session_state

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
inject_custom_css()
init_session_state()

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
def main():
    # ── Header ──────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="header-container">
            <div class="header-icon">🎬</div>
            <div class="header-text">
                <h1>YouTube Channel Downloader</h1>
                <p>Filter by views · Download MP4 · Extract Transcripts</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar (user inputs + controls) ────────────────────────────────────
    channel_url, threshold, start_clicked, output_dir = render_sidebar()

    # ── Main Dashboard (progress + results) ─────────────────────────────────
    render_dashboard(channel_url, threshold, start_clicked, output_dir)


if __name__ == "__main__":
    main()
