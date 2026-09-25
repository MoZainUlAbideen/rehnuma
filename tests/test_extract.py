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


# --- the live pesco-2026-09 misread: the model CALCULATED the bank ------------------
def test_computed_bank_is_caught_and_reread_says_copy(bill_by_id, img):
    """Live (gemini-3.5-flash): Rem kWh present read as previous - Net (1325 + 507 = 1832,
    -319 - 194 = -513) instead of the printed 0 of a settlement month."""
    label = bill_by_id("pesco-2026-09")
    computed = as_model_output(label)
    nm = computed["net_metering"]
    nm["remaining_prev"]["offpeak"] = 1325
    nm["remaining_present"] = {"offpeak": 1832, "peak": -513}
    fake = FakeVision([computed, as_model_output(label)])
    res = extract_bill(img, fake, label.bill_id)
    assert any(c.startswith("nm_remaining_kwh") for c in res.attempts[0].failed_checks)
    feedback = fake.prompts[1][len(build_prompt()):]      # only what the re-read adds
    assert "do not calculate" in feedback
    assert not any(ch.isdigit() for ch in feedback)      # names fields, never values
    assert res.verified


def test_prompt_says_rem_kwh_is_copied_not_computed():
    prompt = build_prompt()
    assert 'Rem kWh "present" is its own printed number' in prompt
    assert "Never work it out" in prompt


# --- one run gives both columns: first read (no loop) and final --------------------
def test_first_pass_is_the_read_before_any_feedback(bill_by_id, img):
    label = bill_by_id("pesco-2026-08")
    misread = as_model_output(label)
    misread["totals"]["current_bill"] = 3278
    res = extract_bill(img, FakeVision([misread, as_model_output(label)]), label.bill_id)
    assert res.first_pass.number == 1 and res.first_pass.bill.totals.current_bill == 3278
    single = extract_bill(img, FakeVision([misread]), label.bill_id, verify=False)
    assert single.bill == res.first_pass.bill          # what a --no-verify run returns


def test_first_pass_skips_a_schema_failure(bill_by_id, img):
    """Schema feedback is sent in single-pass mode too, so the first VALID read counts."""
    label = bill_by_id("pesco-2026-08")
    res = extract_bill(img, FakeVision(["not json", as_model_output(label)]), label.bill_id)
    assert res.first_pass.number == 2


def test_eval_reports_first_read_and_final_side_by_side(tmp_path, bill_by_id):
    from rehnuma.evals.extract_eval import render_markdown, run

    (tmp_path / "pesco-2026-08.jpg").write_bytes(b"x")
    label = bill_by_id("pesco-2026-08")
    misread = as_model_output(label)
    misread["totals"]["current_bill"] = 3278
    rep = run(tmp_path, REAL, FakeVision([misread, as_model_output(label)]), verify=True)
    assert rep["first_pass"]["field_accuracy"] < 1.0 == rep["overall"]["field_accuracy"]
    assert rep["first_pass"]["reconciles_rate"] == 0 and rep["overall"]["reconciles_rate"] == 1
    assert "First read (no loop)" in render_markdown(rep)


# --- free-tier quota: stop at once, resume next time ------------------------------
def _http_error(code, body):
    import io
    import urllib.error
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body.encode()))


def test_daily_quota_stops_without_waiting(monkeypatch):
    import rehnuma.extract.vision_client as vc

    body = ('[{"error": {"code": 429, "message": "You exceeded your current quota", "details":'
            ' [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},'
            ' {"retryDelay": "40s"}]}}]')
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(vc.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(
        _http_error(429, body)))
    sleeps = []
    monkeypatch.setattr(vc.time, "sleep", sleeps.append)
    with pytest.raises(vc.QuotaExhausted):
        vc.OpenAICompatVision("gemini", "m").read("s", "p", b"x", "image/png")
    assert sleeps == []                                   # no 4 x 90 s of pointless waiting


def test_per_minute_limit_still_waits_and_retries(monkeypatch):
    import io

    import rehnuma.extract.vision_client as vc

    calls = []

    def urlopen(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(429, '{"error": {"details": [{"quotaId": "PerMinute"}, '
                                   '{"retryDelay": "3s"}]}}')

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *e):
                return False
        return R(b'{"choices": [{"message": {"content": "ok"}}]}')

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(vc.urllib.request, "urlopen", urlopen)
    sleeps = []
    monkeypatch.setattr(vc.time, "sleep", sleeps.append)
    assert vc.OpenAICompatVision("gemini", "m").read("s", "p", b"x", "image/png") == "ok"
    assert sleeps == [4]


def test_eval_stops_on_quota_then_resumes_from_saved_rows(tmp_path, bill_by_id):
    from rehnuma.evals.extract_eval import run
    from rehnuma.extract.vision_client import QuotaExhausted

    imgs = tmp_path / "img"
    imgs.mkdir()
    ids = ["iesco-2019-07", "iesco-2021-01", "iesco-2023-03"]
    for b in ids:
        (imgs / f"{b}.png").write_bytes(b"x")
    cache = tmp_path / "rows"
    day1 = FakeVision([as_model_output(bill_by_id(ids[0])), QuotaExhausted("per day")])
    rep = run(imgs, REAL, day1, verify=True, cache=cache)
    assert rep["n_read"] == 1 and rep["not_run"] == ids[1:] and rep["stopped"]
    assert day1.responses == [] and len(day1.prompts) == 2    # bill 3 was never attempted
    assert rep["overall"]["api_error_rate"] == 0              # quota is "not run", not failed

    day2 = FakeVision([as_model_output(bill_by_id(b)) for b in ids[1:]])
    rep = run(imgs, REAL, day2, verify=True, cache=cache)
    assert rep["n_read"] == 3 and rep["not_run"] == [] and len(day2.prompts) == 2
    assert rep["overall"]["field_accuracy"] == 1.0


def test_api_errors_are_not_saved_so_they_are_retried(tmp_path, bill_by_id):
    from rehnuma.evals.extract_eval import run

    (tmp_path / "iesco-2021-01.png").write_bytes(b"x")
    cache = tmp_path / "rows"
    run(tmp_path, REAL, FakeVision([LLMError("HTTP 503: overloaded")]), verify=True,
        cache=cache)
    assert not cache.exists() or not list(cache.glob("*.json"))
