"""Site view: a 3D model of the site, a day plan per machine and a fact sheet per component."""

import data
import streamlit as st
from ui import site_scene
from ui.components import header

from offpeak import components, demo_site, roles
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY
from offpeak.tariffs import germany_2026
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
tariff = germany_2026(pv_kwp=assets.pv_kwp)
inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
inputs = demo_site.apply_tariff(inputs, tariff, market_today())
site = {
    "name": data.site().name,
    "city": DEMO_CITY,
    "zone": data.site().zone,
    "date": market_today().isoformat(),
}
hour_now = data.now_utc().tz_convert(MARKET_TZ).hour
day = data.site_day(inputs, data.setup_key(comps))  # planned once per inputs and components
site_scene.show(site_scene.payload(inputs, site, hour_now, tariff, comps, day))

st.page_link(
    "views/components.py",
    label=f"Add or remove them under Setup → {roles.words(data.role())['setup']}",
    icon=":material/add_circle:",
)
