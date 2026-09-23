"""Real conventional (non-solar) IESCO bills, 2019-2023: the engine must recompute
every line from first principles, not just check that totals add up."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from rehnuma.engine import Status, audit_bill, audit_series

IESCO_IDS = ["iesco-2019-07", "iesco-2021-01", "iesco-2023-03"]
ANOMALIES = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "eval" / "expected_anomalies.json")
    .read_text(encoding="utf-8"))

RECOMPUTED = {"rate_lines", "electricity_duty", "gst_on_energy", "fpa_tax_cascade", "gst_on_fpa"}


def _status(findings, check):
    return next(f.status for f in findings if f.check == check)


@pytest.mark.parametrize("bill_id", IESCO_IDS)
def test_fails_only_documented_anomalies(bill_by_id, bill_id):
    findings = audit_bill(bill_by_id(bill_id))
    failed = {f.check for f in findings if f.status == Status.FAIL}
    assert failed == {a["check"] for a in ANOMALIES.get(bill_id, [])}


@pytest.mark.parametrize("bill_id", IESCO_IDS)
def test_every_line_is_recomputed_not_skipped(bill_by_id, bill_id):
    findings = audit_bill(bill_by_id(bill_id))
    for check in RECOMPUTED:
        assert _status(findings, check) == Status.PASS, check


@pytest.mark.parametrize("bill_id", IESCO_IDS)
def test_recomputed_lines_match_exactly(bill_by_id, bill_id):
    """Recomputed lines must match at printed precision with zero delta - the Rs 1
    tolerance exists for printed-total rounding, not to paper over a wrong rule."""
    for f in audit_bill(bill_by_id(bill_id)):
        if f.check in RECOMPUTED and f.status == Status.PASS:
            assert f.delta == 0, f"{f.check}: {f.message}"


def test_different_households_are_never_cross_checked(bill_by_id):
    """Three IESCO bills share disco/tariff/type but belong to different people.
    connection_id keeps them apart; without it they'd be compared as one meter."""
    bills = [bill_by_id(b) for b in IESCO_IDS]
    assert audit_series(bills) == []


# --- error injection on the new checks ------------------------------------------
def _failed(bill):
    return {f.check for f in audit_bill(bill) if f.status == Status.FAIL}


def test_inflated_gst_is_caught(bill_by_id):
    b = bill_by_id("iesco-2023-03")
    b.legacy_charges.govt["gst"] = Decimal("2434")
    assert "gst_on_energy" in _failed(b)


def test_wrong_slab_rate_is_caught(bill_by_id):
    b = bill_by_id("iesco-2019-07")
    b.legacy_charges.rate_lines[0].rate = Decimal("10.20")   # all 200 units at the higher slab
    assert "rate_lines" in _failed(b)


def test_fpa_charged_on_wrong_month_is_caught(bill_by_id):
    b = bill_by_id("iesco-2019-07")
    b.legacy_charges.fpa_parts[0].units = 176    # June's units instead of May's
    assert "fpa_units_vs_history[2019-05]" in _failed(b)


def test_ed_on_wrong_base_is_caught(bill_by_id):
    b = bill_by_id("iesco-2021-01")
    b.legacy_charges.govt["electricity_duty"] = Decimal("5.41")   # 1.5% x (cost + FC)
    assert "electricity_duty" in _failed(b)
