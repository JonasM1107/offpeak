"""My data: the account's own consumption data and how to connect it (ui/connect.py).

- Homeowner: real measurements from the house of Jonas, one of the team (Fronius inverter, every
  15 minutes). They train this home's own models and play "Yesterday at home" in the Home view;
  they never reach a business's models (offpeak/db.py reads them only with the profile).
- Business: there is no real client yet, so the demo site's consumption is example data,
  modelled from its machines. The page says so, and shows where a client's real measurements
  will appear once their smart meter or ERP is connected.
"""

import data
import streamlit as st
from ui.components import card_title, header, kpi
from ui.connect import KEPT, connect_card

from offpeak.load import fronius
from offpeak.sites import DEMO_CITY, DEMO_HOME_SINCE

role = data.role()
header(f"{data.site().name} · {DEMO_CITY}", "My data", live=True)

if role == "home":
    slots, where = data.measurements()
    info = fronius.coverage(slots)
    first = info["first"].tz_convert("Europe/Berlin").date() if info["first"] is not None else None
    last = info["last"].tz_convert("Europe/Berlin").date() if info["last"] is not None else None
    shown = f" Kept here now: {first:%-d %b %Y} to {last:%-d %b %Y}." if first else ""
    st.info(
        f"**Real data from Jonas's home.** This Homeowner demo uses the measurements of a real "
        f"house in {DEMO_CITY}: the home of Jonas, one of the offpeak team, with solar panels, "
        f"a battery and a Fronius inverter. Every 15 minutes since "
        f"{DEMO_HOME_SINCE:%-d %B %Y}, when the inverter started recording.{shown}",
        icon=":material/home:",
    )
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi("Days measured", f"{info['days']:,}", note="15-minute values")
    with k2:
        kpi(
            "Measured",
            f"{first:%b %Y} – {last:%b %Y}" if first else "–",
            note="drop a newer export to add days",
        )
    with k3:
        kpi("Kept", KEPT[where], note="only for this home, never for business models")
else:
    where = "none"
    st.info(
        "**Example data.** offpeak has no business client connected yet, so this demo site's "
        "consumption is modelled from its machines (Site & components), not measured. As soon "
        "as a client connects their smart meter or ERP, their real 15-minute measurements "
        "appear here and the plan and savings use them.",
        icon=":material/science:",
    )
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi("Days measured", "0", note="no client connected yet")
    with k2:
        kpi("Consumption", "Example", note="modelled from the site's machines")
    with k3:
        kpi("Kept", KEPT["none"], note="only for this business, never shared")

connect_card(role)  # files in, and the planned direct connections

with st.container(border=True, key="card_privacy"):
    card_title("Your data", "What happens with it")
    if role == "home":
        st.markdown(
            "- Kept for this home only, marked *home*: business models never read it.\n"
            "- Used for: the Home view's measured day and this home's consumption forecast.\n"
            "- Never in the code repository."
        )
    else:
        st.markdown(
            "- Once connected: kept for this business only; home models never read it.\n"
            "- Used for: this site's plan and savings, with its real consumption.\n"
            "- Never in the code repository."
        )
    if where != "none" and st.button("Delete my measurements"):
        data.delete_measurements()
        st.rerun()
