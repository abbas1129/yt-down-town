"""
=============================================================================
core/pipeline.py
=============================================================================
The main processing pipeline.

Orchestrates: scan → filter → (for each video) download + transcribe.
Designed to be run inside a ``concurrent.futures.ThreadPoolExecutor`` or
directly from the Streamlit main thread (sequential mode).

All external side-effects are reported via a ``progress_callback`` so the
Streamlit UI can display real-time updates without polling.
=============================================================================
"""

from __future__ import annotations

import dataclasses
import logging
import re
from pathlib import Path
from typing import Callable, List

from core.scanner import scan_channel
from core.downloader import download_video, _sanitize_filename
from core.transcriber import generate_transcript

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ProcessedVideo:
    """Holds the outcome of processing one video."""
    video_id: str
    title: str
    view_count: int
    url: str

    # Outcomes
    video_path: Path | None = None   # Path to downloaded MP4 video (or None)
    transcript_path: Path | None = None  # Path to .txt file (or None)
    video_error: str | None = None       # Error message if download failed
    transcript_error: str | None = None  # Error message if transcript failed

    @property
    def success(self) -> bool:
        """True only if BOTH the video and transcript were produced."""
        return (
            self.video_path is not None
            and self.video_path.suffix.lower() == ".mp4"
            and self.transcript_path is not None
        )

    @property
    def partial(self) -> bool:
        """True if at least one output was produced."""
        has_video = self.video_path is not None and self.video_path.suffix.lower() == ".mp4"
        return has_video or self.transcript_path is not None


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    channel_url: str,
    threshold: int,
    output_dir: str | Path,
    progress_callback: Callable[[str], None] | None = None,
    video_done_callback: Callable[[ProcessedVideo], None] | None = None,
) -> tuple[list[dict], list[dict], list[ProcessedVideo]]:
    """
    End-to-end pipeline: scan → filter → download + transcribe.

    Parameters
    ----------
    channel_url : str
        YouTube channel / playlist URL.
    threshold : int
        Minimum view count required for a video to be processed.
    output_dir : str | Path
        Root directory where MP4s and TXTs will be stored.
    progress_callback : callable, optional
        Called with a human-readable string for every significant event.
    video_done_callback : callable, optional
        Called with a ``ProcessedVideo`` immediately after each video is
        fully processed (useful for incremental UI updates).

    Returns
    -------
    all_videos : list[dict]
        Every video's metadata from the channel.
    qualified_videos : list[dict]
        The filtered subset that met the view threshold.
    results : list[ProcessedVideo]
        Processing outcomes, one entry per qualified video.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    # ── Step 1: Scan channel ────────────────────────────────────────────────
    _log("=" * 60)
    _log("STEP 1: Scanning channel for video metadata")
    _log("=" * 60)

    all_videos, qualified_videos = scan_channel(
        channel_url=channel_url,
        threshold=threshold,
        progress_callback=progress_callback,
    )

    if not qualified_videos:
        _log(
            f"⚠️  No videos found with ≥ {threshold:,} views. "
            "Try lowering the view count threshold."
        )
        return all_videos, qualified_videos, []

    _log(f"\n📋 Will process {len(qualified_videos)} video(s).\n")

    # ── Step 2: Process each qualified video ────────────────────────────────
    results: list[ProcessedVideo] = []

    for idx, video_meta in enumerate(qualified_videos, start=1):
        video_id = video_meta["id"]
        title = video_meta["title"]
        view_count = video_meta["view_count"]
        url = video_meta["url"]

        _log("─" * 60)
        _log(
            f"[{idx}/{len(qualified_videos)}] Processing: {title}\n"
            f"   URL: {url}\n"
            f"   Views: {view_count:,}"
        )
        _log("─" * 60)

        # Sanitize the title for safe filesystem use
        sanitized = _sanitize_filename(title, max_length=80) + "_" + video_id

        result = ProcessedVideo(
            video_id=video_id,
            title=title,
            view_count=view_count,
            url=url,
        )

        # ── 2a: Download video ──────────────────────────────────────────
        _log(f"\n[{idx}] Downloading video…")
        try:
            video_path = download_video(
                video_url=url,
                output_dir=output_dir,
                sanitized_title=sanitized,
                progress_callback=progress_callback,
            )
            if video_path:
                result.video_path = video_path
                _log(f"[{idx}] ✅ Video saved: {video_path.name}")
            else:
                result.video_error = "Download returned no file path."
                _log(f"[{idx}] ❌ Video download failed (no file produced).")
        except Exception as exc:
            result.video_error = str(exc)
            _log(f"[{idx}] ❌ Video download exception: {exc}")

        # ── 2b: Generate transcript ─────────────────────────────────────
        _log(f"\n[{idx}] Generating transcript…")
        try:
            txt_path = generate_transcript(
                video_id=video_id,
                video_path=result.video_path,  # may be None if download failed
                output_dir=output_dir,
                sanitized_title=sanitized,
                progress_callback=progress_callback,
            )
            if txt_path:
                result.transcript_path = txt_path
                _log(f"[{idx}] ✅ Transcript saved: {txt_path.name}")
            else:
                result.transcript_error = "All transcript methods failed."
                _log(f"[{idx}] ❌ Transcript generation failed.")
        except Exception as exc:
            result.transcript_error = str(exc)
            _log(f"[{idx}] ❌ Transcript exception: {exc}")

        results.append(result)

        # Notify the UI that this video is done
        if video_done_callback:
            video_done_callback(result)

        _log("")

    # ── Summary ─────────────────────────────────────────────────────────────
    full_success = sum(1 for r in results if r.success)
    partial = sum(1 for r in results if r.partial and not r.success)
    failed = len(results) - full_success - partial

    _log("=" * 60)
    _log("PIPELINE COMPLETE")
    _log(f"  ✅ Fully processed : {full_success}")
    _log(f"  ⚠️  Partial output  : {partial}")
    _log(f"  ❌ Failed          : {failed}")
    _log(f"  📂 Output folder   : {output_dir}")
    _log("=" * 60)

    return all_videos, qualified_videos, results
