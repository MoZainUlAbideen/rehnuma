"""Router + assistant: questions reach the bill engine, the policy guide, or both.
Real PESCO bill, scripted LLM - no API key needed."""

import json
from pathlib import Path

import pytest

from rehnuma.assistant.assistant import ASK_FOR_BILL, ask
from rehnuma.assistant.bill_answer import bill_answer, problems, template_answer
from rehnuma.assistant.route import BILL, BOTH, NEEDS_BILL, POLICY, classify, route
from rehnuma.evals.route_eval import evaluate
from rehnuma.explain.story import build_story
from rehnuma.llm.client import LLMError
from rehnuma.loader import load_bill
from rehnuma.policy.parse import clean, parse_regulations
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.policy.sources import Document

BILL_PATH = Path("data/labels/real/pesco-2026-03.json")
DOC = Document("new", "NEPRA (Prosumer) Regulations, 2026", "Prosumer Regs 2026", "2026-02-09",
               "in_force", "regulations", "u")


class ScriptedLLM:
    name = "scripted"

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user):
        self.prompts.append((system, user))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _index():
    text = clean("3. Application.— (1) Apply to the licensee. (2) The capacity of a facility shall "
                 "not exceed the sanctioned load.\n14. Billing.— (1) Exports are billed at the "
                 "national average energy purchase price.\n")
    return PolicyIndex(parse_regulations("new", [text]))


@pytest.fixture(scope="module")
def story():
    return build_story(load_bill(BILL_PATH))


# --- routing ------------------------------------------------------------------------
@pytest.mark.parametrize("q,expected", [
    ("Why is my bill so high this month?", BILL),
    ("What is a detection bill?", POLICY),               # 'bill' alone is not ownership
    ("Can my solar system be bigger than my sanctioned load?", POLICY),
    ("Is the FPA charged on my bill allowed by NEPRA rules?", BOTH),
    ("میرے سولر نے کتنی بجلی واپس بھیجی؟", BILL),          # agentive: "my solar DID send"
    ("کیا اس بل میں اوسط یونٹ لگانا ٹھیک ہے؟", BOTH),       # a practice on my bill
    ("How do I apply for a passport?", POLICY),          # no signal -> policy (refuses)
])
def test_classify(q, expected):
    assert classify(q) == expected


def test_bill_question_without_a_bill_asks_for_one():
    assert route("Why is my bill so high?", has_bill=False).kind == NEEDS_BILL
    assert route("Is the FPA on my bill allowed by NEPRA?", has_bill=False).kind == POLICY


def test_route_eval_file_is_well_formed():
    qs = json.loads(Path("data/assistant/route_questions.json").read_text(encoding="utf-8"))
    rep = evaluate(qs["questions"])
    assert {r["route"] for r in rep["rows"]} == {BILL, POLICY, BOTH}
    assert any(r["split"] == "heldout" for r in rep["rows"])
    assert all(g["accuracy"] == 1.0 for k, g in rep["groups"].items() if k.startswith("dev"))


# --- bill answers --------------------------------------------------------------------
def test_bill_answer_uses_only_engine_numbers(story):
    ok = f"Your bill added Rs {abs(story.bill_effect)} this month."
    assert problems(ok, story, "en") == []
    assert "not in the facts: 12345" in problems("You owe Rs 12345.", story, "en")[0]


def test_numbers_the_user_wrote_are_allowed(story):
    assert problems("You asked about Rs 8000; your bill is different.", story, "en",
                    question="Why is my bill Rs 8000?") == []


def test_invented_number_gets_one_retry_then_template(story):
    llm = ScriptedLLM("You owe Rs 12345.", "You owe Rs 99999.")
    a = bill_answer("How much do I pay?", story, llm, "en")
    assert a.source == "template_fallback" and a.text == template_answer(story, "en")
    assert "Your previous answer:\nYou owe Rs 12345." in llm.prompts[1][1]


def test_groq_down_falls_back_to_the_template(story):
    a = bill_answer("How much do I pay?", story, ScriptedLLM(LLMError("429")), "ur")
    assert a.source == "template_fallback" and a.text.startswith("آپ کے بل میں")


def test_no_client_gives_the_template(story):
    assert bill_answer("x", story, None, "en").source == "template"


# --- end to end -------------------------------------------------------------------------
def test_both_route_renders_bill_and_rules_sections():
    bill = load_bill(BILL_PATH)
    llm = ScriptedLLM("Your bill shows your current bill amount for this month.",  # bill part
                      "capacity of facility not exceed sanctioned load",          # rewrite
                      "A facility may not exceed the sanctioned load [S1].")      # rules part
    r = ask("Under NEPRA rules, is my bill right about the sanctioned load?",
            _index(), llm, bill=bill, lang="en", docs={"new": DOC})
    assert r.route.kind == BOTH
    out = r.render()
    assert out.index("## Your bill") < out.index("## The rules")
    assert "Prosumer Regs 2026, reg. 3(2)" in out


def test_needs_bill_reply_asks_for_a_photo_and_calls_nothing():
    llm = ScriptedLLM()
    r = ask("میرا بل اتنا زیادہ کیوں ہے؟", _index(), llm)
    assert r.render() == ASK_FOR_BILL["ur"] and llm.prompts == []


def test_policy_question_skips_the_bill_engine():
    bill = load_bill(BILL_PATH)
    llm = ScriptedLLM("capacity sanctioned load", "A facility may not exceed the sanctioned "
                      "load [S1].")
    r = ask("Can my solar system be bigger than my sanctioned load?", _index(), llm, bill=bill,
            lang="en", docs={"new": DOC})
    assert r.bill is None and r.policy.status == "answered"


def test_without_an_llm_rules_questions_get_the_clauses_not_a_crash():
    r = ask("Can my solar system be bigger than my sanctioned load?", _index(), None, lang="en",
            docs={"new": DOC})
    assert r.policy.status == "fallback" and "reg. 3(2)" in r.render()


def test_without_an_llm_an_urdu_rules_question_says_unavailable_not_an_empty_list():
    r = ask("کیا ڈسکو میٹر بدل سکتی ہے؟", _index(), None, docs={"new": DOC})
    assert r.policy.status == "error" and "دستیاب نہیں" in r.render()


def test_bill_facts_spell_out_the_balance_sum():
    """Live finding: 'you already have Rs 134,041 credit' - that total INCLUDES this month's
    Rs 19,285. The facts now give the carried-over balance and the sum explicitly."""
    import json

    from rehnuma.explain.llm_summary import facts_payload
    from rehnuma.explain.story import build_story
    from rehnuma.loader import load_bill

    story = build_story(load_bill("data/labels/real/pesco-2026-09.json"))
    bal = json.loads(facts_payload(story, "en"))["facts"]["balance"]
    assert (bal["carried_over_from_last_bill"], bal["added_by_this_bill"],
            bal["balance_now"]) == (-114756, -19285, -134041)
    assert 114756 in {abs(int(x)) for x in story.allowed_numbers()}
