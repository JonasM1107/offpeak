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
    compact: bool = False,
) -> dict:
    """Everything the page needs: both plans for all 24 hours, per component and for the
    whole site, each plan's bill under the tariff, and every component's fact sheet.

    `inputs` comes from demo_site.apply_tariff() when a tariff is given, so every hour
    has its all-in price. `compact` shows only the 3D stage (the preview in "Edit site")."""
    comps = list(comps if comps is not None else site_components.DEFAULT_COMPONENTS)
    day = site_components.site_day(inputs, comps, tariff)
    # where the layout designer put each component (metres east, south); None = automatic
    positions = layout.world_positions(comps)
    for c in day["components"]:
        c["pos"] = positions.get(c["id"])
    return {
        "site": site,
        "compact": compact,
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
        "components": day["components"],
        "price_class": day["price_class"],
        "smart_battery": day["smart_battery"],
        "models": models(),
    }


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
