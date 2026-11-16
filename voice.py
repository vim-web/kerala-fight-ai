"""Swappable speech providers (TTS and STT) for Malayalam, Manglish and English.

TTS
- EdgeTTSProvider: Microsoft Edge neural voices, free, no key. Streams MP3 chunks as
  they are synthesised, so playback can start before the whole line is ready.
- GoogleTTSProvider: Google Translate TTS over HTTP, used only as a fallback.
- Browser speech is handled in the frontend.

STT
- GeminiSTTProvider: audio transcription with Gemini (needs GEMINI_API_KEY).
- Browser speech recognition is the default in the frontend.

A small in-memory cache keeps the most recent lines, so repeated lines (openers,
rematch lines) play instantly.
"""

import abc
import base64
import logging
import os
import re
from collections import OrderedDict
from typing import AsyncIterator, Optional, Tuple

import httpx

log = logging.getLogger("sparring.voice")

# (character, script) -> Edge voice. ml-IN voices for Malayalam script;
# Indian English voices read Manglish (Latin script) more naturally.
EDGE_VOICES = {
    ("boss", "ml"): "ml-IN-MidhunNeural",
    ("boss", "latin"): "en-IN-PrabhatNeural",
    ("girlfriend", "ml"): "ml-IN-SobhanaNeural",
    ("girlfriend", "latin"): "en-IN-NeerjaNeural",
    ("default", "ml"): "ml-IN-MidhunNeural",
    ("default", "latin"): "en-IN-PrabhatNeural",
}

PROSODY = {
    "boss": ("-4Hz", "+8%"),
    "girlfriend": ("+2Hz", "+6%"),
    "default": ("+0Hz", "+4%"),
}

# Kept for older callers.
CHARACTER_VOICES = {
    "boss": {"edge": "ml-IN-MidhunNeural", "google": "ml", "pitch": "-4Hz", "rate": "+8%"},
    "girlfriend": {"edge": "ml-IN-SobhanaNeural", "google": "ml", "pitch": "+2Hz", "rate": "+6%"},
    "default": {"edge": "ml-IN-MidhunNeural", "google": "ml", "pitch": "+0Hz", "rate": "+4%"},
}

_MALAYALAM = re.compile(r"[\u0d00-\u0d7f]")
_STAGE = re.compile(r"\*[^*]{0,80}\*|\([^)]{0,40}\)")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")


def clean_for_speech(text: str) -> str:
    """Drop stage directions and emoji; keep the words."""
    text = _STAGE.sub(" ", text or "")
    text = _EMOJI.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()[:600]


def script_of(text: str) -> str:
    return "ml" if _MALAYALAM.search(text or "") else "latin"


def get_voice_for_character(character_id: str, provider: str = "edge", text: str = "", lang: str = "ml") -> Tuple[str, str, str]:
    """(voice_name, pitch, rate) for a character, chosen by the script of the text."""
    if provider == "google":
        return "ml", "", ""
    who = character_id if (character_id, "ml") in EDGE_VOICES else "default"
    script = script_of(text) if text else ("ml" if lang == "ml" else "latin")
    pitch, rate = PROSODY.get(who, PROSODY["default"])
    return EDGE_VOICES[(who, script)], pitch, rate


class _LRU:
    def __init__(self, size: int = 96):
        self.size = size
        self.data: "OrderedDict[tuple, bytes]" = OrderedDict()

    def get(self, key):
        if key in self.data:
            self.data.move_to_end(key)
            return self.data[key]
        return None

    def put(self, key, value: bytes) -> None:
        if not value:
            return
        self.data[key] = value
        self.data.move_to_end(key)
        while len(self.data) > self.size:
            self.data.popitem(last=False)


AUDIO_CACHE = _LRU()


class BaseTTSProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def stream(self, text: str, voice_name: str = "", pitch: str = "", rate: str = "") -> AsyncIterator[bytes]:
        """Yield MP3 chunks as they are generated."""

    async def synthesize(self, text: str, voice_name: str = "", pitch: str = "", rate: str = "") -> bytes:
        out = bytearray()
        async for chunk in self.stream(text, voice_name, pitch, rate):
            out += chunk
        return bytes(out)


class EdgeTTSProvider(BaseTTSProvider):
    """Neural voices: ml-IN-MidhunNeural, ml-IN-SobhanaNeural, en-IN-PrabhatNeural, en-IN-NeerjaNeural."""

    name = "edge"

    async def stream(self, text: str, voice_name: str = "", pitch: str = "", rate: str = "") -> AsyncIterator[bytes]:
        import edge_tts

        kwargs = {}
        if pitch:
            kwargs["pitch"] = pitch
        if rate:
            kwargs["rate"] = rate
        communicate = edge_tts.Communicate(text, voice_name or "ml-IN-MidhunNeural", **kwargs)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                yield chunk["data"]


_http: Optional[httpx.AsyncClient] = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))
    return _http


async def close() -> None:
    global _http
    if _http is not None and not _http.is_closed:
        await _http.aclose()
    _http = None


class GoogleTTSProvider(BaseTTSProvider):
    """Fallback via Google Translate TTS (free, no key, unofficial, 200 chars max)."""

    name = "google"

    async def stream(self, text: str, voice_name: str = "", pitch: str = "", rate: str = "") -> AsyncIterator[bytes]:
        tl = "ml" if _MALAYALAM.search(text) else "en"
        res = await _client().get(
            "https://translate.google.com/translate_tts",
            params={"ie": "UTF-8", "tl": tl, "client": "tw-ob", "q": text[:200]},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if res.status_code != 200:
            raise RuntimeError(f"Google TTS returned status {res.status_code}")
        yield res.content


class BaseSTTProvider(abc.ABC):
    @abc.abstractmethod
    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/webm", lang: str = "ml") -> str:
        """Transcribe audio into text."""


class GeminiSTTProvider(BaseSTTProvider):
    """Transcribes audio using Gemini multimodal input."""

    def __init__(self, api_key: Optional[str] = None):
        from llm import real_key

        self.api_key = real_key(api_key or os.getenv("GEMINI_API_KEY", ""))
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/webm", lang: str = "ml") -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required for GeminiSTTProvider.")
        prompt = (
            "Transcribe the speaker's words exactly. Output only the transcript. "
            "Malayalam speech in Malayalam script; Manglish in Latin script."
        )
        payload = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(audio_bytes).decode()}},
            ]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 200},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        res = await _client().post(url, json=payload, headers={"x-goog-api-key": self.api_key}, timeout=25.0)
        if res.status_code != 200:
            raise RuntimeError(f"Gemini STT failed with status {res.status_code}")
        parts = ((res.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts).strip()


_edge_tts = EdgeTTSProvider()
_google_tts = GoogleTTSProvider()


def get_tts_provider(name: str = "edge") -> BaseTTSProvider:
    return _google_tts if (name or "").lower() == "google" else _edge_tts
