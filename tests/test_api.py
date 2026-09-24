"""HTTP API: samples, ask (cached + rate-limited), photo upload. Fake LLM + vision model,
real sample bills and real NEPRA clause index - no API keys."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from rehnuma.api.app import State, create_app  # noqa: E402
from rehnuma.api.limits import DailyLimiter, client_key, seconds_to_midnight_utc  # noqa: E402


class FakeLLM:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        if "search query" in system:                       # the rewrite step
            return "capacity distributed generation facility sanctioned load"
        if "ITS OWN electricity bill" in system:            # the bill part
            return "Your bill for this month is shown on the statement."
        return "The capacity may not exceed the sanctioned load [S1]."


class FakeVision:
    name = "fake-vision"

    def __init__(self, label: Path):
        data = json.loads(label.read_text(encoding="utf-8"))
        for meta in ("bill_id", "source"):
            data.pop(meta, None)
        self.reply = json.dumps(data)

    def read(self, system, prompt, image, mime):
        return self.reply


@pytest.fixture()
def api():
    state = State.load()
    llm = FakeLLM()
    state.llm_factory = lambda: llm
    vision = FakeVision(Path("data/labels/real/iesco-2023-03.json"))   # load before any chdir
    state.vision_factory = lambda: vision
    state.limiter = DailyLimiter({"upload": 2, "ask": 3})
    return TestClient(create_app(state)), state, llm


def test_health_and_samples(api):
    client, state, _ = api
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["samples"] == 7 and h["clauses"] > 500 and h["llm"]
    cards = client.get("/api/samples").json()
    assert {c["id"] for c in cards} == set(state.samples)


def test_sample_view_has_audit_and_both_summaries(api):
    client, *_ = api
    v = client.get("/api/samples/pesco-2026-09").json()
    assert v["audit"]["failed"] == 0 and v["audit"]["passed"] > 10
    assert v["summary"]["ur"] and v["summary"]["en"]
    assert client.get("/api/samples/nope").status_code == 404


def test_known_real_anomaly_is_shown_not_hidden(api):
    """PESCO Mar-26 prints a real Rs 2 inconsistency; the API must show it as a FAIL."""
    client, *_ = api
    v = client.get("/api/samples/pesco-2026-03").json()
    assert "fpa_total_from_lines" in {f["check"] for f in v["audit"]["findings"]
                                      if f["status"] == "FAIL"}


def test_ask_policy_with_citations_linking_to_the_pdf_page(api):
    client, *_ = api
    r = client.post("/api/ask", json={"question": "Can my solar be bigger than my sanctioned "
                                                  "load?", "lang": "en"}).json()
    assert r["route"] == "policy" and r["policy"]["status"] == "answered"
    cite = r["policy"]["citations"][0]
    assert cite["url"].startswith("https://nepra.org.pk/") and "#page=" in cite["url"]


def test_repeated_sample_question_is_cached_and_free(api):
    client, _, llm = api
    body = {"question": "Why is my bill negative this month?", "sample_id": "pesco-2026-09",
            "lang": "en"}
    first = client.post("/api/ask", json=body).json()
    calls = llm.calls
    again = client.post("/api/ask", json={**body, "question": "why is my bill negative this "
                                                             "month ?"}).json()
    assert first["route"] == "bill" and not first["cached"]
    assert again["cached"] and llm.calls == calls


def test_ask_is_rate_limited_per_visitor(api):
    client, *_ = api
    for i in range(3):
        assert client.post("/api/ask", json={"question": f"what is a detection bill {i}"},
                           headers={"x-forwarded-for": "1.2.3.4"}).status_code == 200
    r = client.post("/api/ask", json={"question": "what is a detection bill 9"},
                    headers={"x-forwarded-for": "1.2.3.4"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    other = client.post("/api/ask", json={"question": "what is a detection bill 9"},
                        headers={"x-forwarded-for": "5.6.7.8"})
    assert other.status_code == 200                  # a different visitor is unaffected


def test_bill_question_without_a_bill_asks_for_a_photo(api):
    client, *_ = api
    r = client.post("/api/ask", json={"question": "Why is my bill so high?", "lang": "en"}).json()
    assert r["route"] == "needs_bill" and "upload" in r["text"].lower()


def test_upload_reads_verifies_and_can_be_asked_about(api, tmp_path, monkeypatch):
    client, state, _ = api
    monkeypatch.chdir(tmp_path)                       # prove nothing is written to disk
    r = client.post("/api/bills/extract",
                    files={"file": ("bill.jpg", b"\xff\xd8fake-jpeg", "image/jpeg")})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["extraction"]["verified"] and v["audit"]["failed"] == 0
    assert list(tmp_path.iterdir()) == []
    q = client.post("/api/ask", json={"question": "How much do I have to pay?",
                                      "bill_token": v["bill_token"], "lang": "en"}).json()
    assert q["route"] == "bill" and q["bill"]["text"]


def test_upload_rejects_wrong_type_and_big_files(api):
    client, *_ = api
    assert client.post("/api/bills/extract", files={"file": ("x.pdf", b"%PDF", "application/pdf")}
                       ).status_code == 415
    big = b"\xff" * (8 * 1024 * 1024 + 1)
    assert client.post("/api/bills/extract", files={"file": ("x.jpg", big, "image/jpeg")}
                       ).status_code == 413


def test_expired_or_unknown_upload_token(api):
    client, *_ = api
    r = client.post("/api/ask", json={"question": "how much do I pay", "bill_token": "nope"})
    assert r.status_code == 410


def test_limiter_counts_per_day_and_proxy_address():
    lim = DailyLimiter({"ask": 1})
    day1 = datetime(2026, 9, 24, 23, 59, tzinfo=UTC)
    day2 = datetime(2026, 9, 25, 0, 1, tzinfo=UTC)
    assert lim.take("a", "ask", day1) and not lim.take("a", "ask", day1)
    assert lim.take("a", "ask", day2)                # a new day resets
    assert client_key({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "10.0.0.2") == "9.9.9.9"
    assert seconds_to_midnight_utc(day1) == 61


def test_root_redirects_to_the_docs(api):
    client, *_ = api
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/docs"
