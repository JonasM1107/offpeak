"""Site & components: the machines on the demo site, with a form to add or remove them.
Every change shows up in the site view's 3D model, day plan and fact sheets."""

import data
import pandas as pd
import streamlit as st
from ui.components import card_title, header

from offpeak import components
from offpeak.sites import DEMO_CITY, DEMO_SITE

header(f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}", "Site & components", live=True)
comps, source = data.site_components()

with st.container(border=True, key="card_list"):
    card_title("On this site", f"{len(comps)} components, grouped by what they do")
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
    st.page_link("views/site.py", label="See them in the site view", icon=":material/view_in_ar:")

st.write("")
SAVED = {
    "database": "Changes are saved for everyone using this site.",
    "demo": "Showing the demo components. Your first change saves them together with it.",
    "session": "No database connected: changes last until you reload the page.",
}
add, remove = st.columns([2, 1], gap="medium")
with add, st.container(border=True, key="card_add"):
    card_title(
        "Add a component", "New solar, a second turbine, a heat pump: it appears in the model"
    )
    labels = {k.label: k.key for k in components.CATALOGUE.values()}
    kind = labels[st.selectbox("Type", list(labels))]
    spec = components.CATALOGUE[kind]
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
                    step=1.0,
                    key=f"{kind}_{p.key}",
                )
        st.caption(spec.description)
        if st.form_submit_button("Add to site", type="primary"):
            problems = components.validate(kind, params)
            if problems:
                st.error(" · ".join(problems))
            else:
                data.add_component(
                    components.new_component(kind, name.strip() or spec.label, params)
                )
                st.rerun()
    st.caption(SAVED[source])

with remove, st.container(border=True, key="card_remove"):
    card_title("Remove a component", f"{len(comps)} on this site")
    names = {f"{c.name} · {c.spec.label}": c.id for c in comps}
    picked = st.selectbox("Component", list(names), label_visibility="collapsed")
    if st.button("Remove", disabled=not names):
        data.remove_component(names[picked])
        st.rerun()
