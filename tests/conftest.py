from pathlib import Path

import pytest

from rehnuma.loader import load_bills
from rehnuma.schema import Bill

ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "labels" / "real"


@pytest.fixture(scope="session")
def real_bills() -> list[Bill]:
    bills = load_bills([str(REAL_DIR)])
    assert bills, "no real bill labels found"
    return bills


@pytest.fixture
def bill_by_id(real_bills):
    def _get(bill_id: str) -> Bill:
        # deep copy so tests can mutate freely
        return next(b for b in real_bills if b.bill_id == bill_id).model_copy(deep=True)
    return _get


def conventional_bill_dict() -> dict:
    """A SYNTHETIC non-solar household on the 2026 layout. Numbers are made up but
    internally consistent. Used until we collect real conventional bills."""
    return {
        "bill_id": "synthetic-conventional-001",
        "source": "synthetic",
        "disco": "PESCO",
        "layout": "pesco_v2_2026",
        "connection_type": "conventional",
        "tariff": "A-1a(01)",
        "sanctioned_load_kw": "3.00",
        "bill_month": "2026-08",
        "registers": [
            {"name": "import", "previous": "1234.00", "present": "1484.40", "units": 250},
        ],
        "v2_charges": {"total_electricity_charges": 9000, "subsidies": 0,
                       "net_electricity_charges": 9000, "taxes": 1620},
        "totals": {"arrears": 0, "current_bill": 10620, "payable_within_due": 10620,
                   "lp_surcharge": 1062, "payable_after_due": 11682},
        "history": [{"month": "2026-07", "units": 310, "bill": 12950, "payment": 12950}],
    }
