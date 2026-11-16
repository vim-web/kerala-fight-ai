"""FastAPI backend for the Kerala Fight AI app.

Request flow for one message (all async, nothing blocks the event loop):
  1. _prepare_chat: validate, safety check, anger step, build prompt (fast, local).
  2. _stream_answer: send a `meta` event at once (UI shows "typing"), then stream
     model tokens to the browser as they arrive. The browser starts speaking each
     sentence as soon as it is complete (see static/app.js), so text and voice overlap.
  3. After the `done` event is sent, history is saved off the event loop.

If the browser aborts (Stop button, new message, character switch), Starlette
cancels the generator, which closes the upstream model request too.
"""

import asyncio
import hmac
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

import anger  # noqa: E402
import llm  # noqa: E402
import personas  # noqa: E402
import safety  # noqa: E402
import store  # noqa: E402
import voice  # noqa: E402
from coach import sections as coach_sections  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sparring")

GEMINI = llm.Gemini()
OLLAMA = llm.Ollama()

GEMINI_KEY = GEMINI.key  # empty when missing or a .env placeholder
GEMINI_MODEL = GEMINI.model
OLLAMA_MODEL = OLLAMA.model
OLLAMA_NUM_PREDICT = llm._int_env("OLLAMA_NUM_PREDICT", 60)

_requested = (os.getenv("PROVIDER") or "").strip().lower()
DEFAULT_PROVIDER = "gemini" if GEMINI_KEY else "ollama"
PROVIDER = _requested if _requested in ("gemini", "ollama") else DEFAULT_PROVIDER
if PROVIDER == "gemini" and not GEMINI_KEY:
    log.warning("PROVIDER=gemini but GEMINI_API_KEY is missing or a placeholder; using local Ollama.")
    PROVIDER = "ollama"

APP_PASSCODE = os.getenv("APP_PASSCODE", "").strip()
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

TEMPERATURE = 1.05
MAX_MESSAGES = 24  # context window sent to the model
MAX_TEXT = 1000
LANGS = {"en", "manglish", "ml"}
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _tokens_for(provider: str, user_text: str) -> int:
    """Cap by tokens only. Malayalam script costs several tokens per word on Gemini,
    so the cloud cap is a little higher to avoid replies cut off mid-word."""
    long_msg = len(user_text.split()) >= 25
    if provider == "gemini":
        return 200 if long_msg else 110
    return OLLAMA_NUM_PREDICT * 2 if long_msg else OLLAMA_NUM_PREDICT


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm = asyncio.create_task(OLLAMA.warm_up()) if PROVIDER == "ollama" else None
    log.info("Model: %s (cloud key %s)", PROVIDER, "set" if GEMINI_KEY else "missing")
    try:
        yield
    finally:
        if warm:
            warm.cancel()
        await llm.close()
        await voice.close()


app = FastAPI(title="Kerala Fight AI", lifespan=lifespan)
STORE = anger.SessionStore()
HISTORY = store.Store(os.getenv("SPARRING_DB") or (BASE_DIR / "data" / "sparring.db"))


# ---------------------------------------------------------------- passcode

def _is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in LOCAL_HOSTS


def _passcode_ok(request: Request) -> bool:
    if not APP_PASSCODE or _is_local(request):
        return True
    given = request.headers.get("x-passcode") or request.query_params.get("k") or ""
    return hmac.compare_digest(given.encode(), APP_PASSCODE.encode())


@app.middleware("http")
async def passcode_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path != "/api/config" and not _passcode_ok(request):
        return JSONResponse({"detail": "Passcode required. Enter it in Settings."}, status_code=401)
    return await call_next(request)


# ---------------------------------------------------------------- models

class Msg(BaseModel):
    role: str
    text: str = Field(default="", max_length=4000)


class ChatReq(BaseModel):
    mode: str
    intensity: int = 2
    lang: str = "ml"
    session: str = ""
    scenario: str = ""
    provider: Optional[str] = None
    messages: list[Msg] = Field(default_factory=list, max_length=400)


class CoachReq(BaseModel):
    mode: str
    session: str = ""
    scenario: str = ""
    messages: list[Msg] = Field(default_factory=list, max_length=400)


class TTSReq(BaseModel):
    text: str = Field(max_length=1200)
    mode: str = "boss"
    lang: str = "ml"
    provider: str = "edge"


class RematchReq(BaseModel):
    mode: str
    session: str = ""
    lang: str = "ml"


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _session_id(raw: str) -> str:
    return raw if SESSION_ID.match(raw or "") else uuid.uuid4().hex


def _clean(msgs: list[Msg]) -> list[Msg]:
    out = []
    for m in msgs[-MAX_MESSAGES:]:
        text = (m.text or "").strip()[:MAX_TEXT]
        if text:
            out.append(Msg(role="user" if m.role == "user" else "ai", text=text))
    return out


def _contents(msgs: list[Msg], gemini_safe: bool = False) -> list[dict]:
    items = [{"role": "user" if m.role == "user" else "model", "parts": [{"text": m.text}]} for m in msgs]
    if not gemini_safe:
        return items
    while items and items[0]["role"] == "model":
        items.pop(0)
    merged: list[dict] = []
    for item in items:
        if merged and merged[-1]["role"] == item["role"]:
            merged[-1]["parts"][0]["text"] += "\n" + item["parts"][0]["text"]
        else:
            merged.append({"role": item["role"], "parts": [{"text": item["parts"][0]["text"]}]})
    return merged


_LABEL = re.compile(r"^\s*(boss|girlfriend|character|ai|assistant|model)\s*:\s*", re.I)
_STAGE = re.compile(r"\*[^*\n]{1,80}\*")


def _tidy(reply: str) -> str:
    """Remove name labels, *stage directions* and surrounding quotes the model sometimes adds."""
    text = _STAGE.sub("", reply or "")
    text = "\n".join(_LABEL.sub("", line) for line in text.splitlines())
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def _provider_for(requested: Optional[str]) -> str:
    if requested == "gemini" and GEMINI_KEY:
        return "gemini"
    if requested == "ollama":
        return "ollama"
    return PROVIDER


async def _generate(
    system: str, contents: list[dict], temp: float = TEMPERATURE, provider: str = "",
    max_tokens: int = 60, turn_note: str = "",
) -> str:
    """Non-streaming reply with one retry on empty and a Cloud -> Local fallback."""
    selected = provider or PROVIDER
    try:
        for _ in (1, 2):
            if selected == "gemini":
                full = f"{system}\n\n{turn_note}" if turn_note else system
                reply = await GEMINI.chat(full, contents, temp, max_tokens)
            else:
                reply = await OLLAMA.chat(system, contents, temp, max_tokens, turn_note)
            if reply.strip():
                return _tidy(reply)
    except llm.ProviderError as exc:
        if selected == "gemini" and exc.can_fallback:
            log.info("Cloud failed (%s); falling back to local.", exc.kind)
            return await _generate(system, contents, temp, "ollama", min(max_tokens, OLLAMA_NUM_PREDICT * 2), turn_note)
        raise HTTPException(exc.status, exc.message) from exc
    raise HTTPException(502, "The model went quiet. Send that again.")


def _detect_expression(reply: str, anger_level: int, is_win: bool) -> str:
    """Pick an avatar face (angry, laughing, shocked, sulking, speaking)."""
    if is_win:
        return "sulking"
    lower = reply.lower()
    if any(w in lower for w in ["ഹഹ", "ചിരി", "haha", "hehe", "lol", "trophy", "കപ്പടിച്ചിട്ട്", "impress"]):
        return "laughing"
    if any(w in lower for w in ["എന്താടാ", "what?!", "enthaa?!", "സെർവർ", "പോയോ", "തീർന്നോ", "മറന്നോ", "?!"]):
        return "shocked"
    if any(w in lower for w in ["സോറി", "മിണ്ടില്ല", "മടുത്തു", "തലവേദന", "പോയി തുലയ്", "maduthu", "mindilla"]):
        return "sulking"
    if anger_level >= 8 or any(w in lower for w in ["മൈരേ", "പോടാ", "തെണ്ടി", "ചെറ്റ", "പുല്ല്", "poda", "shut up"]):
        return "angry"
    return "speaking"


async def _prepare_chat(req: ChatReq) -> dict:
    if req.mode not in personas.MODES:
        raise HTTPException(400, "Unknown character.")
    msgs = _clean(req.messages)
    if not msgs or msgs[-1].role != "user":
        raise HTTPException(400, "Send a message first.")

    mode_cfg = personas.MODES[req.mode]
    sid = _session_id(req.session)
    session = STORE.get(sid, mode_cfg["start"])
    lang = req.lang if req.lang in LANGS else "ml"
    requested = req.provider if req.provider in ("gemini", "ollama") else None
    provider = _provider_for(requested)
    notice = ""
    if requested == "gemini" and provider != "gemini":
        notice = "Cloud is not set up (no GEMINI_API_KEY in .env), so Local is answering."

    last_user = msgs[-1].text
    base = {
        "session_obj": session, "sid": sid, "provider": provider, "user_text": last_user,
        "mode": req.mode, "lang": lang, "round_number": session.round_number, "notice": notice,
    }

    if safety.check(last_user):
        log.info("Safety check triggered")
        return {**base, "safety": safety.reply(lang), "change": 0, "anger": session.anger,
                "system": "", "turn_note": "", "contents": [], "scenario": "", "is_win": False}

    is_victory = anger.is_win(last_user)
    if is_victory:
        session.round_over = True

    previous = [m.text for m in msgs if m.role == "user"][:-1][-3:]
    change = anger.step(last_user, previous)
    if not mode_cfg.get("cooldown") and change < 0:
        change = max(change, -1)  # fight mode: an apology never melts them
    next_anger = anger.apply(session.anger, change)

    earlier_notes = list(session.session_notes)  # before this message is noted
    if len(last_user) > 10:
        session.add_note(last_user)

    scene_id = req.scenario if (req.scenario in personas.SCENARIOS and personas.SCENARIOS[req.scenario]["mode"] == req.mode) else ""
    scene = personas.SCENARIOS[scene_id]["scene"] if scene_id else ""

    static, turn_note = personas.prompt_parts(
        mode=req.mode, intensity=_clamp(req.intensity, 1, 3), lang=lang, anger=next_anger,
        scene=scene, user_message=last_user, session_notes=earlier_notes,
        used_insults=session.used_insults, round_win=is_victory,
    )
    return {
        **base, "safety": None, "change": change, "anger": next_anger,
        "system": static, "turn_note": turn_note,
        "contents": _contents(msgs, gemini_safe=provider == "gemini"),
        "scenario": scene_id, "is_win": is_victory,
        "max_tokens": _tokens_for(provider, last_user),
    }


def _save_turn_sync(plan: dict, reply: str) -> None:
    try:
        HISTORY.add_turn(
            plan["sid"], mode=plan["mode"], scenario=plan["scenario"], lang=plan["lang"],
            user_text=plan["user_text"], reply=reply, anger=plan["anger"], delta=plan["change"],
        )
    except Exception as exc:  # history must never break a chat
        log.warning("history save failed: %s", type(exc).__name__)


async def _save_turn(plan: dict, reply: str) -> None:
    if plan.get("user_text"):
        await asyncio.to_thread(_save_turn_sync, plan, reply)


def _finish(plan: dict, reply: str) -> str:
    if plan["session_obj"]:
        plan["session_obj"].turn(plan["change"])
        first_line = next((ln for ln in reply.splitlines() if ln.strip()), reply)
        plan["session_obj"].add_used_insult(first_line[:60])
    return _detect_expression(reply, plan["anger"], plan["is_win"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _token_stream(plan: dict, provider: str) -> AsyncIterator[str]:
    if provider == "gemini":
        full = f"{plan['system']}\n\n{plan['turn_note']}"
        async for piece in GEMINI.stream(full, plan["contents"], TEMPERATURE, plan["max_tokens"]):
            yield piece
    else:
        tokens = min(plan["max_tokens"], OLLAMA_NUM_PREDICT * 2)
        async for piece in OLLAMA.stream(plan["system"], plan["contents"], TEMPERATURE, tokens, plan["turn_note"]):
            yield piece


async def _stream_answer(plan: dict) -> AsyncIterator[str]:
    meta = {
        "anger": plan["anger"], "delta": plan["change"], "session": plan["sid"],
        "provider": plan["provider"], "round_over": plan["is_win"], "round_number": plan["round_number"],
    }
    if plan.get("notice"):
        yield _sse({"type": "notice", "message": plan["notice"]})

    if plan["safety"]:
        yield _sse({"type": "meta", **meta, "safety": True, "expression": "speaking"})
        yield _sse({"type": "chunk", "text": plan["safety"]})
        yield _sse({"type": "done", **meta, "safety": True, "reply": plan["safety"], "expression": "speaking"})
        return

    yield _sse({"type": "meta", **meta, "safety": False})

    provider = plan["provider"]
    collected: list[str] = []
    for attempt in range(3):
        try:
            async for piece in _token_stream(plan, provider):
                collected.append(piece)
                yield _sse({"type": "chunk", "text": piece})
        except llm.ProviderError as exc:
            if not collected and provider == "gemini" and exc.can_fallback:
                provider = "ollama"
                yield _sse({"type": "notice", "message": f"{exc.message} Using Local for now."})
                yield _sse({"type": "provider", "provider": "ollama"})
                continue
            yield _sse({"type": "error", "message": exc.message})
            return
        except Exception:
            log.exception("stream failed")
            yield _sse({"type": "error", "message": "Something went wrong talking to the model. Try again."})
            return
        if "".join(collected).strip():
            break
        collected.clear()  # empty reply: retry once more
    reply = _tidy("".join(collected))
    if not reply:
        yield _sse({"type": "error", "message": "The model went quiet. Send that again."})
        return

    expression = _finish(plan, reply)
    yield _sse({"type": "done", **meta, "provider": provider, "safety": False, "reply": reply, "expression": expression})
    await _save_turn(plan, reply)


# ---------------------------------------------------------------- routes

@app.get("/api/config")
def get_config(request: Request = None):
    """Backend configuration and whether this device must enter the passcode."""
    local = _is_local(request) if request is not None else True
    auth_required = bool(APP_PASSCODE) and not local
    authenticated = (not auth_required) or (request is not None and _passcode_ok(request))
    return {
        "gemini_available": bool(GEMINI_KEY),
        "default_provider": PROVIDER,
        "gemini_model": GEMINI_MODEL,
        "ollama_model": OLLAMA_MODEL,
        "auth_required": auth_required,
        "authenticated": authenticated,
    }


@app.get("/api/modes")
def modes():
    fields = ("label", "blurb", "openers", "avatar", "start", "cooldown", "pitch", "rate")
    return {k: {x: v[x] for x in fields} for k, v in personas.MODES.items()}


@app.get("/api/scenarios")
def scenarios():
    fields = ("label", "blurb", "goal", "mode", "openers")
    return {k: {x: v[x] for x in fields} for k, v in personas.SCENARIOS.items()}


@app.post("/api/chat")
async def chat(req: ChatReq):
    plan = await _prepare_chat(req)
    if plan["safety"]:
        return {"reply": plan["safety"], "safety": True, "anger": plan["anger"], "delta": 0,
                "session": plan["sid"], "provider": plan["provider"], "round_over": False,
                "round_number": plan["round_number"], "expression": "speaking"}
    reply = await _generate(plan["system"], plan["contents"], temp=TEMPERATURE, provider=plan["provider"],
                            max_tokens=plan.get("max_tokens", 60), turn_note=plan["turn_note"])
    expression = _finish(plan, reply)
    await _save_turn(plan, reply)
    return {"reply": reply, "safety": False, "anger": plan["anger"], "delta": plan["change"],
            "session": plan["sid"], "provider": plan["provider"], "round_over": plan["is_win"],
            "round_number": plan["round_number"], "expression": expression}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatReq):
    plan = await _prepare_chat(req)
    return StreamingResponse(
        _stream_answer(plan), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _tts_response(text: str, mode: str, lang: str, provider: str) -> Response:
    text = voice.clean_for_speech(text)
    if not text:
        raise HTTPException(400, "Nothing to say.")
    provider = "google" if provider == "google" else "edge"
    voice_name, pitch, rate = voice.get_voice_for_character(mode, provider, text=text, lang=lang)
    key = (provider, voice_name, pitch, rate, text)
    cached = voice.AUDIO_CACHE.get(key)
    headers = {"Cache-Control": "private, max-age=3600"}
    if cached:
        return Response(cached, media_type="audio/mpeg", headers=headers)

    attempts = [(voice.get_tts_provider(provider), voice_name, pitch, rate)]
    if provider != "google":
        attempts.append((voice.get_tts_provider("google"), "", "", ""))
    for engine, vname, vpitch, vrate in attempts:
        gen = engine.stream(text, vname, vpitch, vrate)
        try:
            first = await gen.__anext__()  # fail fast here so we can fall back
        except Exception as exc:
            log.warning("TTS %s failed: %s", engine.name, type(exc).__name__)
            await gen.aclose()
            continue

        async def body(gen=gen, first=first, cache_key=(engine.name, vname, vpitch, vrate, text)):
            buf = bytearray(first)
            yield first
            try:
                async for chunk in gen:
                    buf += chunk
                    yield chunk
            finally:
                await gen.aclose()
            voice.AUDIO_CACHE.put(cache_key if cache_key[0] == provider else key, bytes(buf))

        return StreamingResponse(body(), media_type="audio/mpeg", headers=headers)
    raise HTTPException(502, "Voice is unavailable right now (needs internet). Text still works.")


@app.post("/api/tts")
async def text_to_speech(req: TTSReq):
    """Stream MP3 speech for a line. Audio starts flowing as soon as it is synthesised."""
    return await _tts_response(req.text, req.mode, req.lang, req.provider)


@app.get("/api/tts")
async def text_to_speech_get(text: str = Query(..., max_length=1200), mode: str = "boss",
                             lang: str = "ml", provider: str = "edge"):
    return await _tts_response(text, mode, lang, provider)


@app.post("/api/rematch")
def rematch(req: RematchReq):
    """Reset the round and return a fresh opening line."""
    mode = req.mode if req.mode in personas.MODES else "boss"
    mode_cfg = personas.MODES[mode]
    sid = _session_id(req.session)
    session = STORE.get(sid, mode_cfg["start"])
    session.new_round()
    lang = req.lang if req.lang in LANGS else "ml"
    opener = mode_cfg["openers"].get(lang) or mode_cfg["openers"]["en"]
    return {"session": sid, "round_number": session.round_number, "anger": session.anger,
            "opener": opener, "expression": "angry"}


@app.post("/api/coach")
async def coach(req: CoachReq):
    if req.mode not in personas.MODES:
        raise HTTPException(400, "Unknown character.")
    msgs = _clean(req.messages)
    if not any(m.role == "user" for m in msgs):
        raise HTTPException(400, "Say something first, then ask for feedback.")
    label = personas.MODES[req.mode]["label"]
    log_text = "\n".join(("USER: " if m.role == "user" else "CHARACTER: ") + m.text for m in msgs)
    system = personas.COACH.format(label=label)
    if req.scenario in personas.SCENARIOS and personas.SCENARIOS[req.scenario]["mode"] == req.mode:
        system += "\nThe user's practice goal was: " + personas.SCENARIOS[req.scenario]["goal"]
    feedback = await _generate(system, [{"role": "user", "parts": [{"text": log_text}]}],
                               temp=0.5, provider=PROVIDER, max_tokens=400)
    session = STORE.find(req.session)
    texts = [m.text for m in msgs if m.role == "user"]
    steps = session.steps if session else anger.steps_from_history(texts)
    start = personas.MODES[req.mode]["start"]
    end = session.anger if session else start
    return {"feedback": feedback, "parts": coach_sections(feedback), "calm": anger.calm_score(start, end, steps)}


@app.get("/api/history/export")
def history_export():
    return JSONResponse(HISTORY.export(), headers={"Content-Disposition": 'attachment; filename="sparring-history.json"'})


@app.get("/api/history")
def history_list():
    return {"sessions": HISTORY.list(), "stats": HISTORY.stats()}


@app.get("/api/history/{sid}")
def history_get(sid: str):
    data = HISTORY.get(sid)
    if not data:
        raise HTTPException(404, "No saved session with that id.")
    return data


@app.delete("/api/history/{sid}")
def history_delete(sid: str):
    return {"deleted": HISTORY.delete(sid)}


@app.delete("/api/history")
def history_clear():
    return {"deleted": HISTORY.clear()}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def service_worker():
    # Served from the root so it can control the whole app.
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC_DIR / "icon.svg", media_type="image/svg+xml")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
