"""Weather: the seven-day forecast for the demo site, and what it means for solar power."""

from html import escape

import data
import streamlit as st
from ui import charts
from ui.components import card_title, header, hhmm, kpi, local

from offpeak.config import MARKET_TZ, OPEN_METEO_ATTRIBUTION
from offpeak.demo_site import ASSETS
from offpeak.generation.pv import pv_kw
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.weather.codes import weather_label
from offpeak.weather.daily import daily_outlook

weather, fetched, _ = data.weather_week()
header(f"{DEMO_SITE.name} · {DEMO_CITY}", "Weather, next 7 days", live=weather is not None)
if weather is None or weather.empty:
    st.info("The weather forecast is not available right now. We try again within the hour.")
    st.stop()

days = daily_outlook(weather, ASSETS.pv_kwp, MARKET_TZ)
if days.empty:
    st.info("The forecast is too short for a daily outlook right now. We try again soon.")
    st.stop()
sunniest = days.loc[days["solar_kwh"].idxmax()]
coldest = days.loc[days["temp_min"].idxmin()]
windiest = days.loc[days["wind_max"].idxmax()]

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi(
        "Solar this week",
        f"{days['solar_kwh'].sum():.0f}",
        "kWh",
        f"Expected from {ASSETS.pv_kwp:.0f} kWp of panels",
        accent=True,
    )
with c2:
    kpi(
        "Sunniest day",
        f"{sunniest['day']:%a %-d %b}",
        note=f"About {sunniest['solar_kwh']:.0f} kWh of solar",
    )
with c3:
    kpi("Coldest night", f"{coldest['temp_min']:.0f}", "°C", f"{coldest['day']:%a %-d %b}")
with c4:
    kpi(
        "Windiest day",
        f"{windiest['day']:%a %-d %b}",
        note=f"Wind up to {windiest['wind_max']:.0f} m/s",
    )

st.write("")
best = days["solar_kwh"].idxmax()
tiles = []
for idx, d in days.iterrows():
    share = round(100 * d["solar_kwh"] / (sunniest["solar_kwh"] or 1))
    tiles.append(
        f'<div class="op-tile{" sunny" if idx == best else ""}">'
        f'<div class="t">{d["day"]:%a %-d %b}</div>'
        f'<div class="temp">{d["temp_max"]:.0f}° / {d["temp_min"]:.0f}°</div>'
        f'<div class="cond">{escape(weather_label(d["weather_code"]))}</div>'
        f'<div class="op-foot">Solar {d["solar_kwh"]:.0f} kWh · rain {d["precip_mm"]:.1f} mm</div>'
        f'<div class="op-bar"><span style="width:{share}%"></span></div></div>'
    )
with st.container(border=True, key="card_days"):
    card_title("Day by day", f"{DEMO_CITY} · DWD ICON via Open-Meteo · high / low temperature")
    st.html(f'<div class="op-tiles week">{"".join(tiles)}</div>')
    st.html(
        '<div class="op-foot">Orange bar = expected solar yield, relative to the sunniest day. '
        "The sunniest day is highlighted: a good day for loads that can wait.</div>"
    )

st.write("")
left, right = st.columns(2, gap="medium")
with left, st.container(border=True, key="card_solar"):
    card_title(
        "Expected solar power",
        f"{ASSETS.pv_kwp:.0f} kWp, {DEMO_SITE.tilt_deg:.0f}° tilt, per 15 minutes",
    )
    kw = pv_kw(weather["gti_wm2"], ASSETS.pv_kwp)
    st.plotly_chart(charts.solar_hours(weather["ts"], kw), config=charts.CONFIG)
    if kw.max() > 0:
        peak = local(weather.loc[kw.idxmax(), "ts"])
        st.caption(
            f"The strongest sun is expected on {peak:%A at %H:%M}, "
            f"about {kw.max():.0f} kW. Running flexible loads in those hours uses your own power "
            "instead of buying it."
        )
with right, st.container(border=True, key="card_temp"):
    card_title("Temperature and wind", "Hourly, wind at 10 m")
    st.plotly_chart(charts.temp_wind(weather), config=charts.CONFIG)
    st.caption(
        "Cold hours raise heating demand and often prices. Strong wind across Germany usually "
        "makes power cheaper, though wind here in the city is only a rough hint of that."
    )

st.caption(f"{OPEN_METEO_ATTRIBUTION} · forecast loaded {hhmm(fetched)}")
