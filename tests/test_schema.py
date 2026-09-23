import pytest
from pydantic import ValidationError

from rehnuma.schema import Bill, Layout, shift_month
from tests.conftest import conventional_bill_dict


def test_all_real_labels_load(real_bills):
    assert len(real_bills) == 7
    assert {b.layout for b in real_bills} == {Layout.PITC_LEGACY, Layout.PESCO_V2_2026}


def test_real_labels_contain_no_identifiers(real_bills):
    """Labels are committed publicly — reference numbers / consumer IDs must never appear."""
    for b in real_bills:
        dumped = b.model_dump_json()
        assert "1260006655" not in dumped
        assert "20261210008050" not in dumped


def test_legacy_layout_requires_legacy_charges(bill_by_id):
    data = bill_by_id("pesco-2026-03").model_dump()
    data["legacy_charges"] = None
    with pytest.raises(ValidationError, match="legacy_charges"):
        Bill.model_validate(data)


def test_conventional_bill_cannot_have_net_metering_block(bill_by_id):
    data = bill_by_id("pesco-2026-08").model_dump()
    data["connection_type"] = "conventional"
    with pytest.raises(ValidationError, match="conventional"):
        Bill.model_validate(data)


def test_bad_month_format_rejected():
    data = conventional_bill_dict()
    data["bill_month"] = "Aug 26"
    with pytest.raises(ValidationError):
        Bill.model_validate(data)


@pytest.mark.parametrize("month,delta,expected", [
    ("2026-01", -1, "2025-12"), ("2025-12", 1, "2026-01"), ("2026-07", 0, "2026-07"),
])
def test_shift_month(month, delta, expected):
    assert shift_month(month, delta) == expected
