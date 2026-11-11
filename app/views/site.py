"""Site view: a 3D picture of the demo site and how power flows through it today."""

import data
from ui import site_scene
from ui.components import header

from offpeak import demo_site
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.timeutils import market_today

header("Overview", "Site view", live=True)

try:
    today_prices, _, _, _ = data.today_and_tomorrow()
except PriceSourceError:
    today_prices = None  # the page falls back to the demo price curve and says so
weather, _, _, _ = data.weather()

inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ)
site = {
    "name": DEMO_SITE.name,
    "city": DEMO_CITY,
    "zone": DEMO_SITE.zone,
    "date": market_today().isoformat(),
}
hour_now = data.now_utc().tz_convert(MARKET_TZ).hour
site_scene.show(site_scene.payload(inputs, site, hour_now))
