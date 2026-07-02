"""
Video download module.

Uses yt-dlp to download a single YouTube video as an MP4 file. The file is
also used by Whisper when YouTube captions are unavailable.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

import yt_dlp

logger = logging.getLogger(__name__)


def _sanitize_filename(title: str, max_length: int = 100) -> str:
    """
    Remove characters that are illegal in Windows / Linux filenames and
    truncate to ``max_length`` characters so paths stay reasonable.
    """
    safe = re.sub(r'[\\/*?:"<>|]', "_", title)
    safe = re.sub(r"[\s_]+", "_", safe).strip("_")
    return safe[:max_length]


def download_video(
    video_url: str,
    output_dir: str | Path,
    sanitized_title: str,
    progress_callback: Callable[[str], None] | None = None,
) -> Path | None:
    """
    Download a YouTube video as MP4 and return the local file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(output_dir / f"{sanitized_title}.%(ext)s")
    expected_mp4 = output_dir / f"{sanitized_title}.mp4"
    last_error: str | None = None

    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    def _progress_hook(d: dict) -> None:
        status = d.get("status", "")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if total:
                pct = downloaded / total * 100
                speed = d.get("_speed_str", "?")
                eta = d.get("_eta_str", "?")
                _log(f"   Down: {pct:.1f}%  speed={speed}  eta={eta}")
        elif status == "finished":
            _log("   Download finished; merging/converting to MP4 if needed.")
        elif status == "error":
            _log("   yt-dlp reported an error during download.")

    ydl_opts = {
        # Pick a progressive/single-file MP4 with both video and audio.
        # This avoids ffmpeg merging, which is not available on this machine.
        "format": (
            "best[ext=mp4][vcodec!=none][acodec!=none]/"
            "best[vcodec!=none][acodec!=none]"
        ),
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "progress_hooks": [_progress_hook],
    }

    _log(f"Starting MP4 video download: {video_url}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except yt_dlp.utils.DownloadError as exc:
        last_error = str(exc)
        _log(f"   DownloadError: {last_error}")
    except Exception as exc:
        last_error = str(exc)
        _log(f"   Unexpected error during download: {last_error}")

    if expected_mp4.exists():
        _log(f"   Saved: {expected_mp4}")
        return expected_mp4

    matches = list(output_dir.glob(f"{sanitized_title}.*"))
    mp4_matches = [f for f in matches if f.suffix.lower() == ".mp4"]
    if mp4_matches:
        _log(f"   Found MP4 at: {mp4_matches[0]}")
        return mp4_matches[0]

    if matches:
        found = ", ".join(f.name for f in matches[:5])
        _log(f"   Expected MP4 not found. Ignoring non-MP4 files: {found}")

    if last_error:
        raise RuntimeError(last_error)

    raise RuntimeError("Download finished but no MP4 file was found.")
