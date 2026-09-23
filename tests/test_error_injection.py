"""Plant known errors in real bills and make sure the engine catches each one.
This is the seed of the auditor's precision/recall eval."""

from decimal import Decimal

from rehnuma.engine import Status, audit_bill, audit_series


def _failed(findings) -> set[str]:
    return {f.check for f in findings if f.status == Status.FAIL}


def test_wrong_register_units(bill_by_id):
    b = bill_by_id("pesco-2026-08")
    b.registers[0].units += 20  # meter reader typed 474 instead of 454
    assert "register_units[import_offpeak]" in _failed(audit_bill(b))


def test_inflated_taxes(bill_by_id):
    b = bill_by_id("pesco-2026-08")
    b.v2_charges.taxes += 150
    assert "v2_current_bill" in _failed(audit_bill(b))


def test_wrong_fpa_rate(bill_by_id):
    b = bill_by_id("pesco-2026-03")
    b.legacy_charges.fpa_rate = Decimal("1.9274")
    assert {"fpa_line", "fpa_tax_cascade"} <= _failed(audit_bill(b))


def test_banked_units_lost(bill_by_id):
    b = bill_by_id("pesco-2026-08")
    b.net_metering.remaining_present.offpeak = 900  # should be 1326
    assert "nm_remaining_kwh[offpeak]" in _failed(audit_bill(b))


def test_meter_reading_jump_between_months(bill_by_id):
    jul, aug = bill_by_id("pesco-2026-07"), bill_by_id("pesco-2026-08")
    aug.registers[0].previous = Decimal("8131.61")  # 100 units appear from nowhere
    assert "meter_continuity[import_offpeak]" in _failed(audit_series([jul, aug]))


def test_credit_not_carried_forward(bill_by_id):
    jul, aug = bill_by_id("pesco-2026-07"), bill_by_id("pesco-2026-08")
    aug.totals.arrears = -100000
    assert "arrears_carry_forward" in _failed(audit_series([jul, aug]))


def test_rounding_gap_of_two_rupees_is_flagged(bill_by_id):
    b = bill_by_id("pesco-2026-07")
    b.totals.current_bill = 3169  # 2 off from 3,171 — beyond Rs 1 tolerance
    assert "v2_current_bill" in _failed(audit_bill(b))
