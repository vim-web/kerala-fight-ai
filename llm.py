"""Model providers: Gemini (cloud) and Ollama (local), both truly streaming.

Latency notes (why this file exists):
- Gemini is called with `streamGenerateContent?alt=sse`, so the first words reach
  the phone while the rest is still being generated. The old code waited for the
  whole reply.
- gemini-2.5-flash "thinks" before answering by default. Thinking adds seconds and,
  worse, spends the tiny output budget, which gave empty or cut-off replies. For
  short banter we switch it off (thinkingBudget=0) on 2.5 Flash models.
- Ollama on a laptop CPU spends most of its time reading the prompt. We keep the
  static part of the prompt first and unchanged, and put per-turn instructions at
  the end, so Ollama can reuse its cached prefix instead of re-reading everything.
- One shared HTTP client keeps connections warm (no new TLS handshake per turn).

Errors are raised as `ProviderError` with a short, friendly message that is safe to
show in the UI. Raw provider responses are logged (truncated) but never sent on.
"""

import json
import logging
import os
from typing import AsyncIterator, Optional

import httpx

log = logging.getLogger("sparring.llm")

PLACEHOLDER_PREFIXES = ("your_", "your-", "<", "xxx", "changeme", "paste")


def real_key(raw: Optional[str]) -> str:
    """Return the key only if it looks real (not empty, not a .env placeholder)."""
    key = (raw or "").strip().strip('"').strip("'")
    if len(key) < 20 or key.lower().startswith(PLACEHOLDER_PREFIXES):
        return ""
    return key


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class ProviderError(Exception):
    """A model call failed. `message` is safe to show the user."""

    def __init__(self, message: str, *, kind: str = "error", status: int = 502):
        super().__init__(message)
        self.message = message
        self.kind = kind  # "config" | "auth" | "rate" | "timeout" | "offline" | "blocked" | "error"
        self.status = status

    @property
    def can_fallback(self) -> bool:
        # Switching provider helps for setup/quota/network problems, not for blocked content.
        return self.kind in ("config", "auth", "rate", "timeout", "offline", "error")


# ---------------------------------------------------------------- shared client

_client_instance: Optional[httpx.AsyncClient] = None


def client() -> httpx.AsyncClient:
    global _client_instance
    if _client_instance is None or _client_instance.is_closed:
        _client_instance = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=6.0),
            limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=120),
        )
    return _client_instance


async def close() -> None:
    global _client_instance
    if _client_instance is not None and not _client_instance.is_closed:
        await _client_instance.aclose()
    _client_instance = None


# ---------------------------------------------------------------- Gemini

class Gemini:
    def __init__(self) -> None:
        self.key = real_key(os.getenv("GEMINI_API_KEY"))
        self.model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()
        base = "https://generativelanguage.googleapis.com/v1beta/models"
        self.url = f"{base}/{self.model}:generateContent"
        self.stream_url = f"{base}/{self.model}:streamGenerateContent?alt=sse"
        raw_budget = os.getenv("GEMINI_THINKING_BUDGET", "").strip()
        self.thinking_budget: Optional[int] = int(raw_budget) if raw_budget.lstrip("-").isdigit() else None

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _body(self, system: str, contents: list, temp: float, max_tokens: int) -> dict:
        config: dict = {"temperature": temp, "maxOutputTokens": max_tokens}
        budget = self.thinking_budget
        if budget is None and "2.5-flash" in self.model:
            budget = 0  # no thinking for quick banter: faster and no wasted tokens
        if budget is not None:
            config["thinkingConfig"] = {"thinkingBudget": budget}
        return {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": config,
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            ],
        }

    @staticmethod
    def _error(status: int, body: str) -> ProviderError:
        log.warning("Gemini HTTP %s: %s", status, (body or "")[:300].replace("\n", " "))
        low = (body or "").lower()
        if status in (401, 403) or "api key not valid" in low or "api_key_invalid" in low:
            return ProviderError("Gemini rejected the API key. Check GEMINI_API_KEY in .env.", kind="auth")
        if status == 429 or "resource_exhausted" in low:
            return ProviderError("Cloud free-tier limit reached. Wait a minute, or switch to Local.", kind="rate", status=429)
        if status == 404:
            return ProviderError("Gemini model not found. Check GEMINI_MODEL in .env.", kind="config")
        if status >= 500:
            return ProviderError("Gemini is having trouble right now. Try again.", kind="error")
        return ProviderError("The cloud model refused the request. Try again.", kind="error")

    @staticmethod
    def _text(data: dict) -> str:
        out = []
        for cand in data.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                if isinstance(part.get("text"), str) and not part.get("thought"):
                    out.append(part["text"])
        return "".join(out)

    def _check(self) -> None:
        if not self.key:
            raise ProviderError("Cloud model is not set up. Add GEMINI_API_KEY to .env, or switch to Local.", kind="config", status=400)

    async def chat(self, system: str, contents: list, temp: float, max_tokens: int) -> str:
        self._check()
        try:
            res = await client().post(
                self.url, json=self._body(system, contents, temp, max_tokens),
                headers={"x-goog-api-key": self.key}, timeout=httpx.Timeout(40.0, connect=6.0),
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("The cloud model took too long. Try again.", kind="timeout", status=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach the cloud model. Check your internet.", kind="offline") from exc
        if res.status_code != 200:
            raise self._error(res.status_code, res.text)
        data = res.json()
        text = self._text(data).strip()
        if not text and (data.get("promptFeedback") or {}).get("blockReason"):
            raise ProviderError("That line got blocked by the cloud filter. Try saying it differently.", kind="blocked")
        return text

    async def stream(self, system: str, contents: list, temp: float, max_tokens: int) -> AsyncIterator[str]:
        self._check()
        try:
            async with client().stream(
                "POST", self.stream_url, json=self._body(system, contents, temp, max_tokens),
                headers={"x-goog-api-key": self.key}, timeout=httpx.Timeout(40.0, connect=6.0),
            ) as res:
                if res.status_code != 200:
                    raise self._error(res.status_code, (await res.aread()).decode("utf-8", "replace"))
                blocked = False
                async for line in res.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if (data.get("promptFeedback") or {}).get("blockReason"):
                        blocked = True
                    piece = self._text(data)
                    if piece:
                        yield piece
                if blocked:
                    raise ProviderError("That line got blocked by the cloud filter. Try saying it differently.", kind="blocked")
        except httpx.TimeoutException as exc:
            raise ProviderError("The cloud model took too long. Try again.", kind="timeout", status=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach the cloud model. Check your internet.", kind="offline") from exc


# ---------------------------------------------------------------- Ollama

class Ollama:
    def __init__(self) -> None:
        self.url = (os.getenv("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL") or "llama3.2:3b"
        self.num_ctx = _int_env("OLLAMA_NUM_CTX", 2048)
        self.num_thread = _int_env("OLLAMA_NUM_THREAD", 4)
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

    @staticmethod
    def window(contents: list) -> list:
        """Trim history in steps of 8 so the start point (and cached prefix) stays put
        for several turns, instead of sliding by one message every turn."""
        if len(contents) <= 12:
            return contents
        start = ((len(contents) - 6) // 8) * 8
        return contents[start:]

    def messages(self, system: str, contents: list, turn_note: str = "") -> list:
        hist = self.window(contents)
        msgs = [{"role": "system", "content": system}]
        msgs += [
            {"role": "assistant" if c["role"] == "model" else "user", "content": c["parts"][0]["text"]}
            for c in hist[:-1]
        ]
        if turn_note:
            msgs.append({"role": "system", "content": turn_note})
        if hist:
            last = hist[-1]
            msgs.append({"role": "assistant" if last["role"] == "model" else "user", "content": last["parts"][0]["text"]})
        return msgs

    def _body(self, system, contents, temp, max_tokens, stream, turn_note):
        return {
            "model": self.model,
            "messages": self.messages(system, contents, turn_note),
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temp,
                "num_predict": max_tokens,
                "num_ctx": self.num_ctx,
                "num_thread": self.num_thread,
            },
        }

    @staticmethod
    def _err(exc: Exception) -> ProviderError:
        if isinstance(exc, httpx.ConnectError):
            return ProviderError("Local model is not running. Start Ollama, or switch to Cloud.", kind="offline")
        if isinstance(exc, httpx.TimeoutException):
            return ProviderError("The local model is too slow right now. Try again.", kind="timeout", status=504)
        return ProviderError("Could not reach the local model.", kind="offline")

    async def chat(self, system, contents, temp, max_tokens, turn_note: str = "") -> str:
        try:
            res = await client().post(f"{self.url}/api/chat", json=self._body(system, contents, temp, max_tokens, False, turn_note))
        except httpx.HTTPError as exc:
            raise self._err(exc) from exc
        if res.status_code != 200:
            log.warning("Ollama HTTP %s: %s", res.status_code, res.text[:300])
            if res.status_code == 404:
                raise ProviderError(f"Local model '{self.model}' is not downloaded. Run: ollama pull {self.model}", kind="config")
            raise ProviderError("The local model returned an error.", kind="error")
        return ((res.json().get("message") or {}).get("content") or "").strip()

    async def stream(self, system, contents, temp, max_tokens, turn_note: str = "") -> AsyncIterator[str]:
        try:
            async with client().stream("POST", f"{self.url}/api/chat", json=self._body(system, contents, temp, max_tokens, True, turn_note)) as res:
                if res.status_code != 200:
                    body = (await res.aread()).decode("utf-8", "replace")
                    log.warning("Ollama HTTP %s: %s", res.status_code, body[:300])
                    if res.status_code == 404:
                        raise ProviderError(f"Local model '{self.model}' is not downloaded. Run: ollama pull {self.model}", kind="config")
                    raise ProviderError("The local model returned an error.", kind="error")
                async for line in res.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    piece = (data.get("message") or {}).get("content") or ""
                    if piece:
                        yield piece
                    if data.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise self._err(exc) from exc

    async def warm_up(self) -> None:
        try:
            await client().post(f"{self.url}/api/generate", json={"model": self.model, "keep_alive": self.keep_alive},
                                timeout=httpx.Timeout(60.0, connect=3.0))
            log.info("Ollama model warmed up")
        except Exception as exc:  # warm-up is best effort
            log.info("Ollama warm-up skipped: %s", type(exc).__name__)

