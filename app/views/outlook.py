"""Price outlook: Offpeak Intelligence's forecast for the days after the published prices
(D+2 to D+7), with a likely range and a short reason per day. The forecast is computed in the
background (offpeak/jobs/forecast_prices.py); how it works is in offpeak/forecast/."""

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak.forecast.outlook import page_payload
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import market_today

TZ = "Europe/Berlin"
header(f"Offpeak Intelligence · Day-ahead market · {DEMO_SITE.zone}", "Price outlook", live=True)

try:
    with st.spinner("Offpeak Intelligence is looking at the coming days…"):
        found = data.price_outlook()
except PriceSourceError:
    found = None
if found is None:
    st.info(
        "The outlook needs a few weeks of price history, which could not be loaded right now. "
        "We try again in a few minutes."
    )
    st.stop()
history, out = found
web.show("outlook", page_payload(history, out, TZ, data.outlook_drivers(market_today())))
