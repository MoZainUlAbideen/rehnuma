"""calculator.py rules, and proof that the plausible ALTERNATIVE rules are rejected
by real bills. A rule we can't distinguish from its alternatives isn't a finding."""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from rehnuma.engine import calculator as calc
from rehnuma.engine.taxes import gst_rate
from rehnuma.schema import FpaPart, RateLine

D = Decimal


def rupees(x: Decimal) -> Decimal:
    return x.quantize(D(1), ROUND_HALF_UP)


def paisa(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"), ROUND_HALF_UP)


# --- GST schedule --------------------------------------------------------------
@pytest.mark.parametrize("month,rate", [
    ("2019-07", "0.17"), ("2021-01", "0.17"), ("2023-01", "0.17"),
    ("2023-02", "0.17"),  # change took effect 14-Feb, so 1-Feb is still 17%
    ("2023-03", "0.18"), ("2026-01", "0.18"),
])
def test_gst_schedule(month, rate):
    assert gst_rate(month) == D(rate)


def test_gst_unknown_before_schedule():
    with pytest.raises(ValueError):
        gst_rate("2010-01")


# --- cost of electricity -----------------------------------------------------------
def test_cost_from_rate_lines_is_unrounded():
    # IESCO Mar-23 prints 10,033 but the current bill only reconciles with 10,033.29
    assert calc.cost_of_electricity([RateLine(rate=D("25.53"), units=393)]) == D("10033.29")


# --- electricity duty: base is cost + QTA, NOT including FC surcharge ------------------
def test_ed_base_excludes_fc_surcharge():
    cost, fc, qta = D("10033.29"), D("1501.26"), D("1262.16")   # IESCO Mar-23, printed ED 169
    assert rupees(calc.electricity_duty(cost, qta, D("1.5"))) == 169
    assert rupees(calc.electricity_duty(cost + fc, qta, D("1.5"))) != 169   # alternative


# --- GST on energy -----------------------------------------------------------------
def test_gst_uses_bill_month_rate():
    # IESCO Mar-23: printed GST 2,334 fits 18%, not 17%
    cost, fc, qta = D("10033.29"), D("1501.26"), D("1262.16")
    ed = calc.electricity_duty(cost, qta, D("1.5"))
    assert rupees(calc.gst_on_energy(cost, fc, qta, ed, "2023-03")) == 2334
    assert rupees((cost + fc + qta + ed) * D("0.17")) != 2334


def test_gst_base_includes_ed():
    # IESCO Jul-19: printed GST 300
    cost, fc = D("1652.60"), D("87.29")
    ed = calc.electricity_duty(cost, D(0), D("1.5"))
    assert rupees(calc.gst_on_energy(cost, fc, D(0), ed, "2019-07")) == 300
    assert rupees((cost + fc) * D("0.17")) != 300      # alternative: without ED -> 296


# --- FPA ---------------------------------------------------------------------------
def test_gst_on_fpa_rounded_per_month():
    # IESCO Jan-21: printed GST on FPA = 14 across two FPA months
    parts = [FpaPart(ref_month="2020-10", units=117, rate=D("0.2925")),
             FpaPart(ref_month="2020-11", units=57, rate=D("0.7696"))]
    b = calc.fpa_breakdown(parts, D("1.5"))
    assert b.gst_on_fpa == 14
    assert rupees((b.fpa + b.ed_on_fpa) * D("0.17")) == 13      # alternative: round once
    assert paisa(b.total) == D("93.26")


def test_gst_on_fpa_uses_reference_month_rate():
    # IESCO Mar-23 bill (18% era) carrying Jan-23 FPA: printed GST on FPA = 46 -> 17%
    parts = [FpaPart(ref_month="2023-01", units=558)]
    b = calc.fpa_breakdown(parts, D("1.5"), printed_fpa=D("266.67"))
    assert b.gst_on_fpa == 46
    assert rupees((D("266.67") + b.ed_on_fpa) * gst_rate("2023-03")) == 49   # alternative


def test_pesco_fpa_cascade():
    parts = [FpaPart(ref_month="2026-01", units=597, rate=D("1.6274"))]
    b = calc.fpa_breakdown(parts, D("1.5"))
    assert b.gst_on_fpa == 178
    assert rupees(b.total) == 1164
    assert rupees(b.ed_on_fpa) == 15     # the bill prints 16 -> documented anomaly


def test_fpa_needs_rate_when_several_months():
    parts = [FpaPart(ref_month="2020-10", units=117), FpaPart(ref_month="2020-11", units=57)]
    with pytest.raises(ValueError, match="rate missing"):
        calc.fpa_breakdown(parts, D("1.5"), printed_fpa=D("78.09"))
