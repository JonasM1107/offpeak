"""Site view: a 3D model of the site, a day plan per machine and a fact sheet per component.

"Edit site" switches the page into an editor: the user rebuilds the site to match their own
facility (start empty or from the current site, add components from a palette, set their
sizes and hours) with the 3D model as a live preview. Nothing is stored until "Save site";
the rules for what may be saved are in offpeak/components.py (validate_site), and data.py
checks them again where the site is saved."""

from dataclasses import replace

import data
import streamlit as st
from ui import site_scene
from ui.components import card_title, header

from offpeak import components, demo_site
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.tariffs import germany_2026
from offpeak.timeutils import market_today

DRAFT = "site_draft"  # the site being edited; only in this browser tab until it is saved

ROLES = {
    "generation": "Generation",
    "storage": "Storage",
    "flexible": "Flexible machines",
    "base": "Always on",
}
ICONS = {
    "pv_field": "solar_power",
    "pv_roof": "roofing",
    "wind": "wind_power",
    "battery": "battery_charging_full",
    "heat_pump": "heat_pump",
    "ev_charger": "ev_station",
    "furnace": "local_fire_department",
    "cold_store": "ac_unit",
}
# when a flexible machine may run: shown in their own row under its size
SCHEDULE_KEYS = ("hours", "earliest", "latest_end", "usual_start")
SAVED = {
    "database": "Saved for everyone using this site.",
    "local": "Saved in this browser tab only. Sign in to save it for everyone.",
    "session": "No database connected: the site is kept until you reload the page.",
}

try:
    today_prices, _, _, _ = data.today_and_tomorrow()
except PriceSourceError:
    today_prices = None  # the page falls back to the demo price curve and says so
weather, _, _, _ = data.weather()
comps, source = data.site_components()
hour_now = data.now_utc().tz_convert(MARKET_TZ).hour


def scene(site_comps, compact: bool = False) -> None:
    """Draw the 3D site for a list of components (the saved site or the draft)."""
    assets, _ = components.site_model(site_comps)
    tariff = germany_2026(pv_kwp=assets.pv_kwp)
    inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
    inputs = demo_site.apply_tariff(inputs, tariff, market_today())
    site = {
        "name": DEMO_SITE.name,
        "city": DEMO_CITY,
        "zone": DEMO_SITE.zone,
        "date": market_today().isoformat(),
    }
    payload = site_scene.payload(inputs, site, hour_now, tariff, site_comps, compact=compact)
    site_scene.show(payload)


def start_editing(start_from) -> None:
    # forget the fields of an earlier draft: they are keyed by component id, and starting
    # again from the current site brings back the same ids
    for key in [k for k in st.session_state if str(k).startswith("draft_")]:
        del st.session_state[key]
    # copies, so editing the draft never changes the site that is shown until it is saved
    st.session_state[DRAFT] = [replace(c, params=dict(c.params)) for c in start_from]


def component_card(c: components.Component, draft: list) -> None:
    """One component of the draft: its name, size and (for machines) when it may run.
    The widgets write straight back into the draft, so the preview follows every change."""
    spec = c.spec
    with st.container(border=True, key=f"draft_card_{c.id}"):
        top, rm = st.columns([6, 1], vertical_alignment="bottom")
        name_key = f"draft_{c.id}_name"
        st.session_state.setdefault(name_key, c.name)
        c.name = top.text_input(
            f":material/{ICONS.get(c.kind, 'bolt')}: {spec.label} · {ROLES[spec.role]}",
            key=name_key,
            max_chars=components.MAX_NAME,
        )
        if rm.button(
            "", key=f"draft_{c.id}_rm", icon=":material/delete:", help="Remove from the site"
        ):
            draft.remove(c)
            st.rerun()
        size = [p for p in spec.params if p.key not in SCHEDULE_KEYS]
        when = [p for p in spec.params if p.key in SCHEDULE_KEYS]
        for row in (size, when):
            if not row:
                continue
            if row is when:
                st.caption("When it may run (hour of the day)")
            for start in range(0, len(row), 2):  # two fields side by side
                for col, p in zip(st.columns(2), row[start : start + 2], strict=False):
                    key = f"draft_{c.id}_{p.key}"
                    st.session_state.setdefault(key, float(c.p(p.key)))
                    c.params[p.key] = col.number_input(
                        f"{p.label} ({p.unit})" if p.unit else p.label,
                        min_value=float(p.min),
                        max_value=float(p.max),
                        step=1.0,
                        key=key,
                    )
        problems = components.validate(c.kind, c.params)
        if problems:
            st.warning(" · ".join(problems), icon=":material/error:")


def editor() -> None:
    draft = st.session_state[DRAFT]
    header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Edit site", live=True)
    st.caption(
        "Build the site to match your own facility. Add what you have from the palette, "
        "set sizes and hours, and watch the model change. Nothing is saved until you press "
        "Save site."
    )
    bar = st.columns([1.3, 1.6, 1, 1, 2.5])
    if bar[0].button("Start empty", icon=":material/crop_free:"):
        start_editing([])
        st.rerun()
    if bar[1].button("Start from current site", icon=":material/restart_alt:"):
        start_editing(comps)
        st.rerun()
    save = bar[2].button("Save site", type="primary", icon=":material/save:")
    if bar[3].button("Cancel", icon=":material/close:"):
        del st.session_state[DRAFT]
        st.rerun()
    status = st.container()  # "saved" or what stops the save, right under the buttons

    with st.container(border=True, key="card_palette"):
        card_title("Add to your site", "Tap a component to add it with typical values")
        for col, (role, label) in zip(st.columns(4), ROLES.items(), strict=True):
            col.caption(label)
            for kind in (k for k in components.CATALOGUE.values() if k.role == role):
                full = len(draft) >= components.MAX_COMPONENTS
                if col.button(
                    kind.label,
                    key=f"add_{kind.key}",
                    icon=f":material/{ICONS.get(kind.key, 'bolt')}:",
                    width="stretch",
                    disabled=full,
                    help=kind.description,
                ):
                    draft.append(
                        components.new_component(kind.key, components.next_name(kind.key, draft))
                    )
                    st.rerun()

    preview, edit = st.columns([3, 2], gap="medium")
    with edit:
        card_title(
            "On your site",
            f"{len(draft)} of at most {components.MAX_COMPONENTS} components",
        )
        if not draft:
            st.info("Your site is empty. Add what you have on site from the palette above.")
        for c in list(draft):
            component_card(c, draft)
    with preview:
        scene(draft, compact=True)

    if save:
        where, problems = data.replace_site(draft)
        if problems:
            status.error("Not saved yet:\n\n" + "\n".join(f"- {p}" for p in problems))
        else:
            del st.session_state[DRAFT]
            st.session_state["site_saved"] = SAVED[where]  # shown after the rerun below
            st.rerun()


if DRAFT in st.session_state:
    editor()
else:
    header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Site view", live=True)
    if "site_saved" in st.session_state:
        st.success(st.session_state.pop("site_saved"), icon=":material/check_circle:")
    # pressed by the "Edit site" tab inside the 3D view (site_scene.html), so it stays hidden
    st.html("<style>.st-key-site_edit { display: none !important; }</style>")
    if st.button("Edit site", key="site_edit"):
        start_editing([])
        st.rerun()
    scene(comps)
    st.page_link(
        "views/components.py",
        label="Add or remove components under Setup → Site & components",
        icon=":material/add_circle:",
    )
