"""Tracing: off by default, never breaks an answer, and when on, the trace shows the whole
path of a question - with long numbers masked and no photo bytes."""

import json
import uuid

import pytest

from rehnuma import obs


def test_off_without_keys_and_everything_still_works(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr("rehnuma.llm.client.load_dotenv", lambda *a: None)   # ignore your .env
    monkeypatch.setattr(obs, "_checked", False)
    monkeypatch.setattr(obs, "_client", None)
    assert obs.client() is None
    with obs.observe("x", input="y") as o:
        o.update(output="z")                         # a no-op, not an error


def test_mask_removes_long_numbers_everywhere():
    data = {"q": "my ref 14 23456 7890123 U and cnic 17301-1234567-1",
            "list": ["0300 1234567", "units 942 and Rs 134,041"]}
    out = obs.mask(data)
    assert "7890123" not in json.dumps(out) and "1234567" not in json.dumps(out)
    assert out["list"][1] == "units 942 and Rs 134,041"         # bill numbers stay


def test_a_broken_tracer_never_breaks_the_request():
    class Broken:
        def start_as_current_observation(self, **_):
            raise RuntimeError("langfuse down")

    obs.set_client(Broken())
    try:
        with obs.observe("x") as o:
            o.update(output=1)
            result = "answered"
        assert result == "answered"
    finally:
        obs.set_client(None)


def test_errors_in_traced_code_still_propagate():
    obs.set_client(None)
    with pytest.raises(ValueError), obs.observe("x"):
        raise ValueError("real bug")


# --- with the real SDK, exporting to memory -------------------------------------------
langfuse = pytest.importorskip("langfuse")


@pytest.fixture()
def spans():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    # the SDK keeps one client per public key: a fresh key per test gets a fresh exporter
    lf = langfuse.Langfuse(public_key=f"pk-lf-{uuid.uuid4().hex}", secret_key="sk-lf-test",
                           base_url="http://127.0.0.1:9", span_exporter=exporter,
                           mask=obs._langfuse_mask)
    obs.set_client(lf)

    def finished():
        lf.flush()
        return {s.name: s for s in exporter.get_finished_spans()}

    yield finished
    obs.set_client(None)


class FakeGroq:
    """Stands in for GroqClient.complete, traced the same way."""
    name = "fake"

    def complete(self, system, user):
        with obs.observe("llm", as_type="generation", model="fake",
                         input=[{"role": "user", "content": user}]) as g:
            if "search query" in system:
                out = "capacity distributed generation facility sanctioned load"
            else:
                out = "The capacity may not exceed the sanctioned load [S1]."
            g.update(output=out, usage_details={"input": 10, "output": 5})
            return out


def test_a_policy_question_is_one_nested_trace(spans):
    from rehnuma.assistant.assistant import ask
    from rehnuma.policy.parse import CHUNKS, load_chunks
    from rehnuma.policy.retrieve import PolicyIndex

    ask("Can my solar be bigger than my sanctioned load? my number 03001234567",
        PolicyIndex(load_chunks(CHUNKS)), FakeGroq(), lang="en")
    s = spans()
    assert {"assistant.ask", "policy.answer", "retrieve", "llm"} <= set(s)
    root = s["assistant.ask"]
    assert s["policy.answer"].parent.span_id == root.context.span_id
    assert s["retrieve"].parent.span_id == s["policy.answer"].context.span_id
    meta = json.dumps(dict(s["policy.answer"].attributes))
    assert "answered" in meta and "drafts" in meta                  # the critic's verdict
    assert "03001234567" not in json.dumps(dict(root.attributes))   # masked
    assert "[number]" in json.dumps(dict(root.attributes))


def test_photo_bytes_never_reach_the_trace(spans, monkeypatch):
    from rehnuma.extract.vision_client import OpenAICompatVision

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    v = OpenAICompatVision("gemini", "m")
    monkeypatch.setattr(v, "_read", lambda *a: {"choices": [{"message": {"content": "{}"}}],
                                                "usage": {"prompt_tokens": 7}})
    secret = b"\xff\xd8" + b"PHOTO-BYTES" * 50
    assert v.read("sys", "prompt", secret, "image/jpeg") == "{}"
    attrs = json.dumps(dict(spans()["vision"].attributes))
    assert "PHOTO-BYTES" not in attrs and "image/jpeg, 552 bytes" in attrs
