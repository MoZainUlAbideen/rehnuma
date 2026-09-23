"""LLM summary + critic, tested with a scripted fake LLM (no network, no API key)."""

import json

import pytest

from rehnuma.evals.summary_eval import run
from rehnuma.explain import build_story
from rehnuma.explain.llm_summary import SYSTEM, facts_payload, llm_summary
from rehnuma.explain.quality import assess, required_numbers, urdu_share
from rehnuma.explain.render import summarize
from rehnuma.llm.client import GroqClient, LLMError


class ScriptedLLM:
    """Returns the scripted drafts in order and records what it was asked."""
    name = "scripted"

    def __init__(self, drafts):
        self.drafts = list(drafts)
        self.prompts = []

    def complete(self, system, user):
        self.prompts.append(user)
        return self.drafts.pop(0)


@pytest.fixture
def sep(bill_by_id):
    return build_story(bill_by_id("pesco-2026-09"))


GOOD_EN = ("- You have nothing to pay; your account is Rs 134,041 in credit.\n"
           "- This month you took 629 units from the grid and sent 942 back.\n"
           "- The 3-month cycle was settled on this bill, crediting you Rs 19,285.\n"
           "- Rehnuma checked 17 calculations and all are correct.")


def test_good_first_draft_is_accepted(sep):
    llm = ScriptedLLM([GOOD_EN])
    res = llm_summary(sep, llm, "en")
    assert res.source == "llm" and res.attempts == 1 and res.quality.passed


def test_invented_number_is_rejected_then_fixed(sep):
    bad = GOOD_EN.replace("Rs 19,285", "about Rs 20,000")
    llm = ScriptedLLM([bad, GOOD_EN])
    res = llm_summary(sep, llm, "en")
    assert res.source == "llm" and res.attempts == 2
    assert res.drafts_rejected[0]["unsupported"] == ["20000"]
    assert res.drafts_rejected[0]["text"] == bad          # kept for diagnosis    
    assert "20000" in llm.prompts[1] and "NOT in the facts" in llm.prompts[1]


def test_missing_must_mention_fact_is_rejected(sep):
    no_export = GOOD_EN.replace(" and sent 942 back", "")
    res = llm_summary(sep, ScriptedLLM([no_export, GOOD_EN]), "en")
    assert res.attempts == 2 and res.drafts_rejected[0]["missing"] == ["units sent back"]


def test_wrong_language_is_rejected(sep):
    res = llm_summary(sep, ScriptedLLM([GOOD_EN] * 3), "ur")   # English when Urdu asked
    assert res.source == "template_fallback"
    assert all(not d["language_ok"] for d in res.drafts_rejected)


def test_user_never_sees_an_unchecked_summary(sep):
    """Three bad drafts -> template fallback, which itself passes the critic."""
    bad = GOOD_EN.replace("134,041", "143,041")
    res = llm_summary(sep, ScriptedLLM([bad] * 3), "en")
    assert res.source == "template_fallback" and res.attempts == 3
    assert res.quality.passed
    assert "143,041" not in res.text


def test_prompt_carries_verified_facts_and_rules(sep):
    payload = json.loads(facts_payload(sep, "ur"))
    assert payload["must_mention"] == required_numbers(sep)
    assert payload["reference_summary"] == summarize(sep, "ur")
    assert "Use ONLY numbers that appear in the FACTS" in SYSTEM


def test_south_asian_digit_grouping_is_understood(sep):
    """An LLM may write 1,34,041 (lakh grouping) - that is still the right number."""
    assert assess(GOOD_EN.replace("134,041", "1,34,041"), sep, "en").passed


def test_urdu_share():
    assert urdu_share("آپ کو کچھ ادا نہیں کرنا") == 1.0
    assert urdu_share("nothing to pay") == 0.0


def test_required_numbers_differ_by_household(bill_by_id):
    solar = required_numbers(build_story(bill_by_id("pesco-2026-08")))
    plain = required_numbers(build_story(bill_by_id("iesco-2023-03")))
    assert "units sent back" in solar and "units used" in plain
    assert required_numbers(build_story(bill_by_id("pesco-2026-03")))["audit problems"] == 1


def test_template_baseline_eval_is_perfect():
    report = run(["data/labels/real"], "template", ["ur", "en"])
    o = report["overall"]
    assert report["n"] == 14
    assert o["mean_faithfulness"] == o["mean_coverage"] == o["language_ok_rate"] == 1.0
    assert o["fallback_rate"] == 0.0



class FailingLLM:
    name = "failing"

    def complete(self, system, user):
        raise LLMError("Groq HTTP 413: Request too large")


def test_llm_error_falls_back_instead_of_crashing(sep):
    """Regression: a 413 from Groq used to crash the whole eval."""
    res = llm_summary(sep, FailingLLM(), "ur")
    assert res.source == "template_fallback" and res.quality.passed
    assert "413" in res.drafts_rejected[0]["error"]


def test_groq_request_caps_output_tokens(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    body = GroqClient(model="allam-2-7b").payload("s", "u")
    assert body["max_tokens"] == 1024 and "reasoning_effort" not in body
    gpt = GroqClient(model="openai/gpt-oss-120b").payload("s", "u")
    assert gpt["reasoning_effort"] == "low"



# --- found by reading real drafts (reports/summary_eval/*/samples.md) -------------------
def test_template_fits_structure_limits(bill_by_id):
    """The limit must never reject our own fallback (it did, at 10 lines)."""
    from rehnuma.explain.quality import MAX_LINES
    from rehnuma.loader import load_bills
    for bill in load_bills(["data/labels/real"]):
        for lang in ("ur", "en"):
            assert len(summarize(build_story(bill), lang)) <= MAX_LINES


def test_repetition_loop_is_rejected(sep):
    """allam-2-7b looped one line 20+ times."""
    loop = GOOD_EN + "\n" + "\n".join(["- Peak hours do not change your rate."] * 20)
    q = assess(loop, sep, "en")
    assert not q.structure_ok and not q.passed


def test_credit_bill_hides_due_date_from_llm(sep):
    payload = json.loads(facts_payload(sep, "ur"))
    assert "due_date" not in payload["facts"] and "payable_after_due" not in payload["facts"]


def test_credit_kept_until_due_date_is_rejected(sep):
    """gpt-oss-120b and qwen3.8-27b both wrote this on the Sep-26 credit bill. False."""
    claim = GOOD_EN + "\n- Your credit is kept until 24 September 2026."
    assert [str(x) for x in assess(claim, sep, "en").unsupported] == ["24"]


def test_payable_bill_gets_readable_due_date(bill_by_id):
    story = build_story(bill_by_id("iesco-2023-03"))
    payload = json.loads(facts_payload(story, "ur"))
    assert payload["facts"]["due_date"] == "13 اپریل 2023"
