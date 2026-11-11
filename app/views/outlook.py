"""Price outlook: forecast prices for the days after the published ones (D+2 to D+7), with
an honest comparison of the forecasts, including the machine learning model
(offpeak/forecast/model.py)."""

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak.forecast.outlook import view_payload
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_SITE

TZ = "Europe/Berlin"
header(f"Day-ahead market · {DEMO_SITE.zone}", "Price outlook", live=True)


try:
    with st.spinner("Forecasting the coming days…"):
        found = data.price_forecast()
except PriceSourceError:
    found = None
payload = view_payload(found[0], found[2], TZ, found[3]) if found else None
if payload is not None:
    payload["insight"] = data.model_insight()
if payload is None:
    st.info(
        "The outlook needs a few weeks of price history, which could not be loaded right now. "
        "We try again in a few minutes."
    )
    st.stop()
web.show("outlook", payload, height=1400)
