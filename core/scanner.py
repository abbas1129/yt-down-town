"""
Shorts channel scanning and metadata extraction via yt-dlp.

This module scans public YouTube Shorts only. It returns all public Shorts it
can discover plus the subset whose view count meets the user threshold.
"""

from __future__ import annotations

import logging
import re
from typing import Callable
from urllib.parse import urlparse, urlunparse

import yt_dlp
from core.youtube import youtube_options

logger = logging.getLogger(__name__)

VideoMeta = dict


def _is_youtube_channel_path(path: str) -> bool:
    return (
        path.startswith("/@")
        or path.startswith("/channel/")
        or path.startswith("/c/")
        or path.startswith("/user/")
    )


def _shorts_tab_url(channel_url: str) -> str:
    """Return the Shorts tab for a YouTube channel-like URL."""
    url = channel_url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")

    if parsed.scheme not in {"https", "http"} or host not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        raise ValueError("Paste a full YouTube channel link, such as https://www.youtube.com/@handle.")

    for suffix in ("/videos", "/shorts", "/streams", "/featured"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break

    if not re.fullmatch(r"/(?:@[^/]+|(?:channel|c|user)/[^/]+)", path):
        raise ValueError("Use a channel link, not a video or playlist link.")
    return urlunparse(parsed._replace(scheme="https", netloc="www.youtube.com", path=f"{path}/shorts", query="", fragment=""))


def _scan_url_candidates(channel_url: str) -> list[str]:
    """Never fall back to long videos when a Shorts tab is empty."""
    return [_shorts_tab_url(channel_url)]


def _flatten_entries(entries: list) -> list:
    """Flatten nested YouTube tab/playlist entries into video entries."""
    flattened: list = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue

        nested = entry.get("entries")
        if nested:
            flattened.extend(_flatten_entries(nested))
            continue

        video_id = entry.get("id") or ""
        url = entry.get("url") or entry.get("webpage_url") or ""
        is_video_id = isinstance(video_id, str) and len(video_id) == 11
        is_video_url = isinstance(url, str) and (
            len(url) == 11 or "watch?v=" in url or "/shorts/" in url
        )
        if is_video_id or is_video_url:
            flattened.append(entry)

    return flattened


def _video_url_from_entry(entry: dict) -> str:
    video_id = entry.get("id", "")
    raw_url = entry.get("webpage_url") or entry.get("url") or ""

    if isinstance(raw_url, str) and raw_url.startswith("http"):
        return raw_url
    if isinstance(raw_url, str) and len(raw_url) == 11:
        return f"https://www.youtube.com/shorts/{raw_url}"
    if video_id:
        return f"https://www.youtube.com/shorts/{video_id}"
    return raw_url


def _fill_missing_short_details(
    videos: list[VideoMeta],
    progress_callback: Callable[[str], None] | None = None,
) -> list[VideoMeta]:
    """Fetch full metadata for Shorts whose flat entries lack view counts."""
    missing = [video for video in videos if video.get("view_count") is None]
    if not missing:
        return videos

    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    _log(f"   Fetching details for {len(missing)} Short(s) with missing view counts...")
    detail_opts = {
        **youtube_options(),
        "skip_download": True,
        "ignoreerrors": True,
    }

    with yt_dlp.YoutubeDL(detail_opts) as ydl:
        for index, video in enumerate(missing, start=1):
            try:
                detail = ydl.extract_info(video["url"], download=False)
            except Exception as exc:
                _log(f"   Detail fetch failed for {video.get('id', 'unknown')}: {exc}")
                continue

            if not detail:
                continue

            video["view_count"] = detail.get("view_count")
            video["duration"] = detail.get("duration") or video.get("duration")
            video["upload_date"] = detail.get("upload_date") or video.get("upload_date")
            video["thumbnail"] = detail.get("thumbnail") or video.get("thumbnail", "")
            video["channel"] = detail.get("channel") or video.get("channel", "")
            video["description"] = detail.get("description") or video.get("description", "")
            video["title"] = detail.get("title") or video.get("title", "Untitled")

            if index % 10 == 0 or index == len(missing):
                _log(f"   Detail progress: {index}/{len(missing)}")

    return videos


def scan_channel(
    channel_url: str,
    threshold: int,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[VideoMeta], list[VideoMeta]]:
    """
    Scan a public YouTube Shorts channel and return all Shorts plus qualified Shorts.

    Only Shorts that meet the view threshold are returned in qualified_videos.
    The pipeline downloads and transcribes only that qualified subset.
    """

    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    _log(f"Scanning public Shorts channel: {channel_url}")
    _log("   Fetching Shorts metadata only, no media download...")

    ydl_opts = {
        **youtube_options(),
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": False,
        "playlistend": None,
    }

    all_videos: list[VideoMeta] = []

    try:
        info = None
        entries: list[dict] = []
        used_url = ""

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for candidate_url in _scan_url_candidates(channel_url):
                _log(f"   Trying: {candidate_url}")
                try:
                    info = ydl.extract_info(candidate_url, download=False)
                except yt_dlp.utils.DownloadError as exc:
                    raise RuntimeError(f"Could not scan this channel. Check the link or connection: {exc}") from exc

                if info is None:
                    raise RuntimeError("YouTube returned no channel information. Please retry the scan.")

                entries = _flatten_entries((info or {}).get("entries", []))
                if entries:
                    used_url = candidate_url
                    break

        if not entries:
            _log("   No public Shorts were found for this channel.")
            return [], []

        _log(f"   Found {len(entries)} public Short entries from: {used_url}")

        seen = set()
        for entry in entries:
            video_id = entry.get("id", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or video_id in seen:
                continue
            seen.add(video_id)
            video_meta: VideoMeta = {
                "id": video_id,
                "url": _video_url_from_entry(entry),
                "title": entry.get("title", "Untitled"),
                "view_count": entry.get("view_count"),
                "duration": entry.get("duration"),
                "upload_date": entry.get("upload_date"),
                "thumbnail": entry.get("thumbnail", ""),
                "channel": entry.get("channel") or (info or {}).get("channel", ""),
                "description": entry.get("description", ""),
            }
            all_videos.append(video_meta)

        all_videos = _fill_missing_short_details(all_videos, progress_callback)

    except yt_dlp.utils.DownloadError as exc:
        raise RuntimeError(f"yt-dlp download error during Shorts scanning: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Unexpected error while scanning Shorts channel: {exc}") from exc

    all_videos.sort(key=lambda v: v["view_count"] or 0, reverse=True)
    unknown = sum(v["view_count"] is None for v in all_videos)
    if unknown:
        _log(f"Warning: {unknown} Shorts have unknown view counts and are excluded from the filter.")
    qualified = [v for v in all_videos if v["view_count"] is not None and v["view_count"] >= threshold]

    _log(f"Total public Shorts discovered: {len(all_videos)}")
    _log(f"Shorts meeting threshold ({threshold:,} views): {len(qualified)}")

    return all_videos, qualified
