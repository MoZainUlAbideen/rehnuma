"""Urdu question -> English search query.

The NEPRA documents are English; BM25 and character n-grams cannot match Urdu script
against them (the retrieval eval shows hit@5 = 0 for Urdu without this step). One short LLM
call turns the question into English search terms; answering still happens in the user's
language later.
"""

from __future__ import annotations

import re

from rehnuma.llm.client import LLMClient, LLMError

URDU = re.compile(r"[؀-ۿ]")

REWRITE_SYSTEM = (
    "You turn a Pakistani electricity consumer's question into an English search query for "
    "NEPRA regulations and the Consumer Service Manual. Use the regulatory terms those "
    "documents use (net billing, net metering, prosumer, distributed generation, sanctioned "
    "load, billing cycle, DISCO, defective meter, detection bill, national average energy "
    "purchase price...). Reply with the query only: one line, no quotes, no explanation."
)


def needs_rewrite(query: str) -> bool:
    return bool(URDU.search(query))


def rewrite(query: str, client: LLMClient | None) -> tuple[str, str | None]:
    """(query to search with, error). English queries pass through unchanged."""
    if not needs_rewrite(query) or client is None:
        return query, None
    try:
        out = client.complete(REWRITE_SYSTEM, query).strip().splitlines()
    except LLMError as e:
        return query, str(e)[:200]
    line = next((ln.strip().strip('"') for ln in out if ln.strip()), "")
    return (line, None) if line else (query, "empty rewrite")
