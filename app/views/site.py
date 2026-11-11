"""Site view: a 3D model of the site, a day plan per machine, a fact sheet per component,
and a form to add or remove components."""

import data
import streamlit as st
from ui import site_scene
from ui.components import card_title, header

from offpeak import components, demo_site
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.timeutils import market_today

header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Site view", live=True)

try:
    today_prices, _, _, _ = data.today_and_tomorrow()
except PriceSourceError:
    today_prices = None  # the page falls back to the demo price curve and says so
weather, _, _, _ = data.weather()
comps, source = data.site_components()

assets, _ = components.site_model(comps)
inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
site = {
    "name": DEMO_SITE.name,
    "city": DEMO_CITY,
    "zone": DEMO_SITE.zone,
    "date": market_today().isoformat(),
}
hour_now = data.now_utc().tz_convert(MARKET_TZ).hour
site_scene.show(site_scene.payload(inputs, site, hour_now, comps))

# ── Add or remove components ─────────────────────────────────────────────────
st.write("")
SAVED = {
    "database": "Changes are saved for everyone using this site.",
    "demo": "Showing the demo components. Your first change saves them together with it.",
    "session": "No database connected: changes last until you reload the page.",
}
add, remove = st.columns([2, 1], gap="medium")
with add, st.container(border=True, key="card_add"):
    card_title(
        "Add a component", "New solar, a second turbine, a heat pump: it appears in the model"
    )
    labels = {k.label: k.key for k in components.CATALOGUE.values()}
    kind = labels[st.selectbox("Type", list(labels))]
    spec = components.CATALOGUE[kind]
    with st.form("add_component", clear_on_submit=True, border=False):
        name = st.text_input("Name", placeholder=f"e.g. {spec.label} north")
        cols = st.columns(3)
        params = {}
        for i, p in enumerate(spec.params):
            with cols[i % 3]:
                params[p.key] = st.number_input(
                    f"{p.label} ({p.unit})" if p.unit else p.label,
                    min_value=float(p.min),
                    max_value=float(p.max),
                    value=float(p.default),
                    step=1.0,
                    key=f"{kind}_{p.key}",
                )
        st.caption(spec.description)
        if st.form_submit_button("Add to site", type="primary"):
            problems = components.validate(kind, params)
            if problems:
                st.error(" · ".join(problems))
            else:
                data.add_component(
                    components.new_component(kind, name.strip() or spec.label, params)
                )
                st.rerun()
    st.caption(SAVED[source])

with remove, st.container(border=True, key="card_remove"):
    card_title("Remove a component", f"{len(comps)} on this site")
    names = {f"{c.name} · {c.spec.label}": c.id for c in comps}
    picked = st.selectbox("Component", list(names), label_visibility="collapsed")
    if st.button("Remove", disabled=not names):
        data.remove_component(names[picked])
        st.rerun()
