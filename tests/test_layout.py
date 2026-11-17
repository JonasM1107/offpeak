"""Where components stand on the site (offpeak/layout.py, the "Edit site" designer)."""

import pytest

from offpeak import components as C
from offpeak import layout as L


def placed(kind, col, row, name=None):
    return L.with_position(C.new_component(kind, name or kind), col, row)


def test_the_grid_has_room_and_keeps_fixed_things_free():
    ground = set(L.ground_squares())
    assert len(ground) > 40
    for _, squares in L.FIXED.values():
        assert not ground & set(squares)  # hall, grid connection and road are not ground
    assert (0, 0) not in ground  # a corner is outside the round fence
    assert (4, 4) in ground and (5, 4) not in ground  # the centre is free, the hall is not


def test_a_part_fits_on_a_free_square_only():
    site = [placed("battery", 3, 5)]
    assert L.why_not(site, "heat_pump", 3, 6) is None
    assert L.why_not(site, "heat_pump", 3, 5) == "Something already stands there."
    assert L.why_not(site, "heat_pump", 5, 3) == "That square belongs to the production hall."
    assert L.why_not(site, "heat_pump", 0, 0) == "That is outside the fence."
    assert L.why_not(site, "heat_pump", -1, 4) == "That is outside the fence."
    assert "roof" in L.why_not(site, "pv_roof", 3, 6)


def test_a_solar_field_needs_two_squares_side_by_side():
    assert L.squares("pv_field", 1, 2) == {(1, 2), (2, 2)}
    site = [placed("battery", 2, 2)]
    assert L.why_not(site, "pv_field", 1, 2) == "Something already stands there."
    assert L.why_not([], "pv_field", 4, 6) is None
    assert L.why_not([], "pv_field", 4, 3) == "That square belongs to the production hall."


def test_moving_a_part_onto_its_own_square_is_fine():
    battery = placed("battery", 3, 5)
    assert L.why_not([battery], "battery", 3, 5, ignore=battery.id) is None


def test_auto_place_gives_the_demo_site_its_usual_spots_without_overlap():
    site = L.auto_place(C.DEFAULT_COMPONENTS)
    assert L.layout_problems(site) == []
    ground = [c for c in site if c.kind not in L.ON_ROOF]
    assert all(L.position(c) is not None for c in ground)
    roof = next(c for c in site if c.kind == "pv_roof")
    assert L.position(roof) is None  # it goes on the hall roof
    battery = next(c for c in site if c.kind == "battery")
    assert L.position(battery) == L.PREFERRED["battery"][0]


def test_auto_place_moves_a_part_whose_stored_square_is_taken_or_broken():
    first, clash = placed("battery", 3, 5, "A"), placed("heat_pump", 3, 5, "B")
    broken = C.new_component("cold_store", "C", {"col": "x", "row": 2})
    site = L.auto_place([first, clash, broken])
    assert L.position(site[0]) == (3, 5)
    assert L.position(site[1]) not in (None, (3, 5))
    assert L.position(site[2]) is not None
    assert L.layout_problems(site) == []


def test_layout_problems_name_what_is_wrong():
    site = [
        placed("battery", 3, 5, "Battery"),
        placed("heat_pump", 3, 5, "Heat pump"),
        placed("cold_store", 5, 3, "Cold store"),
        C.new_component("wind", "Turbine", {"col": 2.5, "row": 3}),
    ]
    assert L.layout_problems(site) == [
        "Heat pump: Something already stands there.",
        "Cold store: That square belongs to the production hall.",
        "Turbine: its place on the site is not a valid square",
    ]


def test_world_positions_match_the_3d_island():
    site = [placed("battery", 4, 4 + 2), placed("pv_field", 1, 2), C.new_component("pv_roof", "R")]
    pos = L.world_positions(site)
    assert pos[site[0].id] == (0.0, 24.0)  # 2 squares south of the centre
    assert pos[site[1].id] == (-30.0, -24.0)  # the middle of its two squares
    assert site[2].id not in pos  # on the roof, drawn by the 3D view itself


# ── Actions from the designer ───────────────────────────────────────────────


def test_add_on_a_free_square_and_by_tapping():
    site, picked, problem = L.apply([], {"action": "add", "kind": "battery", "col": 3, "row": 5})
    assert problem is None and picked == site[0].id and L.position(site[0]) == (3, 5)
    site, picked, problem = L.apply(site, {"action": "add", "kind": "battery"})  # a tap
    assert problem is None and site[1].name == "Battery storage 2"
    assert L.position(site[1]) not in (None, (3, 5))


def test_adding_where_it_cannot_go_changes_nothing():
    site = [placed("battery", 3, 5)]
    for event, why in [
        ({"action": "add", "kind": "heat_pump", "col": 3, "row": 5}, "already stands"),
        ({"action": "add", "kind": "heat_pump", "col": 5, "row": 3}, "production hall"),
        ({"action": "add", "kind": "pv_roof", "target": "ground"}, "roof"),
        ({"action": "add", "kind": "nuclear_plant", "col": 3, "row": 6}, "Unknown"),
    ]:
        after, _, problem = L.apply(site, event)
        assert after == site and why in problem


def test_rooftop_solar_goes_on_the_hall():
    site, _, problem = L.apply([], {"action": "add", "kind": "pv_roof", "target": "hall"})
    assert problem is None and site[0].kind == "pv_roof" and L.position(site[0]) is None


def test_a_full_site_takes_no_more_parts():
    full = [C.new_component("ev_charger", f"EV {i}") for i in range(C.MAX_COMPONENTS)]
    after, _, problem = L.apply(full, {"action": "add", "kind": "battery"})
    assert after == full and "at most 20" in problem


def test_move_remove_and_select():
    battery, pump = placed("battery", 3, 5), placed("heat_pump", 3, 6)
    site = [battery, pump]
    moved, picked, problem = L.apply(site, {"action": "move", "id": battery.id, "col": 2, "row": 5})
    assert problem is None and picked == battery.id and L.position(moved[0]) == (2, 5)
    blocked, _, problem = L.apply(site, {"action": "move", "id": battery.id, "col": 3, "row": 6})
    assert blocked == site and problem == "Something already stands there."
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
    site = [placed("battery", 3, 5)]
    after, _, _ = L.apply(site, event)
    assert after == site
