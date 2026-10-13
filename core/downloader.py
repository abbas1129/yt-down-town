"""
Video download module.

Uses yt-dlp to download a single YouTube video as an MP4 file. The file is
also used by Whisper when YouTube captions are unavailable.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Callable

import yt_dlp
from core.media import find_ffmpeg, has_stream, probe
from core.youtube import youtube_options

logger = logging.getLogger(__name__)


def _sanitize_filename(title: str, max_length: int = 100) -> str:
    """
    Remove characters that are illegal in Windows / Linux filenames and
    truncate to ``max_length`` characters so paths stay reasonable.
    """
    safe = re.sub(r'[\\/*?:"<>|]', "_", title)
    safe = re.sub(r"[\s_]+", "_", safe).strip("_")
    safe = safe[:max_length].strip(". ") or "video"
    if safe.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1,10)], *[f"LPT{i}" for i in range(1,10)]}:
        safe = "_" + safe
    return safe


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

    sanitized_title = _sanitize_filename(sanitized_title)
    expected_mp4 = output_dir / f"{sanitized_title}.mp4"

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

    if not find_ffmpeg():
        raise RuntimeError("Install ffmpeg to download and merge high-quality MP4 videos.")
    ydl_opts = {
        **youtube_options(),
        "format": (
            "bestvideo[ext=mp4][height<=1920][width<=1920]+bestaudio[ext=m4a]/"
            "best[ext=mp4][vcodec!=none][acodec!=none]"
        ),
        "merge_output_format": "mp4",
        "ignoreerrors": False,
        "noplaylist": True,
        "noprogress": True,
        "progress_hooks": [_progress_hook],
    }

    _log(f"Starting MP4 video download: {video_url}")

    with tempfile.TemporaryDirectory(dir=output_dir) as tmp:
        ydl_opts["outtmpl"] = str(Path(tmp) / "source.%(ext)s")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            code = ydl.download([video_url])
        staged = Path(tmp) / "source.mp4"
        if code or not staged.exists():
            raise RuntimeError("Download failed to produce an MP4. Existing files were preserved.")
        info = probe(staged)
        if not has_stream(info, "video") or not has_stream(info, "audio"):
            raise RuntimeError("The downloaded MP4 is missing video or audio.")
        staged.replace(expected_mp4)
    _log(f"Saved: {expected_mp4.name}")
    return expected_mp4
