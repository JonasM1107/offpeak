"""Power: what power costs today and tomorrow, slot by slot, and how prices behaved over up
to two years.

(The file keeps its old name, analytics.py, so links and tests stay valid.) The page loads
two years of hourly prices once; zooming and switching periods happen in the browser.
"""

from datetime import timedelta

import data
import pandas as pd
import streamlit as st
from ui import web
from ui.components import header

from offpeak.analysis import day_detail, hourly_payload
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import market_today

header(f"Day-ahead market · {DEMO_SITE.zone}", "Power", live=True)
end = market_today()
try:
    with st.spinner("Loading two years of prices…"):
        # the past (kept for hours) and today (kept for minutes), loaded apart
        past, _, _ = data.past_prices(end - timedelta(days=729), end - timedelta(days=1))
        today_only, _, _ = data.prices(end, end)
        prices = pd.concat([past, today_only], ignore_index=True)
except PriceSourceError:
    prices = None
if prices is None or prices.empty:
    st.info("Price history could not be loaded right now. We try again in a few minutes.")
    st.stop()

# today and tomorrow in full detail; tomorrow appears once published (around 13:00)
try:
    today_prices, tomorrow_prices, _, _ = data.today_and_tomorrow()
except PriceSourceError:
    today_prices = tomorrow_prices = None
days = [day_detail(today_prices), day_detail(tomorrow_prices)]
web.show("prices", {"prices": hourly_payload(prices), "days": days}, height=1900)
