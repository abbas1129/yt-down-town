"""
Shorts channel scanning and metadata extraction via yt-dlp.

This module scans public YouTube Shorts only. It returns all public Shorts it
can discover plus the subset whose view count meets the user threshold.
"""

from __future__ import annotations

import logging
from typing import Callable
from urllib.parse import urlparse, urlunparse

import yt_dlp

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
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    if "youtube.com" not in host or not _is_youtube_channel_path(path):
        return url

    for suffix in ("/videos", "/shorts", "/streams", "/featured"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break

    return urlunparse(parsed._replace(path=f"{path}/shorts", query="", fragment=""))


def _scan_url_candidates(channel_url: str) -> list[str]:
    """Try the Shorts tab first, then the original URL for playlists/direct tabs."""
    original = channel_url.strip()
    shorts_url = _shorts_tab_url(original)
    candidates = [shorts_url]
    if original not in candidates:
        candidates.append(original)
    return candidates


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
    missing = [video for video in videos if not video.get("view_count")]
    if not missing:
        return videos

    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    _log(f"   Fetching details for {len(missing)} Short(s) with missing view counts...")
    detail_opts = {
        "quiet": True,
        "no_warnings": True,
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

            video["view_count"] = detail.get("view_count") or 0
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
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": True,
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
                    _log(f"   Scan failed for this URL: {exc}")
                    continue

                entries = _flatten_entries((info or {}).get("entries", []))
                if entries:
                    used_url = candidate_url
                    break

        if not entries:
            _log("   No public Shorts were found for this channel.")
            return [], []

        _log(f"   Found {len(entries)} public Short entries from: {used_url}")

        for entry in entries:
            video_id = entry.get("id", "")
            video_meta: VideoMeta = {
                "id": video_id,
                "url": _video_url_from_entry(entry),
                "title": entry.get("title", "Untitled"),
                "view_count": entry.get("view_count") or 0,
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

    all_videos.sort(key=lambda v: v["view_count"], reverse=True)
    qualified = [v for v in all_videos if v["view_count"] >= threshold]

    _log(f"Total public Shorts discovered: {len(all_videos)}")
    _log(f"Shorts meeting threshold ({threshold:,} views): {len(qualified)}")

    return all_videos, qualified
