"""Rehnuma serves households without solar too. Until we collect real
conventional bills, this synthetic one keeps that path honest."""

from rehnuma.engine import Status, audit_bill
from rehnuma.schema import Bill
from tests.conftest import conventional_bill_dict


def test_conventional_bill_reconciles():
    findings = audit_bill(Bill.model_validate(conventional_bill_dict()))
    assert not [f for f in findings if f.status == Status.FAIL]


def test_net_metering_checks_skip_not_pass():
    findings = audit_bill(Bill.model_validate(conventional_bill_dict()))
    nm = [f for f in findings if f.check.startswith("nm_")]
    assert nm and all(f.status == Status.SKIP for f in nm)


def test_late_payment_surcharge_is_checked():
    data = conventional_bill_dict()
    data["totals"]["payable_after_due"] = 12000
    findings = audit_bill(Bill.model_validate(data))
    assert any(f.check == "payable_after_due" and f.status == Status.FAIL for f in findings)
