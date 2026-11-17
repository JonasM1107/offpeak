"""Where each component stands on the site: the grid of the "Edit site" layout designer.

The island in the 3D site view is a circle 120 m across. We lay a grid of 64 x 64 squares
over it (1.875 m each). A component's place is the square its centre stands on, kept in its
params as "col" and "row" (0..63; col goes east, row goes south). The 3D view draws it there.
A component without a square (the demo site, or one added on the Site & components page)
gets the automatic spot it always had.

On the ground every component is a rectangle in metres, as big as its 3D model really is:
a solar field grows with its peak power (more rows of modules), a battery with its
capacity (more containers), the EV chargers with their number. The sizes follow the
builders in app/ui/site_scene.html. A rectangle must stay inside the fence and must not
overlap another one, the production hall, the grid connection, the site meter or the road.
Rooftop solar goes on the hall roof and needs no ground.

Everything here is plain Python, so the rules can be tested without a browser.
"""

from math import ceil, floor, hypot

from offpeak import components as C

SIZE_M = 120  # the grid covers the island: 120 m x 120 m, centred on the site meter
GRID = 64  # squares per side
CELL_M = SIZE_M / GRID  # 1.875 m
FENCE_M = 57.5  # every corner of a component stays this close to the centre (fence: 58.5 m)
ON_ROOF = {"pv_roof"}  # placed on the hall roof, not on the ground

# A rectangle is (west, east, north, south) in metres: x from west to east, z from north to
# south, like the 3D view.
Rect = tuple[float, float, float, float]

# Fixed things on the island (measured from the 3D models), as rectangles on the island.
FIXED: dict[str, tuple[str, Rect]] = {
    "hall": ("Production hall", (6.7, 29.3, -16.4, 1.2)),
    "grid": ("Grid connection", (-7.6, 8.1, -42.2, -29.3)),
    "meter": ("Site meter", (-2.5, 2.5, -2.5, 2.5)),
    "road": ("Road", (22.5, 29.5, 35.0, 57.0)),
}

# Where each kind stood before there was a designer (metres east, south): tried first, so
# the demo site keeps its look when someone starts editing it.
PREFERRED: dict[str, tuple[tuple[float, float], ...]] = {
    "pv_field": ((-26, -18), (-30, -40), (-44, -16), (30, -40)),
    "wind": ((-44, 12), (-34, 32), (-50, -4), (-18, 46), (46, -36)),
    "battery": ((-14, 18), (-22, 34)),
    "heat_pump": ((2, -16), (-6, -26)),
    "ev_charger": ((12, 26), (34, 30)),
    "cold_store": ((42, 14), (44, -4)),
    "furnace": ((33.5, -8),),
}


def _count(value: float, per: float, extra: float, most: int, least: int = 1) -> int:
    """How many units the 3D view draws (containers, heat pump units): the same rounding
    as the builders in site_scene.html (JavaScript's Math.round rounds .5 up)."""
    return max(least, min(most, floor(value / per + extra + 0.5)))


def footprint(c: C.Component) -> Rect:
    """The ground a component covers, around its own centre (west, east, north, south)."""
    k = c.kind
    if k in ("pv_field", "pv_roof"):  # rows of racks, 24 modules each, at most 168 modules
        modules = max(4, min(168, floor(c.p("kwp") / 0.42 + 0.5)))
        rows = ceil(modules / 24)
        return (-12.5, 13.9, -2.1 * rows - 1.7, 2.1 * rows + 0.3)
    if k == "wind":  # the tower's base and the rotor's reach
        return (-6.5, 8.6, -2.6, 3.5)
    if k == "battery":  # containers one behind the other
        n = _count(c.p("kwh"), 250, 0.4, 4)
        return (-7.5, 7.5, -2.8, (n - 1) * 3.6 + 2.8)
    if k == "heat_pump":  # units side by side, buffer tank at the end
        n = _count(c.p("kw"), 10, 0.4, 4)
        return (-2.0, n * 2.8 + 4.1, -2.2, 2.2)
    if k == "ev_charger":  # a row of car bays and the truck bay
        n = max(1, min(8, floor(c.p("count") + 0.5)))
        return (-3.2, n * 4.2 + 8.4, -5.2, 8.8)
    if k == "furnace":
        return (-4.4, 4.8, -4.8, 6.1)
    if k == "cold_store":
        return (-6.2, 7.8, -4.7, 6.1)
    return (-3.0, 3.0, -3.0, 3.0)


def centre(col: int, row: int) -> tuple[float, float]:
    """The middle of a square, in metres east and south of the island's centre."""
    return (
        round(-SIZE_M / 2 + (col + 0.5) * CELL_M, 3),
        round(-SIZE_M / 2 + (row + 0.5) * CELL_M, 3),
    )


def square_at(x: float, z: float) -> tuple[int, int]:
    """The square under a point given in metres."""
    return floor((x + SIZE_M / 2) / CELL_M), floor((z + SIZE_M / 2) / CELL_M)


def rect_at(c: C.Component, col: int, row: int) -> Rect:
    """The component's rectangle on the island when its centre stands on col, row."""
    x, z = centre(col, row)
    w, e, n, s = footprint(c)
    return (x + w, x + e, z + n, z + s)


def overlap(a: Rect, b: Rect) -> bool:
    """True when two rectangles share ground (touching edges are fine)."""
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def inside_fence(r: Rect) -> bool:
    return all(hypot(x, z) <= FENCE_M for x in r[:2] for z in r[2:])


def position(c: C.Component) -> tuple[int, int] | None:
    """The component's square, or None if it has none (or something unusable is stored)."""
    col, row = c.params.get("col"), c.params.get("row")
    if col is None or row is None:
        return None
    try:
        col, row = float(col), float(row)
    except (TypeError, ValueError):
        return None
    if col % 1 or row % 1 or not (0 <= col < GRID and 0 <= row < GRID):
        return None
    return int(col), int(row)


def why_not(site, c: C.Component, col: int, row: int, ignore: str | None = None) -> str | None:
    """Why component `c` cannot stand with its centre on col, row (None = it can). `ignore`
    is the component being moved, so it does not block itself."""
    if c.kind in ON_ROOF:
        return "Rooftop solar goes on the roof of the production hall."
    if not (0 <= col < GRID and 0 <= row < GRID):
        return "That is outside the fence."
    r = rect_at(c, col, row)
    if not inside_fence(r):
        return "That is too close to the fence."
    for label, fixed in FIXED.values():
        if overlap(r, fixed):
            return f"That is on the {label.lower()}."
    for other in site:
        pos = position(other)
        if other.id in (ignore, c.id) or pos is None or other.kind in ON_ROOF:
            continue
        if overlap(r, rect_at(other, *pos)):
            return f"That is on the {other.name}."
    return None


def free_spot(site, c: C.Component) -> tuple[int, int] | None:
    """A free square for a component: its old spots first, then the nearest free one."""
    preferred = [square_at(x, z) for x, z in PREFERRED.get(c.kind, ())]
    start = preferred[0] if preferred else (GRID // 2, GRID // 2 + 8)
    rest = sorted(
        ((col, row) for col in range(GRID) for row in range(GRID)),
        key=lambda sq: hypot(sq[0] - start[0], sq[1] - start[1]),
    )
    for col, row in [*preferred, *rest]:
        if why_not(site, c, col, row) is None:
            return col, row
    return None


def with_position(c: C.Component, col: int, row: int) -> C.Component:
    return C.Component(c.id, c.kind, c.name, {**c.params, "col": col, "row": row})


def without_position(c: C.Component) -> C.Component:
    params = {k: v for k, v in c.params.items() if k not in ("col", "row")}
    return C.Component(c.id, c.kind, c.name, params)


def auto_place(site) -> list[C.Component]:
    """The same site, with a square for every ground component that has none (or one where
    it does not fit). Components that cannot fit anywhere keep no square; the 3D view then
    finds them a spot of its own and the designer says they are not on the plan."""
    placed: list[C.Component] = []
    for c in site:
        pos = position(c)
        if c.kind in ON_ROOF or (pos and why_not(placed, c, *pos) is None):
            placed.append(c)
            continue
        bare = without_position(c)
        spot = free_spot(placed, bare)
        placed.append(with_position(bare, *spot) if spot else bare)
    return placed


def layout_problems(site) -> list[str]:
    """What is wrong with where things stand, in plain words (empty list = fine). A part
    that grew (more kWp, more chargers) can reach into its neighbour: that shows up here."""
    problems = []
    placed: list[C.Component] = []
    for c in site:
        if c.kind in ON_ROOF:
            continue
        pos = position(c)
        if pos is None:
            if "col" in c.params or "row" in c.params:
                problems.append(f"{c.name}: its place on the site is not a valid square")
            continue
        reason = why_not(placed, c, *pos)
        if reason:
            problems.append(f"{c.name}: {reason}")
        else:
            placed.append(c)
    return problems


def world_positions(site) -> dict[str, tuple[float, float]]:
    """3D position (metres east, south) of every ground component that has a square."""
    out = {}
    for c in site:
        pos = position(c)
        if pos is not None and c.kind not in ON_ROOF:
            out[c.id] = centre(*pos)
    return out


# ── What the designer did: one action at a time ─────────────────────────────


def apply(site, event: dict) -> tuple[list[C.Component], str | None, str | None]:
    """Apply one action from the layout designer to the draft site.

    Returns the new site, the component to select, and a problem to show (None if fine).
    Everything the browser sends is checked here like user input: unknown kinds, ids and
    squares are refused, and the draft is never changed by a refused action."""
    site = list(site)
    action = event.get("action")
    by_id = {c.id: c for c in site}

    def square() -> tuple[int, int] | None:
        try:
            return int(event["col"]), int(event["row"])
        except (KeyError, TypeError, ValueError):
            return None

    if action == "add":
        kind = event.get("kind")
        if kind not in C.CATALOGUE:
            return site, None, "Unknown component type."
        if len(site) >= C.MAX_COMPONENTS:
            return site, None, f"A site can have at most {C.MAX_COMPONENTS} components."
        new = C.new_component(kind, C.next_name(kind, site))
        if kind in ON_ROOF:
            if event.get("target") not in (None, "hall"):
                return site, None, why_not(site, new, 0, 0)
            return [*site, new], new.id, None
        spot = square() or free_spot(site, new)
        if spot is None:
            return site, None, "There is no free space left for this."
        reason = why_not(site, new, *spot)
        if reason:
            return site, None, reason
        new = with_position(new, *spot)
        return [*site, new], new.id, None

    c = by_id.get(event.get("id"))
    if c is None:
        return site, None, None  # e.g. a double click on something just removed
    if action == "move":
        spot = square()
        if spot is None or c.kind in ON_ROOF:
            return site, c.id, None
        reason = why_not(site, c, *spot, ignore=c.id)
        if reason:
            return site, c.id, reason
        return [with_position(x, *spot) if x.id == c.id else x for x in site], c.id, None
    if action == "remove":
        return [x for x in site if x.id != c.id], None, None
    if action == "select":
        return site, c.id, None
    return site, None, None
