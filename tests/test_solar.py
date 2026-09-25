"""5c: solar (net-metering) outlook - last 12 months from the balance history, and the
renewal comparison on a real billing cycle."""

import re
from decimal import Decimal

import pytest

from rehnuma.evals.forecast_eval import solar_checks
from rehnuma.forecast.render import rs
from rehnuma.forecast.solar import (
    cycle_bills,
    monthly_amounts,
    renewal_scenario,
    solar_outlook,
)
from rehnuma.forecast.solar_render import summarize_solar
from rehnuma.loader import load_bill, load_bills

REAL = "data/labels/real"


@pytest.fixture(scope="module")
def bills():
    return {b.bill_id: b for b in load_bills([REAL])}


def test_monthly_amounts_come_from_balance_changes(bills):
    amounts = {a.month: a for a in monthly_amounts(bills["pesco-2026-09"])}
    assert len(amounts) == 12
    assert amounts["2026-06"].amount == -47682 and amounts["2026-06"].net_units == -2151
    sep = amounts["2026-09"]                       # the bill's own month
    assert sep.amount == -19285 and sep.net_units == -1320


def test_own_month_includes_the_fuel_adjustment(bills):
    """Regression: Mar-26's own row used 'current bill' (-872), but the balance moved +292
    because the Rs 1,164 fuel adjustment is billed on top - as the next bills' history shows."""
    mar = monthly_amounts(bills["pesco-2026-03"])[-1]
    assert mar.month == "2026-03" and mar.amount == 292


def test_a_gap_in_history_is_not_bridged(bills):
    b = bills["pesco-2026-09"]
    gappy = b.model_copy(update={"history": [h for h in b.history if h.month != "2026-01"]})
    months = [a.month for a in monthly_amounts(gappy)]
    assert months[0] == "2026-03"                 # Feb can't be diffed without Jan


def test_cycle_is_linked_by_meter_continuity(bills):
    others = list(bills.values())
    cycle = cycle_bills(bills["pesco-2026-09"], others)
    assert [c.bill_id for c in cycle] == ["pesco-2026-07", "pesco-2026-08", "pesco-2026-09"]
    assert cycle_bills(bills["pesco-2026-03"], others) is None      # Jan/Feb bills missing
    aug = bills["pesco-2026-08"]
    regs = [r.model_copy(update={"present": r.present + 1}) for r in aug.registers]
    broken = [aug.model_copy(update={"registers": regs}) if b.bill_id == aug.bill_id else b
              for b in others]
    assert cycle_bills(bills["pesco-2026-09"], broken) is None     # a reading doesn't carry


def test_renewal_prices_the_real_cycle(bills):
    r = renewal_scenario(cycle_bills(bills["pesco-2026-09"], list(bills.values())))
    u = r.usage
    assert (u.import_offpeak, u.import_peak, u.export_total) == (1255, 513, 3088)
    assert u.actual_electricity == 2687 + 2774 - 19285
    assert r.fixed_estimate == Decimal("8191.5")          # in-cycle months, x3
    assert r.renewal_total("high") == Decimal("41592.70")  # EPP Rs 11
    assert r.difference("high") > 50000 and r.difference("low") > r.difference("high")


def test_bill_without_its_cycle_gets_no_renewal_numbers(bills):
    o = solar_outlook(bills["pesco-2026-09"])            # no other bills given
    assert o.renewal is None
    assert not any("renewal" in ln for ln in summarize_solar(o, "en"))


def test_conventional_bills_are_rejected():
    with pytest.raises(ValueError):
        solar_outlook(load_bill(f"{REAL}/iesco-2021-01.json"))


@pytest.mark.parametrize("bid", ["pesco-2026-09", "pesco-2026-03"])
@pytest.mark.parametrize("lang", ["ur", "en"])
def test_every_number_in_the_solar_summary_comes_from_the_outlook(bills, bid, lang):
    o = solar_outlook(bills[bid], list(bills.values()))
    allowed = {len(o.last_12), rs(abs(o.last_12_total)), 2025, 2026, 2027, 21, 2, 9, 11}
    for a in o.amounts:
        allowed |= {abs(a.net_units), rs(abs(a.amount))}
    im = o.import_months
    allowed |= {sum(a.net_units for a in im), rs(sum(a.amount for a in im))}
    for lvl in (o.in_cycle_level(False), o.in_cycle_level(True)):
        if lvl:
            allowed.add(rs(lvl[1]))
    if o.renewal:
        r, u = o.renewal, o.renewal.usage
        allowed |= {u.import_offpeak + u.import_peak, u.export_total,
                    rs(abs(u.actual_electricity))}
        allowed |= {rs(r.renewal_total(k)) for k in ("low", "high")}
        allowed |= {rs(r.difference(k)) for k in ("low", "high")}
    text = " ".join(summarize_solar(o, lang))
    found = {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text)}
    assert found <= allowed, found - allowed


def test_solar_eval(bills):
    rep = solar_checks(list(bills.values()))
    assert rep["reconstruction"] and all(r["ok"] for r in rep["reconstruction"])
    naive = rep["last_year_as_forecast"]
    assert naive["months"] == 6 and naive["forecast_total"] < naive["actual_total"]
    (hyp,) = rep["settlement_hypothesis"]
    assert hyp["error"] < 0.10
