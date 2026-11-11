"""Settings: the demo site and where our data comes from. Editing comes in a later step."""

import data
import pandas as pd
import streamlit as st
from ui.components import card_title, header

from offpeak.config import (
    ENERGY_CHARTS_ATTRIBUTION,
    OPEN_METEO_ATTRIBUTION,
    OPEN_METEO_MODEL,
)
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
with right, st.container(border=True, key="card_attrib"):
    card_title("Data sources", "Free sources, credited as their licences require")
    st.html(
        f'<div class="op-row"><div><div class="name">Energy-Charts</div><div class="meta">'
        f"{ENERGY_CHARTS_ATTRIBUTION}</div></div></div>"
        f'<div class="op-row"><div><div class="name">Open-Meteo</div><div class="meta">'
        f"{OPEN_METEO_ATTRIBUTION} · model {OPEN_METEO_MODEL}</div></div></div>"
    )

st.write("")
with st.container(border=True, key="card_jobs"):
    card_title("Scheduled jobs", "Last runs of the jobs that fill the database (German time)")
    runs = data.job_runs()
    if runs is None:
        st.caption("No database connected yet. Add DATABASE_URL to .env or the Streamlit secrets.")
    elif runs.empty:
        st.caption("Connected. No job has run yet.")
    else:
        table = pd.DataFrame(
            {
                "Job": runs["job"],
                "Started": runs["started_at"]
                .dt.tz_convert("Europe/Berlin")
                .dt.strftime("%a %d %b, %H:%M"),
                "Status": runs["status"],
                "Rows": runs["rows_written"],
                "Note": runs["message"].fillna(""),
            }
        )
        st.dataframe(table, hide_index=True, width="stretch")
