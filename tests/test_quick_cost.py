"""The planner's fast pricing (demo_site.QuickCost) gives the same euros as the full
simulate() + bill(), for every plan plan_day tries, under every kind of tariff."""

from datetime import date
from itertools import product

import pytest

from offpeak import components as C
from offpeak import demo_site as D
from offpeak.tariffs import germany_2026, portugal_bte_2026, tariff_for

TZ = "Europe/Berlin"
DAY = date(2026, 11, 18)


def day_inputs(comps, tariff, *, negative=False, sunny=False):
    assets, _ = C.site_model(comps)
    raw = D.hourly_inputs(None, None, TZ, assets)
    if negative:  # a spring Sunday: paid to use power around noon
        raw.loc[10:15, "price_ct"] = -3.0
    if sunny:  # more own power than the site uses, so the battery fills
        raw["pv_kw"] = raw["pv_kw"] * 4
    return D.apply_tariff(raw, tariff, DAY) if tariff is not None else raw


def every_plan(loads):
    """Every plan plan_day can try: each load at each allowed start, battery smart or not."""
    options = [range(f.earliest, f.latest_end - f.hours + 1) for f in loads]
    for starts, smart in product(product(*options), (False, True)):
        yield D.Plan(dict(zip([f.key for f in loads], starts, strict=True)), smart)


CASES = {
    "business": (C.DEFAULT_COMPONENTS, lambda c: germany_2026(pv_kwp=C.site_model(c)[0].pv_kwp)),
    "home with § 14a": (C.DEFAULT_HOME_COMPONENTS, lambda c: tariff_for("home", c)),
    "demand by period": (C.DEFAULT_COMPONENTS, lambda c: portugal_bte_2026()),
    "spot price only": (C.DEFAULT_COMPONENTS, lambda c: None),
}


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("negative,sunny", [(False, False), (True, False), (False, True)])
def test_quick_cost_matches_the_full_bill(case, negative, sunny):
    comps, make_tariff = CASES[case]
    tariff = make_tariff(comps)
    assets, loads = C.site_model(comps)
    inputs = day_inputs(comps, tariff, negative=negative, sunny=sunny)
    quick = D.QuickCost(inputs, tariff, assets, loads)
    plans = list(every_plan(loads))
    # every plan for the small homes; a spread sample for the business (thousands of plans)
    for plan in plans[:: max(1, len(plans) // 300)]:
        assert quick(plan) == pytest.approx(D.cost(inputs, plan, tariff, assets, loads), abs=1e-9)


def test_quick_cost_keeps_the_grid_profile_of_simulate():
    comps = C.DEFAULT_COMPONENTS
    tariff = germany_2026(pv_kwp=C.site_model(comps)[0].pv_kwp)
    assets, loads = C.site_model(comps)
    inputs = day_inputs(comps, tariff, sunny=True)
    plan = D.usual_plan(loads)
    full = D.simulate(inputs, plan, assets, loads)["grid_kw"].tolist()
    assert D.QuickCost(inputs, tariff, assets, loads).grid(plan) == pytest.approx(full)


def test_an_unknown_demand_basis_is_refused():
    comps = C.DEFAULT_COMPONENTS
    tariff = germany_2026(pv_kwp=C.site_model(comps)[0].pv_kwp)
    broken = tariff.__class__(
        **{
            **tariff.__dict__,
            "demand": [tariff.demand[0].__class__(**{**tariff.demand[0].__dict__, "basis": "x"})],
        }
    )
    assets, loads = C.site_model(comps)
    inputs = day_inputs(comps, tariff)
    with pytest.raises(ValueError, match="unknown demand basis"):
        D.QuickCost(inputs, broken, assets, loads)(D.usual_plan(loads))


def old_plan_day(inputs, tariff, assets, loads):
    """plan_day as it was before QuickCost: the same search, every plan priced with the
    full simulate() + bill()."""
    usual = D.usual_plan(loads)
    best = usual

    def price(p):
        return D.cost(inputs, p, tariff, assets, loads)

    for smart in (False, True):
        starts = dict(usual.starts)
        for f in sorted(loads, key=lambda f: -f.kw):
            options = range(f.earliest, f.latest_end - f.hours + 1)
            starts[f.key] = min(options, key=lambda s: price(D.Plan({**starts, f.key: s}, smart)))
        candidate = D.Plan(starts, smart)
        if price(candidate) < price(best):
            best = candidate
    return best


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("negative,sunny", [(False, False), (True, False), (False, True)])
def test_the_planned_day_costs_the_same_as_before(case, negative, sunny):
    comps, make_tariff = CASES[case]
    tariff = make_tariff(comps)
    assets, loads = C.site_model(comps)
    inputs = day_inputs(comps, tariff, negative=negative, sunny=sunny)
    new, old = (
        D.plan_day(inputs, tariff, assets, loads),
        old_plan_day(inputs, tariff, assets, loads),
    )
    # the same bill; where two starts cost exactly the same, the old search picked one by a
    # rounding remainder in the 15th digit, the new one takes the earlier start
    assert D.cost(inputs, new, tariff, assets, loads) == pytest.approx(
        D.cost(inputs, old, tariff, assets, loads), abs=1e-9
    )
