"""Question -> search query in the documents' own vocabulary.

Two gaps, one fix:
  * Urdu: the NEPRA documents are English; BM25 and character n-grams cannot match Urdu
    script against them (retrieval eval: hit@5 = 0% for Urdu without this step).
  * English: people say "export" and "solar"; the regulations say "kWh supplied by
    prosumer to the licensee" and "distributed generation facility". In the eval, the
    REWRITTEN Urdu questions beat the raw English ones on the same topic (p1-ur rank 1 vs
    p1 rank 4), so English questions are rewritten too (mode "all").

For English the user's words and the rewrite are searched as two queries whose rankings
are fused (search_queries), so a rewrite can add vocabulary but never dilute what the user
said. A first version concatenated them and lost more than it gained (dev hit@5 88% -> 75%).
Answering still happens in the user's language later.

The terms in REWRITE_SYSTEM were chosen after seeing dev-set misses; the held-out split in
the retrieval eval is what shows whether they generalise.
"""

from __future__ import annotations

import re

from rehnuma.llm.client import LLMClient, LLMError

URDU = re.compile(r"[\u0600-\u06FF]")        # Arabic-script block (Urdu)

REWRITE_SYSTEM = (
    "You turn a Pakistani electricity consumer's question into an English search query for "
    "NEPRA regulations and the Consumer Service Manual. Use the regulatory terms those "
    "documents use (net billing, net metering, prosumer, distributed generation, sanctioned "
    "load, billing cycle, DISCO, defective meter, detection bill, national average energy "
    "purchase price...). Everyday words map to the documents' wording, e.g. units a solar "
    "system exports = kWh supplied by prosumer/distributed generator to the licensee; units "
    "taken from the grid = kWh supplied by licensee; solar system = distributed generation "
    "facility; WAPDA/electricity company = licensee/DISCO. Reply with the query only: one "
    "line, no quotes, no explanation. Do not name the documents themselves (no NEPRA, "
    "Consumer Service Manual, regulations) and do not add topics the question does not raise; "
    "keep every condition the user states (e.g. an agreement signed before 2026)."
)

MODES = ("urdu", "all")


def needs_rewrite(query: str) -> bool:
    return bool(URDU.search(query))


def rewrite(query: str, client: LLMClient | None, mode: str = "urdu"
            ) -> tuple[str | None, str | None]:
    """(rewrite or None, error). mode "urdu": only Urdu is rewritten; "all": English too."""
    if client is None or (mode == "urdu" and not needs_rewrite(query)):
        return None, None
    try:
        out = client.complete(REWRITE_SYSTEM, query).strip().splitlines()
    except LLMError as e:
        return None, str(e)[:200]
    line = next((ln.strip().strip('"') for ln in out if ln.strip()), "")
    return (line, None) if line else (None, "empty rewrite")


# Names of the SOURCES, not of what the question is about. The rewriter kept appending
# "NEPRA Consumer Service Manual" / "NEPRA regulations" (6 of 27 English rewrites); those
# words occur all over the corpus and dragged p4 (grandfathered export price) into CSM
# billing clauses. Stripped before searching.
_SOURCE_NAMES = re.compile(r"(?i)\b(?:NEPRA|consumer service manual|CSM|prosumer regulations"
                           r"|net metering regulations|regulations?|DISCO licensing orders?)\b")


def clean_rewrite(text: str) -> str:
    return " ".join(_SOURCE_NAMES.sub(" ", text).split())


def search_queries(query: str, rewritten: str | None) -> tuple[str, tuple[str, ...]]:
    """(primary query, extra queries) for PolicyIndex.search.

    Urdu: search the English rewrite only (Urdu script matches nothing in English text).
    English: search the user's words, and the rewrite as a SEPARATE query fused by rank -
    concatenating them diluted the user's precise terms (dev hit@5 88% -> 75%)."""
    rewritten = clean_rewrite(rewritten) if rewritten else None
    if not rewritten:
        return query, ()
    if needs_rewrite(query):
        return rewritten, ()
    return query, (rewritten,)
