"""JSON shapes the frontend renders. Plain dicts: the engine's own types stay internal."""

from __future__ import annotations

from rehnuma.assistant.assistant import Reply
from rehnuma.engine import Status, audit_bill
from rehnuma.explain.render import summarize
from rehnuma.explain.story import build_story
from rehnuma.extract.pipeline import ExtractionResult
from rehnuma.forecast.outlook import NotSupported, outlook
from rehnuma.forecast.render import rs, summarize_outlook
from rehnuma.forecast.solar import solar_outlook
from rehnuma.forecast.solar_render import summarize_solar
from rehnuma.policy.answer import Answer, Source
from rehnuma.schema import Bill, ConnectionType


def _num(x):
    return None if x is None else str(x)


def bill_view(bill: Bill, others: list[Bill] | None = None) -> dict:
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
        "outlook": outlook_view(bill),
        "solar": solar_view(bill, others or []),
    }


def solar_view(bill: Bill, others: list[Bill]) -> dict | None:
    """Last 12 months of a net-metering account + the renewal comparison (no LLM)."""
    if bill.connection_type != ConnectionType.NET_METERING:
        return None
    try:
        o = solar_outlook(bill, others)
    except ValueError as e:
        return {"available": False, "reason": str(e)}
    if not o.amounts:
        return {"available": False, "reason": "the bill history has no consecutive months"}
    r = o.renewal
    return {
        "available": True,
        "summary": {"ur": summarize_solar(o, "ur"), "en": summarize_solar(o, "en")},
        "months": [{"month": a.month, "amount": a.amount, "net_units": a.net_units}
                   for a in o.last_12],
        "total": o.last_12_total,
        "renewal": None if r is None else {
            "months": list(r.usage.months), "actual": r.usage.actual_electricity,
            "renewal_low": rs(r.renewal_total("high")), "renewal_high": rs(r.renewal_total("low")),
        },
    }


def outlook_view(bill: Bill) -> dict:
    """The 12-month outlook (no LLM, so free). `available: false` says why not."""
    try:
        o = outlook(bill)
    except NotSupported as e:
        return {"available": False, "reason": str(e)}
    except ValueError as e:        # e.g. a photo with gaps in its history: skip the outlook
        return {"available": False, "reason": f"not enough history on this bill ({e})"}
    return {
        "available": True,
        "total": rs(o.total),
        "summary": {"ur": summarize_outlook(o, "ur"), "en": summarize_outlook(o, "en")},
        "months": [{"month": u.month, "units": u.units, "low": u.low, "high": u.high,
                    "protected": m.protected, "bill": rs(m.total)}
                   for u, m in zip(o.units, o.months, strict=True)],
        "rates": f"{o.schedule.id} ({o.schedule.confidence})",
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
