"""Answer a question about the user's OWN bill from the engine's verified facts.

The LLM only phrases: the facts are the BillStory (every number from the bill or the
deterministic engine, audited). The same numeric-faithfulness check as the summary applies:
every number in the answer must be one the engine produced (or one the user wrote in the
question). One retry with feedback, then the deterministic template summary - which is
always correct - so a household never gets an invented number.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rehnuma.explain.faithfulness import numbers_in
from rehnuma.explain.llm_summary import facts_payload
from rehnuma.explain.quality import urdu_share
from rehnuma.explain.render import summarize
from rehnuma.explain.story import BillStory
from rehnuma.llm.client import LLMClient, LLMError

LANG_NAME = {"ur": "Urdu (Urdu script, simple everyday words)", "en": "simple English"}
MAX_CHARS = 900

SYSTEM = """You answer a household's question about ITS OWN electricity bill. Use ONLY the \
verified facts given (JSON from Rehnuma's engine; "reference_summary" is a correct summary of \
them). Rules:
1. Never calculate or invent a number: every number you write must appear in the facts.
2. If the facts do not answer the question, say so in one sentence, then give the facts that \
come closest.
3. Do not quote NEPRA rules or give legal opinions - another part of Rehnuma does that.
4. Answer in {lang}, in 1 to 5 short sentences, in plain words."""

LEAD = {"en": "Here is what your bill shows:", "ur": "آپ کے بل میں یہ ہے:"}


@dataclass
class BillAnswer:
    text: str
    source: str                          # llm | template_fallback | template (no client)
    drafts: list[tuple[str, list[str]]] = field(default_factory=list)
    seconds: float = 0.0
    calls: int = 0


def problems(text: str, story: BillStory, lang: str, question: str = "") -> list[str]:
    allowed = story.allowed_numbers() | {abs(x) for x in numbers_in(question)}
    bad = sorted({str(x) for x in numbers_in(text) if abs(x) not in allowed})
    out = []
    if not text.strip():
        out.append("the answer was empty")
    if bad:
        out.append("these numbers are not in the facts: " + ", ".join(bad)
                   + " - use only numbers from the facts")
    share = urdu_share(text)
    if (lang == "ur" and share < 0.5) or (lang == "en" and share > 0.1):
        out.append(f"write the answer in {LANG_NAME[lang]}")
    if len(text) > MAX_CHARS:
        out.append("the answer is too long - at most 5 short sentences")
    return out


def template_answer(story: BillStory, lang: str) -> str:
    return LEAD[lang] + "\n" + "\n".join(f"- {line}" for line in summarize(story, lang))


def bill_answer(question: str, story: BillStory, client: LLMClient | None, lang: str = "ur",
                max_attempts: int = 2) -> BillAnswer:
    start = time.perf_counter()
    if client is None:
        return BillAnswer(template_answer(story, lang), "template")
    base = f"Question: {question}\n\nFacts:\n{facts_payload(story, lang)}"
    user, drafts, calls = base, [], 0
    for _ in range(max_attempts):
        try:
            draft = client.complete(SYSTEM.format(lang=LANG_NAME[lang]), user).strip()
            calls += 1
        except LLMError as e:
            drafts.append(("", [f"LLM error: {str(e)[:120]}"]))
            break
        probs = problems(draft, story, lang, question)
        drafts.append((draft, probs))
        if not probs:
            return BillAnswer(draft, "llm", drafts, time.perf_counter() - start, calls)
        user = (f"{base}\n\nYour previous answer:\n{draft}\n\nThe checker rejected it for these "
                f"reasons only: {'; '.join(probs)}. Fix exactly these problems and keep "
                f"everything else unchanged.")
    return BillAnswer(template_answer(story, lang), "template_fallback", drafts,
                      time.perf_counter() - start, calls)

