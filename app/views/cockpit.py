"""Simulation cockpit: set up your machines (power, job length, allowed hours) and see when in
the coming days each should run and what that saves. The hours ahead come from
offpeak/cockpit.py; the search runs in app/ui/web/cockpit.html so sliders react at once.
Machines added, removed or changed there come back here and are saved (Supabase table
cockpit_machines, or the session without a database)."""

import data
import streamlit as st
from ui import web
from ui.components import header

from offpeak import components
from offpeak.cockpit import clean_machines, horizon
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.tariffs import germany_2026
from offpeak.timeutils import market_today
from offpeak.weather.outlook import generation

TZ = "Europe/Berlin"
header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Simulation cockpit", live=True)

# First keep what the view sent since the last run (each message has a new id).
sent = st.session_state.get("cockpit")
if isinstance(sent, dict) and sent.get("id") != st.session_state.get("cockpit_saved_id"):
    st.session_state["cockpit_saved_id"] = sent.get("id")
    data.save_cockpit_machines(clean_machines(sent.get("machines")))

try:
    with st.spinner("Preparing the coming days…"):
        found = data.price_forecast()
except PriceSourceError:
    found = None
weather, _, _, _ = data.weather(days=7)
if not found or weather is None or weather.empty:
    st.info("Prices or the weather forecast could not be loaded right now. We try again soon.")
    st.stop()
history, forecast, _, _ = found

comps, _ = data.site_components()
assets, _ = components.site_model(comps)
gen = generation(weather, assets.pv_kwp, assets.turbine_kw * assets.turbines)
hours = horizon(
    history,
    forecast,
    gen,
    base_kw=assets.cold_store_kw,
    tariff=germany_2026(pv_kwp=assets.pv_kwp),
    tz=TZ,
    today=market_today(),
)
now = int(data.now_utc().floor("h").timestamp())
saved, storage = data.cockpit_machines()
site_machines = [
    {
        "name": c.name,
        "kw": c.p("kw") * (c.p("count") if c.kind == "ev_charger" else 1),
        "hours": int(c.p("hours")),
        "earliest": int(c.p("earliest")),
        "latest_end": int(c.p("latest_end")),
        "usual_start": int(c.p("usual_start")),
    }
    for c in comps
    if c.spec.role == "flexible"
]
payload = {
    "horizon": hours,
    "machines": clean_machines(saved) if saved is not None else site_machines,
    "saved": saved is not None,
    "storage": storage,
    "now_index": next((i for i, t in enumerate(hours["t"]) if t >= now), 0),
}
web.live("cockpit", payload, key="cockpit", height=1400, keep=("machines", "saved"))
