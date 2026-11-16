"""Tests for the latency/bug-fix pass: providers, streaming, fallbacks, prompt split."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import llm
import main
import personas
import voice


# ---------------------------------------------------------------- keys and errors

def test_placeholder_keys_are_ignored():
    assert llm.real_key("your_gemini_api_key_here") == ""
    assert llm.real_key("") == ""
    assert llm.real_key("short") == ""
    assert llm.real_key("  AIzaSyA1234567890abcdefghijklmnop  ") == "AIzaSyA1234567890abcdefghijklmnop"


def test_gemini_errors_are_friendly_and_never_raw_json():
    raw = '{"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}'
    err = llm.Gemini._error(400, raw)
    assert err.kind == "auth"
    assert "GEMINI_API_KEY" in err.message and "{" not in err.message

    rate = llm.Gemini._error(429, '{"error": {"status": "RESOURCE_EXHAUSTED"}}')
    assert rate.kind == "rate" and "{" not in rate.message


def test_thinking_is_disabled_for_flash_banter():
    g = llm.Gemini()
    g.model = "gemini-2.5-flash"
    g.thinking_budget = None
    body = g._body("sys", [], 1.0, 100)
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert body["generationConfig"]["maxOutputTokens"] == 100


def test_thought_parts_are_not_shown():
    data = {"candidates": [{"content": {"parts": [{"text": "hidden", "thought": True}, {"text": "poda"}]}}]}
    assert llm.Gemini._text(data) == "poda"


# ---------------------------------------------------------------- prompt split

def test_prompt_split_keeps_static_part_stable():
    a_static, a_turn = personas.prompt_parts("boss", 2, "ml", 9, user_message="poda patti", hidden_mood="sarcastic")
    b_static, b_turn = personas.prompt_parts("boss", 2, "ml", 7, user_message="sorry sir, traffic aayirunnu", hidden_mood="explosive")
    assert a_static == b_static  # cacheable prefix
    assert a_turn != b_turn
    assert "LIVE MIRROR RULE" in a_turn and "LIVE MIRROR RULE" not in a_static


def test_system_prompt_still_contains_both_parts():
    text = personas.system_prompt("girlfriend", 3, "manglish", 8, user_message="njan busy aayirunnu")
    assert "HARD SAFETY LIMITS" in text
    assert "REUSE USER'S WORDS" in text


def test_ollama_window_keeps_start_point_for_several_turns():
    contents = [{"role": "user" if i % 2 == 0 else "model", "parts": [{"text": str(i)}]} for i in range(30)]
    starts = set()
    for n in range(20, 26):
        window = llm.Ollama.window(contents[:n])
        starts.add(window[0]["parts"][0]["text"])
        assert len(window) >= 6
    assert len(starts) <= 2  # prefix moves rarely, not every message


def test_ollama_turn_note_goes_just_before_last_user_message():
    o = llm.Ollama()
    contents = [
        {"role": "user", "parts": [{"text": "hi"}]},
        {"role": "model", "parts": [{"text": "enthada"}]},
        {"role": "user", "parts": [{"text": "poda"}]},
    ]
    msgs = o.messages("STATIC", contents, "TURN")
    assert msgs[0] == {"role": "system", "content": "STATIC"}
    assert msgs[-2] == {"role": "system", "content": "TURN"}
    assert msgs[-1] == {"role": "user", "content": "poda"}


# ---------------------------------------------------------------- reply tidying

def test_tidy_removes_labels_stage_directions_and_quotes():
    assert main._tidy('Boss: *sighs* "Poda patti"') == "Poda patti"
    assert main._tidy("line one\n\n\n\nline two") == "line one\n\nline two"


# ---------------------------------------------------------------- streaming endpoint

def _events(text: str) -> list:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_stream_sends_meta_chunks_and_done():
    async def fake_stream(plan, provider):
        for piece in ["പോടാ ", "കഴുതേ!"]:
            yield piece

    client = TestClient(main.app)
    with patch("main._token_stream", fake_stream):
        res = client.post("/api/chat/stream", json={
            "mode": "boss", "lang": "ml", "provider": "ollama",
            "messages": [{"role": "ai", "text": "ഹായ് ഡാ"}, {"role": "user", "text": "പോടാ പട്ടി"}],
        })
    events = _events(res.text)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "meta" and kinds[-1] == "done"
    assert kinds.count("chunk") == 2
    assert events[-1]["reply"] == "പോടാ കഴുതേ!"


def test_stream_falls_back_to_local_when_cloud_key_is_bad():
    calls = []

    async def fake_stream(plan, provider):
        calls.append(provider)
        if provider == "gemini":
            raise llm.ProviderError("Gemini rejected the API key. Check GEMINI_API_KEY in .env.", kind="auth")
        yield "local reply"

    client = TestClient(main.app)
    with patch("main._token_stream", fake_stream), patch.object(main, "GEMINI_KEY", "AIzaFakeKeyForTests1234567"):
        res = client.post("/api/chat/stream", json={
            "mode": "boss", "lang": "en", "provider": "gemini",
            "messages": [{"role": "user", "text": "you are late"}],
        })
    events = _events(res.text)
    assert calls == ["gemini", "ollama"]
    assert any(e["type"] == "notice" and "GEMINI_API_KEY" in e["message"] for e in events)
    assert events[-1]["type"] == "done" and events[-1]["provider"] == "ollama"


def test_stream_error_message_is_friendly():
    async def fake_stream(plan, provider):
        raise llm.ProviderError("Local model is not running. Start Ollama, or switch to Cloud.", kind="offline")
        yield ""  # pragma: no cover

    client = TestClient(main.app)
    with patch("main._token_stream", fake_stream):
        res = client.post("/api/chat/stream", json={
            "mode": "girlfriend", "lang": "en", "provider": "ollama",
            "messages": [{"role": "user", "text": "hi"}],
        })
    last = _events(res.text)[-1]
    assert last["type"] == "error" and "Ollama" in last["message"] and "{" not in last["message"]


def test_stream_retries_empty_reply():
    attempts = []

    async def fake_stream(plan, provider):
        attempts.append(1)
        if len(attempts) == 1:
            return
        yield "second try"

    client = TestClient(main.app)
    with patch("main._token_stream", fake_stream):
        res = client.post("/api/chat/stream", json={
            "mode": "boss", "lang": "en", "provider": "ollama",
            "messages": [{"role": "user", "text": "hello boss"}],
        })
    assert len(attempts) == 2
    assert _events(res.text)[-1]["reply"] == "second try"


def test_long_conversations_are_trimmed_not_rejected():
    msgs = [{"role": "user" if i % 2 else "ai", "text": f"line {i}"} for i in range(1, 120)]
    msgs.append({"role": "user", "text": "still fighting"})

    async def fake_stream(plan, provider):
        assert len(plan["contents"]) <= main.MAX_MESSAGES
        yield "ok"

    client = TestClient(main.app)
    with patch("main._token_stream", fake_stream):
        res = client.post("/api/chat/stream", json={"mode": "boss", "lang": "en", "provider": "ollama", "messages": msgs})
    assert res.status_code == 200
    assert _events(res.text)[-1]["type"] == "done"


def test_safety_message_short_circuits_the_model():
    async def fake_stream(plan, provider):  # pragma: no cover - must not run
        raise AssertionError("model should not be called")
        yield ""

    client = TestClient(main.app)
    with patch("main._token_stream", fake_stream):
        res = client.post("/api/chat/stream", json={
            "mode": "boss", "lang": "en", "messages": [{"role": "user", "text": "i want to die"}],
        })
    done = _events(res.text)[-1]
    assert done["safety"] is True and "14416" in done["reply"]


# ---------------------------------------------------------------- passcode and voice

def test_passcode_required_only_for_network_clients():
    client = TestClient(main.app)
    with patch.object(main, "APP_PASSCODE", "4321"), patch.object(main, "LOCAL_HOSTS", {"127.0.0.1"}):
        assert client.get("/api/history").status_code == 401
        assert client.get("/api/history", headers={"X-Passcode": "4321"}).status_code == 200
        assert client.get("/api/config").status_code == 200  # config stays open
    assert client.get("/api/history").status_code == 200  # testclient counts as local


def test_voice_matches_script_of_text():
    assert voice.get_voice_for_character("girlfriend", text="എന്താടാ")[0] == "ml-IN-SobhanaNeural"
    assert voice.get_voice_for_character("girlfriend", text="enthada")[0] == "en-IN-NeerjaNeural"
    assert voice.get_voice_for_character("boss", text="പോടാ")[0] == "ml-IN-MidhunNeural"


def test_speech_text_drops_stage_directions_and_emoji():
    assert voice.clean_for_speech("*sighs* poda 😡 patti") == "poda patti"


def test_tts_falls_back_to_google_and_caches():
    class Broken(voice.BaseTTSProvider):
        name = "edge"

        async def stream(self, text, voice_name="", pitch="", rate=""):
            raise RuntimeError("no network")
            yield b""  # pragma: no cover

    class Fake(voice.BaseTTSProvider):
        name = "google"

        async def stream(self, text, voice_name="", pitch="", rate=""):
            yield b"ID3"
            yield b"audio"

    voice.AUDIO_CACHE.data.clear()
    providers = {"edge": Broken(), "google": Fake()}
    client = TestClient(main.app)
    with patch("voice.get_tts_provider", lambda name="edge": providers["google" if name == "google" else "edge"]):
        res = client.post("/api/tts", json={"text": "test line", "mode": "boss", "lang": "en"})
        assert res.status_code == 200 and res.content == b"ID3audio"
        again = client.get("/api/tts", params={"text": "test line", "mode": "boss", "lang": "en"})
        assert again.content == b"ID3audio"

