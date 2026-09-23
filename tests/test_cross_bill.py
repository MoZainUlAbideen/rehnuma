from rehnuma.engine import Status, audit_series


def test_series_has_no_failures(real_bills):
    fails = [f"{f.bill_id} {f.check}: {f.message}"
             for f in audit_series(real_bills) if f.status == Status.FAIL]
    assert not fails, "\n".join(fails)


def test_consecutive_checks_actually_ran(real_bills):
    findings = audit_series(real_bills)
    passed = {f.check for f in findings if f.status == Status.PASS}
    for expected in ["meter_continuity[import_offpeak]", "arrears_carry_forward",
                     "nm_bank_carry_forward[offpeak]", "nm_month_counter"]:
        assert expected in passed


def test_march_bill_appears_in_july_history(real_bills):
    findings = audit_series(real_bills)
    f = next(f for f in findings
             if f.check == "bill_in_later_history[2026-03.bill]"
             and f.bill_id == "pesco-2026-03->pesco-2026-07")
    assert f.status == Status.PASS
