"""Plain-language summaries: Urdu by default, English on request, and every number
traceable to the verified engine."""

import random

import pytest

from rehnuma.explain import build_story, check_faithfulness, summarize
from rehnuma.explain.faithfulness import numbers_in
from rehnuma.synth.generator import build_bill, sample_household

ALL_REAL = ["iesco-2019-07", "iesco-2021-01", "iesco-2023-03",
            "pesco-2026-03", "pesco-2026-07", "pesco-2026-08", "pesco-2026-09"]
URDU = range(0x0600, 0x06FF + 1)


def text(bill, lang="ur"):
    return "\n".join(summarize(build_story(bill), lang))


@pytest.mark.parametrize("bill_id", ALL_REAL)
@pytest.mark.parametrize("lang", ["ur", "en"])
def test_template_summary_is_fully_faithful(bill_by_id, bill_id, lang):
    bill = bill_by_id(bill_id)
    f = check_faithfulness(text(bill, lang), build_story(bill))
    assert f.stated and f.unsupported == [] and f.score == 1.0


@pytest.mark.parametrize("bill_id", ALL_REAL)
def test_urdu_is_default_and_written_in_urdu(bill_by_id, bill_id):
    lines = summarize(build_story(bill_by_id(bill_id)))      # no lang given
    assert all(any(ord(ch) in URDU for ch in line) for line in lines)


def test_unknown_language_rejected(bill_by_id):
    with pytest.raises(ValueError):
        summarize(build_story(bill_by_id("pesco-2026-09")), "fr")


def test_faithfulness_catches_an_invented_number(bill_by_id):
    story = build_story(bill_by_id("pesco-2026-09"))
    f = check_faithfulness("Your credit is Rs 134,041 and you saved Rs 9,999.", story)
    assert [str(x) for x in f.unsupported] == ["9999"] and f.score == 0.5


def test_tariff_codes_are_not_counted_as_numbers():
    assert numbers_in("tariff A-1a(01) and A-1b(03)T, 200 units") == [200]


# --- solar owners: units sent vs used, and how they became the bill ------------------
def test_solar_story_september(bill_by_id):
    t = text(bill_by_id("pesco-2026-09"), "en")
    assert "took 629 units from the grid and sent 942 units back" in t
    assert "last month of the 3-month cycle" in t
    assert "credited you Rs 19,285" in t
    assert "Rs 134,041 in credit" in t


def test_solar_story_mid_cycle_bank(bill_by_id):
    t = text(bill_by_id("pesco-2026-08"), "en")
    assert "month 2" in t
    assert "1,326 extra off-peak units saved and 319 peak units still to be charged" in t


def test_bill_effect_includes_separately_billed_fpa(bill_by_id):
    """Regression: Mar-26 prints current bill -872 but FPA +1,164 is billed on its own line,
    so the bill ADDED Rs 292. The first draft wrongly said 'credited you Rs 872'."""
    t = text(bill_by_id("pesco-2026-03"), "en")
    assert "charges of Rs 292 were added" in t
    assert "credited you Rs 872" not in t


# --- households without solar: peak hours and the 200-unit limit -------------------
def test_flat_tariff_explains_peak_hours_dont_matter(bill_by_id):
    t = text(bill_by_id("iesco-2021-01"), "en")
    assert "peak hours do not change your rate" in t


def test_unprotected_household_is_told_why(bill_by_id):
    t = text(bill_by_id("iesco-2023-03"), "en")
    assert "not a protected consumer: all 6 months were above 200 units" in t


def test_no_protected_lines_before_the_category_existed(bill_by_id):
    t = text(bill_by_id("iesco-2019-07"), "en")
    assert "protected" not in t


def _protected_household(units_this_month):
    rng = random.Random(4)
    while True:
        hh = sample_household(rng, seed=1)
        if hh.protected_profile:
            hh.usage[hh.bill_month] = units_this_month
            return hh


def test_protected_household_near_limit_is_warned():
    t = "\n".join(summarize(build_story(build_bill(_protected_household(190), "p1")), "en"))
    assert "You are a protected consumer" in t
    assert "Careful: you used 190 units" in t


def test_protected_household_far_from_limit_gets_no_warning():
    t = "\n".join(summarize(build_story(build_bill(_protected_household(90), "p2")), "en"))
    assert "You are a protected consumer" in t and "Careful" not in t


# --- the audit stays visible for people who want it ---------------------------------
def test_audit_result_is_one_line(bill_by_id):
    t = text(bill_by_id("pesco-2026-03"), "en")
    assert "found 1 mismatch on this bill (up to Rs 2)" in t
