"""Resumable per-video jobs. Credentials never enter saved metadata."""
from __future__ import annotations
import hashlib
import json
import re
import tempfile
from pathlib import Path
from core.downloader import download_video
from core.elevenlabs_client import generate_voiceover, voice_fingerprint
from core.media import probe, has_stream, render_composite
from core.transcriber import generate_transcript


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as file:
        staged = Path(file.name)
        file.write(text)
    try:
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def job_folder(root: Path, video_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Invalid YouTube video ID.")
    return root / video_id


def save_job(folder: Path, job: dict) -> None:
    atomic_text(folder / "job.json", json.dumps(job, ensure_ascii=False, indent=2))


def load_jobs(root: Path) -> list[dict]:
    jobs = []
    for path in sorted(root.glob("*/job.json")) if root.exists() else []:
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            if job_folder(root, job["id"]).resolve() == path.parent.resolve():
                jobs.append(job)
        except (ValueError, KeyError, OSError):
            continue
    return jobs


def artifact(folder: Path, job: dict, key: str) -> Path | None:
    name = job.get(key)
    if not isinstance(name, str) or Path(name).name != name:
        return None
    path = folder / name
    return path if path.is_file() and path.stat().st_size else None


def prepare_video(root: Path, metadata: dict, log=lambda message: None) -> dict:
    folder = job_folder(root, metadata["id"])
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / "job.json"
    job = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {
        "id": metadata["id"], "title": metadata["title"], "url": metadata["url"], "view_count": metadata["view_count"]}
    job["error"] = ""
    try:
        source = artifact(folder, job, "source")
        if source:
            info = probe(source)
            if not has_stream(info, "video") or not has_stream(info, "audio"):
                source = None
        if not source:
            log("Downloading source video…")
            source = download_video(metadata["url"], folder, "source", log)
            job["source"] = source.name
            save_job(folder, job)
        if not artifact(folder, job, "transcript"):
            log("Transcribing source…")
            transcript = generate_transcript(metadata["id"], source, folder, "transcript", progress_callback=log)
            if transcript is None:
                raise RuntimeError("No transcript could be generated. Retry or paste a transcript in the editor.")
            job["transcript"] = transcript.name
            if not artifact(folder, job, "script"):
                atomic_text(folder / "script.txt", transcript.read_text(encoding="utf-8"))
                job["script"] = "script.txt"
        log("Video and transcript ready.")
    except Exception as exc:
        job["error"] = str(exc)
        raise
    finally:
        save_job(folder, job)
    return job


def save_script(folder: Path, job: dict, text: str) -> None:
    if not text.strip():
        raise ValueError("The transcript cannot be empty.")
    prior = artifact(folder, job, "script")
    if not prior or prior.read_text(encoding="utf-8").strip() != text.strip():
        for key in ("voice", "voice_fingerprint", "preview", "final", "preview_signature", "final_signature"):
            job.pop(key, None)
    atomic_text(folder / "script.txt", text.strip() + "\n")
    job.update(script="script.txt", error="")
    save_job(folder, job)


def make_voice(root: Path, job: dict, api_key: str, voice_id: str) -> Path:
    folder = job_folder(root, job["id"])
    script = artifact(folder, job, "script")
    if not script:
        raise ValueError("Save a transcript first.")
    text = script.read_text(encoding="utf-8")
    path = generate_voiceover(text, api_key, voice_id, folder)
    fingerprint = voice_fingerprint(text, voice_id)
    if fingerprint != job.get("voice_fingerprint"):
        for key in ("preview", "final", "preview_signature", "final_signature"):
            job.pop(key, None)
    job.update(voice=path.name, voice_id=voice_id.strip(), voice_fingerprint=fingerprint, error="")
    save_job(folder, job)
    return path


def save_facecam(root: Path, data: bytes, suffix: str) -> Path:
    if suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise ValueError("Upload an MP4, MOV, MKV, or WebM face-cam.")
    folder = root / "facecams"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (hashlib.sha256(data).hexdigest()[:20] + suffix.lower())
    if target.exists():
        return target
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        staged = Path(tmp) / ("upload" + suffix.lower())
        staged.write_bytes(data)
        if not has_stream(probe(staged), "video"):
            raise ValueError("Your face-cam file has no video track.")
        staged.replace(target)
    return target


def render_signature(folder: Path, job: dict, facecam: Path, layout: str, timing: str, loop: bool, preview: bool) -> str:
    parts = [layout, timing, loop, preview, job.get("voice_fingerprint")]
    for path in (artifact(folder, job, "source"), artifact(folder, job, "voice"), facecam):
        if not path or not path.is_file():
            raise ValueError("Prepare the video, generate the voiceover, and choose your face-cam first.")
        stat = path.stat()
        parts.append([str(path.resolve()), stat.st_size, stat.st_mtime_ns])
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:20]


def make_render(root: Path, job: dict, facecam: Path, layout: str, timing: str, loop: bool, preview: bool, progress=None) -> Path:
    folder = job_folder(root, job["id"])
    signature = render_signature(folder, job, facecam, layout, timing, loop, preview)
    key = "preview" if preview else "final"
    previous = artifact(folder, job, key)
    if previous and job.get(key + "_signature") == signature:
        return previous
    target = folder / f"{key}_{signature}.mp4"
    render_composite(artifact(folder, job, "source"), artifact(folder, job, "voice"), facecam,
                     target, layout, preview, timing, loop, progress)
    job.update({key: target.name, key + "_signature": signature, "error": ""})
    save_job(folder, job)
    return target
