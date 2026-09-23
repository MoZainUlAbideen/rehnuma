"""LLM summary with a deterministic critic.

    draft  ->  critic (numbers / coverage / language)  ->  retry with feedback  ->  ...
                                                         -> template fallback

The LLM gets the verified facts (and the template summary as a reference) and is asked
to say them the way a helpful lineman would. It is never trusted with arithmetic: the
critic rejects any number that is not in the BillStory. After `max_attempts` failed
drafts, the user gets the template summary instead - never an unchecked one.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

from rehnuma.explain.quality import Quality, assess, required_numbers
from rehnuma.explain.render import summarize
from rehnuma.explain.story import BillStory
from rehnuma.llm.client import LLMClient, LLMError

LANG_NAME = {"ur": "Urdu (Urdu script, simple everyday words)", "en": "simple English"}

SYSTEM = """You explain Pakistani electricity bills to ordinary households, many of whom do \
not read bills and would normally ask the lineman to explain. Write like a kind, patient \
lineman: short, clear sentences, no jargon.

Hard rules:
1. Use ONLY numbers that appear in the FACTS. Never add, subtract, estimate or round numbers \
yourself. If a number is not in the FACTS, do not state it.
2. Write digits as 0-9 (not Urdu/Arabic digits). Keep tariff codes like A-1a exactly as given.
3. Start with what the household must pay (or their credit) and by when.
4. Output 5 to 8 lines, each starting with "- ". No headings, no extra commentary."""


def facts_payload(story: BillStory, lang: str) -> str:
    facts = asdict(story)
    facts["due_date"] = story.due_date.isoformat() if story.due_date else None
    return json.dumps({
        "language": LANG_NAME[lang],
        "must_mention": required_numbers(story),
        "facts": facts,
        "reference_summary": summarize(story, lang),
    }, ensure_ascii=False, indent=1, default=str)


def _feedback(q: Quality, lang: str) -> str:
    parts = []
    if q.unsupported:
        parts.append("These numbers are NOT in the facts; remove them: "
                     + ", ".join(str(x) for x in q.unsupported))
    if q.missing:
        parts.append("You left out: " + ", ".join(q.missing))
    if not q.language_ok:
        parts.append(f"Write the whole summary in {LANG_NAME[lang]}.")
    return "Your previous draft was rejected. " + " ".join(parts) + " Write it again."


@dataclass
class SummaryResult:
    text: str
    source: str                     # "llm" | "template_fallback"
    attempts: int
    quality: Quality
    drafts_rejected: list[dict] = field(default_factory=list)
    latency_s: float = 0.0


def llm_summary(story: BillStory, client: LLMClient, lang: str = "ur",
                max_attempts: int = 3) -> SummaryResult:
    start = time.perf_counter()
    user = facts_payload(story, lang)
    rejected: list[dict] = []
    for attempt in range(1, max_attempts + 1):
        try:
            draft = client.complete(SYSTEM, user).strip()
        except LLMError as e:          # rate limit, too large, network... -> template
            rejected.append({"attempt": attempt, "text": "", "error": str(e)[:300],
                             "unsupported": [], "missing": [], "language_ok": False})
            break
        q = assess(draft, story, lang)
        if q.passed:
            return SummaryResult(draft, "llm", attempt, q, rejected,
                                 time.perf_counter() - start)
        rejected.append({"attempt": attempt, "text": draft,
                         "unsupported": [str(x) for x in q.unsupported],
                         "missing": q.missing, "language_ok": q.language_ok})
        user = facts_payload(story, lang) + "\n\n" + _feedback(q, lang)
    text = "\n".join(f"- {line}" for line in summarize(story, lang))
    return SummaryResult(text, "template_fallback", max_attempts, assess(text, story, lang),
                         rejected, time.perf_counter() - start)
