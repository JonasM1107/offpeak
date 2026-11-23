"""The "Connect your consumption data" card, on Settings (both roles) and on My data (homes).

One place to bring an account's own consumption into offpeak: a drag-and-drop field for files,
and the direct connections (smart meter, ERP such as SAP, energy management) with what each
needs. Which connector is available or planned comes from offpeak/load/connectors.py; reading
and checking a file from offpeak/load/fronius.py and offpeak/load/meter.py. This file only
draws them.

What happens with a file:
- A Fronius Solar.web history (homes): checked, then kept for this home after a click
  (data.save_measurements), as before on the My data page.
- Any other consumption export (time + kWh or kW): checked and summarised for this tab. It is
  not stored and not used by the plan yet; the card says so.
"""

from html import escape

import data
import pandas as pd
import streamlit as st

from offpeak.load import connectors, fronius, meter
from ui.components import card_title

KEPT = {"database": "in the database", "session": "in this tab only", "none": "nothing yet"}
UPLOAD_KEY = "meter_upload_{}"  # session key: the last checked consumption export per role


def _tiles(role: str) -> None:
    measured = role == "home" and data.measurements()[1] != "none"
    tiles = []
    for c in connectors.for_role(role):
        if c.key == "fronius" and measured:
            pill, cls = "Connected", "on"
        elif c.status == connectors.AVAILABLE:
            pill, cls = "Available", "ok"
        else:
            pill, cls = "Planned", "plan"
        tiles.append(
            f'<div class="op-conn {cls}"><div class="top"><span class="t">{escape(c.name)}</span>'
            f'<span class="pill">{pill}</span></div><div class="k">{escape(c.kind)}</div>'
            f'<div class="d">{escape(c.how)}</div></div>'
        )
    st.html(f'<div class="op-conns">{"".join(tiles)}</div>')


def _show_export(found: dict) -> None:
    """A checked consumption export: its numbers and the average day."""
    a, b, c = st.columns(3)
    a.metric("Days", f"{found['days']}")
    b.metric("Average per day", f"{found['kwh_per_day']:,.1f} kWh")
    c.metric("Peak", f"{found['peak_kw']:,.1f} kW")
    profile = pd.DataFrame({"kW": found["by_hour"]}, index=pd.Index(range(24), name="Hour"))
    st.caption("Average power per hour of the day (German time)")
    st.bar_chart(profile, height=160, color="#FF5F00")


def connect_card(role: str) -> None:
    """The card: connectors, the drop field and what happened with the last file."""
    with st.container(border=True, key="card_connect"):
        card_title(
            "Connect your consumption data",
            "Your own measurements make the plan and the savings fit you exactly",
        )
        _tiles(role)
        kinds = "a Fronius Solar.web history or " if role == "home" else ""
        st.markdown(
            f"**Drop a file** — {kinds}a consumption export from your smart meter app or ERP "
            "(CSV with a time and a kWh or kW column)."
        )
        upload = st.file_uploader(
            "Consumption file",
            type=["csv"],
            key=f"connect_upload_{role}",
            label_visibility="collapsed",
        )
        if upload is not None:
            _handle(role, upload)
        elif (found := st.session_state.get(UPLOAD_KEY.format(role))) is not None:
            st.info("Your last file, checked in this tab:", icon=":material/description:")
            _show_export(found)


def _handle(role: str, upload) -> None:
    """Read the dropped file: a Fronius history first (homes), else a consumption export."""
    if role == "home":
        try:
            new = fronius.read_csv(upload)
        except (fronius.FroniusFileError, ValueError, pd.errors.ParserError):
            upload.seek(0)  # not a Fronius file: read it again as a consumption export
        else:
            got = fronius.coverage(new)
            gaps = got["missing_slots"]
            st.success(
                f"Fronius history: {got['days']} days, {got['first']:%-d %b %Y} to "
                f"{got['last']:%-d %b %Y}" + (f", {gaps} quarter-hours missing." if gaps else ".")
            )
            if st.button("Keep these measurements", type="primary", key="connect_keep"):
                kept_in = data.save_measurements(new)
                st.toast(f"Kept {KEPT[kept_in]}.", icon=":material/check:")
                st.rerun()
            return
    try:
        slots = meter.read_csv(upload)
    except meter.MeterFileError as err:
        st.error(f"This file cannot be used: {err}")
        return
    found = meter.summary(slots)
    st.session_state[UPLOAD_KEY.format(role)] = found
    st.success(
        f"Consumption export: {found['days']} days, {found['first']:%-d %b %Y} to "
        f"{found['last']:%-d %b %Y}, {found['kwh']:,.0f} kWh in total."
    )
    _show_export(found)
    st.caption(
        "Checked and shown for this tab only, not stored. Using your own consumption in the plan "
        "comes with the direct connections above."
    )
