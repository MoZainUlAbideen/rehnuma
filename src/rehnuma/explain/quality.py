"""Quality checks for any summary (template or LLM).

  * faithfulness - every number stated comes from the BillStory (faithfulness.py)
  * coverage     - the numbers a household MUST hear are actually there
  * language     - an Urdu summary is really in Urdu
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rehnuma.explain.faithfulness import check_faithfulness, numbers_in
from rehnuma.explain.story import BillStory

URDU_MIN_SHARE = 0.6    # share of letters that must be Urdu script in an Urdu summary


def required_numbers(story: BillStory) -> dict[str, int]:
    """What a summary must not leave out, by what users told us they care about."""
    req = {"amount to pay / credit": abs(story.payable)}
    if story.solar:
        req["units taken from grid"] = story.solar.imported.total
        req["units sent back"] = story.solar.exported.total
        req["what this bill added/credited"] = abs(story.bill_effect)
    else:
        req["units used"] = story.units
        if story.protected and story.protected.near_limit:
            req["200-unit limit"] = 200
    if story.audit and story.audit.problems:
        req["audit problems"] = story.audit.problems
    return req


def urdu_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(0x0600 <= ord(ch) <= 0x06FF for ch in letters) / len(letters)


@dataclass(frozen=True)
class Quality:
    faithfulness: float
    unsupported: list[Decimal]
    missing: list[str]
    language_ok: bool

    @property
    def coverage(self) -> float:
        return 1.0 if not self._n_required else 1 - len(self.missing) / self._n_required

    _n_required: int = 0

    @property
    def passed(self) -> bool:
        return not self.unsupported and not self.missing and self.language_ok


def assess(text: str, story: BillStory, lang: str) -> Quality:
    f = check_faithfulness(text, story)
    stated = set(numbers_in(text))
    req = required_numbers(story)
    missing = [name for name, value in req.items() if Decimal(value) not in stated]
    lang_ok = urdu_share(text) >= URDU_MIN_SHARE if lang == "ur" else urdu_share(text) < 0.05
    return Quality(f.score, f.unsupported, missing, lang_ok, _n_required=len(req))
