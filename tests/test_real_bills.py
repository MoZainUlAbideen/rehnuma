"""The engine must reconcile every real bill we have. If one of these fails,
either the label has a transcription error or our model of the bill is wrong -
investigate, don't loosen the tolerance.

Real bills can contradict themselves. Those cases are listed, with a diagnosis,
in data/eval/expected_anomalies.json. A bill must fail EXACTLY its listed checks.
"""

import json
from pathlib import Path

import pytest

from rehnuma.engine import Status, audit_bill

BILL_IDS = ["pesco-2026-03", "pesco-2026-07", "pesco-2026-08", "pesco-2026-09"]
ANOMALIES_PATH = Path(__file__).resolve().parents[1] / "data" / "eval" / "expected_anomalies.json"
ANOMALIES = json.loads(ANOMALIES_PATH.read_text(encoding="utf-8"))


def _get(findings, check):
    return next(f for f in findings if f.check == check)


@pytest.mark.parametrize("bill_id", BILL_IDS)
def test_real_bill_fails_only_its_documented_anomalies(bill_by_id, bill_id):
    findings = audit_bill(bill_by_id(bill_id))
    failed = {f.check for f in findings if f.status == Status.FAIL}
    expected = {a["check"] for a in ANOMALIES.get(bill_id, [])}
    unexpected = [f"{f.check}: {f.message}" for f in findings
                  if f.status == Status.FAIL and f.check not in expected]
    assert not unexpected, "new failures:\n" + "\n".join(unexpected)
    assert failed == expected, f"documented anomalies no longer fail: {expected - failed}"


@pytest.mark.parametrize("bill_id", BILL_IDS)
def test_real_bill_is_actually_checked(bill_by_id, bill_id):
    """Guard against a 'pass' that is really everything being skipped."""
    findings = audit_bill(bill_by_id(bill_id))
    assert sum(f.status == Status.PASS for f in findings) >= 10


def test_fpa_total_follows_unrounded_cascade_not_printed_lines(bill_by_id):
    """Mar-26: the printed lines 972 + 178 + 16 = 1,166 but Total FPA is 1,164.
    The total is reproduced exactly by (597 x 1.6274) x 1.015 x 1.18 = 1,163.63 -> 1,164,
    so the cascade is the source of truth and the printed ED line is the odd one out."""
    findings = audit_bill(bill_by_id("pesco-2026-03"))
    assert _get(findings, "fpa_tax_cascade").delta == 0
    lines = _get(findings, "fpa_total_from_lines")
    assert lines.status == Status.FAIL and lines.delta == -2


def test_known_rs1_rounding_gap_is_reported_not_hidden(bill_by_id):
    """Jul-26: 2,687 + 484 = 3,171 but the bill prints 3,170."""
    f = _get(audit_bill(bill_by_id("pesco-2026-07")), "v2_current_bill")
    assert f.status == Status.PASS
    assert f.delta == -1


def test_settlement_month_resets_bank(bill_by_id):
    nm = bill_by_id("pesco-2026-09").net_metering
    assert nm.month_count == nm.cycle_length
    assert (nm.remaining_present.offpeak, nm.remaining_present.peak) == (0, 0)