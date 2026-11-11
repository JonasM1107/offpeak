import pandas as pd
import pytest

from offpeak import components as C
from offpeak import demo_site

TZ = "Europe/Berlin"


@pytest.fixture
def day():
    assets, _ = C.site_model(C.DEFAULT_COMPONENTS)
    inputs = demo_site.hourly_inputs(None, None, TZ, assets)
    return C.site_day(inputs, C.DEFAULT_COMPONENTS)


def test_site_model_sums_assets_and_lists_flexible_loads():
    assets, loads = C.site_model(C.DEFAULT_COMPONENTS)
    assert assets.pv_kwp == 60  # field 40 + roof 20
    assert assets.turbine_kw == 30  # two 15 kW turbines
    assert {f.key for f in loads} == {"heat-pump", "furnace", "ev"}
    assert next(f for f in loads if f.key == "ev").kw == 30  # 3 chargers x 10 kW


def test_component_series_add_up_to_the_site(day):
    rows = pd.DataFrame(day["rows"]["offpeak"])
    s = day["series"]["offpeak"]
    pv = pd.Series(s["pv-field"]) + pd.Series(s["pv-roof"])
    assert (pv - rows["pv_kw"]).abs().max() < 0.01
    assert (pd.Series(s["wind-1"]) + pd.Series(s["wind-2"]) - rows["wind_kw"]).abs().max() < 0.01


def test_every_flexible_load_runs_its_hours_inside_its_window(day):
    for c in C.DEFAULT_COMPONENTS:
        if c.spec.role != "flexible":
            continue
        kw = day["series"]["offpeak"][c.id]
        hours = [h for h, v in enumerate(kw) if v > 0]
        assert len(hours) == c.p("hours")
        assert c.p("earliest") <= hours[0] and hours[-1] < c.p("latest_end")


def test_plan_is_not_more_expensive_than_usual(day):
    total = {name: sum(r["cost_eur"] for r in rows) for name, rows in day["rows"].items()}
    assert total["offpeak"] <= total["usual"] + 1e-9


def test_parts_and_materials_add_up():
    pv = C.Component("x", "pv_field", "PV", {"kwp": 42})
    part_list = C.parts(pv)
    assert next(p for p in part_list if p.key == "modules").qty == 100  # 42 kWp / 420 W
    mats = C.materials(part_list)
    assert sum(m[1] for m in mats) == pytest.approx(
        sum(sum(p.materials.values()) for p in part_list), abs=0.5
    )
    assert mats[0][0] == "Glass"  # glass is the heaviest material of a solar field


@pytest.mark.parametrize("kind", list(C.CATALOGUE))
def test_every_kind_has_parts_facts_and_works_in_the_model(kind):
    c = C.new_component(kind, "New")
    assert C.parts(c) and C.facts(c)
    assets, loads = C.site_model([c])
    inputs = demo_site.hourly_inputs(None, None, TZ, assets)
    result = C.site_day(inputs, [c])
    assert len(result["series"]["offpeak"][c.id]) == 24


def test_validate_explains_problems():
    assert C.validate("pv_field", {"kwp": 40}) == []
    assert C.validate("pv_field", {"kwp": 0}) == ["Peak power must be between 1 and 2000 kWp"]
    problems = C.validate(
        "heat_pump", {"kw": 8, "hours": 6, "earliest": 20, "latest_end": 24, "usual_start": 20}
    )
    assert "The allowed hours are shorter than the run time" in problems


def test_hour_ranges_and_price_classes():
    assert C.hour_ranges([False, True, True, False, True]) == "01–03, 04–05"
    classes = C.price_classes(list(range(24)))
    assert classes[:8] == ["cheap"] * 8 and classes[-8:] == ["dear"] * 8


def test_advice_for_a_flexible_load(day):
    hp = next(c for c in day["components"] if c["id"] == "heat-pump")
    assert hp["advice"]["best"] and hp["advice"]["usual"] == "05–11"
    assert hp["analytics"]["offpeak"]["energy_kwh"] == 48  # 8 kW x 6 h
