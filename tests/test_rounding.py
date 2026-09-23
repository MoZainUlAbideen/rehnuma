from decimal import Decimal

from rehnuma.engine.findings import Status, compare, to_rupees


def test_round_half_up_not_bankers():
    # Python's round(0.5) == 0 (banker's). Bills round half up.
    assert to_rupees(Decimal("0.5")) == 1
    assert to_rupees(Decimal("2.5")) == 3
    assert to_rupees(Decimal("-0.4")) == 0


def test_register_rounding_seen_on_real_bill():
    # Mar-26 bill: 7071.29 - 6876.51 = 194.78 -> printed 195
    assert to_rupees(Decimal("7071.29") - Decimal("6876.51")) == 195
    # 16468.6 - 15969.11 = 499.49 -> printed 499
    assert to_rupees(Decimal("16468.6") - Decimal("15969.11")) == 499


def test_compare_tolerance():
    assert compare("x", None, 3171, 3170, tolerance=1).status == Status.PASS
    assert compare("x", None, 3172, 3170, tolerance=1).status == Status.FAIL
    assert compare("x", None, 3171, 3170).status == Status.FAIL  # default: exact



def test_recomputed_tolerance_follows_printed_precision():
    """Regression: a Rs 1 tolerance let ED 5.41 pass for a printed 5.04."""
    from rehnuma.engine.checks import compare_printed, printed_step

    assert printed_step(Decimal("5.04")) == Decimal("0.01")
    assert printed_step(Decimal("1164")) == Decimal("1")
    computed = Decimal("5.0373")
    assert compare_printed("ed", "x", computed, Decimal("5.41"), "ED").status == Status.FAIL
    assert compare_printed("ed", "x", computed, Decimal("5.04"), "ED").status == Status.PASS