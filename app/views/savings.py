"""Savings: what the Offpeak plan would have saved over the last 30 or 90 days, day by day,
with a replay of each day. The replay is offpeak/savings.py; the view app/ui/web/savings.html."""

from datetime import timedelta

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak import savings
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.timeutils import market_today

TZ = "Europe/Berlin"
header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Savings", live=True)

period = st.segmented_control(
    "Period",
    ["Last 30 days", "Last 90 days"],
    default="Last 30 days",
    key="savings_period",
    label_visibility="collapsed",
)
n_days = 90 if period == "Last 90 days" else 30
comps, _ = data.site_components()


setup = data.setup_key(comps)
try:
    with st.spinner(f"Replaying the last {n_days} days…"):
        days = data.savings_replay(market_today() - timedelta(days=1), n_days, setup)
except Exception as err:  # prices or weather archive unavailable
    print(f"offpeak: savings replay failed: {err}")
    days = []
if not days:
    st.info("Past prices or weather could not be loaded right now. We try again in a few minutes.")
    st.stop()
web.show("savings", {"days": days, "summary": savings.summary(days)}, height=1500)
