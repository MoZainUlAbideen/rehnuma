"""Milestone 5: 12-month outlook - units, rupees, and the 200-unit protected limit."""

import re
from decimal import Decimal

import pytest

from rehnuma.evals.forecast_eval import backtest, engine_consistency, profiles
from rehnuma.forecast.cost import cost_path, latest_schedule, month_cost
from rehnuma.forecast.outlook import NotSupported, edge_in_reach, outlook
from rehnuma.forecast.render import rs, summarize_outlook
from rehnuma.forecast.units import forecast_units, monthly_units
from rehnuma.loader import load_bill
from rehnuma.schema import HistoryEntry, shift_month

REAL = "data/labels/real"
SCHED = latest_schedule()


def bill(bid):
    return load_bill(f"{REAL}/{bid}.json")


def year(start: str, units: list[int]) -> dict[str, int]:
    return {shift_month(start, i): u for i, u in enumerate(units)}


# --- units -----------------------------------------------------------------------------
def test_forecast_is_same_month_last_year_with_a_neighbour_range():
    series = year("2025-01", [50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160])
    fc = forecast_units(series, "2025-12")
    assert [f.month for f in fc][:2] == ["2026-01", "2026-02"] and len(fc) == 12
    feb = fc[1]
    assert (feb.units, feb.low, feb.high) == (60, 50, 70)     # Jan..Mar of last year


def test_forecast_needs_twelve_months():
    with pytest.raises(ValueError, match="12 months"):
        forecast_units(year("2025-06", [100] * 6), "2025-11")


def test_monthly_units_includes_this_bills_own_month():
    s = monthly_units(bill("iesco-2021-01"))
    assert len(s) == 13 and s["2021-01"] == 58 and s["2020-09"] == 226


# --- rupees and the protected rule ----------------------------------------------------
def test_crossing_200_by_one_unit_costs_far_more_than_one_unit():
    under = month_cost("2026-06", 200, True, SCHED, Decimal(2), Decimal("1.5"))
    over = month_cost("2026-06", 201, True, SCHED, Decimal(2), Decimal("1.5"))
    assert not over.protected and over.total - under.total > 50 * 47   # >> any unit rate


def test_one_bad_month_costs_protection_for_the_next_six():
    history = year("2025-01", [150] * 12)
    plan = [(m, 250 if m == "2026-01" else 150) for m in year("2026-01", [0] * 12)]
    path = cost_path(history, plan, SCHED, Decimal(2), Decimal("1.5"), "A-1a(01)")
    status = {c.month: c.protected for c in path}
    assert not any(status[shift_month("2026-01", k)] for k in range(0, 7))   # Jan + 6 after
    assert status["2026-08"]                                                # back in Aug


def test_edges_in_reach():
    assert edge_in_reach(211, SCHED) == 200
    assert edge_in_reach(230, SCHED) == 200 and edge_in_reach(231, SCHED) is None
    assert edge_in_reach(513, SCHED) == 500
    assert edge_in_reach(50, SCHED) is None


# --- the outlook on real bills --------------------------------------------------------
def test_june_cut_is_worth_over_a_thousand_rupees_per_unit():
    """iesco-2021-01 crossed 200 in Jun (211) and Sep (226) last year."""
    o = outlook(bill("iesco-2021-01"))
    assert o.cross_months == ["2021-06", "2021-09"]
    june = next(c for c in o.chances if c.month == "2021-06")
    assert june.protected_gained == 2 and june.per_unit > 1000
    assert o.saving_if_capped > june.saving           # both months together save more


def test_no_protection_claim_when_an_earlier_month_already_lost_it():
    """Jul-2020 (203 units) is the last forecast month: holding it at 200 changes no later
    month inside the window, so it must not be sold as 'keeps protected rates'."""
    o = outlook(bill("iesco-2019-07"))
    july = next(c for c in o.chances if c.month == "2020-07")
    assert july.protected_gained == 0 and not july.keeps_protection
    text = " ".join(summarize_outlook(o, "en"))
    assert "July 2020: about 203 units, 3 over the 200-unit slab edge" in text


def test_heavy_user_gets_slab_edges_not_protection_advice():
    o = outlook(bill("iesco-2023-03"))
    lines = summarize_outlook(o, "en")
    assert any("out of reach" in ln for ln in lines)
    assert not any(c.keeps_protection for c in o.chances)
    assert {c.edge for c in o.chances} <= {300, 400, 500}


def test_solar_bills_are_not_forecast_here():
    with pytest.raises(NotSupported, match="solar"):
        outlook(bill("pesco-2026-09"))


@pytest.mark.parametrize("bid", ["iesco-2019-07", "iesco-2021-01", "iesco-2023-03"])
@pytest.mark.parametrize("lang", ["ur", "en"])
def test_every_number_in_the_summary_comes_from_the_outlook(bid, lang):
    o = outlook(bill(bid))
    allowed = {rs(o.total), rs(o.saving_if_capped), 12, 200, 6}
    for c in o.chances:
        allowed |= {c.units, c.edge, c.over, rs(c.saving), rs(c.per_unit), c.protected_gained}
    for m in o.months:
        allowed |= {int(m.month[:4])}
    text = " ".join(summarize_outlook(o, lang))
    found = {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text)}
    assert found <= allowed, found - allowed


# --- the eval -------------------------------------------------------------------------
def test_backtest_scores_a_later_bill_of_the_same_household():
    early = bill("iesco-2021-01")
    fc = {f.month: f.units for f in forecast_units(monthly_units(early), "2021-01")}
    later_hist = [HistoryEntry(month=m, units=Decimal(u + 10), bill=0) for m, u in fc.items()
                  if m < "2022-01"]
    lc = early.legacy_charges.model_copy(update={"units_consumed": fc["2022-01"] + 10})
    late = early.model_copy(update={"bill_id": "later", "bill_month": "2022-01",
                                    "history": later_hist, "legacy_charges": lc})
    rep = backtest([early, late])
    assert rep["n"] == 12 and rep["mae_units"] == 10


def test_backtest_ignores_different_households():
    bills = [bill(b) for b in ("iesco-2019-07", "iesco-2021-01", "iesco-2023-03")]
    assert backtest(bills)["n"] == 0


def test_households_have_different_seasons():
    """The evidence for own-history forecasting: two summer peakers, one winter peaker."""
    se = profiles([bill(b) for b in ("iesco-2019-07", "iesco-2021-01", "iesco-2023-03")])
    corr = se["correlation"]
    assert corr["iesco-web-a vs iesco-web-b"] > 0.8
    assert corr["iesco-web-a vs iesco-web-c"] < 0 and corr["iesco-web-b vs iesco-web-c"] < 0


def test_forecast_prices_months_with_the_audited_engine():
    rows = engine_consistency([bill(b) for b in ("iesco-2019-07", "iesco-2021-01",
                                                 "iesco-2023-03")])
    assert len(rows) == 3 and all(r.get("ok") for r in rows)


def test_urdu_uses_singular_for_one_month():
    """'مزید 1 مہینے' read wrong; one month is 'مہینہ'."""
    lines = summarize_outlook(outlook(bill("iesco-2021-01")), "ur")
    sept = next(ln for ln in lines if ln.startswith("ستمبر"))
    assert "مزید 1 مہینہ" in sept and "مزید 1 مہینے" not in sept
