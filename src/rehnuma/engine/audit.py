"""Run all checks and summarise the results."""

from __future__ import annotations

from collections import Counter
from itertools import groupby

from rehnuma.engine.checks import SINGLE_BILL_CHECKS
from rehnuma.engine.cross_bill import audit_pairs
from rehnuma.engine.findings import Finding, Status
from rehnuma.schema import Bill


def audit_bill(bill: Bill) -> list[Finding]:
    findings: list[Finding] = []
    for check in SINGLE_BILL_CHECKS:
        findings.extend(check(bill))
    return findings


def audit_series(bills: list[Bill]) -> list[Finding]:
    """Cross-bill checks, run separately for each connection. Bills are grouped by
    connection_id; without one we fall back to (disco, tariff, connection type)."""
    def key(b: Bill) -> tuple[str, ...]:
        if b.connection_id:
            return ("id", b.connection_id)
        return ("fallback", b.disco, b.tariff, b.connection_type.value)

    out: list[Finding] = []
    for _, group in groupby(sorted(bills, key=key), key=key):
        out.extend(audit_pairs(list(group)))
    return out


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts = Counter(f.status for f in findings)
    return {s.value: counts.get(s, 0) for s in Status}
