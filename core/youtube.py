"""Shared extraction settings for current YouTube support."""
import shutil
from pathlib import Path
from core.media import find_ffmpeg


def youtube_options() -> dict:
    options = {"quiet": True, "socket_timeout": 25, "retries": 2, "extractor_retries": 2}
    runtimes = {}
    for name in ("deno", "node"):
        path = shutil.which(name)
        if path:
            runtimes[name] = {"path": path}
    if runtimes:
        options["js_runtimes"] = runtimes
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        options["ffmpeg_location"] = str(Path(ffmpeg).parent)
    return options
