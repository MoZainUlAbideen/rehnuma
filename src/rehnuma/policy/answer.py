"""Cited answers from NEPRA clauses, checked by a deterministic critic.

    question -> rewrite -> fused retrieval -> [S1..Sk] sources -> LLM draft
                                                  ^                    |
                                                  +--- critic feedback -+ (one retry)

The LLM may only use the numbered sources. The critic (no LLM) rejects a draft when:
  * it cites a source tag that was not provided ([S9] of 5),
  * a sentence carries no source tag,
  * a number is not in any cited source (or in the question / the source's label) -
    "thirty days" in a source supports "30 days" in the answer,
  * an Urdu answer is not mostly Urdu script (or an English one is),
  * it relies on a REPEALED source without saying the rule is old.
Feedback names the problems, never the answer. If the retry fails too, the user gets an
honest fallback that lists the relevant clauses instead of an unverified answer. The model
answers NOT_FOUND when the sources don't cover the question -> a polite refusal.

Rehnuma never calculates bills here: arithmetic belongs to the engine, not the LLM.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from rehnuma.llm.client import LLMClient, LLMError
from rehnuma.policy.parse import Chunk
from rehnuma.policy.query import needs_rewrite, rewrite, search_queries
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.policy.sources import Document, load_sources

K = 5
SOURCE_CHARS = 900          # per source: keeps a request ~2k tokens (Groq free-tier TPM/TPD)
NOT_FOUND = "NOT_FOUND"
URDU_MIN_SHARE = 0.5        # Urdu answers keep Latin terms (NEPRA, kWh, DISCO) - 0.5 not 0.6

LANG_NAME = {"ur": "Urdu (Urdu script, simple everyday words)", "en": "simple English"}

SYSTEM = """You answer questions from Pakistani electricity consumers using ONLY the numbered \
NEPRA sources given to you.
Rules:
1. End every sentence with the tag(s) of the source(s) it relies on, e.g. [S2] or [S1][S3].
2. State only what the sources say. No outside knowledge, no guesses, no personal advice.
3. If the sources do not answer the question at all, reply with exactly NOT_FOUND and nothing \
else. If they answer only part of it, answer that part and say which part they do not cover.
4. If you rely on a source marked REPEALED, say clearly that it is the old (repealed) rule, and \
cite the source marked SAVINGS CLAUSE for when the old rule still applies. Take that from the \
savings clause's text only.
5. Copy numbers exactly as the source gives them (you may write "thirty days" as 30 days).
6. Never calculate bill amounts.
7. Answer in {lang}, in 2 to 6 short sentences. Write the tags as [S1], [S2] in Latin letters.
8. Write the name of any price or rate exactly as the source writes it, in English, even in an \
Urdu answer, e.g. (national average power purchase price). Never translate or shorten it: the \
"power" and "energy" purchase prices are different rates.
Format example: "The agreement lasts five years [S2]. It can be ended by written notice [S1]."
"""

REFUSED = {
    "en": "Sorry, I could not find this in the NEPRA documents I have. Please check with your "
          "electricity company (DISCO) or NEPRA.",
    "ur": "معذرت، یہ بات میرے پاس موجود نیپرا کے دستاویزات میں نہیں ملی۔ براہِ کرم اپنی بجلی "
          "کمپنی (DISCO) یا نیپرا سے رابطہ کریں۔",
}
FALLBACK = {
    "en": "I could not write an answer I was able to verify. These are the rules that apply:",
    "ur": "میں اس سوال کا تصدیق شدہ جواب نہیں بنا سکا۔ متعلقہ قواعد یہ ہیں:",
}
UNAVAILABLE = {
    "en": "The answer service is unavailable right now. Please try again later.",
    "ur": "جواب دینے کی سروس ابھی دستیاب نہیں۔ براہِ کرم کچھ دیر بعد دوبارہ کوشش کریں۔",
}
# words a repealed-source answer must contain (either language may mix)
REPEAL_MARKERS = ("repeal", "old ", "older", "previous", "earlier", "2015",
                  "منسوخ", "پرانے", "پرانی", "پرانا", "سابقہ", "پہلے والے")


# --- sources --------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    tag: str                 # "S1"
    chunk: Chunk
    doc: Document
    savings_for: str = ""    # set when this clause was ADDED as the savings clause of a
                             # repealed document ("Net Metering Regs 2015")

    @property
    def repealed(self) -> bool:
        return self.doc.status == "repealed"

    @property
    def label(self) -> str:
        c = self.chunk
        if c.clause[0].isdigit():
            unit = f"reg. {c.clause}" if self.doc.style == "regulations" else f"clause {c.clause}"
        elif c.clause.startswith("p") and c.clause[1:].isdigit():
            unit = "text"
        else:
            unit = c.clause
        return f"{self.doc.short}, {unit}, p. {c.page}"

    def render(self) -> str:
        status = (f"REPEALED - {self.doc.note}" if self.repealed and self.doc.note
                  else "REPEALED" if self.repealed else "in force")
        if self.savings_for:
            status += f"; SAVINGS CLAUSE: says when the repealed {self.savings_for} still applies"
        text = self.chunk.text[:SOURCE_CHARS] + ("..." if len(self.chunk.text) > SOURCE_CHARS
                                                  else "")
        return f"[{self.tag}] {self.label} ({status})\n{text}"


def make_sources(chunks: list[Chunk], docs: dict[str, Document],
                 corpus: list[Chunk] | None = None) -> list[Source]:
    """Numbered sources. For every repealed document among them, its savings clause (the
    rule deciding when the old document still applies) is appended from `corpus`.

    Why: a household on a pre-2026 net-metering agreement asked (in Urdu) how its exports
    are priced now. Retrieval returned five clauses of the repealed 2015 rules and missed
    Prosumer Regs 21(2); the model then answered from a paraphrase in our own metadata.
    The clause that decides the answer is now always in front of the model."""
    out = [Source(f"S{i}", c, docs[c.doc_id]) for i, c in enumerate(chunks, 1)]
    have = {(c.doc_id, c.clause) for c in chunks}
    for s in list(out):
        sc = s.doc.savings_clause
        if not (s.repealed and sc and corpus) or sc in have:
            continue
        for c in corpus:
            if (c.doc_id, c.clause) == sc:
                out.append(Source(f"S{len(out) + 1}", c, docs[c.doc_id],
                                  savings_for=s.doc.short))
        have.add(sc)
    return _add_references(out, docs, corpus or [], have)


_REFERENCE = re.compile(r"(?i)\b(annex(?:ure)?|schedule)\s*[-—]?\s*([IVX]{1,5}|\d{1,2})\b")
MAX_REFERENCED = 2


def _add_references(out: list[Source], docs: dict[str, Document], corpus: list[Chunk],
                    have: set) -> list[Source]:
    """Append annexures/schedules that a retrieved clause points to ("The Security Deposit
    rates are as per Annexure - IV"). Without this the model saw the pointer but not the
    rates, and refused a question the manual does answer (c5)."""
    added = 0
    for s in list(out):
        for kind, num in _REFERENCE.findall(s.chunk.text):
            prefix = "Annex" if kind.lower().startswith("annex") else "Schedule"
            clause = f"{prefix}-{num.upper()}"
            key = (s.chunk.doc_id, clause)
            if key in have or added >= MAX_REFERENCED:
                continue
            target = next((c for c in corpus if (c.doc_id, c.clause) == key), None)
            if target:
                out.append(Source(f"S{len(out) + 1}", target, docs[target.doc_id]))
                added += 1
            have.add(key)
    return out


# --- critic ---------------------------------------------------------------------------
TAG = re.compile(r"\[\s*S\s*(\d+)\s*\]")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
          "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50,
          "sixty": 60, "ninety": 90, "hundred": 100, "thousand": 1000}
_WORD_RE = re.compile(r"(?i)\b(" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")\b")


def numbers_in(text: str) -> set[str]:
    """Numbers as normalised strings; Urdu digits and English number words included."""
    text = text.translate(_DIGITS)
    out = {n.replace(",", "").rstrip(".") for n in _NUMBER.findall(text)}
    out |= {str(_WORDS[w.lower()]) for w in _WORD_RE.findall(text)}
    return {n[:-2] if n.endswith(".0") else n for n in out}


def urdu_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum("؀" <= c <= "ۿ" for c in letters) / len(letters) if letters else 0.0


_TRAILING_TAGS = re.compile(r"([.!?۔؟])\s*((?:\[\s*S\s*\d+\s*\]\s*)+)")


# Abbreviations whose full stop does not end a sentence. "Rs. 1,220/kW ... etc." once split
# a correct, cited answer (c5) into fragments that each looked uncited.
_ABBREV = re.compile(r"(?i)\b(?:rs|etc|e\.g|i\.e|no|nos|reg|regs|sr|mr|dr|approx|viz|cf)\.")

# Sentences that say what the sources do NOT cover have nothing to cite; the prompt asks for
# exactly these in a partial answer.
_ABSENCE = re.compile(r"(?i)(?:do(?:es)? not (?:provide|cover|mention|say|give|specify|state)"
                      r"|not (?:covered|mentioned|specified|given|provided)|no information"
                      r"|ذکر نہیں|موجود نہیں|نہیں دی|نہیں ملت|معلومات نہیں)")


def sentences(text: str) -> list[str]:
    """Sentences with their tags. Models write "...commissioning. [S1]" - the tag AFTER the
    full stop belongs to that sentence; splitting at the full stop first once marked every
    correctly cited sentence as uncited."""
    text = _ABBREV.sub(lambda m: m.group(0).replace(".", "\u2024"), text)   # "Rs." is no end
    text = _TRAILING_TAGS.sub(lambda m: f" {m.group(2).strip()}{m.group(1)} ", text)
    parts = re.split(r"(?<=[.!?۔؟])\s+|\n+", text)
    return [p.strip() for p in parts if sum(c.isalpha() for c in TAG.sub("", p)) >= 8]


def paragraphs(text: str) -> list[list[str]]:
    return [sentences(p) for p in re.split(r"\n\s*\n|\n", text) if p.strip()]


def uncited_sentences(text: str) -> list[str]:
    """Sentences with no tag of their own AND no tagged neighbour in the same paragraph.

    Strict per-sentence tagging made the fallback fire on three correct answers in one run
    (c5, c3-ur, p4-ur): "claim. claim [S5][S6]" and a one-line conclusion after a tagged
    sentence are ordinary citation style, and the retry would not restructure them. The
    user then got no answer at all. A paragraph with no tag anywhere still fails, and every
    number is still checked against the cited sources."""
    out = []
    for para in paragraphs(text):
        tagged = [bool(TAG.search(s)) for s in para]
        for i, s in enumerate(para):
            if tagged[i] or _ABSENCE.search(s):
                continue
            if (i > 0 and tagged[i - 1]) or (i + 1 < len(para) and tagged[i + 1]):
                continue
            out.append(s)
    return out


@dataclass
class Check:
    bad_tags: list[str] = field(default_factory=list)
    uncited: list[str] = field(default_factory=list)
    unsupported_numbers: list[str] = field(default_factory=list)
    wrong_language: bool = False
    repealed_unflagged: list[str] = field(default_factory=list)
    missing_savings: list[str] = field(default_factory=list)   # savings tags not cited
    rate_terms_missing: list[str] = field(default_factory=list)
    no_citation: bool = False

    @property
    def passed(self) -> bool:
        return not (self.bad_tags or self.uncited or self.unsupported_numbers
                    or self.wrong_language or self.repealed_unflagged
                    or self.missing_savings or self.rate_terms_missing or self.no_citation)

    def problems(self) -> list[str]:
        out = []
        if self.no_citation:
            out.append("the answer cites no source; tag every sentence with [S#]")
        if self.bad_tags:
            out.append(f"these tags do not exist: {', '.join(self.bad_tags)}")
        if self.uncited:
            out.append(f"{len(self.uncited)} sentence(s) have no [S#] tag")
        if self.unsupported_numbers:
            out.append("these numbers are not in the sources you cited: "
                       + ", ".join(self.unsupported_numbers))
        if self.wrong_language:
            out.append("the answer is not in the requested language")
        if self.repealed_unflagged:
            out.append(f"{', '.join(self.repealed_unflagged)} is REPEALED; say it is the old "
                       "rule and when it still applies")
        if self.missing_savings:
            out.append("you relied on a REPEALED source; also cite "
                       f"{', '.join(self.missing_savings)} (the SAVINGS CLAUSE) for when the old "
                       "rule still applies")
        if self.rate_terms_missing:
            out.append("write these rate names exactly, in English: "
                       + "; ".join(self.rate_terms_missing))
        return out


def check(text: str, sources: list[Source], lang: str, question: str = "") -> Check:
    by_tag = {s.tag: s for s in sources}
    cited_tags = [f"S{n}" for n in TAG.findall(text)]
    c = Check()
    c.no_citation = not cited_tags
    c.bad_tags = sorted({t for t in cited_tags if t not in by_tag})
    c.uncited = uncited_sentences(text)
    cited = [by_tag[t] for t in dict.fromkeys(cited_tags) if t in by_tag]
    allowed = numbers_in(question)
    for s in cited:                  # exactly what the model was shown for that source
        allowed |= numbers_in(s.render())
    stated = numbers_in(TAG.sub(" ", text))
    c.unsupported_numbers = sorted(stated - allowed, key=lambda n: (len(n), n))
    share = urdu_share(TAG.sub("", text))
    c.wrong_language = share < URDU_MIN_SHARE if lang == "ur" else share > 0.1
    low = text.lower()
    if not any(m in low for m in REPEAL_MARKERS):
        c.repealed_unflagged = [s.tag for s in cited if s.repealed]
    if any(s.repealed for s in cited):
        savings = [s.tag for s in sources if s.savings_for]
        if savings and not any(s.savings_for for s in cited):
            c.missing_savings = savings
    c.rate_terms_missing = _missing_rate_terms(text, cited)
    return c


# Rates whose names must survive translation verbatim. In Urdu both became "qaumi ausat
# ... khareedari qeemat" and the model told a grandfathered household it gets the ENERGY
# purchase price; Prosumer Regs 21(2) says POWER purchase price until the agreement ends.
RATE_TERMS = ("national average power purchase price", "national average energy purchase price")
PRICE_WORDS = ("price", "rate", "tariff", "قیمت", "ریٹ", "نرخ", "ٹیرف")


def _squash(text: str) -> str:
    return re.sub(r"[\s\-‑]+", "", text).lower()


def _missing_rate_terms(text: str, cited: list[Source]) -> list[str]:
    """If the answer talks about a price and a cited source names one of RATE_TERMS, the
    answer must contain that exact English name."""
    low = text.lower()
    if not any(w in low for w in PRICE_WORDS):
        return []
    answer = _squash(text)
    named = [t for t in RATE_TERMS if any(_squash(t) in _squash(s.render()) for s in cited)]
    return [t for t in named if _squash(t) not in answer]


# --- answering ------------------------------------------------------------------------
@dataclass
class Answer:
    question: str
    lang: str
    status: str                         # answered | refused | fallback | error
    text: str
    sources: list[Source]
    cited: list[Source]
    rewrite: str | None = None
    drafts: list[tuple[str, list[str]]] = field(default_factory=list)   # (draft, problems)
    seconds: float = 0.0
    calls: int = 0

    def render(self) -> str:
        """User-facing text: the answer followed by what each tag refers to."""
        if self.status == "answered":
            refs = "\n".join(f"[{s.tag}] {s.label}" + (" (repealed)" if s.repealed else "")
                             for s in self.cited)
            return f"{self.text}\n\n{refs}"
        return self.text


def detect_lang(question: str) -> str:
    return "ur" if needs_rewrite(question) else "en"


def _user_prompt(question: str, sources: list[Source], feedback: list[str] | None,
                 previous: str | None = None) -> str:
    """The retry sees its own previous draft and is told to fix ONLY the listed problems.
    Without the draft, a retry rewrote from scratch: a correct first answer to the family's
    question (power price until the agreement ends, energy price for renewals) was rejected
    for two untagged sentences, and the rewrite said "energy" for both periods."""
    body = f"Question: {question}\n\nSources:\n\n" + "\n\n".join(s.render() for s in sources)
    if feedback:
        if previous:
            body += f"\n\nYour previous answer:\n{previous}"
        body += ("\n\nThe checker rejected it for these reasons only: " + "; ".join(feedback)
                 + ". Fix exactly these problems and keep everything else - the facts, the "
                 "rate names and the citations - unchanged.")
    return body


def _fallback_text(lang: str, sources: list[Source]) -> str:
    refs = "\n".join(f"- {s.label}" + (" (repealed)" if s.repealed else "") for s in sources[:3])
    return f"{FALLBACK[lang]}\n{refs}"


def answer(question: str, index: PolicyIndex, client: LLMClient, lang: str | None = None,
           k: int = K, max_attempts: int = 2, rewritten: str | None = None,
           docs: dict[str, Document] | None = None) -> Answer:
    """Answer `question` from the index. `rewritten` skips the rewrite call (eval replay)."""
    start = time.perf_counter()
    lang = lang or detect_lang(question)
    docs = docs or {d.id: d for d in load_sources()}
    calls = 0
    if rewritten is None:
        rewritten, _err = rewrite(question, client, mode="all")
        calls += 1
    primary, also = search_queries(question, rewritten)
    sources = make_sources([h.chunk for h in index.search(primary, k=k, also=also)], docs,
                           corpus=index.chunks)
    ans = Answer(question, lang, "fallback", "", sources, [], rewritten)

    feedback, previous = None, None
    for _ in range(max_attempts):
        try:
            draft = client.complete(SYSTEM.format(lang=LANG_NAME[lang]),
                                    _user_prompt(question, sources, feedback,
                                                 previous)).strip()
            calls += 1
        except LLMError as e:
            ans.status, ans.text = "error", UNAVAILABLE[lang]
            ans.drafts.append(("", [f"LLM error: {str(e)[:120]}"]))
            break
        if NOT_FOUND in draft and len(TAG.sub("", draft).strip()) > len(NOT_FOUND) + 5:
            # partial answer that also appended the marker ("... no information. NOT_FOUND.")
            draft = re.sub(r"\s*\bNOT_FOUND\b\.?", "", draft).strip()
        if NOT_FOUND in draft and len(TAG.sub("", draft).strip()) <= len(NOT_FOUND) + 5:
            ans.status, ans.text = "refused", REFUSED[lang]
            ans.drafts.append((draft, []))
            break
        chk = check(draft, sources, lang, question)
        ans.drafts.append((draft, chk.problems()))
        if chk.passed:
            by_tag = {s.tag: s for s in sources}
            ans.status, ans.text = "answered", draft
            ans.cited = [by_tag[f"S{n}"] for n in dict.fromkeys(TAG.findall(draft))]
            break
        feedback, previous = chk.problems(), draft
    else:
        ans.status, ans.text = "fallback", _fallback_text(lang, sources)
    ans.seconds, ans.calls = time.perf_counter() - start, calls
    return ans
