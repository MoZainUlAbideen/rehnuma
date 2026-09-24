"""Answer layer: cited answers, the deterministic critic, retry, refusal, fallback.
A scripted fake LLM replays drafts, so no API key is needed."""

from rehnuma.llm.client import LLMError
from rehnuma.policy.answer import (
    REFUSED,
    answer,
    check,
    make_sources,
    numbers_in,
)
from rehnuma.policy.parse import clean, parse_regulations
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.policy.sources import Document

NEW = Document("new", "NEPRA (Prosumer) Regulations, 2026", "Prosumer Regs 2026", "2026-02-09",
               "in_force", "regulations", "u")
OLD = Document("old", "Net Metering Regulations, 2015", "Net Metering Regs 2015", "2015-09-01",
               "repealed", "regulations", "u", repealed_by="new",
               note="Agreements signed under it keep their price until the term ends.")
DOCS = {"new": NEW, "old": OLD}

NEW_TEXT = clean(
    "7. Term of agreement.— (1) The term of the agreement between prosumer and licensee shall "
    "be five years from commissioning.\n"
    "14. Billing.— (1) The kWh supplied by prosumer to the licensee shall be billed at the "
    "national average energy purchase price. (2) Excess credit is carried to the next billing "
    "cycle or paid quarterly.\n")
OLD_TEXT = clean(
    "7. Term of Agreement.— (1) The term of the Agreement shall be three years.\n"
    "14. Billing for Net Metering.— (1) Net kWh are credited to the next billing cycle.\n")


def _index():
    return PolicyIndex(parse_regulations("new", [NEW_TEXT]) + parse_regulations("old", [OLD_TEXT]))


def _sources(*clauses):
    chunks = {(c.doc_id, c.clause): c for c in _index().chunks}
    return make_sources([chunks[k] for k in clauses], DOCS)


class ScriptedLLM:
    name = "scripted"

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


# --- critic ---------------------------------------------------------------------------
def test_good_cited_answer_passes():
    src = _sources(("new", "7(1)"))
    assert check("The agreement lasts 5 years from commissioning. [S1]", src, "en").passed


def test_number_words_in_the_source_support_digits_in_the_answer():
    assert numbers_in("five years and thirty days") == {"5", "30"}
    assert numbers_in("۵ سال") == {"5"}                          # Urdu digits


def test_invented_number_is_caught():
    src = _sources(("new", "7(1)"))
    c = check("The agreement lasts 10 years. [S1]", src, "en")
    assert c.unsupported_numbers == ["10"] and not c.passed


def test_a_number_from_an_uncited_source_does_not_count():
    """Five years is in S1, three years in S2; citing only S1 cannot support 3."""
    src = _sources(("new", "7(1)"), ("old", "7(1)"))
    assert check("It lasts 3 years. [S1]", src, "en").unsupported_numbers == ["3"]


def test_uncited_sentence_and_unknown_tag_are_caught():
    src = _sources(("new", "7(1)"))
    c = check("The agreement lasts 5 years. [S1] You can renew it after that period.", src, "en")
    assert len(c.uncited) == 1
    assert check("It lasts 5 years. [S4]", src, "en").bad_tags == ["S4"]


def test_urdu_answer_must_be_in_urdu():
    src = _sources(("new", "7(1)"))
    assert check("The agreement lasts 5 years. [S1]", src, "ur").wrong_language
    assert check("معاہدہ پانچ سال کے لیے ہوتا ہے۔ [S1]", src, "ur").passed


def test_repealed_source_must_be_flagged():
    src = _sources(("old", "7(1)"))
    assert check("The agreement lasts 3 years. [S1]", src, "en").repealed_unflagged == ["S1"]
    assert check("Under the old 2015 rules the agreement lasted 3 years. [S1]", src, "en").passed


def test_clause_numbers_from_the_label_are_allowed():
    src = _sources(("new", "14(2)"))
    assert check("Under regulation 14(2), extra credit is paid quarterly. [S1]", src, "en").passed


# --- answering ------------------------------------------------------------------------
def test_answer_passes_first_time():
    llm = ScriptedLLM("The agreement lasts 5 years from commissioning. [S1]")
    a = answer("how long is the prosumer agreement term", _index(), llm, rewritten="",
               docs=DOCS)
    assert a.status == "answered" and a.cited[0].chunk.clause == "7(1)"
    assert "Prosumer Regs 2026, reg. 7(1)" in a.render()


def test_retry_gets_problem_list_but_never_the_answer():
    llm = ScriptedLLM("The agreement lasts 10 years. [S1]",
                      "The agreement lasts 5 years from commissioning. [S1]")
    a = answer("how long is the prosumer agreement term", _index(), llm, rewritten="",
               docs=DOCS)
    assert a.status == "answered" and len(a.drafts) == 2
    retry = llm.prompts[1]
    assert "not in the sources you cited: 10" in retry
    assert "Your previous answer:\nThe agreement lasts 10 years. [S1]" in retry   # fix, not redo
    assert "keep everything else" in retry
    assert "should be 5" not in retry and "expected" not in retry


def test_two_failed_drafts_give_an_honest_fallback():
    llm = ScriptedLLM("It lasts 10 years. [S1]", "It lasts 12 years. [S1]")
    a = answer("how long is the prosumer agreement term", _index(), llm, rewritten="",
               docs=DOCS)
    assert a.status == "fallback" and "reg. 7(1)" in a.text and "12" not in a.text


def test_not_found_becomes_a_refusal_in_the_users_language():
    a = answer("کیا اگلے مہینے بجلی مہنگی ہوگی؟", _index(), ScriptedLLM("NOT_FOUND"),
               rewritten="will tariff increase next month", docs=DOCS)
    assert a.status == "refused" and a.text == REFUSED["ur"] and a.lang == "ur"


def test_llm_outage_is_reported_not_hidden():
    a = answer("agreement term", _index(), ScriptedLLM(LLMError("Groq HTTP 429")), rewritten="",
               docs=DOCS)
    assert a.status == "error" and "unavailable" in a.text


def test_urdu_question_is_answered_from_the_english_rewrite():
    llm = ScriptedLLM("rewritten: unused",)
    llm.replies = ["سولر معاہدہ پانچ سال کے لیے ہوتا ہے۔ [S1]"]
    a = answer("سولر کا معاہدہ کتنے سال کا ہوتا ہے؟", _index(), llm,
               rewritten="term of agreement prosumer licensee years", docs=DOCS)
    assert a.status == "answered" and a.cited[0].chunk.clause == "7(1)"


def test_tag_after_the_full_stop_belongs_to_that_sentence():
    """Regression: splitting at '.' before looking for tags marked '...years. [S1]' uncited."""
    from rehnuma.policy.answer import sentences
    parts = sentences("It lasts 5 years. [S1] Extra credit is paid quarterly. [S2][S3]")
    assert len(parts) == 2 and all("[S" in p for p in parts)
    urdu = sentences("معاہدہ پانچ سال کا ہے۔ [S1] اضافی رقم ہر سہ ماہی ملتی ہے۔ [S2]")
    assert len(urdu) == 2 and all("[S" in p for p in urdu)


def test_fact_check_matches_whole_numbers_and_urdu_words():
    from rehnuma.evals.policy_answer_eval import fact_present
    assert fact_present("Up to 2 months on average. [S1]", ["2", "two"])
    assert not fact_present("Under the 2026 rules. [S1]", ["2", "two"])       # 2 is not 2026
    assert fact_present("زیادہ سے زیادہ دو ماہ [S1]", ["2", "two", "دو"])
    assert fact_present("۱۵ دن میں [S1]", ["15", "fifteen"])                 # Urdu digits


# --- repealed rules + savings clause (the family's real question) -----------------------
OLD_SAVED = Document("old", "Net Metering Regulations, 2015", "Net Metering Regs 2015",
                     "2015-09-01", "repealed", "regulations", "u", repealed_by="new",
                     note="Repealed. When it still applies is decided by the savings clause.",
                     savings_clause=("new", "21(2)"))
SAVINGS_TEXT = clean(
    "21. Savings and Repeal.— (1) The 2015 regulations are repealed. (2) Agreements executed "
    "under the repealed regulations are billed under regulation 14 from the next billing "
    "cycle: Provided that exported units are billed at the national average power purchase "
    "price till the expiry of the term of their agreement.\n")
DOCS2 = {"new": NEW, "old": OLD_SAVED}


def _corpus():
    return (parse_regulations("new", [NEW_TEXT + "\n" + SAVINGS_TEXT])
            + parse_regulations("old", [OLD_TEXT]))


def test_savings_clause_is_added_when_only_old_rules_were_retrieved():
    """Real failure: the Urdu question 'my net metering was installed before 2026 - how are
    my units priced now?' retrieved only 2015 clauses, missed reg. 21(2), and the model
    answered from a paraphrase in our metadata."""
    corpus = _corpus()
    old_only = [c for c in corpus if c.doc_id == "old"]
    src = make_sources(old_only, DOCS2, corpus=corpus)
    added = [s for s in src if s.savings_for]
    assert [s.chunk.clause for s in added] == ["21(2)"]
    assert "SAVINGS CLAUSE" in added[0].render()


def test_relying_on_old_rules_without_the_savings_clause_is_rejected():
    corpus = _corpus()
    src = make_sources([c for c in corpus if c.doc_id == "old"], DOCS2, corpus=corpus)
    tag = next(s.tag for s in src if s.savings_for)
    old_tag = next(s.tag for s in src if s.chunk.clause == "14(1)")
    only_old = f"Under the old 2015 rules, net kWh are credited to the next cycle [{old_tag}]."
    c = check(only_old, src, "en")
    assert c.missing_savings == [tag] and not c.passed
    both = (f"Under the old 2015 rules, net kWh were credited to the next cycle [{old_tag}]. "
            f"Your exports are now billed at the national average power purchase price until "
            f"your agreement expires [{tag}].")
    assert check(both, src, "en").passed


def test_numbers_in_the_source_header_count():
    """h5: a correct answer fell back because '2026' was only in the header the model saw."""
    corpus = _corpus()
    src = make_sources([c for c in corpus if c.clause == "21(2)"], DOCS2, corpus=corpus)
    assert check(f"This is set by the 2026 Prosumer Regs [{src[0].tag}].", src, "en").passed


# --- rate names survive translation ------------------------------------------------------
def test_urdu_answer_must_keep_the_exact_rate_name():
    """Real failure: 'qaumi ausat tawanai khareedari qeemat' (ENERGY) for a grandfathered
    household whose savings clause says POWER purchase price."""
    corpus = _corpus()
    src = make_sources([c for c in corpus if c.clause == "21(2)"], DOCS2, corpus=corpus)
    t = src[0].tag
    vague = f"آپ کے یونٹ قومی اوسط توانائی خریداری قیمت پر گنے جائیں گے [{t}]۔"
    c = check(vague, src, "ur")
    assert c.rate_terms_missing == ["national average power purchase price"] and not c.passed
    exact = (f"معاہدہ ختم ہونے تک آپ کے یونٹ (national average power purchase price) کی "
             f"قیمت پر گنے جائیں گے، اور تجدید کے بعد نئے ریٹ لاگو ہوں گے [{t}]۔")
    assert check(exact, src, "ur").rate_terms_missing == []


def test_rate_rule_only_applies_when_a_price_is_discussed():
    corpus = _corpus()
    src = make_sources([c for c in corpus if c.clause == "21(2)"], DOCS2, corpus=corpus)
    assert check(f"The old agreements stay valid until they expire [{src[0].tag}].", src,
                 "en").rate_terms_missing == []


def test_referenced_annexure_is_added_to_the_sources():
    """c5: the retrieved clause said 'rates are as per Annexure - IV' but the annexure was not
    retrieved, so the model refused."""
    from rehnuma.policy.parse import parse_manual
    text = clean("CHAPTER 5\nSECURITY DEPOSIT\n5.1 SECURITY DEPOSIT\n"
                 "5.1.1 The Security Deposit rates are as per Annexure - IV, approved by NEPRA.\n"
                 "Annexure - IV\nSecurity deposit: Rs 1,500 per kW for residential consumers.\n")
    corpus = parse_manual("csm", [text])
    csm = Document("csm", "Consumer Service Manual", "CSM 2025", "2025", "in_force", "manual", "u")
    src = make_sources([c for c in corpus if c.clause == "5.1.1"], {"csm": csm}, corpus=corpus)
    assert [s.chunk.clause for s in src] == ["5.1.1", "Annex-IV"]
