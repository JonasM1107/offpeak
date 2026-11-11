"""The 3D site view: Python works out the numbers, a three.js page draws them.

The HTML template (site_scene.html) gets one JSON payload and needs no further calls, so
moving the time slider or switching the schedule happens in the browser without a rerun.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components

from offpeak import demo_site

TEMPLATE = Path(__file__).with_name("site_scene.html")


def payload(inputs: pd.DataFrame, site: dict, hour_now: int) -> dict:
    """Everything the page needs: both schedules for all 24 hours, plus site facts."""
    a = demo_site.ASSETS

    plan = demo_site.plan_day(inputs)

    def rows(p: demo_site.Plan) -> list[dict]:
        return demo_site.simulate(inputs, p).round(3).to_dict("records")

    return {
        "site": site,
        "hour_now": hour_now,
        "real": {
            "price": bool(inputs["price_real"].all()),
            "weather": bool(inputs["weather_real"].any()),
        },
        "assets": {
            "pv_kwp": a.pv_kwp,
            "turbines": a.turbines,
            "turbine_kw": a.turbine_kw,
            "battery_kwh": a.battery_kwh,
        },
        "offpeak": rows(plan),
        "usual": rows(demo_site.USUAL),
        "windows": {
            "offpeak": demo_site.windows(plan),
            "usual": demo_site.windows(demo_site.USUAL),
        },
        "smart_battery": plan.smart_battery,
    }


def render_html(data: dict) -> str:
    # "</" inside the JSON would end the <script> tag early
    return TEMPLATE.read_text().replace("__DATA__", json.dumps(data).replace("</", "<\\/"))


def show(data: dict, height: int = 770) -> None:
    components.html(render_html(data), height=height, scrolling=False)
