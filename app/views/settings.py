"""Settings: the demo site. Data sources and job runs moved to the Data & status page."""

import streamlit as st
from ui.components import card_title, header

from offpeak.sites import DEMO_CITY, DEMO_SITE

header("Setup", "Settings", live=True)
left, right = st.columns(2, gap="medium")
with left, st.container(border=True, key="card_site"):
    card_title("Site", "Read-only for now; editing sites and loads comes next")
    facts = {
        "Name": DEMO_SITE.name,
        "Location": f"{DEMO_CITY} ({DEMO_SITE.lat:.2f}, {DEMO_SITE.lon:.2f})",
        "Price zone": DEMO_SITE.zone,
        "Panel": f"{DEMO_SITE.tilt_deg:.0f}° tilt, facing {DEMO_SITE.azimuth_deg:.0f}° (south)",
    }
    st.html(
        "".join(
            f'<div class="op-row"><span class="meta">{k}</span><span>{v}</span></div>'
            for k, v in facts.items()
        )
    )
with right, st.container(border=True, key="card_more"):
    card_title("More settings", "Planned")
    planned = {
        "Language": "English (German next)",
        "Tariff": "Tariff calculator page",
        "Machines": "Site &amp; components page",
    }
    st.html(
        "".join(
            f'<div class="op-row"><span class="meta">{k}</span><span>{v}</span></div>'
            for k, v in planned.items()
        )
    )
