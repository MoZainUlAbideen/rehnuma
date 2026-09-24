"""What we ask the vision model for.

PII by design: the schema has NO field for name, address, reference number, consumer ID,
CNIC or phone. The model is told not to output them, and pydantic drops any unknown field
it adds anyway, so identifiers never reach storage.
"""

from __future__ import annotations

import json

from rehnuma.schema import Bill

# Filled in by code, never by the model
META_FIELDS = ("bill_id", "connection_id", "source", "uncertain_fields", "notes")


def extraction_schema() -> dict:
    schema = Bill.model_json_schema()
    for f in META_FIELDS:
        schema["properties"].pop(f, None)
        if f in schema.get("required", []):
            schema["required"].remove(f)
    return schema


SYSTEM = """You transcribe Pakistani electricity bills into JSON, exactly as printed.
You are a careful data-entry clerk, not an accountant: copy what is printed even if the
numbers do not add up. Never calculate, correct or guess a value. Output ONLY one JSON object."""


INSTRUCTIONS = """Transcribe this electricity bill into JSON matching the JSON Schema below.

Layout ("layout"):
- "pitc_legacy": the classic PITC bill (IESCO/PESCO/...: "PESCO CHARGES"/"IESCO CHARGES" and
  "GOVT CHARGES" tables, a "BILL CALCULATION" block, "TOTAL FPA").
- "pesco_v2_2026": PESCO's 2026 design with a QR code and a "BILL CHARGES BREAKDOWN" block.
Put charges in "legacy_charges" for pitc_legacy, or "v2_charges" for pesco_v2_2026.

Connection: "net_metering" if the bill shows export units / a net-metering box / "NET METERING",
otherwise "conventional" (then omit "net_metering").

Rules:
- Money: negative for credits. "CR" or a leading minus means negative (e.g. "CR -79,745" -> -79745).
- Dates as YYYY-MM-DD; months as YYYY-MM ("JAN 26" -> "2026-01", "Jul 19" -> "2019-07").
- disco: "PESCO", "IESCO", "LESCO", ... from the bill header.
- ed_rate_pct: the "ED@" percentage in the header, e.g. 1.5.
- registers: one entry per meter row. Names: "import" (single meter), or "import_offpeak",
  "import_peak", "export_offpeak", "export_peak" (in the order printed: IMP rows then EXP rows,
  off-peak before peak).
- net_metering: copy the box values exactly with their printed signs (Exp/Imp/Net, Mnt Cnt as
  month_count/cycle_length, Rem kWh previous/present). dg_capacity_kw from "DG CAPACITY" if shown.
- legacy_charges.govt: printed government lines only, keys: electricity_duty, tv_fee, gst,
  nj_surcharge, income_tax, extra_tax, further_tax, gst_on_fpa, ed_on_fpa, income_tax_on_fpa.
- fpa_parts: from the FPA note ("Fuel Price Adj for MAY-19 @ 0.0999/KWH" -> ref_month 2019-05,
  rate 0.0999; units = that month's units in the bill history). Rate null if not printed.
- rate_lines: each "rate X units" line of the BILL CALCULATION block (skip lines with 0 units).
- history: every row of the 12-month history table, status as printed ("LK", "SS") or null.
- totals.lp_surcharge: the L.P. surcharge amount (0 if blank).
- Leave optional fields out if not printed. Do not invent fields.

PRIVACY: do NOT output names, addresses, reference numbers, consumer IDs, CNICs or phone
numbers. The schema has no place for them.

JSON Schema:
"""


def build_prompt(feedback: str | None = None) -> str:
    text = INSTRUCTIONS + json.dumps(extraction_schema(), separators=(",", ":"))
    if feedback:
        text += "\n\n" + feedback
    return text
