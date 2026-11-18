"""The site designer at the top of Site & components (Business portal): the 3D site on a
64 x 64 grid, where parts are dragged on, moved and removed.

There is one site, not a copy to edit: every action is saved straight away
(data.replace_site, which checks the site rules and the layout rules again where it is
saved). So the designer, the table and the add and remove forms below it, and the site view
always show the same site. Where each part stands is kept with the part in the database
(col and row in its params, offpeak/layout.py).
"""

import data
import streamlit as st

from offpeak import components, demo_site, layout
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY
from offpeak.tariffs import tariff_for
from offpeak.timeutils import market_today
from ui import layout_designer, site_scene
from ui.components import card_title

PICK = "designer_pick"  # the part whose size and hours are shown under the designer
SEEN = "designer_seen"  # the last designer action already handled
MESSAGE = "designer_message"  # why the last action was refused, shown after the rerun
SCHEDULE_KEYS = ("hours", "earliest", "latest_end", "usual_start")


def on_the_grid(comps) -> list[components.Component]:
    """The saved site as the designer shows it: every part with a name of its own and a
    square (parts added before the designer existed have none yet). Saved like this with
    the first change made in the designer."""
    return layout.auto_place(components.unique_names(comps))


def _scene(site_comps) -> dict:
    """The 3D scene in edit mode. The day is planned once per set of parts (data.site_day):
    where a part stands does not change the plan, so moving one plans nothing again."""
    try:
        today_prices, _, _, _ = data.today_and_tomorrow()
    except PriceSourceError:
        today_prices = None  # the scene falls back to the demo price curve
    weather, _, _, _ = data.weather()
    assets, _ = components.site_model(site_comps)
    tariff = tariff_for(data.role(), site_comps)
    inputs = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
    inputs = demo_site.apply_tariff(inputs, tariff, market_today())
    unplaced = [layout.without_position(c) for c in site_comps]
    day = data.site_day(inputs, data.setup_key(unplaced), data.role())
    site = {
        "name": data.site().name,
        "city": DEMO_CITY,
        "zone": data.site().zone,
        "date": market_today().isoformat(),
    }
    hour_now = data.now_utc().tz_convert(MARKET_TZ).hour
    return site_scene.payload(inputs, site, hour_now, tariff, site_comps, day=day, edit=True)


def _save(new) -> list[str]:
    """Save the site as it is now; returns what stopped it (empty list = saved)."""
    where, problems = data.replace_site(new)
    return problems if where is None else []


def _size_and_hours(c: components.Component, site_comps) -> None:
    """The picked part's name, size and (for machines) hours. A change is saved as soon as
    it is valid; until then the fields keep what was typed and say what is wrong."""
    spec = c.spec
    changed = components.Component(c.id, c.kind, c.name, dict(c.params), c.profile)
    with st.container(border=True, key=f"designer_card_{c.id}"):
        name_key = f"designer_{c.id}_name"
        st.session_state.setdefault(name_key, c.name)
        changed.name = st.text_input(
            f"{spec.label}", key=name_key, max_chars=components.MAX_NAME
        ).strip()
        size = [p for p in spec.params if p.key not in SCHEDULE_KEYS]
        when = [p for p in spec.params if p.key in SCHEDULE_KEYS]
        for row in (size, when):
            if not row:
                continue
            if row is when:
                st.caption("When it may run (hour of the day)")
            for start in range(0, len(row), 2):  # two fields side by side
                for col, p in zip(st.columns(2), row[start : start + 2], strict=False):
                    key = f"designer_{c.id}_{p.key}"
                    st.session_state.setdefault(key, float(c.p(p.key)))
                    changed.params[p.key] = col.number_input(
                        f"{p.label} ({p.unit})" if p.unit else p.label,
                        min_value=float(p.min),
                        max_value=float(p.max),
                        step=1.0,
                        key=key,
                    )
    # the fields give 120.0 for a stored 120 and fill in defaults, so compare the values
    edited = any(float(c.p(p.key)) != changed.params[p.key] for p in spec.params)
    if changed.name == c.name.strip() and not edited:
        return  # nothing changed, nothing to save
    problems = components.validate(c.kind, changed.params)
    if not problems:
        new = [changed if x.id == c.id else x for x in site_comps]
        problems = _save(new)
        if not problems:
            st.rerun()  # the designer, the table and the site view show the change
    st.warning(" · ".join(problems), icon=":material/error:")


def show(comps) -> None:
    """The designer and, under it, the picked part's size and hours."""
    site_comps = on_the_grid(comps)
    with st.container(border=True, key="card_designer"):
        card_title(
            "Site layout",
            "Drag parts from the list onto the squares, move them, tap one to set its size "
            "and hours. Every change is saved at once and shows up in the site view.",
        )
        if MESSAGE in st.session_state:  # what the last drag or drop could not do
            st.warning(st.session_state.pop(MESSAGE), icon=":material/info:")
        # The designer reports one action at a time; offpeak/layout.py decides if it is
        # allowed. Streamlit returns the last action on every rerun, so each is handled once.
        event = layout_designer.show(
            _scene(site_comps), site_comps, st.session_state.get(PICK), key="designer"
        )
        if event and event.get("n") != st.session_state.get(SEEN):
            st.session_state[SEEN] = event.get("n")
            new, picked, problem = layout.apply(site_comps, event)
            st.session_state[PICK] = picked
            if problem is None and new != site_comps:
                problems = _save(new)
                problem = " · ".join(problems) if problems else None
            if problem:
                st.session_state[MESSAGE] = problem
            st.rerun()
        picked = next((c for c in site_comps if c.id == st.session_state.get(PICK)), None)
        if picked is not None:
            _size_and_hours(picked, site_comps)
        else:
            st.caption("Tap a part on the site to set its size and hours.")
