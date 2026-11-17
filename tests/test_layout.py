"""Where components stand on the site (offpeak/layout.py, the "Edit site" designer):
a 64 x 64 grid over the island, every part a rectangle as big as its 3D model."""

import pytest

from offpeak import components as C
from offpeak import layout as L


def at(kind, x, z, name=None, **params):
    """A component whose centre stands on the square under x, z (metres east, south)."""
    return L.with_position(C.new_component(kind, name or kind, params), *L.square_at(x, z))


def test_the_grid_covers_the_island_in_64_squares():
    assert L.GRID == 64 and L.CELL_M == pytest.approx(1.875)
    assert L.square_at(0, 0) == (32, 32)
    assert L.square_at(-60, -60) == (0, 0) and L.square_at(59.9, 59.9) == (63, 63)
    assert L.centre(32, 32) == pytest.approx((0.9375, 0.9375), abs=0.001)


def test_footprints_grow_with_the_part():
    small, big = (
        C.new_component("pv_field", "S", {"kwp": 10}),
        C.new_component("pv_field", "B", {"kwp": 60}),
    )
    assert L.footprint(big)[3] - L.footprint(big)[2] > L.footprint(small)[3] - L.footprint(small)[2]
    one, four = (
        C.new_component("battery", "1", {"kwh": 100}),
        C.new_component("battery", "4", {"kwh": 2000}),
    )
    assert L.footprint(four)[3] > L.footprint(one)[3]  # more containers, one behind the other
    few, many = (
        C.new_component("ev_charger", "3", {"count": 3}),
        C.new_component("ev_charger", "8", {"count": 8}),
    )
    assert L.footprint(many)[1] > L.footprint(few)[1]


def test_a_part_fits_on_free_ground_only():
    battery = at("battery", -14, 20, "Battery")
    pump = C.new_component("heat_pump", "Pump")
    assert L.why_not([battery], pump, *L.square_at(-30, 0)) is None
    assert L.why_not([battery], pump, *L.square_at(-14, 20)) == "That is on the Battery."
    assert L.why_not([battery], pump, *L.square_at(18, -8)) == "That is on the production hall."
    assert L.why_not([battery], pump, *L.square_at(-4, 0)) == "That is on the site meter."
    assert L.why_not([battery], pump, *L.square_at(-57, 0)) == "That is too close to the fence."
    assert L.why_not([battery], pump, 64, 3) == "That is outside the fence."
    assert "roof" in L.why_not([], C.new_component("pv_roof", "R"), 30, 30)


def test_moving_a_part_onto_its_own_place_is_fine():
    battery = at("battery", -14, 20)
    assert L.why_not([battery], battery, *L.position(battery), ignore=battery.id) is None


def test_auto_place_gives_the_demo_site_its_usual_spots_without_overlap():
    site = L.auto_place(C.DEFAULT_COMPONENTS)
    assert L.layout_problems(site) == []
    assert all(L.position(c) is not None for c in site if c.kind not in L.ON_ROOF)
    roof = next(c for c in site if c.kind == "pv_roof")
    assert L.position(roof) is None  # it goes on the hall roof
    battery = next(c for c in site if c.kind == "battery")
    assert L.position(battery) == L.square_at(*L.PREFERRED["battery"][0])


def test_auto_place_moves_a_part_whose_stored_square_is_taken_or_broken():
    first, clash = at("battery", -14, 20, "A"), at("heat_pump", -14, 20, "B")
    broken = C.new_component("cold_store", "C", {"col": "x", "row": 2})
    site = L.auto_place([first, clash, broken])
    assert L.position(site[0]) == L.position(first)
    assert L.position(site[1]) not in (None, L.position(first))
    assert L.position(site[2]) is not None
    assert L.layout_problems(site) == []


def test_a_crowded_site_places_what_fits_and_leaves_the_rest_off_the_plan():
    crowd = [C.new_component("ev_charger", f"E{i}", {"count": 8}) for i in range(20)]
    site = L.auto_place(crowd)
    placed = [c for c in site if L.position(c) is not None]
    assert 0 < len(placed) < 20 and L.layout_problems(site) == []


def test_layout_problems_name_what_is_wrong():
    site = [
        at("battery", -14, 20, "Battery"),
        at("heat_pump", -14, 20, "Heat pump"),
        at("cold_store", 18, -8, "Cold store"),
        C.new_component("wind", "Turbine", {"col": 2.5, "row": 3}),
    ]
    assert L.layout_problems(site) == [
        "Heat pump: That is on the Battery.",
        "Cold store: That is on the production hall.",
        "Turbine: its place on the site is not a valid square",
    ]


def test_a_part_that_grew_into_its_neighbour_is_found():
    field = at("pv_field", -26, -18, "Field", kwp=10)
    pump = at("heat_pump", -26, -8, "Pump")
    assert L.layout_problems([field, pump]) == []
    grown = L.with_position(C.new_component("pv_field", "Field", {"kwp": 70}), *L.position(field))
    assert L.layout_problems([grown, pump]) == ["Pump: That is on the Field."]


def test_world_positions_are_the_centre_of_the_square():
    site = [at("battery", -14, 20), C.new_component("pv_roof", "R")]
    pos = L.world_positions(site)
    assert pos[site[0].id] == L.centre(*L.square_at(-14, 20))
    assert site[1].id not in pos  # on the roof, drawn by the 3D view itself


# ── Actions from the designer ───────────────────────────────────────────────


def test_add_on_free_ground_and_by_tapping():
    col, row = L.square_at(-14, 20)
    site, picked, problem = L.apply(
        [], {"action": "add", "kind": "battery", "col": col, "row": row}
    )
    assert problem is None and picked == site[0].id and L.position(site[0]) == (col, row)
    site, picked, problem = L.apply(site, {"action": "add", "kind": "battery"})  # a tap
    assert problem is None and site[1].name == "Battery storage 2"
    assert L.position(site[1]) is not None and L.layout_problems(site) == []


def test_adding_where_it_cannot_go_changes_nothing():
    site = [at("battery", -14, 20, "Battery")]
    hall, battery = L.square_at(18, -8), L.square_at(-14, 20)
    for event, why in [
        ({"action": "add", "kind": "heat_pump", "col": battery[0], "row": battery[1]}, "Battery"),
        ({"action": "add", "kind": "heat_pump", "col": hall[0], "row": hall[1]}, "production hall"),
        ({"action": "add", "kind": "pv_roof", "target": "ground"}, "roof"),
        ({"action": "add", "kind": "nuclear_plant", "col": 3, "row": 6}, "Unknown"),
    ]:
        after, _, problem = L.apply(site, event)
        assert after == site and why in problem


def test_rooftop_solar_goes_on_the_hall():
    site, _, problem = L.apply([], {"action": "add", "kind": "pv_roof", "target": "hall"})
    assert problem is None and site[0].kind == "pv_roof" and L.position(site[0]) is None


def test_a_full_site_takes_no_more_parts():
    full = [C.new_component("cold_store", f"Store {i}") for i in range(C.MAX_COMPONENTS)]
    after, _, problem = L.apply(full, {"action": "add", "kind": "battery"})
    assert after == full and "at most 20" in problem


def test_move_remove_and_select():
    battery, pump = at("battery", -14, 20, "Battery"), at("heat_pump", -30, 0, "Pump")
    site = [battery, pump]
    col, row = L.square_at(-14, 40)
    moved, picked, problem = L.apply(
        site, {"action": "move", "id": battery.id, "col": col, "row": row}
    )
    assert problem is None and picked == battery.id and L.position(moved[0]) == (col, row)
    col, row = L.square_at(-30, 0)
    blocked, _, problem = L.apply(
        site, {"action": "move", "id": battery.id, "col": col, "row": row}
    )
    assert blocked == site and problem == "That is on the Pump."
    gone, picked, _ = L.apply(site, {"action": "remove", "id": pump.id})
    assert gone == [battery] and picked is None
    same, picked, _ = L.apply(site, {"action": "select", "id": pump.id})
    assert same == site and picked == pump.id


@pytest.mark.parametrize(
    "event",
    [
        {"action": "move", "id": "nobody", "col": 1, "row": 1},
        {"action": "move", "col": "x", "row": None},
        {"action": "remove"},
        {"action": "explode", "id": "x"},
        {},
    ],
)
def test_odd_or_forged_actions_change_nothing(event):
    site = [at("battery", -14, 20)]
    after, _, _ = L.apply(site, event)
    assert after == site
