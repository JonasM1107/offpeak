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


# ── Editing a whole site ("Edit site" in the site view) ─────────────────────


def test_next_name_numbers_a_second_of_the_same_kind():
    assert C.next_name("heat_pump", []) == "Heat pump"
    site = [C.new_component("heat_pump", "heat pump")]  # taken, whatever the capitals
    assert C.next_name("heat_pump", site) == "Heat pump 2"
    site.append(C.new_component("heat_pump", "Heat pump 2"))
    assert C.next_name("heat_pump", site) == "Heat pump 3"


def test_validate_site_accepts_the_demo_site_and_a_single_component():
    assert C.validate_site(C.DEFAULT_COMPONENTS) == []
    assert C.validate_site([C.new_component("pv_roof", "Roof")]) == []


def test_validate_site_rejects_an_empty_site():
    # an empty list in the database would show the demo site again
    assert C.validate_site([]) == ["Add at least one component before saving"]


def test_validate_site_rejects_missing_long_and_duplicate_names():
    site = [
        C.new_component("pv_roof", "  "),
        C.new_component("battery", "x" * (C.MAX_NAME + 1)),
        C.new_component("heat_pump", "Heat pump"),
        C.new_component("heat_pump", "HEAT PUMP "),
    ]
    problems = C.validate_site(site)
    assert "Component 1 (Rooftop solar) needs a name" in problems
    assert any("at most 60 characters" in p for p in problems)
    assert "HEAT PUMP: two components have this name" in problems
    assert len(problems) == 3


def test_validate_site_rejects_bad_values_and_unknown_kinds():
    too_big = C.new_component("pv_field", "Field", {"kwp": 1_000_000})
    impossible = C.new_component("furnace", "Oven", {"hours": 10, "earliest": 8, "latest_end": 12})
    not_a_number = C.new_component("wind", "Turbine", {"kw": "lots"})
    unknown = C.Component("x", "nuclear_plant", "Reactor", {})
    problems = C.validate_site([too_big, impossible, not_a_number, unknown])
    assert "Field: Peak power must be between 1 and 2000 kWp" in problems
    assert "Oven: The allowed hours are shorter than the run time" in problems
    assert "Turbine: every size and hour must be a number" in problems
    assert "Reactor: unknown type" in problems


def test_validate_site_limits_the_number_of_components():
    full = [C.new_component("ev_charger", f"Charger {i}") for i in range(C.MAX_COMPONENTS)]
    assert C.validate_site(full) == []  # exactly at the limit is fine
    one_more = full + [C.new_component("ev_charger", "One too many")]
    assert C.validate_site(one_more) == ["A site can have at most 20 components"]
