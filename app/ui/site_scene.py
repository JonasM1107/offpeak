"""The 3D site view: Python works out the numbers, a three.js page draws them.

The HTML template (site_scene.html) gets one JSON payload and needs no further calls, so
moving the time slider, switching the plan or clicking through the fact sheets happens in
the browser without a rerun.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components

from offpeak import components as site_components
from offpeak.tariffs import Tariff

TEMPLATE = Path(__file__).with_name("site_scene.html")


def payload(
    inputs: pd.DataFrame, site: dict, hour_now: int, tariff: Tariff | None = None, comps=None
) -> dict:
    """Everything the page needs: both plans for all 24 hours, per component and for the
    whole site, each plan's bill under the tariff, and every component's fact sheet.

    `inputs` comes from demo_site.apply_tariff() when a tariff is given, so every hour
    has its all-in price."""
    comps = list(comps if comps is not None else site_components.DEFAULT_COMPONENTS)
    day = site_components.site_day(inputs, comps, tariff)
    return {
        "site": site,
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
    }


def render_html(data: dict) -> str:
    # "</" inside the JSON would end the <script> tag early
    return TEMPLATE.read_text().replace("__DATA__", json.dumps(data).replace("</", "<\\/"))


def height_for(data: dict) -> int:
    """Pixel height of the page: stage, KPIs, one day-plan row per machine, fact sheets."""
    plan_rows = 3 + sum(1 for c in data["components"] if c["role"] != "generation")
    return 600 + 12 + 96 + 12 + 110 + plan_rows * 36 + 12 + 760 + 40


def show(data: dict) -> None:
    components.html(render_html(data), height=height_for(data), scrolling=False)
