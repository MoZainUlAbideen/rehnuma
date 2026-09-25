"""Tracing with Langfuse - optional, and off unless configured.

On only when BOTH are true:
  * the `obs` extra is installed (`uv sync --extra obs`), and
  * LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set (.env locally, Render env vars live).
    LANGFUSE_BASE_URL picks the region (https://cloud.langfuse.com EU, the default, or
    https://us.cloud.langfuse.com); LANGFUSE_TRACING_ENVIRONMENT=production on Render keeps
    live traffic apart from local runs and evals.
Otherwise every call here is a no-op, so tests, CI and a key-less deploy behave exactly as
before. A tracing failure must never break an answer: errors inside the SDK are swallowed.

What a trace holds, per question: the API call -> the assistant (route) -> the bill answer
and/or the policy answer -> retrieval (query, clauses returned) -> each LLM call (prompt,
draft, tokens, latency) and the critic's verdict on every draft. Photo reading adds the
vision calls and which checks failed.

Privacy: bill photos are NEVER sent (the vision span records only type and size). Any run of
10+ digits (phone, CNIC, reference and consumer numbers) is replaced with "[number]"
before anything leaves the process - the bill schema already has no identifier fields.
"""

from __future__ import annotations

import atexit
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

LONG_NUMBER = re.compile(r"(?<!\d)\d(?:[\s-]?\d){9,}(?!\d)")

_client: Any = None
_checked = False


def mask(data: Any = None, **_: Any) -> Any:
    """Redact long digit runs anywhere in strings, dicts and lists."""
    if isinstance(data, str):
        return LONG_NUMBER.sub("[number]", data)
    if isinstance(data, dict):
        return {k: mask(v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [mask(v) for v in data]
    return data


def _langfuse_mask(*, data: Any, **kwargs: Any) -> Any:
    return mask(data)


def client() -> Any:
    """The Langfuse client, or None when tracing is off."""
    global _client, _checked
    if _checked:
        return _client
    _checked = True
    from rehnuma.llm.client import load_dotenv
    load_dotenv()
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import Langfuse
    except ImportError:
        return None
    try:
        _client = Langfuse(mask=_langfuse_mask)
        atexit.register(flush)                    # CLIs and evals exit before a batch ships
    except Exception:                             # noqa: BLE001 - tracing must never break us
        _client = None
    return _client


def set_client(c: Any) -> None:
    """Tests: install a client built with an in-memory exporter (or None to switch off)."""
    global _client, _checked
    _client, _checked = c, True


class _Null:
    def update(self, **_: Any) -> None:
        pass


class _Safe:
    """Wraps an observation so a failing update can't take the request down."""

    def __init__(self, obs: Any):
        self._obs = obs

    def update(self, **kwargs: Any) -> None:
        try:
            self._obs.update(**kwargs)
        except Exception:                         # noqa: BLE001
            pass


@contextmanager
def observe(name: str, as_type: str = "span", **kwargs: Any) -> Iterator[Any]:
    """`with observe("policy.answer", as_type="chain", input=...) as o: ...; o.update(...)`.
    Nests automatically. Exceptions from the wrapped code propagate unchanged (and are
    recorded as an ERROR on the observation)."""
    c = client()
    if c is None:
        yield _Null()
        return
    try:
        cm = c.start_as_current_observation(name=name, as_type=as_type, **kwargs)
        obs = cm.__enter__()
    except Exception:                             # noqa: BLE001
        yield _Null()
        return
    try:
        yield _Safe(obs)
    except BaseException as e:
        _Safe(obs).update(level="ERROR", status_message=str(e)[:300])
        cm.__exit__(type(e), e, e.__traceback__)
        raise
    else:
        try:
            cm.__exit__(None, None, None)
        except Exception:                         # noqa: BLE001
            pass


def usage(data: dict) -> dict[str, int] | None:
    """OpenAI-style `usage` -> Langfuse usage_details."""
    u = data.get("usage") or {}
    out = {"input": u.get("prompt_tokens"), "output": u.get("completion_tokens")}
    return {k: v for k, v in out.items() if isinstance(v, int)} or None


def flush() -> None:
    c = _client
    if c is not None:
        try:
            c.flush()
        except Exception:                         # noqa: BLE001
            pass
