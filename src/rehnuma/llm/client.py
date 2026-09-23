"""LLM clients.

GroqClient talks to Groq's OpenAI-compatible endpoint using only the standard library
(no extra dependency). Configure with environment variables or a `.env` file:

    GROQ_API_KEY=...                 required
    REHNUMA_LLM_MODEL=...            optional; default below. If Groq says the model
                                     doesn't exist, pick a current one from the Groq console.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"   # available on Groq as of Sep-2026


class LLMError(RuntimeError):
    """Any failure talking to the LLM. Callers fall back to the template summary."""


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env reader: KEY=VALUE lines; never overrides real environment variables."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class GroqClient:
    def __init__(self, model: str | None = None, temperature: float = 0.2,
                 max_retries: int = 4, timeout: float = 60.0, max_tokens: int = 1024):
        load_dotenv()
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not set (add it to .env)")
        self.model = model or os.environ.get("REHNUMA_LLM_MODEL", DEFAULT_MODEL)
        self.name = f"groq:{self.model}"
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        # Groq counts max_tokens against the tokens-per-minute limit. Unset, a request
        # reserves the model's full default output: allam-2-7b asked for 6,260 tokens
        # against a 6,000 TPM free-tier limit and got HTTP 413. A summary needs ~300.
        self.max_tokens = max_tokens

    def payload(self, system: str, user: str) -> dict:
        body = {
            "model": self.model, "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"   # reasoning model: don't think for minutes
        return body

    def complete(self, system: str, user: str) -> str:
        body = json.dumps(self.payload(system, user)).encode("utf-8")
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(GROQ_URL, data=body, method="POST", headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "rehnuma/0.1",
            })
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                if e.code == 429 and attempt < self.max_retries:      # rate limited: back off
                    wait = float(e.headers.get("retry-after") or 2 ** attempt * 2)
                    time.sleep(min(wait, 30))
                    continue
                raise LLMError(f"Groq HTTP {e.code}: {detail}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                raise LLMError(f"Groq unreachable: {e}") from e
        raise LLMError("Groq: retries exhausted")