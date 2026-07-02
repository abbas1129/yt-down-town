"""
=============================================================================
ui/sidebar.py
=============================================================================
Sidebar UI: channel URL input, view-count threshold, output directory
picker, and the START button.
=============================================================================
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads" / "YT_Downloads")


def render_sidebar() -> tuple[str, int, bool, str]:
    """
    Render the full sidebar and return user-selected values.

    Returns
    -------
    channel_url : str
    threshold   : int
    start_clicked : bool   — True only on the click event
    output_dir  : str      — absolute path chosen by the user
    """
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; padding: 0.5rem 0 1rem;">
                <span style="font-size:2.5rem;">🎬</span>
                <h2 style="margin:0; color:#c084fc; font-size:1.2rem;">YT Downloader</h2>
                <p style="color:#64748b; font-size:0.75rem; margin:0.2rem 0 0;">
                    Filter · Download · Transcribe
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Channel URL ──────────────────────────────────────────────────
        st.markdown("**📡 Channel URL**")
        channel_url = st.text_input(
            label="channel_url",
            label_visibility="collapsed",
            placeholder="https://www.youtube.com/@ChannelHandle",
            help=(
                "Paste any valid YouTube channel URL.  Accepted formats:\n"
                "• https://www.youtube.com/@handle\n"
                "• https://www.youtube.com/channel/UCxxx\n"
                "• https://www.youtube.com/c/Name\n"
                "• https://www.youtube.com/user/Name"
            ),
            key="channel_url_input",
        )

        st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

        # ── View count threshold ─────────────────────────────────────────
        st.markdown("**👁️ Minimum View Count**")
        threshold = st.number_input(
            label="threshold",
            label_visibility="collapsed",
            min_value=0,
            max_value=10_000_000_000,
            value=1_000_000,
            step=100_000,
            format="%d",
            help="Only videos with at least this many views will be downloaded.",
            key="threshold_input",
        )

        # Human-readable threshold preview
        st.markdown(
            f"<p style='color:#64748b; font-size:0.78rem; margin:-0.4rem 0 0.8rem;'>"
            f"Threshold: <strong style='color:#818cf8'>{int(threshold):,}</strong> views"
            f"</p>",
            unsafe_allow_html=True,
        )

        # ── Output directory ─────────────────────────────────────────────
        st.markdown("**📂 Output Directory**")
        output_dir = st.text_input(
            label="output_dir",
            label_visibility="collapsed",
            value=DEFAULT_OUTPUT_DIR,
            help="Absolute path where MP4 and TXT files will be saved.",
            key="output_dir_input",
        )

        # Validate the path (non-blocking warning)
        output_path = Path(output_dir) if output_dir else Path(DEFAULT_OUTPUT_DIR)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            st.markdown(
                f"<p style='color:#34d399; font-size:0.75rem; margin:-0.4rem 0 0.8rem;'>"
                f"✅ Folder ready</p>",
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown(
                f"<p style='color:#f87171; font-size:0.75rem; margin:-0.4rem 0 0.8rem;'>"
                f"⚠️ Cannot create this path</p>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Quality note ─────────────────────────────────────────────────
        st.markdown(
            """
            <div class="info-box">
            <strong>Video format:</strong> MP4 video using yt-dlp and ffmpeg.<br><br>
            <strong>Transcript order:</strong>
            <ol style="margin:0.3rem 0 0; padding-left:1.2rem;">
              <li>YouTube captions (API)</li>
              <li>Whisper AI (local fallback)</li>
            </ol>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

        # ── Start button ─────────────────────────────────────────────────
        pipeline_running = st.session_state.get("pipeline_running", False)

        start_clicked = st.button(
            label="🚀 Start Download" if not pipeline_running else "⏳ Running…",
            use_container_width=True,
            disabled=pipeline_running or not channel_url.strip(),
            key="start_button",
        )

        # ── Reset button (only shown after a run) ─────────────────────────
        if st.session_state.get("pipeline_done") or st.session_state.get("pipeline_error"):
            if st.button("🔄 Reset", use_container_width=True, key="reset_button"):
                _reset_session()
                st.rerun()

        st.divider()

        # ── Instructions ─────────────────────────────────────────────────
        with st.expander("ℹ️ How to use"):
            st.markdown(
                """
                1. Paste a YouTube channel URL above.
                2. Set a minimum view count threshold.
                3. Choose where to save files.
                4. Click **Start Download**.

                The app will:
                - Scan the full channel for video metadata
                - Filter videos by view count
                - Download each MP4 video file
                - Extract transcripts via captions or Whisper AI
                - Show direct MP4 and TXT download buttons for each result
                """
            )

    return channel_url.strip(), int(threshold), start_clicked, str(output_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _reset_session() -> None:
    """Clear all pipeline-related session state keys."""
    keys_to_reset = [
        "pipeline_running", "pipeline_done", "pipeline_error",
        "all_videos", "qualified_videos", "processed_results",
        "current_video_index", "log_messages", "output_dir",
    ]
    for k in keys_to_reset:
        if k in st.session_state:
            del st.session_state[k]
