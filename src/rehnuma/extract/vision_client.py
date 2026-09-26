"""Vision LLM client for any OpenAI-compatible endpoint (standard library only).

Default provider: Google Gemini via its OpenAI-compatible API (free key from AI Studio).
Configure in `.env`:

    GEMINI_API_KEY=...
    REHNUMA_VISION_MODEL=gemini-3.8-flash      # optional; list yours with --list-models
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rehnuma import obs
from rehnuma.llm.client import LLMError, load_dotenv


class VisionClient(Protocol):
    name: str

    def read(self, system: str, prompt: str, image: bytes, mime: str) -> str: ...


@dataclass(frozen=True)
class Provider:
    base_url: str
    key_env: str
    default_model: str


PROVIDERS = {
    "gemini": Provider("https://generativelanguage.googleapis.com/v1beta/openai",
                       "GEMINI_API_KEY", "gemini-3.5-flash"),
    "groq": Provider("https://api.groq.com/openai/v1", "GROQ_API_KEY", ""),
}


RETRY_DELAY = re.compile(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"')
# Gemini names the quota it enforced ("GenerateRequestsPerDayPerProjectPerModel-FreeTier").
DAILY_QUOTA = re.compile(r"per\s*day", re.IGNORECASE)


class QuotaExhausted(LLMError):
    """The provider's quota is spent. A daily quota does not come back in a few seconds, so
    retrying only burns minutes: callers should stop and try again later."""


def is_daily_quota(detail: str) -> bool:
    return bool(DAILY_QUOTA.search(detail))


def retry_after(headers, detail: str, attempt: int) -> float:
    """Gemini says how long to wait inside the error body ("retryDelay": "37s"). Use it;
    fixed 3/6/12/24 s waits were far too short for a quota limit."""
    if headers.get("retry-after"):
        return float(headers["retry-after"])
    m = RETRY_DELAY.search(detail)
    return float(m.group(1)) + 1 if m else 2 ** attempt * 5


def mime_for(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    return {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")


class OpenAICompatVision:
    def __init__(self, provider: str = "gemini", model: str | None = None,
                 max_tokens: int = 8192, timeout: float = 120.0, max_retries: int = 4):
        load_dotenv()
        p = PROVIDERS[provider]
        self.key = os.environ.get(p.key_env)
        if not self.key:
            raise LLMError(f"{p.key_env} is not set (add it to .env)")
        self.base_url = p.base_url
        self.model = model or os.environ.get("REHNUMA_VISION_MODEL") or p.default_model
        if not self.model:
            raise LLMError("no vision model given (use --model or REHNUMA_VISION_MODEL)")
        self.name = f"{provider}:{self.model}"
        self.max_tokens, self.timeout, self.max_retries = max_tokens, timeout, max_retries

    def _request(self, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(f"{self.base_url}/{path}", data=data,
                                         method="POST" if data else "GET", headers={
                "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                "User-Agent": "rehnuma/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")
                message = " ".join(detail.split())[:600]     # keep which quota was hit
                if e.code == 429 and is_daily_quota(detail):
                    # Waiting 90 s x 4 retries cannot bring back a DAILY quota (seen live:
                    # 3 minutes lost per bill before giving up)
                    raise QuotaExhausted(f"{self.name} daily quota used up: {message}") from e
                if e.code in (429, 503) and attempt < self.max_retries:
                    time.sleep(min(retry_after(e.headers, detail, attempt), 90))
                    continue
                if e.code == 429:
                    raise QuotaExhausted(f"{self.name} still rate-limited after "
                                         f"{self.max_retries} retries: {message}") from e
                raise LLMError(f"{self.name} HTTP {e.code}: {message}") from e
            except (OSError, http.client.HTTPException) as e:   # URLError, timeouts, resets
                raise LLMError(f"{self.name} unreachable: {e}") from e
        raise LLMError(f"{self.name}: retries exhausted")

    def list_models(self) -> list[str]:
        return sorted(m["id"] for m in self._request("models")["data"])

    def read(self, system: str, prompt: str, image: bytes, mime: str) -> str:
        # the photo itself is never traced - only its type and size
        with obs.observe("vision", as_type="generation", model=self.model,
                         input={"system": system, "prompt": prompt,
                                "image": f"<{mime}, {len(image)} bytes - not recorded>"}) as gen:
            data = self._read(system, prompt, image, mime)
            try:
                text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                raise LLMError(f"{self.name}: unexpected response shape") from e
            gen.update(output=text, usage_details=obs.usage(data))
            return text

    def _read(self, system: str, prompt: str, image: bytes, mime: str) -> dict:
        b64 = base64.b64encode(image).decode("ascii")
        body = {
            "model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ]},
            ],
        }
        return self._request("chat/completions", body)