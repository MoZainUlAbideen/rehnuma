"""The engine must reconcile every real bill we have. If one of these fails,
either the label has a transcription error or our model of the bill is wrong —
investigate, don't loosen the tolerance."""

import pytest

from rehnuma.engine import Status, audit_bill

BILL_IDS = ["pesco-2026-03", "pesco-2026-07", "pesco-2026-08", "pesco-2026-09"]


def _get(findings, check):
    return next(f for f in findings if f.check == check)


@pytest.mark.parametrize("bill_id", BILL_IDS)
def test_real_bill_has_no_failures(bill_by_id, bill_id):
    findings = audit_bill(bill_by_id(bill_id))
    fails = [f"{f.check}: {f.message}" for f in findings if f.status == Status.FAIL]
    assert not fails, "\n".join(fails)


@pytest.mark.parametrize("bill_id", BILL_IDS)
def test_real_bill_is_actually_checked(bill_by_id, bill_id):
    """Guard against a 'pass' that is really everything being skipped."""
    findings = audit_bill(bill_by_id(bill_id))
    assert sum(f.status == Status.PASS for f in findings) >= 10


def test_fpa_tax_cascade_is_exact_when_rounded_once(bill_by_id):
    """Mar-26: adding the printed (rounded) lines gives 1,165, but computing
    (597 x 1.6274) x 1.015 x 1.18 unrounded and rounding once gives the printed 1,164."""
    findings = audit_bill(bill_by_id("pesco-2026-03"))
    assert _get(findings, "fpa_tax_cascade").delta == 0
    assert _get(findings, "fpa_total_from_lines").delta == -1


def test_known_rs1_rounding_gap_is_reported_not_hidden(bill_by_id):
    """Jul-26: 2,687 + 484 = 3,171 but the bill prints 3,170."""
    f = _get(audit_bill(bill_by_id("pesco-2026-07")), "v2_current_bill")
    assert f.status == Status.PASS
    assert f.delta == -1


def test_settlement_month_resets_bank(bill_by_id):
    nm = bill_by_id("pesco-2026-09").net_metering
    assert nm.month_count == nm.cycle_length
    assert (nm.remaining_present.offpeak, nm.remaining_present.peak) == (0, 0)
