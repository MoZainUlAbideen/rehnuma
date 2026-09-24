"""JSON shapes the frontend renders. Plain dicts: the engine's own types stay internal."""

from __future__ import annotations

from rehnuma.assistant.assistant import Reply
from rehnuma.engine import Status, audit_bill
from rehnuma.explain.render import summarize
from rehnuma.explain.story import build_story
from rehnuma.extract.pipeline import ExtractionResult
from rehnuma.policy.answer import Answer, Source
from rehnuma.schema import Bill


def _num(x):
    return None if x is None else str(x)


def bill_view(bill: Bill) -> dict:
    """The bill, Rehnuma's audit of it, and the plain-language summary in both languages."""
    findings = audit_bill(bill)
    story = build_story(bill)
    return {
        "bill": bill.model_dump(mode="json"),
        "audit": {
            "passed": sum(f.status == Status.PASS for f in findings),
            "failed": sum(f.status == Status.FAIL for f in findings),
            "skipped": sum(f.status == Status.SKIP for f in findings),
            "findings": [{"check": f.check, "status": f.status.value, "message": f.message,
                          "expected": _num(f.expected), "actual": _num(f.actual)}
                         for f in findings],
        },
        "summary": {"ur": summarize(story, "ur"), "en": summarize(story, "en")},
    }


def sample_card(bill: Bill) -> dict:
    return {"id": bill.bill_id, "disco": bill.disco, "month": bill.bill_month,
            "connection_type": bill.connection_type.value, "layout": bill.layout.value,
            "payable": bill.totals.payable_within_due}


def citation(s: Source) -> dict:
    """Everything needed to link a claim to the official PDF page."""
    return {"tag": s.tag, "label": s.label, "document": s.doc.title, "clause": s.chunk.clause,
            "page": s.chunk.page, "url": f"{s.doc.url}#page={s.chunk.page}",
            "repealed": s.repealed, "savings_for": s.savings_for or None}


def policy_view(a: Answer) -> dict:
    return {"status": a.status, "text": a.text,
            "citations": [citation(s) for s in a.cited],
            "sources_considered": [s.label for s in a.sources]}


def reply_view(reply: Reply) -> dict:
    return {
        "route": reply.route.kind,
        "lang": reply.lang,
        "text": reply.render(),
        "bill": ({"text": reply.bill.text, "source": reply.bill.source}
                 if reply.bill else None),
        "policy": policy_view(reply.policy) if reply.policy else None,
    }


def extraction_view(res: ExtractionResult) -> dict:
    return {"verified": res.verified, "attempts": len(res.attempts),
            "failed_checks": res.failed_checks, "seconds": round(res.seconds, 1)}
