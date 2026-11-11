"""Weather & solar: the 7-day forecast, what the site's solar and wind will produce, and how
good yesterday's solar forecast was. The numbers come from offpeak/weather/outlook.py; the
interactive view is app/ui/web/weather.html."""

import data
import streamlit as st
from ui import web
from ui.components import header, hhmm

from offpeak import components
from offpeak.config import OPEN_METEO_MODEL
from offpeak.sites import DEMO_CITY
from offpeak.timeutils import market_today
from offpeak.weather.outlook import daily_outlook, generation, view_payload

TZ = "Europe/Berlin"
header(f"{DEMO_CITY} · DWD ICON via Open-Meteo", "Weather & solar", live=True)

with st.spinner("Loading the forecast…"):
    weather, fetched, _, _ = data.weather(days=7)
if weather is None or weather.empty:
    st.info("The weather forecast is not available right now. We try again within the hour.")
    st.stop()

comps, _ = data.site_components()
assets, _ = components.site_model(comps)
pv_kwp, wind_kw = assets.pv_kwp, assets.turbine_kw * assets.turbines
gen = generation(weather, pv_kwp, wind_kw)
days = daily_outlook(weather, gen, TZ)
days = days[days["date"] >= market_today()].head(7).reset_index(drop=True)

payload = view_payload(weather, gen, days, data.solar_check(7), pv_kwp, TZ)
payload["meta"] = {
    "pv_kwp": round(pv_kwp, 1),
    "wind_kw": round(wind_kw, 1),
    "model": OPEN_METEO_MODEL,
    "fetched": f"{fetched:%-d %b}, {hhmm(fetched)} German time",
    "now": int(data.now_utc().timestamp()),
}
if payload["accuracy"] is None:  # the view needs the block; show an empty comparison
    payload["accuracy"] = {
        "days": [],
        "summary": {},
        "hourly": {"t": [], "day": [], "forecast_kw": [], "measured_kw": []},
    }
web.show("weather", payload, height=1500)
