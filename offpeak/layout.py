"""Where each component stands on the site: the grid of the "Edit site" layout designer.

The island in the 3D site view is a circle about 120 m across. We lay a 9 × 9 grid of
12 m squares over it (like the tiles of a city builder). A component on the grid has its
square in its params, as "col" and "row" (0..8, col goes east, row goes south); the 3D view
then draws it there. A component without a square (the demo site, or one added on the
Site & components page) gets the automatic spot it always had.

Some squares are taken by fixed things: the production hall (2 × 2), the grid connection
and the road. Squares near the edge are outside the fence. A solar field needs two squares
side by side; rooftop solar goes on the hall roof and needs no square.

Everything here is plain Python, so the rules can be tested without a browser.
"""

from math import hypot

from offpeak import components as C

GRID = 9  # squares per side
CELL_M = 12  # metres per square in the 3D view
CENTRE = (GRID - 1) / 2
FENCE_M = 50  # a square's centre must be at most this far from the island's centre

# fixed things on the island, with the squares they cover (see site_scene.html)
FIXED = {
    "hall": ("Production hall", ((5, 3), (6, 3), (5, 4), (6, 4))),
    "grid": ("Grid connection", ((4, 1),)),
    "road": ("Road", ((6, 7),)),
}
FOOTPRINT = {"pv_field": (2, 1)}  # (squares east-west, north-south); everything else 1 × 1
ON_ROOF = {"pv_roof"}  # placed on the hall roof, not on the ground

# Squares tried first for each kind when nothing was chosen: the spots the 3D view used
# before there was a designer, so the demo site looks the same.
PREFERRED = {
    "pv_field": ((1, 2), (1, 1), (0, 3), (6, 1)),
    "wind": ((0, 5), (1, 7), (0, 4), (2, 8), (8, 1)),
    "battery": ((3, 5), (2, 7)),
    "heat_pump": ((4, 3), (3, 2)),
    "ev_charger": ((5, 6), (7, 6)),
    "cold_store": ((7, 5), (8, 4)),
    "furnace": ((7, 3),),
}


def _fixed_squares() -> set[tuple[int, int]]:
    return {sq for _, squares in FIXED.values() for sq in squares}


def inside_fence(col: int, row: int) -> bool:
    return (
        0 <= col < GRID
        and 0 <= row < GRID
        and hypot(col - CENTRE, row - CENTRE) * CELL_M <= FENCE_M
    )


def ground_squares() -> list[tuple[int, int]]:
    """Every square a component may stand on: inside the fence and not taken by the hall,
    the grid connection or the road."""
    fixed = _fixed_squares()
    return [
        (c, r)
        for r in range(GRID)
        for c in range(GRID)
        if inside_fence(c, r) and (c, r) not in fixed
    ]


def footprint(kind: str) -> tuple[int, int]:
    return FOOTPRINT.get(kind, (1, 1))


def squares(kind: str, col: int, row: int) -> set[tuple[int, int]]:
    """The squares a component of this kind covers when its corner is at col, row."""
    w, h = footprint(kind)
    return {(col + dc, row + dr) for dc in range(w) for dr in range(h)}


def position(c: C.Component) -> tuple[int, int] | None:
    """The component's square, or None if it has none (or something unusable is stored)."""
    col, row = c.params.get("col"), c.params.get("row")
    if col is None or row is None:
        return None
    try:
        col, row = float(col), float(row)
    except (TypeError, ValueError):
        return None
    if col % 1 or row % 1:
        return None
    return int(col), int(row)


def _occupied(site, ignore: str | None = None) -> set[tuple[int, int]]:
    taken = set()
    for c in site:
        pos = position(c)
        if c.id != ignore and pos is not None and c.kind not in ON_ROOF:
            taken |= squares(c.kind, *pos)
    return taken


def why_not(site, kind: str, col: int, row: int, ignore: str | None = None) -> str | None:
    """Why a component of `kind` cannot stand at col, row (None = it can). `ignore` is the
    component being moved, so it does not block itself."""
    if kind in ON_ROOF:
        return "Rooftop solar goes on the roof of the production hall."
    covered = squares(kind, col, row)
    ground = set(ground_squares())
    if not covered <= ground:
        fixed = next((label for label, sq in FIXED.values() if covered & set(sq)), None)
        return (
            f"That square belongs to the {fixed.lower()}."
            if fixed
            else "That is outside the fence."
        )
    if covered & _occupied(site, ignore):
        return "Something already stands there."
    return None


def free_spot(site, kind: str, ignore: str | None = None) -> tuple[int, int] | None:
    """A free square for a component: its preferred spots first, then the nearest free one."""
    preferred = PREFERRED.get(kind, ())
    start = preferred[0] if preferred else (int(CENTRE), int(CENTRE))
    rest = sorted(ground_squares(), key=lambda sq: hypot(sq[0] - start[0], sq[1] - start[1]))
    for col, row in [*preferred, *rest]:
        if why_not(site, kind, col, row, ignore) is None:
            return col, row
    return None


def with_position(c: C.Component, col: int, row: int) -> C.Component:
    return C.Component(c.id, c.kind, c.name, {**c.params, "col": col, "row": row})


def auto_place(site) -> list[C.Component]:
    """The same site, with a square for every ground component that has none (or an
    unusable one). Components that cannot fit keep no square; the 3D view then finds
    them a spot of its own and the designer lists them as not placed."""
    placed: list[C.Component] = []
    for c in site:
        pos = position(c)
        if c.kind in ON_ROOF or (pos and why_not(placed, c.kind, *pos) is None):
            placed.append(c)
            continue
        spot = free_spot(placed, c.kind)
        params = {k: v for k, v in c.params.items() if k not in ("col", "row")}
        bare = C.Component(c.id, c.kind, c.name, params)
        placed.append(with_position(bare, *spot) if spot else bare)
    return placed


def layout_problems(site) -> list[str]:
    """What is wrong with where things stand, in plain words (empty list = fine)."""
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
        reason = why_not(placed, c.kind, *pos)
        if reason:
            problems.append(f"{c.name}: {reason}")
        else:
            placed.append(c)
    return problems


def world(kind: str, col: int, row: int) -> tuple[float, float]:
    """Where the 3D view puts the component: metres east (x) and south (z) of the island's
    centre, at the middle of the squares it covers."""
    w, h = footprint(kind)
    return (
        round((col + (w - 1) / 2 - CENTRE) * CELL_M, 2),
        round((row + (h - 1) / 2 - CENTRE) * CELL_M, 2),
    )


def world_positions(site) -> dict[str, tuple[float, float]]:
    """3D position of every component that has a square, by component id."""
    out = {}
    for c in site:
        pos = position(c)
        if pos is not None and c.kind not in ON_ROOF:
            out[c.id] = world(c.kind, *pos)
    return out


# ── What the designer did: one event at a time ──────────────────────────────


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
            col, row = int(event["col"]), int(event["row"])
        except (KeyError, TypeError, ValueError):
            return None
        return col, row

    if action == "add":
        kind = event.get("kind")
        if kind not in C.CATALOGUE:
            return site, None, "Unknown component type."
        if len(site) >= C.MAX_COMPONENTS:
            return site, None, f"A site can have at most {C.MAX_COMPONENTS} components."
        new = C.new_component(kind, C.next_name(kind, site))
        if kind in ON_ROOF:
            if event.get("target") not in (None, "hall"):
                return site, None, why_not(site, kind, 0, 0)
            return [*site, new], new.id, None
        spot = square() or free_spot(site, kind)
        if spot is None:
            return site, None, "There is no free square left for this."
        reason = why_not(site, kind, *spot)
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
        reason = why_not(site, c.kind, *spot, ignore=c.id)
        if reason:
            return site, c.id, reason
        return [with_position(x, *spot) if x.id == c.id else x for x in site], c.id, None
    if action == "remove":
        return [x for x in site if x.id != c.id], None, None
    if action == "select":
        return site, c.id, None
    return site, None, None
