"""My data (homeowners only): bring the house's measurements from Fronius Solar.web into
offpeak. They train this home's own models and play "Yesterday at home" in the Home view;
they never reach a business's models (offpeak/db.py reads them only with the profile)."""

from datetime import date, timedelta

import data
import streamlit as st
from ui.components import card_title, header, kpi

from offpeak.load import fronius
from offpeak.sites import DEMO_CITY

FIRST_DAY = date(2023, 9, 16)  # the demo home's first day with its Fronius inverter

header(f"{data.site().name} · {DEMO_CITY}", "My data", live=True)
if data.role() != "home":
    st.info("Measured data is part of the Homeowner portal.")
    st.stop()

slots, where = data.measurements()
info = fronius.coverage(slots)
k1, k2, k3 = st.columns(3)
with k1:
    kpi("Days measured", f"{info['days']:,}", note="15-minute values")
with k2:
    last = info["last"].tz_convert("Europe/Berlin").date() if info["last"] is not None else None
    kpi("Newest day", f"{last:%a %-d %b %Y}" if last else "–", note="sync again to add new days")
with k3:
    kept = {"database": "in the database", "session": "in this tab only", "none": "nothing yet"}
    kpi("Kept", kept[where], note="only for this home, never for business models")

since = (last + timedelta(days=1)) if last else FIRST_DAY
with st.container(border=True, key="card_sync_1"):
    card_title(
        "1 · Get the new days from Solar.web",
        f"From {since:%-d %b %Y} to yesterday, in a few seconds per month",
    )
    st.markdown(
        "Open your system's chart page on **solarweb.com** (Analyse → Energiebilanz) while "
        "signed in, open the browser console (⌥⌘J in Chrome), paste this and press Enter. It "
        "reads the same data the Solar.web charts show, changes nothing, and downloads "
        "`fronius_5min.csv`."
    )
    st.code(
        (
            f"const FIRST = new Date({since.year}, {since.month - 1}, {since.day});\n"
            + fronius.SYNC_SCRIPT
        ),
        language="javascript",
    )

with st.container(border=True, key="card_sync_2"):
    card_title("2 · Add the file here", "Checked before anything is kept")
    upload = st.file_uploader("fronius_5min.csv", type=["csv"], label_visibility="collapsed")
    if upload is not None:
        try:
            new = fronius.read_csv(upload)
        except (fronius.FroniusFileError, ValueError) as err:
            st.error(f"This file cannot be used: {err}")
        else:
            got = fronius.coverage(new)
            gaps = got["missing_slots"]
            st.success(
                f"{got['days']} days, {got['first']:%-d %b %Y} to {got['last']:%-d %b %Y}"
                + (f", {gaps} quarter-hours missing." if gaps else ".")
            )
            if st.button("Keep these measurements", type="primary"):
                kept_in = data.save_measurements(new)
                st.toast(f"Kept {kept[kept_in]}.", icon=":material/check:")
                st.rerun()

with st.container(border=True, key="card_privacy"):
    card_title("Your data", "What happens with it")
    st.markdown(
        "- Kept for this home only, marked *home*: business models never read it.\n"
        "- Used for: the Home view's measured day and this home's consumption forecast.\n"
        "- Never in the code repository."
    )
    if where != "none" and st.button("Delete my measurements"):
        data.delete_measurements()
        st.rerun()
