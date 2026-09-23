"""Slab engine and protected-status rules."""

from decimal import Decimal

import pytest

from rehnuma.schema import HistoryEntry, shift_month
from rehnuma.tariffs import (
    UnknownRate,
    load_schedules,
    protected_eligible,
    schedule_for,
    slab_rate_lines,
)

D = Decimal


def lines(ls):
    return [(str(ln.rate), ln.units) for ln in ls]


def test_every_schedule_states_source_and_confidence():
    for s in load_schedules():
        assert s.source and s.confidence in {"official", "secondary", "observed"}


def test_schedule_lookup_by_month():
    assert schedule_for("A-1a(01)", "2019-07").id == "observed-2019"
    assert schedule_for("A-1a(01)", "2026-02").id == "observed-2023"   # new one starts 12-Feb
    assert schedule_for("A-1a(01)", "2026-03").id == "a1-2026-02"
    assert schedule_for("A-1b(03)T", "2026-03") is None                # ToU not modelled yet


# --- the structure of real bills ------------------------------------------------------
def test_one_previous_slab_benefit_2019():
    assert lines(slab_rate_lines(203, schedule_for("A-1a", "2019-07"), False)) == [
        ("8.11", 200), ("10.20", 3)]


def test_unprotected_no_slab_benefit_2023():
    assert lines(slab_rate_lines(393, schedule_for("A-1a", "2023-03"), False)) == [("25.53", 393)]


def test_unknown_rate_is_an_error_not_a_guess():
    with pytest.raises(UnknownRate):
        slab_rate_lines(150, schedule_for("A-1a", "2019-07"), False)


# --- 2026 schedule ---------------------------------------------------------------
S26 = "2026-03"


@pytest.mark.parametrize("units,protected,expected", [
    (80, True, [("10.54", 80)]),
    (150, True, [("10.54", 100), ("13.01", 50)]),        # one previous slab benefit
    (150, False, [("28.91", 150)]),                      # every unit at slab reached
    (201, False, [("33.10", 201)]),
    (750, False, [("47.20", 750)]),
    (230, True, [("33.10", 230)]),                       # protected above 200 -> unprotected
])
def test_2026_slabs(units, protected, expected):
    assert lines(slab_rate_lines(units, schedule_for("A-1a", S26), protected)) == expected


def test_protected_vs_unprotected_gap_is_large():
    """Why this check matters: the same 150 units cost ~2.3x more unprotected."""
    s = schedule_for("A-1a", S26)
    prot = sum(ln.rate * ln.units for ln in slab_rate_lines(150, s, True))
    unprot = sum(ln.rate * ln.units for ln in slab_rate_lines(150, s, False))
    assert unprot / prot > 2


# --- protected eligibility ---------------------------------------------------------
def _history(month, units_by_offset):
    return [HistoryEntry(month=shift_month(month, -k), units=D(u), bill=0)
            for k, u in units_by_offset.items()]


def test_protected_when_six_months_at_or_below_200():
    h = _history("2026-05", {k: 200 if k == 3 else 150 for k in range(1, 7)})
    assert protected_eligible(h, "2026-05", "A-1a(01)") is True


def test_one_month_above_200_loses_protection():
    h = _history("2026-05", {k: 201 if k == 6 else 150 for k in range(1, 7)})
    assert protected_eligible(h, "2026-05", "A-1a(01)") is False


def test_incomplete_history_is_unknown():
    h = _history("2026-05", {k: 150 for k in range(1, 5)})
    assert protected_eligible(h, "2026-05", "A-1a(01)") is None


def test_tou_is_never_protected():
    h = _history("2026-05", {k: 50 for k in range(1, 7)})
    assert protected_eligible(h, "2026-05", "A-1b(03)T") is False
