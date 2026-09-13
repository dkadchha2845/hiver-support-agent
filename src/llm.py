"""Provider-agnostic chat client with on-disk caching.

Default provider is Ollama with an open-weights model, so the whole pipeline
runs for free and offline. Groq / Gemini / OpenRouter free tiers are supported
by setting AGENT_PROVIDER / JUDGE_PROVIDER + the matching API key, which is how
the "stronger judge" sensitivity check in the report was run.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from config import CACHE, LLM_MAX_RETRIES, LLM_TIMEOUT, OLLAMA_HOST


class LLMError(RuntimeError):
    pass


@dataclass
class LLMStats:
    calls: int = 0
    cache_hits: int = 0
    retries: int = 0
    wall_seconds: float = 0.0
    json_repairs: int = 0
    hard_failures: int = 0

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class LLM:
    provider: str
    model: str
    temperature: float = 0.0
    use_cache: bool = True
    stats: LLMStats = field(default_factory=LLMStats)

    # ------------------------------------------------------------ caching
    def _cache_key(self, system: str, user: str, json_mode: bool) -> str:
        """Content hash of everything that changes the *request*.

        Decoding options (seed 7, num_ctx, top_p) are fixed in code and deliberately
        NOT part of the key: they are properties of this repo, not of a call. If you
        change them, clear results/llm_cache or you will be replaying answers
        generated under the old settings.
        """
        blob = json.dumps(
            {
                "p": self.provider,
                "m": self.model,
                "t": self.temperature,
                "s": system,
                "u": user,
                "j": json_mode,
            },
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:40]

    def _cache_path(self, key: str):
        return CACHE / f"{key}.json"

    # ------------------------------------------------------------ public
    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        key = self._cache_key(system, user, json_mode)
        path = self._cache_path(key)
        if self.use_cache and path.exists():
            self.stats.cache_hits += 1
            return json.loads(path.read_text())["response"]

        last_err: Exception | None = None
        t0 = time.time()
        for attempt in range(LLM_MAX_RETRIES):
            try:
                text = self._call(system, user, json_mode)
                self.stats.calls += 1
                self.stats.wall_seconds += time.time() - t0
                path.write_text(
                    json.dumps(
                        {"model": self.model, "provider": self.provider, "response": text}
                    )
                )
                return text
            except Exception as exc:  # noqa: BLE001 - retry on any transport error
                last_err = exc
                self.stats.retries += 1
                time.sleep(1.5 * (attempt + 1))
        self.stats.hard_failures += 1
        self.stats.wall_seconds += time.time() - t0
        raise LLMError(f"{self.provider}/{self.model} failed: {last_err}")

    def chat_json(self, system: str, user: str, schema_hint: dict | None = None) -> dict:
        """Chat that must return a JSON object. Falls back to brace-extraction."""
        raw = self.chat(system, user, json_mode=True)
        obj = _parse_json_loose(raw)
        if obj is None:
            self.stats.json_repairs += 1
            repair = (
                "The following text should have been a single JSON object but is "
                "malformed. Return only the corrected JSON object, nothing else.\n\n"
                + raw[:4000]
            )
            obj = _parse_json_loose(self.chat("You repair malformed JSON.", repair, True))
        if obj is None:
            raise LLMError("could not parse JSON from model output")
        return obj

    # ------------------------------------------------------------ providers
    def _call(self, system: str, user: str, json_mode: bool) -> str:
        fn = {
            "ollama": self._ollama,
            "groq": self._openai_compatible,
            "openrouter": self._openai_compatible,
            "gemini": self._gemini,
        }.get(self.provider)
        if fn is None:
            raise LLMError(f"unknown provider {self.provider!r}")
        return fn(system, user, json_mode)

    def _ollama(self, system: str, user: str, json_mode: bool) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": 5120, "seed": 7},
        }
        if json_mode:
            payload["format"] = "json"
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat", json=payload, timeout=LLM_TIMEOUT
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    def _openai_compatible(self, system: str, user: str, json_mode: bool) -> str:
        if self.provider == "groq":
            base = "https://api.groq.com/openai/v1/chat/completions"
            key = os.environ["GROQ_API_KEY"]
        else:
            base = "https://openrouter.ai/api/v1/chat/completions"
            key = os.environ["OPENROUTER_API_KEY"]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        r = requests.post(
            base,
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _gemini(self, system: str, user: str, json_mode: bool) -> str:
        key = os.environ["GEMINI_API_KEY"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={key}"
        )
        cfg: dict[str, Any] = {"temperature": self.temperature}
        if json_mode:
            cfg["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": cfg,
        }
        r = requests.post(url, json=payload, timeout=LLM_TIMEOUT)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json_loose(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1] if "\n" in text else text
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        pass
    start, depth = text.find("{"), 0
    if start == -1:
        return None
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except Exception:  # noqa: BLE001
                    return None
    return None


def ping(provider: str, model: str) -> bool:
    try:
        LLM(provider, model, use_cache=False).chat("You reply with one word.", "Say OK.")
        return True
    except Exception:  # noqa: BLE001
        return False
