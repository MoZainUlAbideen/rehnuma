"""Synthetic generator and the auditor eval."""

import copy
import random

import pytest

from rehnuma.engine import Status, audit_bill
from rehnuma.evals.auditor_eval import run
from rehnuma.synth.errors import ERROR_TYPES
from rehnuma.synth.generator import build_bill, sample_household


def _households(n, seed=1):
    rng = random.Random(seed)
    return [sample_household(rng, seed=i) for i in range(n)]


def test_clean_synthetic_bills_pass_the_auditor():
    for i, hh in enumerate(_households(200)):
        fails = [f for f in audit_bill(build_bill(hh, f"t{i}")) if f.status == Status.FAIL]
        assert not fails, f"t{i}: {fails[0].check}: {fails[0].message}"


def test_synthetic_bills_are_marked_synthetic():
    b = build_bill(_households(1)[0], "t0")
    assert b.source == "synthetic" and "SYNTHETIC" in b.notes[0]


def test_generator_is_deterministic():
    a = build_bill(_households(1, seed=9)[0], "x")
    b = build_bill(_households(1, seed=9)[0], "x")
    assert a.model_dump() == b.model_dump()


def test_both_protected_and_unprotected_households_are_generated():
    profiles = {hh.protected_profile for hh in _households(100)}
    assert profiles == {True, False}


@pytest.mark.parametrize("err", [e for e in ERROR_TYPES if e.expected_check],
                         ids=lambda e: e.name)
def test_each_detectable_error_changes_the_bill_and_is_caught(err):
    rng = random.Random(3)
    tried = 0
    for i, hh in enumerate(_households(300, seed=5)):
        if not err.applies(hh):
            continue
        clean = build_bill(copy.deepcopy(hh), f"e{i}")
        bad = err.apply(hh, rng, f"e{i}")
        assert bad.model_dump() != clean.model_dump(), "error planted no change"
        fails = {f.check for f in audit_bill(bad) if f.status == Status.FAIL}
        assert any(c.startswith(err.expected_check) for c in fails), fails
        tried += 1
        if tried == 5:
            break
    assert tried == 5


def test_undetectable_error_really_is_consistent():
    """If the auditor ever 'catches' this, the generator leaked an inconsistency."""
    err = next(e for e in ERROR_TYPES if e.expected_check is None)
    rng = random.Random(0)
    for i, hh in enumerate(_households(30, seed=8)):
        fails = [f for f in audit_bill(err.apply(hh, rng, f"u{i}")) if f.status == Status.FAIL]
        assert not fails


def test_eval_report_shape_and_no_false_positives():
    report = run(n=300, seed=11)
    o = report["overall"]
    assert o["n_error_bills"] + o["n_clean_bills"] + o["n_undetectable_bills"] == 300
    assert o["false_positive_rate"] == 0.0
    assert o["localisation_rate"] == 1.0
