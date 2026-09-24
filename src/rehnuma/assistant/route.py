"""Which part of Rehnuma answers a question: the bill engine, the policy guide, or both.

    "Why is my bill so high?"                  -> bill    (engine: verified numbers)
    "Can my solar be bigger than my load?"     -> policy  (cited NEPRA clauses)
    "Is the FPA on my bill allowed by NEPRA?"  -> both    (the bill's facts + the rule)

Rules, not an LLM call: routing runs on every message, so it must be instant, free, work
when Groq is down, and be testable. The signals are deliberately about OWNERSHIP ("my
bill", "this month", "did I use") vs RULES ("allowed", "NEPRA", "can the DISCO", "how
long"). "What is a detection bill?" mentions a bill but asks about a rule, so the word
"bill" alone is not a bill signal. With no signal at all the question goes to the policy
guide, which refuses if the documents don't cover it.

Written from the dev questions in data/assistant/route_questions.json. Held-out run 1
scored EN 90% / UR 67%; its three failures (Urdu agentive "my solar DID send", "was I
charged", "is it right to apply average units") were fixed, moved to dev, and a fresh
held-out batch was written before re-running.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BILL = "bill"
POLICY = "policy"
BOTH = "both"
NEEDS_BILL = "needs_bill"          # a bill question, but no bill uploaded yet

_BILL_SIGNALS = [
    # English: the user's own bill, period, consumption or money
    r"\b(my|this) bill\b", r"\bin my bill\b", r"\bon my bill\b",
    r"\bthis month\b", r"\blast month\b", r"\bthis time\b",
    r"\bhow much (do|should|will) i (have to )?pay\b", r"\bdue date\b",
    r"\b(did|do|have) i (use|used|consume|send|sent|export)\b", r"\bdid my\b",
    r"\bmy (units|consumption|credit|bank|arrears|payment|meter reading)\b",
    r"\bam i (still )?(a )?protected\b", r"\bi used\b",
    r"\b(was|were|am) i (charged|billed)\b", r"\bmy (exported|imported) units\b",
    # Urdu
    r"میرا بل", r"میرے بل", r"یہ بل", r"اس بل",
    r"اس مہینے", r"پچھلے مہینے", r"اس بار",
    r"مجھے کتنے", r"کتنے پیسے", r"آخری تاریخ", r"استعمال ہوئے", r"میں نے",
    r"میرے \S+ نے", r"میرا میٹر",        # "my solar DID send", "my meter"
]
_POLICY_SIGNALS = [
    # English: rules, rights, limits, definitions
    r"\bnepra\b", r"\brules?\b", r"\blaw\b", r"\blegal\b", r"\ballowed\b", r"\bregulations?\b",
    r"\bcan (the )?(disco|licensee|company|wapda)\b", r"\bcan i\b", r"\bhow long\b",
    r"\bmaximum\b", r"\bhow many months can\b", r"\bwhat is an?\b", r"\bwho pays\b",
    r"\bagreement\b", r"\bdetection bill\b", r"\bcomplaint\b", r"\bsecurity deposit\b",
    r"\bnew connection\b", r"\bsanctioned load\b", r"\bnet billing\b", r"\bnet metering\b",
    r"\bprosumer\b", r"\baccording to\b",
    # Urdu
    r"قانون", r"قاعد", r"نیپرا", r"اجازت", r"شکایت", r"معاہدہ",
    r"کیا بجلی کمپنی", r"کیا ڈسکو", r"گنے جاتے", r"کتنے دن میں", r"کتنے سال",
    r"نیٹ بلنگ", r"نیٹ میٹرنگ",
    r"(لگانا|لگانے|کرنا) (ٹھیک|درست|جائز)", r"جائز",   # "is it right to apply X" - a practice
]
_BILL_RE = [re.compile(p, re.I) for p in _BILL_SIGNALS]
_POLICY_RE = [re.compile(p, re.I) for p in _POLICY_SIGNALS]


@dataclass(frozen=True)
class Route:
    kind: str                       # bill | policy | both | needs_bill
    bill_signals: tuple[str, ...]
    policy_signals: tuple[str, ...]

    @property
    def reason(self) -> str:
        return (f"bill signals: {', '.join(self.bill_signals) or '-'}; "
                f"policy signals: {', '.join(self.policy_signals) or '-'}")


def _hits(text: str, patterns: list[re.Pattern]) -> tuple[str, ...]:
    return tuple(m.group(0) for p in patterns if (m := p.search(text)))


def classify(question: str) -> str:
    """bill | policy | both - ignoring whether a bill is available."""
    b, p = _hits(question, _BILL_RE), _hits(question, _POLICY_RE)
    if b and p:
        return BOTH
    return BILL if b else POLICY


def route(question: str, has_bill: bool) -> Route:
    b, p = _hits(question, _BILL_RE), _hits(question, _POLICY_RE)
    kind = classify(question)
    if kind == BILL and not has_bill:
        kind = NEEDS_BILL
    elif kind == BOTH and not has_bill:
        kind = POLICY                # answer the rule; the reply asks for the bill too
    return Route(kind, b, p)
