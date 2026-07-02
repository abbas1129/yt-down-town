"""
Transcript generation module.

Order:
1. youtube-transcript-api captions
2. yt-dlp subtitles / auto-captions, converted from VTT to plain text
3. Whisper fallback only when ffmpeg is installed
"""

from __future__ import annotations

import html
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import yt_dlp

logger = logging.getLogger(__name__)

_YTDLP_CAPTIONS_RATE_LIMITED = False
_FFMPEG_AVAILABLE: bool | None = None
_FFMPEG_PATH: str | None = None
_WHISPER_MODEL = None
_WHISPER_MODEL_NAME = "tiny"


def _clean_transcript_text(raw: str) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", raw.strip())
    return cleaned + "\n"


def _vtt_to_plain_text(raw: str) -> str:
    lines: list[str] = []
    previous = ""
    skip_block = False

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            skip_block = False
            continue

        upper = line.upper()
        if upper == "WEBVTT" or upper.startswith(("KIND:", "LANGUAGE:")):
            continue
        if upper.startswith(("NOTE", "STYLE", "REGION")):
            skip_block = True
            continue
        if skip_block or "-->" in line or line.isdigit():
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if line and line != previous:
            lines.append(line)
            previous = line

    return _clean_transcript_text(" ".join(lines)) if lines else ""


def _make_logger(progress_callback: Callable[[str], None] | None) -> Callable[[str], None]:
    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    return _log


def _find_ffmpeg() -> str | None:
    path = shutil.which("ffmpeg")
    if path:
        return path

    winget_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if winget_root.exists():
        matches = sorted(winget_root.glob("Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe"))
        if matches:
            return str(matches[-1])

    return None


def _fetch_via_api(
    video_id: str,
    preferred_languages: list[str],
    progress_callback: Callable[[str], None] | None,
) -> str | None:
    _log = _make_logger(progress_callback)
    _log("   [Stage 1] Fetching captions via youtube-transcript-api...")

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        _log("   youtube-transcript-api is not installed.")
        return None

    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        transcript = None

        for lang in preferred_languages:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                _log(f"   Found manual transcript ({lang}).")
                break
            except Exception:
                pass

        if transcript is None:
            for lang in preferred_languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    _log(f"   Found auto-generated transcript ({lang}).")
                    break
                except Exception:
                    pass

        if transcript is None:
            available = list(transcript_list)
            if available:
                transcript = available[0]
                _log(f"   Using first available transcript language: {transcript.language_code}")

        if transcript is None:
            _log("   No transcript found via API.")
            return None

        lines: list[str] = []
        for seg in transcript.fetch():
            text = seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
            if text:
                lines.append(text)

        full_text = " ".join(lines)
        _log(f"   Transcript fetched via API: {len(lines)} segments.")
        return _clean_transcript_text(full_text) if full_text.strip() else None
    except Exception as exc:
        _log(f"   youtube-transcript-api failed: {exc}")
        return None


def _fetch_via_ytdlp(
    video_id: str,
    preferred_languages: list[str],
    progress_callback: Callable[[str], None] | None,
) -> str | None:
    global _YTDLP_CAPTIONS_RATE_LIMITED

    _log = _make_logger(progress_callback)
    if _YTDLP_CAPTIONS_RATE_LIMITED:
        _log("   Skipping yt-dlp captions: caption requests were rate-limited earlier in this run.")
        return None

    _log("   [Stage 2] Fetching captions via yt-dlp...")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    subtitle_langs = list(dict.fromkeys(preferred_languages + ["en.*", "en"]))

    with tempfile.TemporaryDirectory() as tmp_dir:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": subtitle_langs,
            "subtitlesformat": "vtt",
            "outtmpl": str(Path(tmp_dir) / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as exc:
            message = str(exc)
            if "429" in message or "Too Many Requests" in message:
                _YTDLP_CAPTIONS_RATE_LIMITED = True
                _log("   yt-dlp captions are rate-limited; skipping this method for remaining videos.")
            else:
                _log(f"   yt-dlp captions failed: {message}")
            return None

        for caption_file in sorted(Path(tmp_dir).glob(f"{video_id}*.vtt")):
            try:
                text = _vtt_to_plain_text(caption_file.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                _log(f"   Could not read caption file {caption_file.name}: {exc}")
                continue

            if text.strip():
                _log(f"   Captions fetched via yt-dlp: {caption_file.name}")
                return text

        _log("   No usable yt-dlp captions found.")
        return None


def _extract_audio_from_video(video_path: Path, audio_path: Path) -> bool:
    try:
        ffmpeg_path = _find_ffmpeg()
        if ffmpeg_path is None:
            logger.error("ffmpeg not found; cannot extract audio for Whisper.")
            return False

        result = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(audio_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.error(f"Audio extraction failed: {exc}")
        return False


def _transcribe_via_whisper(
    video_path: Path,
    progress_callback: Callable[[str], None] | None,
) -> str | None:
    global _FFMPEG_AVAILABLE, _FFMPEG_PATH, _WHISPER_MODEL

    _log = _make_logger(progress_callback)
    if _FFMPEG_AVAILABLE is None:
        _FFMPEG_PATH = _find_ffmpeg()
        _FFMPEG_AVAILABLE = _FFMPEG_PATH is not None

    if not _FFMPEG_AVAILABLE:
        _log("   Skipping Whisper fallback: ffmpeg is not installed.")
        return None

    try:
        import whisper
    except ImportError:
        _log("   openai-whisper is not installed; cannot generate AI transcript.")
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / "audio.wav"
        if not _extract_audio_from_video(video_path, audio_path) or not audio_path.exists():
            _log("   Audio extraction failed; cannot run Whisper.")
            return None

        try:
            if _WHISPER_MODEL is None:
                _log(f"   Loading Whisper model ({_WHISPER_MODEL_NAME})...")
                _WHISPER_MODEL = whisper.load_model(_WHISPER_MODEL_NAME)

            _log("   Running Whisper transcription...")
            result = _WHISPER_MODEL.transcribe(str(audio_path), fp16=False)
            text = result.get("text", "").strip()
            return _clean_transcript_text(text) if text else None
        except Exception as exc:
            _log(f"   Whisper transcription failed: {exc}")
            return None


def generate_transcript(
    video_id: str,
    video_path: Path | None,
    output_dir: str | Path,
    sanitized_title: str,
    preferred_languages: list[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> Path | None:
    if preferred_languages is None:
        preferred_languages = ["en", "en-US", "en-GB", "es"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = output_dir / f"{sanitized_title}.txt"
    _log = _make_logger(progress_callback)

    _log(f"Generating transcript for video ID: {video_id}")

    text = _fetch_via_api(video_id, preferred_languages, progress_callback)
    if text is None:
        text = _fetch_via_ytdlp(video_id, preferred_languages, progress_callback)
    if text is None and video_path and video_path.exists():
        text = _transcribe_via_whisper(video_path, progress_callback)
    elif text is None:
        _log("   No video file available for Whisper fallback.")

    if text is None:
        _log("   All transcript methods failed.")
        return None

    try:
        txt_path.write_text(text, encoding="utf-8")
        _log(f"   Transcript saved: {txt_path}")
        return txt_path
    except OSError as exc:
        _log(f"   Failed to write transcript file: {exc}")
        return None
