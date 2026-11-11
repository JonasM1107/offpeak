"""Prices: an interactive look at day-ahead prices over up to two years.

(The file keeps its old name, analytics.py, so links and tests stay valid.) The page loads
two years of hourly prices once; zooming and switching periods happen in the browser.
"""

from datetime import timedelta

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak.analysis import hourly_payload
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import market_today

header(f"Day-ahead market · {DEMO_SITE.zone}", "Prices", live=True)
end = market_today()
try:
    with st.spinner("Loading two years of prices…"):
        prices, _, _ = data.prices(end - timedelta(days=729), end)
except PriceSourceError:
    prices = None
if prices is None or prices.empty:
    st.info("Price history could not be loaded right now. We try again in a few minutes.")
    st.stop()

web.show("prices", {"prices": hourly_payload(prices)}, height=1500)
