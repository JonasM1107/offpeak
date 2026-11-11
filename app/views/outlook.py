"""Price outlook: forecast prices for the days after the published ones (D+2 to D+7), with
an honest comparison of the forecasts. The ML model plugs in at offpeak/forecast/model.py."""

from datetime import timedelta

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak.analysis import hourly
from offpeak.forecast.outlook import backtest, view_payload
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import market_today

TZ = "Europe/Berlin"
header(f"Day-ahead market · {DEMO_SITE.zone}", "Price outlook", live=True)


@st.cache_data(ttl=1800, show_spinner=False)
def build(start, end) -> dict | None:
    """The backtest takes a couple of seconds, so its result is kept for half an hour."""
    prices, _, _ = data.prices(start, end)
    if prices.empty:
        return None
    history = hourly(prices, TZ).set_index("ts")["ct"]
    try:
        test = backtest(history, TZ)
    except ValueError:  # too little history to judge the forecasts
        return None
    return view_payload(history, test, TZ)


today = market_today()
try:
    with st.spinner("Forecasting the coming days…"):
        payload = build(today - timedelta(days=180), today + timedelta(days=1))
except PriceSourceError:
    payload = None
if payload is None:
    st.info(
        "The outlook needs a few weeks of price history, which could not be loaded right now. "
        "We try again in a few minutes."
    )
    st.stop()
web.show("outlook", payload, height=1400)
