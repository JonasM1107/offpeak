"""Edit site (Business portal): the layout designer, a page of its own next to the site view.

The site view stays exactly as it is; this page opens the 3D scene in edit mode. The site
is shown on a 64 x 64 grid with the Blender models: drag parts from the list onto the
site, move them, remove them, tap one to set its size and hours. Nothing is stored until
"Save site"; the rules are in offpeak/layout.py and offpeak/components.py, and
data.replace_site checks them again (and the portal) where the site is saved. Saved
parts then stand in the site view where they were placed."""

from dataclasses import replace

import data
import streamlit as st
from ui import layout_designer, site_scene
from ui.components import card_title, header

from offpeak import components, demo_site, layout
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY
from offpeak.tariffs import tariff_for
from offpeak.timeutils import market_today

DRAFT = "site_draft"  # the site being edited; only in this browser tab until it is saved
PICK = "draft_pick"  # the part whose size and hours are shown below the designer
SEEN = "designer_seen"  # the last designer action already handled
MESSAGE = "designer_message"  # why the last action was refused

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


def scene_inputs(site_comps):
    """Prices, weather and tariff for every hour, for these components."""
    assets, _ = components.site_model(site_comps)
    tariff = tariff_for(data.role(), site_comps)  # a household's tariff for a home
    inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
    return demo_site.apply_tariff(inputs, tariff, market_today()), tariff


def site_info() -> dict:
    return {
        "name": data.site().name,
        "city": DEMO_CITY,
        "zone": data.site().zone,
        "date": market_today().isoformat(),
    }


def scene_data(site_comps) -> dict:
    """The layout designer's scene for the draft (planned fresh: the draft changes)."""
    inputs, tariff = scene_inputs(site_comps)
    return site_scene.payload(inputs, site_info(), hour_now, tariff, site_comps, edit=True)


def start_editing(start_from) -> None:
    # forget the fields of an earlier draft: they are keyed by component id, and starting
    # again from the current site brings back the same ids
    for key in [k for k in st.session_state if str(k).startswith("draft_")]:
        del st.session_state[key]
    # copies, so editing the draft never changes the site that is shown until it is saved;
    # parts without a square (the demo site) get their usual spot on the grid
    st.session_state[DRAFT] = layout.auto_place(
        [replace(c, params=dict(c.params)) for c in start_from]
    )


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
            draft.remove(c)  # the part list below resets the pick on the next run
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
    header(f"{data.site().name} · {DEMO_CITY} · {data.site().zone}", "Edit site", live=True)
    st.caption(
        "Lay out your site like it really is: drag parts from the left onto the squares, "
        "drag them around, tap one to set its size and hours. Nothing is saved until you "
        "press Save site."
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
        del st.session_state[DRAFT]  # nothing was saved: back to the site view as it was
        st.switch_page("views/site.py")
    status = st.container()  # "saved" or what stops the save, right under the buttons
    if MESSAGE in st.session_state:  # what the last drag or drop could not do
        status.warning(st.session_state.pop(MESSAGE), icon=":material/info:")

    # The layout designer reports one action at a time; offpeak/layout.py decides if it is
    # allowed. Streamlit returns the last action on every rerun, so each is handled once.
    event = layout_designer.show(
        scene_data(draft), draft, st.session_state.get(PICK), key="designer"
    )
    if event and event.get("n") != st.session_state.get(SEEN):
        st.session_state[SEEN] = event.get("n")
        st.session_state[DRAFT], picked, problem = layout.apply(draft, event)
        st.session_state[PICK] = picked
        if problem:
            st.session_state[MESSAGE] = problem
        st.rerun()

    with st.expander("Add without dragging", icon=":material/keyboard:"):
        st.caption("Each part goes on the next free square; drag it to its place later.")
        for col, (role, label) in zip(st.columns(4), ROLES.items(), strict=True):
            col.caption(label)
            for kind in (k for k in components.CATALOGUE.values() if k.role == role):
                if col.button(
                    kind.label,
                    key=f"add_{kind.key}",
                    icon=f":material/{ICONS.get(kind.key, 'bolt')}:",
                    width="stretch",
                    disabled=len(draft) >= components.MAX_COMPONENTS,
                    help=kind.description,
                ):
                    st.session_state[DRAFT], picked, problem = layout.apply(
                        draft, {"action": "add", "kind": kind.key}
                    )
                    st.session_state[PICK] = picked
                    if problem:
                        st.session_state[MESSAGE] = problem
                    st.rerun()

    settings, check = st.columns([2, 3], gap="medium")
    with settings:
        card_title("Size and hours", f"{len(draft)} of at most {components.MAX_COMPONENTS} parts")
        if not draft:
            st.info("Your site is empty. Drag what you have on site from the parts list.")
        else:
            names = {
                c.id: c.name if c.name == c.spec.label else f"{c.name} · {c.spec.label}"
                for c in draft
            }
            if st.session_state.get(PICK) not in names:
                st.session_state[PICK] = None
            picked = st.selectbox(
                "Part",
                list(names),
                format_func=names.get,
                index=None,
                placeholder="Tap a part on the site, or pick it here",
                key=PICK,
                label_visibility="collapsed",
            )
            chosen = next((c for c in draft if c.id == picked), None)
            if chosen is not None:
                component_card(chosen, draft)
    with check:
        # e.g. a part that grew (more kWp, more chargers) now reaches into its neighbour
        card_title("Layout check", "Shown before you save")
        problems = layout.layout_problems(draft)
        for problem in problems:
            st.warning(problem, icon=":material/warning:")
        if draft and not problems:
            st.success("Everything fits.", icon=":material/check_circle:")

    if save:
        where, problems = data.replace_site(draft)
        if problems:
            status.error("Not saved yet:\n\n" + "\n".join(f"- {p}" for p in problems))
        else:
            del st.session_state[DRAFT]
            st.session_state["site_saved"] = SAVED[where]  # shown after the rerun below
            st.rerun()


if data.role() != "business":
    # the menu shows this page to Business accounts only; an address typed by hand lands here
    header(f"{data.site().name} · {DEMO_CITY}", "Edit site", live=True)
    st.info("Edit site is part of the Business portal.", icon=":material/info:")
    st.page_link("views/site.py", label="Back to the site view", icon=":material/arrow_back:")
    st.stop()

if DRAFT not in st.session_state:
    # A blank site to lay out the first time; once the user saved their own layout, that
    # one, so they keep working on it. Either way the other start is one button away.
    start_editing(comps if source in ("database", "local") else [])
if "site_saved" in st.session_state:
    st.success(st.session_state.pop("site_saved"), icon=":material/check_circle:")
    st.page_link("views/site.py", label="See it in the site view", icon=":material/view_in_ar:")
editor()
