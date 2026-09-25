"""Rehnuma's HTTP API (milestone 7).

    GET  /api/health              is it up; is an LLM / vision model configured
    GET  /api/samples             the real sample bills (free, no quota)
    GET  /api/samples/{id}        bill + audit + Urdu/English summary (free, no LLM)
    POST /api/bills/extract       photo -> verified bill (vision model; rate-limited)
    POST /api/ask                 question about a bill and/or the rules (rate-limited,
                                  cached per sample bill so repeated demo questions are free)

Privacy: an uploaded photo is read into memory, sent to the vision model and dropped - it
is never written to disk. The extracted bill has no field for names, addresses or
reference numbers (the schema has none), and is kept in memory for an hour so follow-up
questions can refer to it by token.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from rehnuma import obs
from rehnuma.api.limits import DailyLimiter, client_key, seconds_to_midnight_utc
from rehnuma.api.views import bill_view, extraction_view, reply_view, sample_card
from rehnuma.assistant.assistant import ask
from rehnuma.extract.pipeline import extract_bill
from rehnuma.llm.client import LLMClient, LLMError
from rehnuma.loader import load_bills
from rehnuma.policy.parse import CHUNKS, load_chunks
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.policy.sources import load_sources
from rehnuma.schema import Bill

SAMPLES_DIR = Path("data/labels/real")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
UPLOAD_TTL_S = 3600
MAX_UPLOADS_KEPT = 200


def _groq() -> LLMClient | None:
    from rehnuma.llm.client import GroqClient
    try:
        return GroqClient(temperature=0.0, max_tokens=700)
    except LLMError:                       # no key: the assistant still runs without an LLM
        return None


def _gemini():
    from rehnuma.extract.vision_client import OpenAICompatVision
    try:
        return OpenAICompatVision("gemini")
    except LLMError:
        return None


@dataclass
class State:
    index: PolicyIndex
    docs: dict
    samples: dict[str, Bill]
    llm_factory: Callable[[], LLMClient | None] = _groq
    vision_factory: Callable[[], object | None] = _gemini
    limiter: DailyLimiter = field(default_factory=DailyLimiter)
    uploads: dict[str, tuple[float, Bill]] = field(default_factory=dict)
    answer_cache: dict[tuple, dict] = field(default_factory=dict)

    @classmethod
    def load(cls) -> State:
        return cls(PolicyIndex(load_chunks(CHUNKS)), {d.id: d for d in load_sources()},
                   {b.bill_id: b for b in load_bills([str(SAMPLES_DIR)])})

    def keep_upload(self, bill: Bill) -> str:
        now = time.time()
        self.uploads = {k: v for k, v in self.uploads.items() if now - v[0] < UPLOAD_TTL_S}
        while len(self.uploads) >= MAX_UPLOADS_KEPT:
            self.uploads.pop(next(iter(self.uploads)))
        token = uuid.uuid4().hex
        self.uploads[token] = (now, bill)
        return token

    def upload(self, token: str) -> Bill | None:
        hit = self.uploads.get(token)
        return hit[1] if hit and time.time() - hit[0] < UPLOAD_TTL_S else None


class AskBody(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    sample_id: str | None = None
    bill_token: str | None = None
    lang: str | None = Field(default=None, pattern="^(ur|en)$")


def _normalise(q: str) -> str:
    return re.sub(r"[\s?؟.!۔]+", " ", q.casefold()).strip()


def _limit(state: State, request: Request, kind: str) -> None:
    key = client_key({k.lower(): v for k, v in request.headers.items()},
                     request.client.host if request.client else None)
    if not state.limiter.take(key, kind):
        raise HTTPException(429, detail=f"Daily limit reached for {kind} "
                            f"({state.limiter.limits[kind]} per day). Sample bills stay free.",
                            headers={"Retry-After": str(seconds_to_midnight_utc())})


def cors_origins() -> list[str]:
    """REHNUMA_CORS_ORIGINS, comma separated. A browser sends its origin without a trailing
    slash, so "https://x.vercel.app/" (pasted from the address bar - it happened while
    deploying) would never match: slashes and spaces are stripped."""
    raw = os.environ.get("REHNUMA_CORS_ORIGINS", "http://localhost:3000")
    return [o.strip().rstrip("/") for o in raw.replace("\n", ",").split(",") if o.strip()]


def create_app(state: State | None = None) -> FastAPI:
    app = FastAPI(title="Rehnuma API", version="0.1.0",
                  description="Pakistani electricity bills: audit, plain-language summary "
                              "and cited NEPRA rules, in Urdu or English.")
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(),
                       allow_methods=["GET", "POST"], allow_headers=["*"])
    app.state.rehnuma = state or State.load()

    def st() -> State:
        return app.state.rehnuma

    @app.get("/", include_in_schema=False)
    def root():                      # the Space page frames "/" - send visitors to the docs
        return RedirectResponse("/docs")

    @app.get("/api/health")
    def health():
        s = st()
        return {"status": "ok", "clauses": len(s.index.chunks), "samples": len(s.samples),
                "llm": s.llm_factory() is not None, "vision": s.vision_factory() is not None,
                "limits": s.limiter.limits}

    @app.get("/api/samples")
    def samples():
        return [sample_card(b) for b in sorted(st().samples.values(), key=lambda b: b.bill_id)]

    @app.get("/api/samples/{sample_id}")
    def sample(sample_id: str):
        bill = st().samples.get(sample_id)
        if bill is None:
            raise HTTPException(404, detail=f"no sample bill {sample_id!r}")
        return bill_view(bill, list(st().samples.values()))

    @app.post("/api/bills/extract")
    async def extract(request: Request, file: Annotated[UploadFile, File()]):
        s = st()
        if file.content_type not in IMAGE_TYPES:
            raise HTTPException(415, detail="upload a JPEG, PNG or WebP photo of the bill")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, detail="photo too large (max 8 MB)")
        vision = s.vision_factory()
        if vision is None:
            raise HTTPException(503, detail="photo reading is not configured on this server")
        _limit(s, request, "upload")
        bill_id = f"upload-{uuid.uuid4().hex[:8]}"
        with obs.observe("api.extract", metadata={"mime": file.content_type,
                                                  "bytes": len(data)}):
            res = extract_bill(data, vision, bill_id, mime=file.content_type)
        del data                                     # the photo is never stored
        if res.quota_exhausted:
            raise HTTPException(503, detail="Photo reading has used up today's free quota. "
                                "Try again tomorrow - the sample bills still work.")
        if res.bill is None:
            last = res.attempts[-1].error if res.attempts else "no output"
            raise HTTPException(502, detail=f"could not read the bill: {last}")
        return {"bill_token": s.keep_upload(res.bill), "extraction": extraction_view(res),
                **bill_view(res.bill, list(s.samples.values()))}

    @app.post("/api/ask")
    def ask_endpoint(body: AskBody, request: Request):
        s = st()
        bill = None
        if body.sample_id:
            bill = s.samples.get(body.sample_id)
            if bill is None:
                raise HTTPException(404, detail=f"no sample bill {body.sample_id!r}")
        elif body.bill_token:
            bill = s.upload(body.bill_token)
            if bill is None:
                raise HTTPException(410, detail="that uploaded bill has expired - upload again")
        key = (body.sample_id, _normalise(body.question), body.lang) if body.sample_id or \
            not body.bill_token else None
        meta = {"sample_id": body.sample_id, "upload": bool(body.bill_token), "lang": body.lang}
        if key and key in s.answer_cache:
            with obs.observe("api.ask", input=body.question, metadata={**meta, "cached": True}):
                return {**s.answer_cache[key], "cached": True}
        _limit(s, request, "ask")
        with obs.observe("api.ask", input=body.question, metadata={**meta, "cached": False}) as sp:
            reply = ask(body.question, s.index, s.llm_factory(), bill=bill, lang=body.lang,
                        docs=s.docs)
            out = reply_view(reply)
            sp.update(output=out["text"], metadata={"route": out["route"]})
        if key and not _degraded(out):
            s.answer_cache[key] = out
        return {**out, "cached": False}

    return app


def _degraded(out: dict) -> bool:
    """Never cache an answer produced while the LLM was failing."""
    p = out.get("policy")
    b = out.get("bill")
    return bool((p and p["status"] == "error") or (b and b["source"] == "template_fallback"))
