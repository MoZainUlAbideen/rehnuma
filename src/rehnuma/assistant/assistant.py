"""One question in, one reply out: route -> bill engine and/or policy guide -> render.

    ask("Is the FPA on my bill allowed by NEPRA?", bill=my_bill)
      -> route: both
      -> bill part:   verified facts about THIS bill (numbers checked against the engine)
      -> policy part: cited NEPRA clauses (critic-checked)

The two parts are rendered under their own headings so a reader always knows which
sentences are about their numbers and which are the rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from rehnuma.assistant.bill_answer import BillAnswer, bill_answer
from rehnuma.assistant.route import BILL, BOTH, NEEDS_BILL, POLICY, Route, classify, route
from rehnuma.explain.story import build_story
from rehnuma.llm.client import LLMClient
from rehnuma.policy.answer import Answer, answer, detect_lang
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.schema import Bill

HEAD_BILL = {"en": "Your bill", "ur": "آپ کا بل"}
HEAD_RULES = {"en": "The rules", "ur": "قواعد"}
ASK_FOR_BILL = {
    "en": "This question is about your own bill. Please upload a photo of your bill and ask "
          "again.",
    "ur": "یہ سوال آپ کے اپنے بل کے بارے میں ہے۔ براہِ کرم اپنے بل کی تصویر اپ لوڈ کریں اور "
          "دوبارہ پوچھیں۔",
}
ALSO_UPLOAD = {
    "en": "To check this against your own bill, upload a photo of it.",
    "ur": "اپنے بل پر یہ جانچنے کے لیے اس کی تصویر اپ لوڈ کریں۔",
}


@dataclass
class Reply:
    question: str
    lang: str
    route: Route
    bill: BillAnswer | None = None
    policy: Answer | None = None

    def render(self) -> str:
        if self.route.kind == NEEDS_BILL:
            return ASK_FOR_BILL[self.lang]
        parts = []
        if self.bill:
            parts.append(f"## {HEAD_BILL[self.lang]}\n{self.bill.text}")
        if self.policy:
            body = self.policy.render()
            parts.append(f"## {HEAD_RULES[self.lang]}\n{body}" if self.bill else body)
            if classify(self.question) == BOTH and not self.bill:
                parts.append(ALSO_UPLOAD[self.lang])
        return "\n\n".join(parts)


def ask(question: str, index: PolicyIndex, client: LLMClient | None, bill: Bill | None = None,
        lang: str | None = None, rewritten: str | None = None, docs=None) -> Reply:
    lang = lang or detect_lang(question)
    r = route(question, has_bill=bill is not None)
    reply = Reply(question, lang, r)
    if r.kind in (BILL, BOTH):
        reply.bill = bill_answer(question, build_story(bill), client, lang)
    if r.kind in (POLICY, BOTH):
        reply.policy = answer(question, index, client, lang=lang, rewritten=rewritten, docs=docs)
    return reply
