"""Field-level comparison of an extracted Bill against a hand-verified label.

Both bills are flattened to {path: value}. Lists are keyed by their natural key
(history by month, registers by name, FPA parts by reference month), so one missed
history row costs one row, not every row after it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from rehnuma.extract.prompt import META_FIELDS
from rehnuma.schema import Bill

LIST_KEYS = {"history": "month", "registers": "name", "fpa_parts": "ref_month"}

# Fields a household actually acts on - reported separately from the long tail
KEY_FIELDS = (
    "totals.payable_within_due", "totals.payable_after_due", "totals.arrears",
    "totals.current_bill", "due_date", "bill_month", "tariff", "connection_type", "layout",
)


_NUMBER = re.compile(r"-?\d+(\.\d+)?")


def _norm(v):
    """Compare values, not spellings. model_dump(mode="json") turns Decimals into strings,
    so the label's "1652.60" and the model's "1652.6" must both become Decimal("1652.6").
    Before this fix, formatting alone was scored as misreads in the first Gemini run."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, str):
        v = v.strip()
        if not _NUMBER.fullmatch(v):
            return v                                  # dates, tariffs, enum values
    if isinstance(v, (int, float, Decimal, str)):
        d = Decimal(str(v))
        return d.quantize(Decimal(1)) if d == d.to_integral_value() else d.normalize()
    return str(v)


def flatten(obj, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not prefix and k in META_FIELDS:
                continue
            out.update(flatten(v, f"{prefix}{k}."))
    elif isinstance(obj, list):
        key = LIST_KEYS.get(prefix.rstrip(".").split(".")[-1])
        for i, item in enumerate(obj):
            tag = item.get(key) if key and isinstance(item, dict) else i
            out.update(flatten(item, f"{prefix}{tag}."))
    else:
        out[prefix.rstrip(".")] = _norm(obj)
    return out


# zero-valued defaults mean "not printed": neither reward nor punish them
_DEFAULT_ZERO = {"meter_rent", "service_rent", "fixed_charges", "fc_surcharge", "tr_surcharge",
                 "qta", "installment", "adjustments", "subsidies", "payment", "lp_surcharge"}


def bill_fields(bill: Bill) -> dict[str, object]:
    fields = flatten(bill.model_dump(mode="json", exclude_none=True))
    return {k: v for k, v in fields.items() if not (isinstance(v, Decimal) and v == 0
                                                    and k.split(".")[-1] in _DEFAULT_ZERO)}



@dataclass
class Comparison:
    correct: list[str]
    wrong: list[tuple[str, object, object]]     # (field, expected, got)
    missing: list[str]
    extra: list[str]

    @property
    def total(self) -> int:
        return len(self.correct) + len(self.wrong) + len(self.missing)

    @property
    def accuracy(self) -> float:
        return len(self.correct) / self.total if self.total else 0.0

    def key_accuracy(self) -> float:
        labelled = set(self.correct) | {w[0] for w in self.wrong} | set(self.missing)
        keys = [f for f in KEY_FIELDS if f in labelled]
        return sum(f in self.correct for f in keys) / len(keys) if keys else 0.0


def compare(expected: Bill, got: Bill | None) -> Comparison:
    exp = bill_fields(expected)
    act = bill_fields(got) if got is not None else {}
    correct, wrong, missing = [], [], []
    for k, v in exp.items():
        if k not in act:
            missing.append(k)
        elif act[k] == v:
            correct.append(k)
        else:
            wrong.append((k, v, act[k]))
    extra = [k for k in act if k not in exp]
    return Comparison(correct, wrong, missing, extra)
