# yt down town

A production-ready **Streamlit** web app that scans a YouTube channel, filters videos by view count, downloads each qualifying video as **MP4**, and generates matching **transcript (.txt)** files — all with a premium dark-mode UI.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔍 Channel Scanning | Metadata-only scan via `yt-dlp` flat-playlist (no premature downloads) |
| 👁️ View-Count Filter | User-defined threshold; default 1,000,000 views |
| 📥 Video Download | MP4 at 1080p → 720p → best available; ffmpeg merging |
| 📝 Auto Transcripts | YouTube captions (API) → Whisper AI fallback |
| ⬇️ Direct Downloads | Download each MP4 and transcript directly from its result row |
| 📂 Folder Access | One-click to open the output folder in Explorer |
| 🎨 Premium UI | Dark mode, gradients, animated cards, live log console |

---

## 📁 Project Structure

```
yt-channel-downloader/
├── app.py                  # Streamlit entry point
├── requirements.txt
├── .streamlit/
│   └── config.toml         # Dark theme & server settings
├── core/
│   ├── __init__.py
│   ├── session.py          # Session-state initialisation
│   ├── scanner.py          # Channel metadata extraction (yt-dlp)
│   ├── downloader.py       # MP4 video download (yt-dlp)
│   ├── transcriber.py      # Transcript pipeline (API + Whisper)
│   └── pipeline.py         # End-to-end orchestration
└── ui/
    ├── __init__.py
    ├── styles.py           # Custom CSS injection
    ├── sidebar.py          # Sidebar inputs + controls
    └── dashboard.py        # Main dashboard, results, log
```

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **ffmpeg** on PATH  
  - Windows: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **GPU acceleration** (optional): Install PyTorch with CUDA support *before* the above command by following instructions at [pytorch.org](https://pytorch.org/get-started/locally/).  Whisper will automatically use the GPU if available.

### 3. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**.

---

## 🔧 Usage

1. Paste a YouTube channel URL into the sidebar  
   (supports `/@handle`, `/channel/UCxxx`, `/c/Name`, `/user/Name`)
2. Set the **minimum view count** threshold (default: 1,000,000)
3. Optionally change the **output directory** (defaults to `~/Downloads/YT_Downloads`)
4. Click **🚀 Start Download**

The app will:
- Scan the entire channel (metadata only)
- Filter & sort videos by view count
- For each qualifying video:
  - Download the MP4 (1080p preferred)
  - Fetch the transcript via YouTube's caption API
  - Fall back to Whisper AI transcription if captions are unavailable
- Display a result card per video (✅ complete / ⚠️ partial / ❌ failed)
- Offer direct **Download MP4** and **Download TXT** buttons per result

---

## 📋 Output

For each qualifying video you get two files with matching names:

```
YT_Downloads/
├── My_Amazing_Video_Title.mp4
├── My_Amazing_Video_Title.txt
├── Another_Top_Video.mp4
└── Another_Top_Video.txt
```

---

## ⚙️ Configuration

| Setting | File | Key |
|---|---|---|
| Streamlit theme | `.streamlit/config.toml` | `[theme]` |
| Server port | `.streamlit/config.toml` | `server.port` |
| Default output dir | `ui/sidebar.py` | `DEFAULT_OUTPUT_DIR` |
| Whisper model size | `core/transcriber.py` | `whisper.load_model("base")` |
| Video format preference | `core/downloader.py` | `format_selector` |

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `ffmpeg not found` | Install ffmpeg and ensure it's on your PATH |
| Channel scan returns 0 videos | Try different URL formats; some channels require the `/videos` suffix |
| Whisper takes too long | Use `"tiny"` or `"small"` model in `transcriber.py`; or install CUDA PyTorch |
| Rate limiting / 403 errors | yt-dlp may need updating: `pip install -U yt-dlp` |
| No transcripts found | Video may not have captions and audio extraction may fail if ffmpeg is missing |

---

## 📦 Key Dependencies

| Library | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `yt-dlp` | YouTube downloader & metadata extractor |
| `youtube-transcript-api` | Fast caption fetcher |
| `openai-whisper` | AI offline speech-to-text |
| `torch` | Required by Whisper |

---

## 📄 License

MIT License — free to use, modify, and distribute.
