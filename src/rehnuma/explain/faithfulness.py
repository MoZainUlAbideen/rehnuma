"""Numeric faithfulness: every number a summary states must come from the BillStory.

The template baseline must score 100%. The LLM summary (next step) is measured with
the same function, so any invented or miscopied number shows up as a failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from rehnuma.explain.story import BillStory

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
TARIFF_CODE = re.compile(r"A-1[ab](?:\(\d+\)T?)?")


@dataclass(frozen=True)
class Faithfulness:
    stated: list[Decimal]
    unsupported: list[Decimal]

    @property
    def score(self) -> float:
        return 1.0 if not self.stated else 1 - len(self.unsupported) / len(self.stated)


def numbers_in(text: str) -> list[Decimal]:
    text = TARIFF_CODE.sub(" ", text)          # 'A-1a(01)' is a name, not a quantity
    return [Decimal(m.replace(",", "")) for m in NUMBER.findall(text)]


def check_faithfulness(text: str, story: BillStory) -> Faithfulness:
    allowed = story.allowed_numbers()
    stated = numbers_in(text)
    return Faithfulness(stated, [x for x in stated if x not in allowed])
