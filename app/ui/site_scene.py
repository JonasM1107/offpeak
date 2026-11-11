"""The 3D site view: Python works out the numbers, a three.js page draws them.

The HTML template (site_scene.html) gets one JSON payload and needs no further calls, so
moving the time slider or switching the schedule happens in the browser without a rerun.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components

from offpeak import demo_site
from offpeak.tariffs import Tariff

TEMPLATE = Path(__file__).with_name("site_scene.html")


def _bill(b) -> dict:
    return {
        "lines": {k: round(v, 2) for k, v in b.lines.items()},
        "total": round(b.total, 2),
        "peak_kw": round(b.peak_kw, 1),
        "ct_per_kwh": round(b.ct_per_kwh, 2),
    }


def payload(inputs: pd.DataFrame, site: dict, hour_now: int, tariff: Tariff) -> dict:
    """Everything the page needs: both schedules for all 24 hours, priced with the tariff,
    plus each schedule's bill for the day and the site facts.

    `inputs` comes from demo_site.apply_tariff(), so every hour has its all-in price."""
    a = demo_site.ASSETS
    plan = demo_site.plan_day(inputs, tariff)
    price_cols = ["energy_ct", "grid_ct", "levies_ct", "tax_ct", "import_ct", "export_ct"]

    def rows(p: demo_site.Plan) -> list[dict]:
        day = demo_site.simulate(inputs, p).join(inputs[price_cols].reset_index(drop=True))
        return day.round(3).to_dict("records")

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
        "tariff": {"name": tariff.name},
        "offpeak": rows(plan),
        "usual": rows(demo_site.USUAL),
        "bill": {
            "offpeak": _bill(demo_site.day_bill(inputs, plan, tariff)),
            "usual": _bill(demo_site.day_bill(inputs, demo_site.USUAL, tariff)),
        },
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
