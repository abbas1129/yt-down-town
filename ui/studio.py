"""Shorts → transcript → ElevenLabs voice → face-cam composition."""
from __future__ import annotations
import os
import tempfile
import uuid
from pathlib import Path
import streamlit as st
from core.media import LAYOUTS, find_ffmpeg, probe
from core.scanner import scan_channel
from core.workflow import (artifact, job_folder, load_jobs, make_render, make_voice,
                           prepare_video, render_signature, save_facecam, save_script)

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "downloads" / "studio"


def _download(path, label, key, mime):
    with path.open("rb") as file:
        st.download_button(label, file, file_name=path.name, mime=mime, key=key, on_click="ignore")


def _settings():
    with st.sidebar:
        st.title("Shorts Studio")
        st.caption("Discover → prepare → voice → compose")
        if os.getenv("SHORTS_STUDIO_CLOUD") == "1":
            session = st.session_state.setdefault("cloud_workspace", uuid.uuid4().hex)
            root = Path(tempfile.gettempdir()) / "shorts-studio" / session
            st.info("Online session: download your results before leaving. Working files are temporary and may disappear when the server restarts. Face-cam uploads are limited to 4 MB.")
        else:
            output = st.text_input("Project folder", str(DEFAULT_ROOT), key="studio_root")
            root = Path(output).expanduser().resolve()
        with st.expander("ElevenLabs voice settings", expanded=True):
            api_key = st.text_input("API key", value=os.getenv("ELEVENLABS_API_KEY", ""), type="password", key="eleven_key")
            voice_id = st.text_input("Voice ID", value=os.getenv("ELEVENLABS_VOICE_ID", ""), key="eleven_voice")
            st.caption("Choose a voice from your ElevenLabs account. Your key stays in this session, not in project files.")
            st.link_button("Open ElevenLabs", "https://elevenlabs.io/app/voice-library")
        st.caption("ffmpeg ready" if find_ffmpeg() else "Install ffmpeg before downloading or rendering.")
        st.info("Your face-cam stays as recorded. This replaces audio; it does not animate your lips.")
    return root, api_key, voice_id


def _live_log():
    placeholder, messages = st.empty(), []
    def log(message):
        messages.append(message)
        placeholder.code("\n".join(messages[-10:]), language=None)
    return log


def _discovery(root):
    st.subheader("1 · Find the most-viewed Shorts")
    left, right = st.columns([3, 1])
    channel = left.text_input("YouTube channel link", placeholder="https://www.youtube.com/@handle", key="studio_channel")
    choice = right.selectbox("Minimum views", ["10 million", "5 million", "Custom"], key="studio_threshold_choice")
    threshold = {"10 million": 10_000_000, "5 million": 5_000_000}.get(choice)
    if threshold is None:
        threshold = int(st.number_input("Custom minimum views", min_value=0, value=1_000_000, step=100_000))
    if st.button("Find Shorts", type="primary", disabled=not channel.strip(), key="scan_shorts"):
        try:
            with st.status("Scanning the channel’s Shorts…", expanded=True) as status:
                videos, _ = scan_channel(channel, threshold, _live_log())
                st.session_state["studio_scan"] = {"channel": channel.strip(), "videos": videos}
                st.session_state.pop("studio_selection", None)
                status.update(label=f"Found {len(videos):,} Shorts", state="complete", expanded=False)
        except Exception as exc:
            st.session_state.pop("studio_scan", None)
            st.error(str(exc))
    scan = st.session_state.get("studio_scan")
    if not scan or scan["channel"] != channel.strip():
        return
    videos = scan["videos"]
    qualified = [v for v in videos if v.get("view_count") is not None and v["view_count"] >= threshold]
    unknown = sum(v.get("view_count") is None for v in videos)
    st.caption(f"{len(qualified):,} match this filter · sorted by most views · public Shorts only")
    if unknown:
        st.warning(f"View counts are unavailable for {unknown} Shorts; those are excluded.")
    if not qualified:
        st.info("No Shorts meet this threshold. Lower the filter or scan another channel.")
        return
    st.dataframe([{"Title": v["title"], "Views": v["view_count"], "YouTube": v["url"]} for v in qualified],
                 hide_index=True, width="stretch", column_config={"YouTube": st.column_config.LinkColumn("YouTube")})
    by_id = {v["id"]: v for v in qualified}
    existing = st.session_state.get("studio_selection")
    if existing is not None:
        st.session_state["studio_selection"] = [v for v in existing if v in by_id]
    selected = st.multiselect("Shorts to prepare", list(by_id), default=list(by_id)[:1] if existing is None else None,
                              format_func=lambda vid: f"{by_id[vid]['title']} · {by_id[vid]['view_count']:,} views", key="studio_selection")
    if st.button(f"Download & transcribe {len(selected)} Shorts", disabled=not selected, key="prepare_shorts"):
        bar, log, errors = st.progress(0.0), _live_log(), []
        for i, vid in enumerate(selected):
            try:
                prepare_video(root, by_id[vid], log)
            except Exception as exc:
                errors.append(f"{by_id[vid]['title']}: {exc}")
            bar.progress((i + 1) / len(selected))
        for error in errors:
            st.error(error)
        if not errors:
            st.success("Prepared. Continue with your saved videos below.")


def _facecam(root):
    st.subheader("4 · Add your face-cam")
    uploaded = st.file_uploader("Your face-cam video", type=["mp4", "mov", "mkv", "webm"], key="studio_face_upload")
    if uploaded and st.button("Save face-cam", key="save_facecam"):
        try:
            face = save_facecam(root, uploaded.getvalue(), Path(uploaded.name).suffix)
            st.session_state["studio_face_path"] = str(face)
            st.success("Face-cam saved for reuse across Shorts.")
        except Exception as exc:
            st.error(str(exc))
    folder = root / "facecams"
    saved = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix in {".mp4", ".mov", ".mkv", ".webm"}) if folder.exists() else []
    if not saved:
        st.caption("Upload your face-cam to unlock previews and final renders.")
        return None
    index = next((i for i, p in enumerate(saved) if str(p) == st.session_state.get("studio_face_path")), 0)
    face = st.selectbox("Saved face-cam", saved, index=index, format_func=lambda p: p.name, key="face_choice")
    with st.expander("View face-cam"):
        st.video(str(face))
    return face


def _composition(root, job, dirty):
    folder, face = job_folder(root, job["id"]), _facecam(root)
    st.subheader("5 · Preview & export")
    layout = st.selectbox("Layout", list(LAYOUTS), format_func=LAYOUTS.get, key="studio_layout")
    timing = st.selectbox("Video timing", ["preserve", "fit"],
                          format_func=lambda x: {"preserve": "Keep source speed; hold last frame if needed",
                                                 "fit": "Fit the full source video to voiceover length"}[x], key="studio_timing")
    loop = st.checkbox("Loop my face-cam if it is shorter than the final video", key="studio_loop")
    st.caption("Original and face-cam audio are muted. Without looping, a short face-cam holds its last frame.")
    source, voice = artifact(folder, job, "source"), artifact(folder, job, "voice")
    ready = bool(source and voice and face and not dirty)
    if source and voice:
        try:
            sd, vd = probe(source)["duration"], probe(voice)["duration"]
            st.caption(f"Source: {sd:.1f}s · voiceover: {vd:.1f}s · final: {(max(sd, vd) if timing == 'preserve' else vd):.1f}s")
        except Exception as exc:
            ready = False
            st.error(str(exc))
    left, right = st.columns(2)
    preview_clicked = left.button("Render preview", disabled=not ready, key="render_preview")
    final_clicked = right.button("Render final MP4", disabled=not ready, type="primary", key="render_final")
    if preview_clicked or final_clicked:
        try:
            bar = st.progress(0.0, text="Composing video…")
            make_render(root, job, face, layout, timing, loop, preview_clicked, bar.progress)
            st.success("Preview ready." if preview_clicked else "Final video ready.")
        except Exception as exc:
            st.error(str(exc))
    for key in ("preview", "final"):
        path = artifact(folder, job, key)
        if not path:
            continue
        current = False
        if ready:
            try:
                current = job.get(key + "_signature") == render_signature(folder, job, face, layout, timing, loop, key == "preview")
            except (ValueError, OSError):
                pass
        st.write(("Current " if current else "Previous ") + key)
        if not current:
            st.caption("Rendered with earlier settings. Render again to apply your current choices.")
        st.video(str(path))
        _download(path, f"Download {key} MP4", f"get_{key}_{job['id']}", "video/mp4")
    return face, layout, timing, loop


def _batch(root, jobs, api_key, voice_id, face, layout, timing, loop):
    with st.expander("Batch voiceovers & final videos"):
        by_id = {j["id"]: j for j in jobs}
        selected = st.multiselect("Saved videos for this batch", list(by_id), format_func=lambda v: by_id[v]["title"], key="batch_jobs")
        st.caption("Uses saved transcripts. Voice generation sends them to ElevenLabs and uses credits. Matching saved voiceovers are reused.")
        a, b = st.columns(2)
        generate = a.button("Generate batch voiceovers", disabled=not (selected and api_key and voice_id), key="batch_voice")
        render = b.button("Render batch finals", disabled=not (selected and face), key="batch_render")
        if generate or render:
            bar, errors = st.progress(0.0), []
            for i, vid in enumerate(selected):
                job = by_id[vid]
                st.write(job["title"])
                try:
                    if generate:
                        make_voice(root, job, api_key, voice_id)
                    else:
                        make_render(root, job, face, layout, timing, loop, False)
                except Exception as exc:
                    errors.append(f"{job['title']}: {exc}")
                bar.progress((i + 1) / len(selected))
            for error in errors:
                st.error(error)
            if not errors:
                st.session_state["studio_notice"] = "Batch finished. Select a saved video to preview or download it."
                st.rerun()


def render_studio():
    root, api_key, voice_id = _settings()
    st.title("Turn top Shorts into your videos")
    st.caption("Channel → download → transcript → ElevenLabs voiceover → your face-cam → MP4")
    if st.session_state.get("studio_notice"):
        st.success(st.session_state.pop("studio_notice"))
    _discovery(root)
    st.divider()
    jobs = load_jobs(root)
    if not jobs:
        st.info("Your prepared videos will appear here. Start by scanning a channel.")
        return
    by_id = {j["id"]: j for j in jobs}
    chosen = st.selectbox("Saved video", list(by_id), format_func=lambda vid: by_id[vid]["title"], key="active_job")
    job, folder = by_id[chosen], job_folder(root, chosen)
    st.caption(f"Files saved in {folder}")
    if job.get("error"):
        st.warning(job["error"])
    if st.button("Retry / finish preparation", key="retry_job"):
        try:
            job = prepare_video(root, job, _live_log())
            st.success("Preparation complete.")
        except Exception as exc:
            st.error(str(exc))
    st.subheader("2 · Review the transcript")
    with st.expander("Source video & transcript"):
        source = artifact(folder, job, "source")
        if source:
            st.video(str(source))
            _download(source, "Download source MP4", "download_source", "video/mp4")
        for field, label, mime in [("transcript", "Download original transcript", "text/plain")]:
            path = artifact(folder, job, field)
            if path:
                _download(path, label, f"download_{field}", mime)
    script = artifact(folder, job, "script")
    saved = script.read_text(encoding="utf-8") if script else ""
    edited = st.text_area("Words ElevenLabs will read", value=saved, height=230, key=f"script_{root}_{chosen}")
    dirty = edited.strip() != saved.strip()
    st.caption(f"{len(edited.strip()):,} characters · reads the transcript as written; no automatic commentary rewrite")
    if st.button("Save transcript", disabled=not edited.strip(), key="save_script"):
        try:
            save_script(folder, job, edited)
            dirty = False
            st.success("Saved. If you changed the words, generate the voiceover again.")
        except Exception as exc:
            st.error(str(exc))
    if dirty:
        st.info("Save your transcript changes before generating a voiceover or rendering this video.")
    st.subheader("3 · Generate the ElevenLabs voiceover")
    st.caption("Sends the saved transcript to ElevenLabs and uses your credits. Identical saved generations are reused.")
    if st.button("Generate voiceover", disabled=dirty or not job.get("script") or not api_key or not voice_id, key="make_voice"):
        try:
            with st.spinner("Generating voiceover…"):
                make_voice(root, job, api_key, voice_id)
            st.success("Voiceover ready. Listen before rendering.")
        except Exception as exc:
            st.error(str(exc))
    voice = artifact(folder, job, "voice")
    if voice:
        st.audio(str(voice))
        st.caption(f"Generated with voice ID: {job.get('voice_id', 'unknown')}")
        _download(voice, "Download voiceover", "download_voice", "audio/mpeg")
    voice_changed = bool(voice and voice_id.strip() and job.get("voice_id") != voice_id.strip())
    if voice_changed:
        st.warning("Your selected voice differs from the saved voiceover. Generate it again to use the new voice.")
    face, layout, timing, loop = _composition(root, job, dirty or voice_changed)
    _batch(root, load_jobs(root), api_key, voice_id, face, layout, timing, loop)
