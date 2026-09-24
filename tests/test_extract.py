"""Extraction pipeline, tested with a scripted fake vision model (no API key needed)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from rehnuma.engine import Status, audit_bill
from rehnuma.extract.compare import _norm, compare
from rehnuma.extract.pipeline import extract_bill, parse_json
from rehnuma.extract.prompt import META_FIELDS, build_prompt, extraction_schema
from rehnuma.llm.client import LLMError
from rehnuma.loader import load_bill
from rehnuma.schema import Bill

REAL = Path("data/labels/real")

PII_WORDS = ("name", "address", "reference", "consumer_id", "cnic", "phone")


class FakeVision:
    """Returns scripted responses in order; records the prompts it was given."""
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def read(self, system, prompt, image, mime):
        self.prompts.append(prompt)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


def as_model_output(bill) -> dict:
    """What a perfect vision model would return: the label minus our meta fields."""
    d = bill.model_dump(mode="json", exclude_none=True)
    return {k: v for k, v in d.items() if k not in META_FIELDS}


@pytest.fixture
def img(tmp_path):
    p = tmp_path / "bill.jpg"
    p.write_bytes(b"\xff\xd8fake")
    return p


# --- privacy ---------------------------------------------------------------------
def test_schema_has_no_place_for_identifiers():
    props = json.dumps(extraction_schema()["properties"]).lower()
    for word in PII_WORDS:
        assert f'"{word}' not in props, word


def test_identifiers_added_by_the_model_are_dropped(bill_by_id, img):
    out = as_model_output(bill_by_id("iesco-2021-01"))
    out.update(name="SOME PERSON", reference_no="15 14213 3720505 U", cnic="12345")
    res = extract_bill(img, FakeVision([out]), "iesco-2021-01")
    dumped = res.bill.model_dump_json()
    assert "SOME PERSON" not in dumped and "3720505" not in dumped and "12345" not in dumped


# --- happy path and the verify loop ----------------------------------------------------
def test_perfect_read_is_verified_and_fully_accurate(bill_by_id, img):
    label = bill_by_id("iesco-2023-03")
    res = extract_bill(img, FakeVision([as_model_output(label)]), label.bill_id)
    assert res.verified and len(res.attempts) == 1
    assert compare(label, res.bill).accuracy == 1.0


def test_misread_digit_is_caught_and_reread(bill_by_id, img):
    label = bill_by_id("pesco-2026-08")
    misread = as_model_output(label)
    misread["totals"]["current_bill"] = 3278           # 3273 misread as 3278
    fake = FakeVision([misread, as_model_output(label)])
    res = extract_bill(img, fake, label.bill_id)
    assert res.verified and len(res.attempts) == 2
    assert res.attempts[0].failed_checks                 # the engine flagged the misread
    assert "re-read" in fake.prompts[1] and "exactly what is printed" in fake.prompts[1]
    feedback = fake.prompts[1].split("JSON Schema")[-1]
    assert "3273" not in feedback and "expected" not in feedback   # never told the answer
    assert "BILL CHARGES BREAKDOWN" in feedback                     # told WHERE to look


def test_single_pass_mode_keeps_the_misread(bill_by_id, img):
    label = bill_by_id("pesco-2026-08")
    misread = as_model_output(label)
    misread["totals"]["current_bill"] = 3278
    res = extract_bill(img, FakeVision([misread]), label.bill_id, verify=False)
    assert not res.verified and len(res.attempts) == 1
    cmp = compare(label, res.bill)
    assert ("totals.current_bill", Decimal(3273), Decimal(3278)) in cmp.wrong


def test_real_anomaly_is_reported_not_fixed(bill_by_id, img):
    """PESCO Mar-26 genuinely contradicts itself. A faithful reader keeps the printed
    values; the pipeline must not end up with 'corrected' numbers."""
    label = bill_by_id("pesco-2026-03")
    out = as_model_output(label)
    res = extract_bill(img, FakeVision([out, out, out]), label.bill_id)
    assert not res.verified and len(res.attempts) == 3
    assert compare(label, res.bill).accuracy == 1.0
    assert "fpa_total_from_lines" in res.failed_checks


def test_invalid_json_gets_schema_feedback(bill_by_id, img):
    label = bill_by_id("iesco-2019-07")
    bad = as_model_output(label)
    bad["layout"] = "some_new_layout"
    fake = FakeVision([bad, as_model_output(label)])
    res = extract_bill(img, fake, label.bill_id)
    assert res.verified and not res.attempts[0].ok_schema
    assert "did not match the schema" in fake.prompts[1]


def test_api_error_ends_cleanly(img):
    res = extract_bill(img, FakeVision([LLMError("HTTP 429")]), "x")
    assert res.bill is None and not res.verified and "429" in res.attempts[0].error


def test_parse_json_tolerates_fences():
    assert parse_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_prompt_mentions_privacy_and_exact_copying():
    p = build_prompt()
    assert "do NOT output names" in p and "JSON Schema" in p


# --- comparison ---------------------------------------------------------------------
def test_compare_keys_history_by_month(bill_by_id):
    label = bill_by_id("iesco-2023-03")
    got = label.model_copy(deep=True)
    got.history = got.history[1:]                       # model skipped the first row
    cmp = compare(label, got)
    assert all(k.startswith("history.2022-03.") for k in cmp.missing)
    assert not cmp.wrong                                 # later rows still line up


def test_compare_ignores_meta_fields(bill_by_id):
    label = bill_by_id("iesco-2021-01")
    got = label.model_copy(deep=True, update={"notes": ["different"], "uncertain_fields": []})
    assert compare(label, got).accuracy == 1.0



# --- eval accounting ---------------------------------------------------------------
def test_api_errors_are_not_scored_as_misreads(tmp_path, bill_by_id):
    """Regression: 7 Gemini quota/overload errors were once reported as 0% accuracy."""
    from pathlib import Path

    from rehnuma.evals.extract_eval import run

    labels = Path("data/labels/real")
    (tmp_path / "iesco-2021-01.png").write_bytes(b"x")
    (tmp_path / "iesco-2023-03.png").write_bytes(b"x")
    good = as_model_output(bill_by_id("iesco-2021-01"))
    fake = FakeVision([good, LLMError("HTTP 429: quota")])
    rep = run(tmp_path, labels, fake, verify=True)
    o = rep["overall"]
    assert rep["n"] == 2 and rep["n_read"] == 1
    assert o["api_error_rate"] == 0.5
    assert o["field_accuracy"] == 1.0            # measured on the bill that was read


def test_retry_after_uses_gemini_retry_delay():
    from rehnuma.extract.vision_client import retry_after
    body = '{"error": {"details": [{"retryDelay": "37s"}]}}'
    assert retry_after({}, body, 0) == 38
    assert retry_after({"retry-after": "4"}, body, 0) == 4
    assert retry_after({}, "no hint", 1) == 10

def test_norm_compares_values_not_formatting():
    """Regression: "1652.60" vs "1652.6" and "7.00" vs "7" were scored as misreads."""
    assert _norm("1652.60") == _norm("1652.6") == _norm(Decimal("1652.6"))
    assert _norm("7.00") == _norm("7.0") == _norm("7") == _norm(7)
    assert _norm("70") == _norm(70)                   # normalize() would give 7E+1
    assert _norm("-105168") != _norm("-100168")       # real misreads still count
    assert _norm("2026-03") == "2026-03" and _norm("A-1a(01)") == "A-1a(01)"


def test_compare_ignores_decimal_formatting():
    label = load_bill(REAL / "iesco-2023-03.json")
    data = label.model_dump(mode="json")
    data["legacy_charges"]["cost_of_electricity"] = str(
        Decimal(data["legacy_charges"]["cost_of_electricity"]).normalize())
    assert compare(label, Bill.model_validate(data)).wrong == []


def test_ed_on_fpa_misread_is_caught():
    """Gemini copied GST on FPA (46) into ED on FPA (4) on IESCO Mar-23; no check saw it."""
    bill = load_bill(REAL / "iesco-2023-03.json")
    data = bill.model_dump(mode="json")
    data["legacy_charges"]["govt"]["ed_on_fpa"] = "46"
    fails = {f.check for f in audit_bill(Bill.model_validate(data)) if f.status == Status.FAIL}
    assert "ed_on_fpa" in fails
