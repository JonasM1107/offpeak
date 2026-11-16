"""Dashboard: what to do now, what is next, and what it brings. The answers come from
offpeak/dashboard.py; the view (app/ui/web/dashboard.html) adds the live countdowns, ticking
steps off, the shift slider and the clickable hours. Prices in detail are on the Power page,
the weather on Weather & solar, the full planning in the cockpit."""

from datetime import datetime
from zoneinfo import ZoneInfo

import data
import streamlit as st
from ui import account, web
from ui.components import header

from offpeak import dashboard
from offpeak.config import ENERGY_CHARTS_ATTRIBUTION, OPEN_METEO_ATTRIBUTION
from offpeak.sites import DEMO_CITY, DEMO_SITE

hour = datetime.now(ZoneInfo("Europe/Berlin")).hour
greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
first_name = account.editor_name(account.editor() or "").split(" ")[0]
header(
    f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}",
    f"{greeting}, {first_name}" if first_name else greeting,
    live=True,
)

with st.spinner("Looking at the coming hours…"):
    ahead = data.hours_ahead()
if ahead is None:
    st.info("Prices could not be loaded right now. We try again in a few minutes.")
    st.stop()
hours, now_index = ahead
machines, _, _ = data.machines_to_plan()
saved, saved_state = data.saved_recently(30)
payload = dashboard.payload(hours, now_index, machines, saved)
payload["saved_state"] = saved_state
payload["credits"] = f"{ENERGY_CHARTS_ATTRIBUTION} · {OPEN_METEO_ATTRIBUTION}"
web.show("dashboard", payload, height=1300)
