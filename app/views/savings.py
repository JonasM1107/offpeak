"""Savings: what the Offpeak plan would have saved over the last 30 or 90 days, day by day,
with a replay of each day. The replay is offpeak/savings.py; the view app/ui/web/savings.html."""

from datetime import timedelta

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak import components, roles, savings
from offpeak.sites import DEMO_CITY
from offpeak.timeutils import market_today

TZ = "Europe/Berlin"
header(f"{data.site().name} · {DEMO_CITY} · {data.site().zone}", "Savings", live=True)

period = st.segmented_control(
    "Period",
    ["Last 30 days", "Last 90 days"],
    default="Last 30 days",
    key="savings_period",
    label_visibility="collapsed",
)
n_days = 90 if period == "Last 90 days" else 30
comps, _ = data.site_components()
if not components.site_model(comps)[1]:  # no machine or device whose start can move
    w = roles.words(data.role())
    st.info(
        f"Nothing to plan yet: this {w['site']} has no {w['machines']} that can run at another "
        "time (a heat pump, a wallbox, a washing machine, ...), so the plan cannot save "
        f"anything. Add one under {w['setup']}.",
        icon=":material/info:",
    )
    st.page_link("views/components.py", label=w["setup"], icon=":material/add_circle:")
    st.stop()


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
payload = {"days": days, "summary": savings.summary(days), "words": roles.words(data.role())}
web.show("savings", payload, height=1500)
