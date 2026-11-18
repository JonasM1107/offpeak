"""The 3D site view: Python works out the numbers, a three.js page draws them.

The HTML template (site_scene.html) gets one JSON payload and needs no further calls, so
moving the time slider, switching the plan or clicking through the fact sheets happens in
the browser without a rerun.
"""

import base64
import gzip
import json
from functools import cache
from pathlib import Path

import pandas as pd
import streamlit as st

from offpeak import components as site_components
from offpeak import layout
from offpeak.tariffs import Tariff

TEMPLATE = Path(__file__).with_name("site_scene.html")
MODELS = Path(__file__).with_name("models")  # GLB files built by scripts/blender/


# The models each profile's scene uses; the others are not sent.
HOME_MODELS = {
    "semi_detached",
    "carport",
    "wallbox",
    "ev_car",
    "home_battery",
    "home_meter",
    "grid_cabinet",
    "pv_module",
    "pv_inverter",
    "heat_pump_unit",
    "tree_round",
    "tree_tall",
    "fence_segment",
    "pv_field",
    "pv_rack",
}


def models_for(profile: str) -> dict[str, str]:
    """The models one profile's scene needs (a home has no turbines or furnace halls)."""
    every = models()
    if profile == "home":
        return {k: v for k, v in every.items() if k in HOME_MODELS}
    return {k: v for k, v in every.items() if k not in HOME_MODELS - SHARED}


SHARED = {
    "pv_module",
    "pv_inverter",
    "heat_pump_unit",
    "tree_round",
    "tree_tall",
    "fence_segment",
    "pv_rack",
}


@cache
def models() -> dict[str, str]:
    """The detailed 3D models by file name without .glb, gzip-compressed (about a third of
    the size) and base64-encoded. They travel inside the page's data, so the page needs no
    file server; the browser unpacks them. Read once per app process."""
    return {
        p.stem: base64.b64encode(gzip.compress(p.read_bytes(), mtime=0)).decode()
        for p in sorted(MODELS.glob("*.glb"))
    }


def payload(
    inputs: pd.DataFrame,
    site: dict,
    hour_now: int,
    tariff: Tariff | None = None,
    comps=None,
    measured: dict | None = None,
    day: dict | None = None,
    compact: bool = False,
    edit: bool = False,
) -> dict:
    """Everything the page needs: both plans for all 24 hours, per component and for the
    whole site, each plan's bill under the tariff, and every component's fact sheet.

    `inputs` comes from demo_site.apply_tariff() when a tariff is given, so every hour
    has its all-in price. `day` is site_components.site_day() for these inputs if it was
    already worked out (app/data.py keeps it, so a second visit does not plan again).
    `compact` shows only the 3D stage. `edit` turns the stage into the "Edit site" layout
    designer (see editor_data); it is compact too, and the models are loaded as files
    instead of travelling inside the data on every change."""
    comps = list(comps if comps is not None else site_components.DEFAULT_COMPONENTS)
    profile = comps[0].profile if comps else "business"  # all of a site's are one profile
    if day is None:
        day = site_components.site_day(inputs, comps, tariff)
    # where the layout designer put each component (metres east, south); None = automatic.
    # Added to copies: `day` may be the one app/data.py keeps for the next visit.
    positions = layout.world_positions(comps)
    placed = [{**c, "pos": positions.get(c["id"])} for c in day["components"]]
    out = {
        "site": site,
        "compact": compact or edit,
        "edit": editor_data(comps) if edit else None,
        "hour_now": hour_now,
        "real": {
            "price": bool(inputs["price_real"].all()),
            "weather": bool(inputs["weather_real"].any()),
        },
        "tariff": {"name": tariff.name} if tariff is not None else None,
        # whole-site rows per plan, also at the top level as before
        "offpeak": day["rows"]["offpeak"],
        "usual": day["rows"]["usual"],
        "rows": day["rows"],
        "bill": day["bill"],
        "series": day["series"],
        "components": placed,
        "price_class": day["price_class"],
        "smart_battery": day["smart_battery"],
        "profile": profile,
        "models": {} if edit else models_for(profile),
        "model_names": sorted(models_for(profile)) if edit else None,
    }
    if measured:  # a measured day, played like a third plan ("Yesterday at home")
        out["rows"]["measured"] = measured["rows"]
        out["series"]["measured"] = measured["series"]
        if out["bill"] is not None and measured["bill"] is not None:
            out["bill"]["measured"] = measured["bill"]
        for c in out["components"]:
            c["analytics"]["measured"] = measured["analytics"][c["id"]]
        out["measured"] = {"date": measured["date"], "price_class": measured["price_class"]}
    return out


def render_html(data: dict) -> str:
    # "</" inside the JSON would end the <script> tag early
    return TEMPLATE.read_text().replace("__DATA__", json.dumps(data).replace("</", "<\\/"))


def height_for(data: dict) -> int:
    """Pixel height of the page: stage, KPIs, one day-plan row per machine, fact sheets."""
    if data.get("compact"):
        return 600 + 12
    plan_rows = 3 + sum(1 for c in data["components"] if c["role"] != "generation")
    return 600 + 12 + 96 + 12 + 110 + plan_rows * 36 + 12 + 760 + 40


def show(data: dict) -> None:
    # st.iframe replaces st.components.v1.html, which Streamlit removes. Our own template and
    # JSON only, so the frame may run its script (three.js).
    st.iframe(render_html(data), height=height_for(data))


# ── The "Edit site" layout designer ──────────────────────────────────────────

ROLES = (
    ("generation", "Generation"),
    ("storage", "Storage"),
    ("flexible", "Flexible machines"),
    ("base", "Always on"),
)


def editor_data(comps) -> dict:
    """What the layout designer draws and checks while dragging: the grid, the fixed
    things, every part's footprint and square, and the parts list (the business
    catalogue: the designer is part of the Business portal). All numbers come from
    offpeak/layout.py, which also has the final say on every action."""
    return {
        "grid": layout.GRID,
        "cell": layout.CELL_M,
        "size": layout.SIZE_M,
        "fence": layout.FENCE_M,
        "fixed": [list(rect) for _, rect in layout.FIXED.values()],
        "hall": list(layout.FIXED["hall"][1]),
        "roof": sorted(layout.ON_ROOF),
        "roles": [list(r) for r in ROLES],
        "kinds": [
            {
                "key": k.key,
                "label": k.label,
                "role": k.role,
                "description": k.description,
                # the footprint of a new part, with the kind's typical values
                "rect": list(layout.footprint(site_components.new_component(k.key, k.label))),
            }
            for k in site_components.CATALOGUE.values()
        ],
        "rects": {c.id: list(layout.footprint(c)) for c in comps},
        "squares": squares(comps),
    }


def squares(comps) -> dict[str, list[int]]:
    """Every placed part's square, by id."""
    out = {}
    for c in comps:
        pos = layout.position(c)
        if pos is not None and c.kind not in layout.ON_ROOF:
            out[c.id] = list(pos)
    return out
