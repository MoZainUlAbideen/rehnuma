"""Bill photo -> Bill, verified by the reconciliation engine.

    photo -> vision model -> JSON -> schema validation -> audit
               ^                                           |
               +------ re-read feedback (verify mode) -----+

The auditor doubles as the extraction checker: real bills reconcile, so a failed check
usually means a misread digit. The feedback NEVER tells the model what a value should be -
only which fields to re-read and to copy them exactly as printed. Otherwise the model
could "fix" numbers to make them add up and hide a real billing error (like the Rs 2
contradiction printed on the PESCO Mar-26 bill).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from rehnuma import obs
from rehnuma.engine import Status, audit_bill
from rehnuma.extract.prompt import SYSTEM, build_prompt
from rehnuma.extract.vision_client import QuotaExhausted, VisionClient, mime_for
from rehnuma.llm.client import LLMError
from rehnuma.schema import Bill

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in ``` fences or add a sentence; take the outer object."""
    if not isinstance(text, str) or not text.strip():
        # e.g. a thinking model spent its whole token budget and returned no content
        raise ValueError("the model returned no text")
    m = JSON_BLOCK.search(text)
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(0))


def to_bill(data: dict, bill_id: str, source: str = "real") -> Bill:
    data = {**data, "bill_id": bill_id, "source": source}
    return Bill.model_validate(data)    # unknown keys (e.g. a name) are dropped here


@dataclass
class Attempt:
    number: int
    ok_schema: bool
    failed_checks: list[str] = field(default_factory=list)
    error: str | None = None
    bill: Bill | None = None                # what this attempt read (schema-valid only)
    quota_exhausted: bool = False           # the provider refused: try again later


@dataclass
class ExtractionResult:
    bill: Bill | None
    verified: bool                  # schema-valid AND no failed reconciliation check
    attempts: list[Attempt]
    seconds: float

    @property
    def failed_checks(self) -> list[str]:
        return self.attempts[-1].failed_checks if self.attempts else []

    @property
    def quota_exhausted(self) -> bool:
        return any(a.quota_exhausted for a in self.attempts)

    @property
    def first_pass(self) -> Attempt | None:
        """The first schema-valid read. Re-read feedback is only sent AFTER a schema-valid
        read, so this is exactly what a single-pass run (verify=False) returns - the eval
        scores it as the "no re-read loop" column without spending a second run's quota."""
        return next((a for a in self.attempts if a.ok_schema), None)


def _schema_feedback(err: Exception) -> str:
    return ("Your previous JSON did not match the schema: " + str(err)[:1500]
            + "\nReturn the full corrected JSON.")


# Which printed fields each failed check involves. Feedback names FIELDS only - never the
# auditor's "expected X, got Y" message, which would hand the model the answer and let it
# "fix" a real billing error instead of re-reading (caught by test_extract.py).
FIELDS_FOR_CHECK = {
    "register_units": "meter readings (previous, present, units)",
    "nm_": "the net-metering box (Exp/Imp/Net, month count, remaining kWh - copy both printed "
           "Rem kWh values, do not calculate one from the other)",
    "legacy_units_consumed": "units consumed and the meter rows",
    "legacy_current_bill": "the DISCO charges, government charges and current bill",
    "legacy_disco_total": "the DISCO charge lines and their TOTAL",
    "legacy_govt_total": "the government charge lines and their TOTAL",
    "rate_lines": "the BILL CALCULATION block and cost of electricity",
    "tariff_rates": "the BILL CALCULATION block and the 12-month history units",
    "electricity_duty": "electricity duty and the ED% in the header",
    "gst_on_energy": "the GST line",
    "nj_surcharge": "the N.J surcharge line",
    "fpa": "the FPA line, the FPA note (month and rate), taxes on FPA and TOTAL FPA",
    "gst_on_fpa": "GST on FPA",
    "ed_on_fpa": "ED on FPA (a separate line from GST on FPA)",
    "v2_": "the BILL CHARGES BREAKDOWN block",
    "payable": "arrears, current bill, TOTAL FPA and the payable amounts",
    "arrears_vs_history": "arrears and the last rows of the bill history",
}


def fields_to_reread(failed_checks: list[str]) -> list[str]:
    out: list[str] = []
    for check in failed_checks:
        for prefix, fields in FIELDS_FOR_CHECK.items():
            if check.startswith(prefix) and fields not in out:
                out.append(fields)
    return out or ["all amounts"]


def _reread_feedback(failed_checks: list[str]) -> str:
    return ("Some values in your previous transcription may be misread. Look at the image "
            "again and re-read, digit by digit: " + "; ".join(fields_to_reread(failed_checks))
            + ". Copy exactly what is printed, even if it does not add up - real bills can "
            "contain errors. Return the full JSON.")


def extract_bill(image_path: str | Path | bytes, client: VisionClient, bill_id: str,
                 verify: bool = True, max_attempts: int = 3,
                 mime: str | None = None) -> ExtractionResult:
    """`image_path` may be raw bytes (an upload: the photo never touches disk) - then
    `mime` is required."""
    with obs.observe("extract_bill", as_type="chain",
                     metadata={"verify": verify, "max_attempts": max_attempts}) as span:
        res = _extract_bill(image_path, client, bill_id, verify, max_attempts, mime)
        span.update(output={"verified": res.verified, "attempts": len(res.attempts),
                            "failed_checks": res.failed_checks,
                            "quota_exhausted": res.quota_exhausted},
                    level="WARNING" if res.bill is None else "DEFAULT")
        return res


def _extract_bill(image_path: str | Path | bytes, client: VisionClient, bill_id: str,
                  verify: bool, max_attempts: int, mime: str | None) -> ExtractionResult:
    start = time.perf_counter()
    if isinstance(image_path, bytes):
        if not mime:
            raise ValueError("mime is required when passing image bytes")
        image = image_path
    else:
        image = Path(image_path).read_bytes()
        mime = mime or mime_for(image_path)
    attempts: list[Attempt] = []
    best: tuple[int, Bill] | None = None      # (number of failed checks, bill)
    feedback = None
    for n in range(1, max_attempts + 1):
        try:
            raw = client.read(SYSTEM, build_prompt(feedback), image, mime)
            bill = to_bill(parse_json(raw), bill_id)
        except LLMError as e:
            attempts.append(Attempt(n, False, error=str(e)[:300],
                                    quota_exhausted=isinstance(e, QuotaExhausted)))
            break
        except (ValueError, ValidationError) as e:
            attempts.append(Attempt(n, False, error=str(e)[:300]))
            feedback = _schema_feedback(e)
            continue
        fails = [f.check for f in audit_bill(bill) if f.status == Status.FAIL]
        attempts.append(Attempt(n, True, fails, bill=bill))
        if best is None or len(fails) < best[0]:
            best = (len(fails), bill)
        if not fails or not verify:
            break
        feedback = _reread_feedback(fails)
    return ExtractionResult(best[1] if best else None, best is not None and best[0] == 0,
                            attempts, time.perf_counter() - start)
