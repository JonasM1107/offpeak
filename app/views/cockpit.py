"""Simulation cockpit: set up your machines (power, job length, allowed hours) and see when in
the coming days each should run and what that saves. The hours ahead come from
offpeak/cockpit.py; the search runs in app/ui/web/cockpit.html so sliders react at once.
Machines added, removed or changed there come back here and are saved (Supabase table
cockpit_machines, or the session without a database)."""

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak.cockpit import clean_machines
from offpeak.sites import DEMO_CITY, DEMO_SITE

header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Simulation cockpit", live=True)

# First keep what the view sent since the last run (each message has a new id).
sent = st.session_state.get("cockpit")
if isinstance(sent, dict) and sent.get("id") != st.session_state.get("cockpit_saved_id"):
    st.session_state["cockpit_saved_id"] = sent.get("id")
    data.save_cockpit_machines(clean_machines(sent.get("machines")))

with st.spinner("Preparing the coming days…"):
    ahead = data.hours_ahead()
if ahead is None:
    st.info("Prices or the weather forecast could not be loaded right now. We try again soon.")
    st.stop()
hours, now_index = ahead
machines, saved, storage = data.machines_to_plan()
payload = {
    "horizon": hours,
    "machines": machines,
    "saved": saved,
    "storage": storage,
    "now_index": now_index,
}
web.live("cockpit", payload, key="cockpit", height=1400, keep=("machines", "saved"))
