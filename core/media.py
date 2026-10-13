"""Local media inspection and compositing. No shell interpolation."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable


def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    root = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    matches = sorted(root.glob("Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe")) if root.exists() else []
    return str(matches[-1]) if matches else None


def probe(path: str | Path) -> dict:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("Install ffmpeg and ffprobe before preparing or rendering videos.")
    sibling = Path(ffmpeg).with_name("ffprobe.exe" if Path(ffmpeg).suffix else "ffprobe")
    ffprobe = str(sibling) if sibling.exists() else shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is missing. Install the complete ffmpeg package.")
    result = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f"Cannot read media file: {Path(path).name}")
    data = json.loads(result.stdout)
    data["duration"] = float(data.get("format", {}).get("duration") or 0)
    if data["duration"] <= 0:
        raise RuntimeError(f"Media has no usable duration: {Path(path).name}")
    return data


def has_stream(info: dict, kind: str) -> bool:
    return any(s.get("codec_type") == kind for s in info.get("streams", []))


def _run(args: list[str], output: Path, duration: float = 0,
         progress: Callable[[float], None] | None = None) -> None:
    """Capture stderr on disk to avoid pipe deadlock during long renders."""
    with tempfile.TemporaryFile(mode="w+b") as errors:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors, text=True,
                              encoding="utf-8", errors="replace") as process:
            try:
                for line in process.stdout:
                    if progress and duration and line.startswith("out_time_us="):
                        value = line.partition("=")[2].strip()
                        if value.isdigit():
                            progress(min(0.99, int(value) / 1_000_000 / duration))
                code = process.wait()
            except BaseException:
                process.kill()
                process.wait()
                raise
        if code:
            errors.seek(0)
            detail = errors.read().decode("utf-8", errors="replace")[-1600:]
            raise RuntimeError(f"Media processing failed: {detail}")
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("Media processing produced no output.")
    if progress:
        progress(1.0)


def extract_audio(video: Path, output: Path) -> Path:
    if not has_stream(probe(video), "audio"):
        raise RuntimeError("The source video has no audio track.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staged = Path(tmp) / "audio.wav"
        _run([find_ffmpeg(), "-y", "-nostdin", "-v", "error", "-i", str(video),
              "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(staged)], staged)
        staged.replace(output)
    return output


LAYOUTS = {
    "below": "Vertical · face-cam below",
    "overlay": "Vertical · face-cam overlay",
    "beside": "Horizontal · face-cam beside",
}


def render_composite(source: Path, narration: Path, facecam: Path, output: Path,
                     layout: str = "below", preview: bool = False,
                     timing: str = "preserve", loop_facecam: bool = False,
                     progress: Callable[[float], None] | None = None) -> Path:
    """Mute both video inputs. Narration is the only output audio.

    Preserve mode keeps source speed and full narration, holding the last frame
    when narration is longer. Fit mode adjusts source speed to narration length.
    Face-cam holds its final frame unless looping was explicitly selected.
    """
    if layout not in LAYOUTS or timing not in {"preserve", "fit"}:
        raise ValueError("Unknown layout or timing option.")
    src, voice, face = probe(source), probe(narration), probe(facecam)
    if not has_stream(src, "video") or not has_stream(face, "video") or not has_stream(voice, "audio"):
        raise ValueError("Choose a source video, a face-cam video, and an audio voiceover.")
    duration = max(src["duration"], voice["duration"]) if timing == "preserve" else voice["duration"]
    factor = duration / src["duration"] if timing == "fit" else 1
    scale = 0.5 if preview else 1
    w, h = ((1920, 1080) if layout == "beside" else (1080, 1920))
    w, h = int(w * scale), int(h * scale)
    def px(n): return int(n * scale) // 2 * 2
    if layout == "below":
        sw, sh, sx, sy = px(1000), px(1040), px(40), px(440)
        fw, fh, fx, fy = px(1000), px(360), px(40), px(1520)
    elif layout == "overlay":
        sw, sh, sx, sy = w, h, 0, 0
        fw, fh, fx, fy = px(340), px(440), px(700), px(1440)
    else:
        sw, sh, sx, sy = px(1400), px(1000), px(40), px(40)
        fw, fh, fx, fy = px(400), px(520), px(1480), px(280)
    filters = (
        f"color=c=0x0d0d1a:s={w}x{h}:r=30:d={duration}[bg];"
        f"[0:v]setpts={factor}*(PTS-STARTPTS),fps=30,"
        f"scale={sw}:{sh}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1,"
        f"pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2:color=0x0d0d1a,"
        f"tpad=stop_mode=clone:stop_duration={duration}[src];"
        f"[1:v]setpts=PTS-STARTPTS,fps=30,"
        f"scale={fw}:{fh}:force_original_aspect_ratio=increase:force_divisible_by=2,"
        f"crop={fw}:{fh},setsar=1,tpad=stop_mode=clone:stop_duration={duration}[face];"
        f"[bg][src]overlay={sx}:{sy}:eof_action=repeat[base];"
        f"[base][face]overlay={fx}:{fy}:eof_action=repeat,format=yuv420p[v];"
        f"[2:a]asetpts=PTS-STARTPTS,apad,atrim=duration={duration}[a]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staged = Path(tmp) / "render.mp4"
        args = [find_ffmpeg(), "-y", "-nostdin", "-v", "error", "-i", str(source)]
        if loop_facecam:
            args += ["-stream_loop", "-1"]
        args += ["-i", str(facecam), "-i", str(narration), "-filter_complex", filters,
                 "-map", "[v]", "-map", "[a]", "-t", str(duration), "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "25" if preview else "20", "-c:a", "aac",
                 "-b:a", "192k", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(staged)]
        _run(args, staged, duration, progress)
        result = probe(staged)
        if not has_stream(result, "video") or not has_stream(result, "audio"):
            raise RuntimeError("Rendered file is missing video or audio.")
        staged.replace(output)
    return output
