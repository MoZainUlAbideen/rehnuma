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
