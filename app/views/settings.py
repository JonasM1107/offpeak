"""Settings: connecting the account's own consumption data (ui/connect.py), then the signed-in
role's site (the demo site or the demo home). Data sources are credited on the dashboard and
the Prices page."""

from html import escape

import data
import streamlit as st
from ui.components import card_title, header
from ui.connect import connect_card

from offpeak import components, roles
from offpeak.sites import DEMO_CITY, facing

role, here = data.role(), data.site()
w = roles.words(role)
header("Setup", "Settings", live=True)
connect_card(role)  # first, so it is the first thing seen here
left, right = st.columns(2, gap="medium")
with left, st.container(border=True, key="card_site"):
    card_title(w["Site"], f"Read-only here; {w['machines']} are changed under {w['setup']}")
    facts = {
        "Account type": roles.LABELS[role],
        "Name": here.name,
        "Location": f"{DEMO_CITY} ({here.lat:.2f}, {here.lon:.2f})",
        "Price zone": here.zone,
        "Panel": f"{here.tilt_deg:.0f}° tilt, facing {here.azimuth_deg:.0f}° "
        f"({facing(here.azimuth_deg)})",
    }
    if role == "home":  # household sizes: what runs all the time, per day and per year
        assets, _ = components.site_model(data.site_components()[0])
        base = assets.cold_store_kw  # kW around the clock
        facts["Base load"] = f"{base * 24:.1f} kWh a day · {base * 8760:,.0f} kWh a year"
    st.html(
        "".join(
            f'<div class="op-row"><span class="meta">{k}</span><span>{escape(str(v))}</span></div>'
            for k, v in facts.items()
        )
    )
with right, st.container(border=True, key="card_more"):
    card_title("More settings", "Planned")
    planned = {
        "Language": "English (German next)",
        w["Machines"]: f"{w['setup']} page",
    }
    st.html(
        "".join(
            f'<div class="op-row"><span class="meta">{k}</span><span>{escape(v)}</span></div>'
            for k, v in planned.items()
        )
    )
