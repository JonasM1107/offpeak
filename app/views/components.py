"""Site & components (business) or Home & devices (homeowner): what is on the signed-in
role's site, with a form to add or remove it. The site plan comes first
(ui/site_designer.py): drag and drop, saved at once, so plan, table and 3D view agree.
Each role picks from its own catalogue (offpeak/components.py); app/data.py checks again
where it is saved. Every change shows up in the site or home view's 3D model, day plan and
fact sheets."""

import data
import pandas as pd
import streamlit as st
from ui import site_designer
from ui.components import card_title, header

from offpeak import components, roles
from offpeak.sites import DEMO_CITY

profile, here = data.role(), data.site()
w = roles.words(profile)
catalogue = components.CATALOGUES[profile]
header(f"{here.name} · {DEMO_CITY} · {here.zone}", w["setup"], live=True)
comps, source = data.site_components()
site_designer.show(comps)
st.write("")

with st.container(border=True, key="card_list"):
    card_title(f"In this {w['site']}", f"{len(comps)} {w['machines']}, grouped by what they do")
    ROLES = {
        "generation": "Generation",
        "storage": "Storage",
        "flexible": "Flexible load",
        "base": "Base load",
    }
    table = pd.DataFrame(
        [
            {
                "Name": c.name,
                "Type": c.spec.label,
                "Role": ROLES[c.spec.role],
                "Size": " · ".join(
                    f"{c.p(p.key):g} {p.unit}".strip()
                    for p in c.spec.params
                    if p.key not in ("hours", "earliest", "latest_end", "usual_start")
                ),
                "Allowed hours": (
                    f"{c.p('earliest'):02.0f}–{c.p('latest_end'):02.0f}, {c.p('hours'):g} h a day"
                    if c.spec.role == "flexible"
                    else "–"
                ),
            }
            for c in sorted(comps, key=lambda c: list(ROLES).index(c.spec.role))
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.page_link(
        "views/site.py", label=f"See them in the {w['view'].lower()}", icon=":material/view_in_ar:"
    )

st.write("")
SAVED = {
    "database": f"Changes are saved for everyone using this {w['site']}.",
    "demo": "Showing the demo components. Your first change saves them together with it.",
    "session": "No database connected: changes last until you reload the page.",
    "local": "You're not signed in: changes stay in this browser tab. Sign in under "
    "Account to save them for everyone.",
}
add, remove = st.columns([2, 1], gap="medium")
with add, st.container(border=True, key="card_add"):
    card_title(
        f"Add to the {w['site']}",
        "A heat pump, a second wallbox, a dishwasher: it appears in the model"
        if profile == "home"
        else "New solar, a second turbine, a heat pump: it appears in the model",
    )
    labels = {k.label: k.key for k in catalogue.values()}
    kind = labels[st.selectbox("Type", list(labels))]
    spec = catalogue[kind]
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
                    # 0.1 kW steps for small devices; counts and hours stay whole numbers
                    step=0.1 if p.unit == "kW" and p.max <= 5 else 1.0,
                    key=f"{kind}_{p.key}",
                )
        st.caption(spec.description)
        if st.form_submit_button(f"Add to {w['site']}", type="primary"):
            problems = components.validate(kind, params, profile)
            if problems:
                st.error(" · ".join(problems))
            else:
                new = components.new_component(kind, name.strip() or spec.label, params, profile)
                try:
                    data.add_component(new)
                except ValueError:  # not part of this role's catalogue: refused where saved
                    st.error(f"This cannot be added to a {roles.LABELS[profile]} account.")
                else:
                    st.rerun()
    st.caption(SAVED[source])

with remove, st.container(border=True, key="card_remove"):
    card_title(f"Remove from the {w['site']}", f"{len(comps)} {w['machines']}")
    names = {f"{c.name} · {c.spec.label}": c.id for c in comps}
    picked = st.selectbox("Component", list(names), label_visibility="collapsed")
    if st.button("Remove", disabled=not names):
        data.remove_component(names[picked])
        st.rerun()
