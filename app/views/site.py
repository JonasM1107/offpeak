"""Site view: a 3D model of the site, a day plan per machine and a fact sheet per component."""

import data
import streamlit as st
from ui import site_scene
from ui.components import header

from offpeak import components, demo_site, roles
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY
from offpeak.tariffs import tariff_for
from offpeak.timeutils import market_today

header(
    f"{data.site().name} · {DEMO_CITY} · {data.site().zone}",
    roles.words(data.role())["view"],
    live=True,
)

try:
    today_prices, _, _, _ = data.today_and_tomorrow()
except PriceSourceError:
    today_prices = None  # the page falls back to the demo price curve and says so
weather, _, _, _ = data.weather()
comps, source = data.site_components()

assets, _ = components.site_model(comps)
tariff = tariff_for(data.role(), comps)  # a household's tariff for a home
inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
inputs = demo_site.apply_tariff(inputs, tariff, market_today())
site = {
    "name": data.site().name,
    "city": DEMO_CITY,
    "zone": data.site().zone,
    "date": market_today().isoformat(),
}
hour_now = data.now_utc().tz_convert(MARKET_TZ).hour
# a home with measurements can also play its last measured day ("Yesterday at home")
measured = data.measured_scene_day(comps, tariff) if data.role() == "home" else None
day = data.site_day(inputs, data.setup_key(comps), data.role())  # planned once, then kept
site_scene.show(site_scene.payload(inputs, site, hour_now, tariff, comps, measured, day))

st.page_link(
    "views/components.py",
    label=f"Add or remove them under Setup → {roles.words(data.role())['setup']}",
    icon=":material/add_circle:",
)
