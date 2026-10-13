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
    page_title="Shorts Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Local module imports
# ---------------------------------------------------------------------------
from ui.studio import render_studio
from ui.styles import inject_custom_css

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
inject_custom_css()

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
def main():
    render_studio()


if __name__ == "__main__":
    main()
