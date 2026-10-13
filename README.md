# Shorts Studio

## Vercel hosting

`Dockerfile.vercel` packages Streamlit, FFmpeg, Node.js, CPU PyTorch and the
Whisper tiny model. `vercel.json` overrides the Python API framework preset.
Deployment excludes local downloads, environment files and credentials.

The hosted interface uses a separate temporary workspace for each browser session.
Download results before leaving: files are not persistent across restarts or
instance changes. Face-cam uploads are limited to 4 MB on this initial hosting
configuration. Persistent cloud storage and larger direct uploads require a
separate storage integration. Local operation retains its existing saved folders
and 200 MB upload limit.

A local Streamlit workflow for turning selected YouTube Shorts into narrated videos with your face-cam.

## Workflow

1. Paste a full YouTube channel link. Scan public **Shorts only**, sort by views, and choose **10 million**, **5 million**, or a custom minimum.
2. Select the Shorts to prepare. Download each MP4 with its audio included, and obtain a transcript through captions or local Whisper. No separate source-audio file is saved; Whisper may use a temporary audio file that is removed after transcription.
3. Review and save the transcript. It is read as written; the app does not rewrite it into commentary or translate it.
4. Enter your ElevenLabs API key and voice ID in the sidebar. Click **Generate voiceover** and listen to the audio.
5. Upload and save your face-cam. Choose a layout, render a preview, then export the final MP4.
6. Use **Batch voiceovers & final videos** to process multiple saved jobs with their saved transcripts and the selected face-cam/layout.

## Run locally

Requires Python 3.10+, ffmpeg/ffprobe, and a supported JavaScript runtime (Node 22+ or Deno). Windows WinGet ffmpeg installations are detected automatically.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit. The default port is 8501.

Enter `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` through environment variables or the app's sidebar. Keys are never stored in job manifests. Do not commit keys. The speech model is `eleven_multilingual_v2`, with MP3 output and a 10,000-character limit per request.

Speech generation sends the saved transcript to ElevenLabs and uses account credits. No speech is generated on page load or render. Identical transcript/voice generations are reused. Requests are not automatically retried after a timeout because a request may already have been billed.

## Layout and timing

- **Vertical / face-cam below**: 1080 x 1920, source fitted in a centered panel, face-cam below.
- **Vertical / overlay**: 1080 x 1920, source centered with face-cam in the bottom-right corner.
- **Horizontal / beside**: 1920 x 1080, source in the main panel with face-cam alongside.
- Previews use half the final dimensions and include the complete timeline.
- Both source and face-cam audio are muted; only the generated narration is used.
- Keep-source-speed mode preserves the full source and narration, holding the last source frame if narration runs longer. Short narration is padded with silence.
- Fit mode adjusts source speed to narration duration. This fits total duration, not sentence-by-sentence synchronization.
- Face-cam holds its last frame if short, unless you explicitly enable looping. Face-cam is cropped to fit its panel; source footage is fitted without cropping.
- This app composites your recorded face-cam. It does not perform lip-sync or animate a face.

## Saved projects

Default output: `downloads/studio/<YouTube-video-ID>/`.

Each job stores `job.json`, `source.mp4` (with its original audio), `transcript.txt`, editable `script.txt`, generated voiceovers, and preview/final MP4s. No separate source-audio output is created. Face-cams are stored under `downloads/studio/facecams/`. Existing jobs reload after restart. Video IDs avoid title collisions. Changing the saved transcript invalidates references to older voiceovers/renders without deleting those files. Changing layout, timing, or face-cam marks earlier renders as previous versions.

The source downloader uses separate MP4 video and M4A audio when available, merged with ffmpeg, with a single-file MP4 fallback. Actual quality depends on YouTube's available formats. A failed download cannot be reported as success using an old output file.

## Checks and limits

```powershell
python -m unittest discover -s tests -v
```

Tests cover scan failures, filtering, filename isolation behavior, script invalidation, ElevenLabs request/caching behavior, real ffmpeg layouts, full-resolution output, timing, and audio replacement. API tests use simulated responses and no account credits.

YouTube can restrict downloads or captions. Whisper uses the local tiny model (downloaded on first use), and transcript accuracy should be reviewed. Jobs run sequentially in the current app session; saved stages survive restarts, but there is no background queue or mid-file resume. Keep the app connected while a stage is running. Face-cam uploads use Streamlit's 200 MB limit. A saved per-video output can be retried independently.

The previous downloader UI modules remain for compatibility, but `app.py` now opens Shorts Studio.
