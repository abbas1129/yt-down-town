"""ElevenLabs speech generation; credentials never enter saved job metadata."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

import requests

from core.media import has_stream, probe


MODEL_ID = "eleven_multilingual_v2"


def voice_fingerprint(text: str, voice_id: str) -> str:
    payload = json.dumps([text.strip(), voice_id.strip(), MODEL_ID], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def generate_voiceover(text: str, api_key: str, voice_id: str, output_dir: Path) -> Path:
    text, api_key, voice_id = text.strip(), api_key.strip(), voice_id.strip()
    if not text:
        raise ValueError("Review and save a transcript first.")
    if len(text) > 10000:
        raise ValueError("This voice model supports up to 10,000 characters per generation. Shorten the transcript.")
    if not api_key or not re.fullmatch(r"[A-Za-z0-9_-]+", voice_id):
        raise ValueError("Enter an ElevenLabs API key and a valid voice ID in Voice settings.")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"voice_{voice_fingerprint(text, voice_id)}.mp3"
    if output.exists():
        if has_stream(probe(output), "audio"):
            return output
    # No automatic retries: a timed-out request may already have used credits.
    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": api_key, "Accept": "audio/mpeg"},
            json={"text": text, "model_id": MODEL_ID}, timeout=(15, 180),
        )
    except requests.Timeout:
        raise RuntimeError("ElevenLabs timed out. Check its generation history before retrying; credits may have been used.") from None
    except requests.RequestException:
        raise RuntimeError("Could not connect to ElevenLabs. Check your connection and try again.") from None
    if response.status_code != 200:
        messages = {401: "Check your ElevenLabs API key.", 403: "Your key or plan cannot use this voice.",
                    429: "ElevenLabs is rate-limiting requests or your quota is exhausted."}
        raise RuntimeError(messages.get(response.status_code, f"ElevenLabs rejected the request (HTTP {response.status_code}). Check your voice, plan, and transcript."))
    if not response.content or "audio" not in response.headers.get("Content-Type", "").lower():
        raise RuntimeError("ElevenLabs returned no usable audio.")
    with tempfile.TemporaryDirectory(dir=output_dir) as tmp:
        staged = Path(tmp) / "voice.mp3"
        staged.write_bytes(response.content)
        if not has_stream(probe(staged), "audio"):
            raise RuntimeError("Generated voiceover has no audio stream.")
        staged.replace(output)
    return output
