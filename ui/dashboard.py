"""
=============================================================================
ui/dashboard.py
=============================================================================
Main dashboard panel displayed to the right of the sidebar.

Sections:
  1. Welcome / idle state – shown before any run starts.
  2. Scanning state – channel being scanned.
  3. Processing state – live progress while videos are downloading.
  4. Results panel – cards for each processed video + direct download buttons.
  5. Log console – collapsible scrollable real-time console.
=============================================================================
"""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from core.pipeline import run_pipeline, ProcessedVideo


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _views_color(views: int) -> str:
    if views >= 10_000_000:
        return "#f59e0b"   # gold
    if views >= 1_000_000:
        return "#818cf8"   # indigo
    return "#64748b"       # grey


def _fmt_views(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "?"
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def _push_log(msg: str) -> None:
    """Append a message to the session-state log list."""
    st.session_state.setdefault("log_messages", [])
    st.session_state["log_messages"].append(msg)


def _render_log_console() -> None:
    """Render the live log console as an expander."""
    logs = st.session_state.get("log_messages", [])
    if not logs:
        return

    with st.expander("📋 Live Log Console", expanded=False):
        lines_html = ""
        for line in logs[-300:]:  # cap to last 300 lines to keep DOM light
            if any(x in line for x in ["✅", "COMPLETE", "saved"]):
                css_class = "log-success"
            elif any(x in line for x in ["❌", "error", "Error", "failed"]):
                css_class = "log-error"
            elif any(x in line for x in ["⚠️", "warn", "Warn"]):
                css_class = "log-warn"
            elif any(x in line for x in ["STEP", "PIPELINE", "===", "──"]):
                css_class = "log-info"
            else:
                css_class = ""
            safe_line = (
                line.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
            )
            lines_html += f'<p class="log-line {css_class}">{safe_line}</p>'

        st.markdown(
            f'<div class="log-console">{lines_html}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Video result card
# ---------------------------------------------------------------------------


def _read_file_bytes(path: Path | None) -> bytes | None:
    if not path or not path.exists() or not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_transcript_text(path: Path | None, max_chars: int = 60_000) -> str:
    if not path or not path.exists() or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Could not read transcript: {exc}"

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars].rstrip()
        + "\n\n[Transcript preview truncated in the app. Use Download TXT for the full file.]"
    )


def _render_video_card(result: ProcessedVideo, key_prefix: str) -> None:
    """Render a styled card for one processed video."""
    if result.success:
        card_class = "success"
        status_emoji = "✅"
    elif result.partial:
        card_class = "partial"
        status_emoji = "⚠️"
    else:
        card_class = "failed"
        status_emoji = "❌"

    # Build badge HTML
    video_badge = (
        '<span class="vc-badge badge-video">MP4</span>'
        if result.video_path
        else '<span class="vc-badge badge-missing">No MP4</span>'
    )
    txt_badge = (
        '<span class="vc-badge badge-txt">📄 TXT</span>'
        if result.transcript_path
        else '<span class="vc-badge badge-missing">📄 No TXT</span>'
    )

    views_color = _views_color(result.view_count)
    views_str = _fmt_views(result.view_count)

    error_html = ""
    if result.video_error:
        safe = result.video_error.replace("<", "&lt;").replace(">", "&gt;")
        error_html += f'<p style="color:#f87171;font-size:0.74rem;margin:0.3rem 0 0;">📹 Error: {safe}</p>'
    if result.transcript_error:
        safe = result.transcript_error.replace("<", "&lt;").replace(">", "&gt;")
        error_html += f'<p style="color:#f87171;font-size:0.74rem;margin:0.2rem 0 0;">📄 Error: {safe}</p>'

    st.markdown(
        f"""
        <div class="video-card {card_class}">
            <div class="vc-title">{status_emoji} {result.title}</div>
            <div class="vc-meta">
                <span style="color:{views_color}; font-weight:600;">{views_str} views</span>
                &nbsp;·&nbsp;
                <a href="{result.url}" target="_blank"
                   style="color:#818cf8; text-decoration:none;">Watch on YouTube ↗</a>
            </div>
            <div style="margin-top:0.5rem;">
                {video_badge}
                {txt_badge}
            </div>
            {error_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_video_card(result: ProcessedVideo, key_prefix: str) -> None:
    """Render a processed video with download controls and transcript text."""
    if result.success:
        card_class = "success"
        status = "Complete"
    elif result.partial:
        card_class = "partial"
        status = "Partial"
    else:
        card_class = "failed"
        status = "Failed"

    video_badge = (
        '<span class="vc-badge badge-video">MP4 ready</span>'
        if result.video_path
        else '<span class="vc-badge badge-missing">No MP4</span>'
    )
    txt_badge = (
        '<span class="vc-badge badge-txt">Transcript ready</span>'
        if result.transcript_path
        else '<span class="vc-badge badge-missing">No transcript</span>'
    )

    views_color = _views_color(result.view_count)
    views_str = _fmt_views(result.view_count)
    safe_title = html.escape(result.title)
    safe_url = html.escape(result.url, quote=True)

    error_html = ""
    if result.video_error:
        error_html += (
            '<p style="color:#f87171;font-size:0.74rem;margin:0.3rem 0 0;">'
            f"Video error: {html.escape(result.video_error)}</p>"
        )
    if result.transcript_error:
        error_html += (
            '<p style="color:#f87171;font-size:0.74rem;margin:0.2rem 0 0;">'
            f"Transcript error: {html.escape(result.transcript_error)}</p>"
        )

    st.markdown(
        f"""
        <div class="video-card {card_class}">
            <div class="vc-title">{status} - {safe_title}</div>
            <div class="vc-meta">
                <span style="color:{views_color}; font-weight:600;">{views_str} views</span>
                &nbsp;Â·&nbsp;
                <a href="{safe_url}" target="_blank"
                   style="color:#818cf8; text-decoration:none;">Watch on YouTube</a>
            </div>
            <div style="margin-top:0.5rem;">
                {video_badge}
                {txt_badge}
            </div>
            {error_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 2], vertical_alignment="top")
    stable_id = result.video_id or str(abs(hash(result.url)))
    base_key = f"{key_prefix}_{stable_id}"

    with left:
        video_path = result.video_path if result.video_path and result.video_path.suffix.lower() == ".mp4" else None
        video_bytes = _read_file_bytes(video_path)
        if video_bytes and video_path:
            st.download_button(
                label="Download MP4",
                data=video_bytes,
                file_name=video_path.name,
                mime="video/mp4",
                use_container_width=True,
                key=f"video_download_{base_key}",
            )
        else:
            st.button(
                "MP4 unavailable",
                disabled=True,
                use_container_width=True,
                key=f"video_unavailable_{base_key}",
            )

        transcript_bytes = _read_file_bytes(result.transcript_path)
        if transcript_bytes and result.transcript_path:
            st.download_button(
                label="Download TXT",
                data=transcript_bytes,
                file_name=result.transcript_path.name,
                mime="text/plain",
                use_container_width=True,
                key=f"transcript_download_{base_key}",
            )
        else:
            st.button(
                "TXT unavailable",
                disabled=True,
                use_container_width=True,
                key=f"transcript_unavailable_{base_key}",
            )

    with right:
        transcript_text = _read_transcript_text(result.transcript_path)
        if transcript_text:
            st.text_area(
                label="Transcript",
                value=transcript_text,
                height=220,
                disabled=True,
                key=f"transcript_text_{base_key}",
            )
        else:
            st.info("Transcript will appear here after it is generated.")


# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------

def _render_metrics(all_count: int, qualified_count: int, results: list[ProcessedVideo]) -> None:
    success = sum(1 for r in results if r.success)
    partial = sum(1 for r in results if r.partial and not r.success)
    failed = len(results) - success - partial

    cols = st.columns(5)
    data = [
        (str(all_count),       "Total Videos"),
        (str(qualified_count), "Qualified"),
        (str(success),         "✅ Complete"),
        (str(partial),         "⚠️ Partial"),
        (str(failed),          "❌ Failed"),
    ]
    for col, (val, label) in zip(cols, data):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="value">{val}</div>
                    <div class="label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Public render function
# ---------------------------------------------------------------------------

def render_dashboard(
    channel_url: str,
    threshold: int,
    start_clicked: bool,
    output_dir: str,
) -> None:
    """
    Render the main dashboard panel.

    This function is the central controller: it handles triggering the
    pipeline, displaying progress, and showing results.
    """

    # ── Trigger pipeline when Start is clicked ──────────────────────────────
    if start_clicked and channel_url:
        # Reset any previous run
        st.session_state["pipeline_running"] = True
        st.session_state["pipeline_done"] = False
        st.session_state["pipeline_error"] = None
        st.session_state["all_videos"] = []
        st.session_state["qualified_videos"] = []
        st.session_state["processed_results"] = []
        st.session_state["log_messages"] = []
        st.session_state["output_dir"] = output_dir
        st.session_state["current_video_index"] = 0

        # ── Run pipeline synchronously in the Streamlit thread ───────────
        # (Streamlit isn't truly async – we update state and rerun after done)
        progress_placeholder = st.empty()
        status_placeholder = st.empty()

        def _on_progress(msg: str) -> None:
            _push_log(msg)

        def _on_video_done(result: ProcessedVideo) -> None:
            st.session_state["processed_results"].append(result)
            st.session_state["current_video_index"] += 1

        try:
            with st.spinner("🔍 Scanning channel and processing videos…"):
                all_videos, qualified_videos, results = run_pipeline(
                    channel_url=channel_url,
                    threshold=threshold,
                    output_dir=output_dir,
                    progress_callback=_on_progress,
                    video_done_callback=_on_video_done,
                )

            st.session_state["all_videos"] = all_videos
            st.session_state["qualified_videos"] = qualified_videos
            st.session_state["processed_results"] = results
            st.session_state["pipeline_done"] = True

        except Exception as exc:
            st.session_state["pipeline_error"] = str(exc)
            _push_log(f"❌ Fatal pipeline error: {exc}")
        finally:
            st.session_state["pipeline_running"] = False

        st.rerun()

    # ── Display idle / result states ────────────────────────────────────────
    pipeline_running = st.session_state.get("pipeline_running", False)
    pipeline_done = st.session_state.get("pipeline_done", False)
    pipeline_error = st.session_state.get("pipeline_error")

    # ── Error state ──────────────────────────────────────────────────────────
    if pipeline_error:
        st.error(f"**Pipeline Error:** {pipeline_error}")
        _render_log_console()
        return

    # ── Running state ─────────────────────────────────────────────────────────
    if pipeline_running:
        st.info("⏳ Pipeline is running… Please wait.")
        _render_log_console()
        return

    # ── Idle (no run yet) ──────────────────────────────────────────────────────
    if not pipeline_done:
        _render_welcome()
        return

    # ── Results ────────────────────────────────────────────────────────────────
    all_videos = st.session_state.get("all_videos", [])
    qualified_videos = st.session_state.get("qualified_videos", [])
    results: list[ProcessedVideo] = st.session_state.get("processed_results", [])
    out_dir = st.session_state.get("output_dir", output_dir)

    # Metrics
    st.markdown('<div class="section-header">📊 Summary</div>', unsafe_allow_html=True)
    _render_metrics(len(all_videos), len(qualified_videos), results)

    st.divider()

    # Video result cards
    if results:
        st.markdown('<div class="section-header">🎬 Processed Videos</div>', unsafe_allow_html=True)

        # Filter tabs
        tab_all, tab_ok, tab_warn, tab_fail = st.tabs(
            ["All", "✅ Complete", "⚠️ Partial", "❌ Failed"]
        )

        with tab_all:
            for r in results:
                _render_video_card(r, "all")

        with tab_ok:
            ok = [r for r in results if r.success]
            if ok:
                for r in ok:
                    _render_video_card(r, "ok")
            else:
                st.info("No fully successful videos.")

        with tab_warn:
            warn = [r for r in results if r.partial and not r.success]
            if warn:
                for r in warn:
                    _render_video_card(r, "warn")
            else:
                st.info("No partial results.")

        with tab_fail:
            fail = [r for r in results if not r.partial]
            if fail:
                for r in fail:
                    _render_video_card(r, "fail")
            else:
                st.success("No failures! 🎉")

    elif qualified_videos:
        st.warning(
            "Qualified videos were found but none were successfully processed. "
            "Check the log console for details."
        )
    else:
        st.info(
            f"No videos with ≥ {threshold:,} views were found on this channel. "
            "Try lowering the threshold."
        )

    # Log console (always shown after a run)
    st.divider()
    _render_log_console()


# ---------------------------------------------------------------------------
# Welcome / idle screen
# ---------------------------------------------------------------------------

def _render_welcome() -> None:
    """Render the splash / welcome screen shown before any pipeline run."""
    st.markdown(
        """
        <div style="text-align:center; padding: 3rem 1rem;">
            <div style="font-size:5rem; margin-bottom:1rem;
                        filter: drop-shadow(0 0 24px rgba(99,102,241,0.6));">🎬</div>
            <h2 style="font-size:1.8rem; font-weight:700;
                       background: linear-gradient(90deg, #818cf8, #c084fc, #f472b6);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                       background-clip: text; margin-bottom:0.5rem;">
                YouTube Channel Downloader
            </h2>
            <p style="color:#64748b; max-width:480px; margin:0 auto 2rem; font-size:0.92rem;">
                Enter a channel URL in the sidebar, set a view-count threshold,
                and hit <strong style="color:#818cf8;">Start Download</strong> to begin.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Feature cards
    cols = st.columns(3)
    features = [
        ("🔍", "Smart Scanning", "Fetches full channel metadata without downloading any media first."),
        ("📥", "MP4 Video", "Downloads MP4 video using yt-dlp and ffmpeg conversion."),
        ("📝", "Auto Transcripts", "YouTube captions first; falls back to Whisper AI offline transcription."),
    ]
    for col, (icon, title, desc) in zip(cols, features):
        with col:
            st.markdown(
                f"""
                <div class="metric-card" style="text-align:left; padding:1.2rem;">
                    <div style="font-size:1.8rem; margin-bottom:0.5rem;">{icon}</div>
                    <div style="font-weight:600; color:#e2e8f0; margin-bottom:0.3rem;">{title}</div>
                    <div style="font-size:0.8rem; color:#64748b;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
