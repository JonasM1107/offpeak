"""Sign in: editors (the team) sign in to save changes to the site's components and cockpit
machines for everyone. Visitors can use every page without signing in."""

from datetime import UTC, datetime

import streamlit as st
from ui import account
from ui.components import card_title, header

from offpeak import auth

header("Setup", "Account", live=True)
who = account.editor()
left, _ = st.columns([1.1, 1])
with left, st.container(border=True, key="card_account"):
    if who:
        card_title("You are signed in", f"as {who}")
        st.markdown(
            "Changes to the site's components and the cockpit machines are saved for everyone. "
            f"You stay signed in on this browser for {auth.SESSION_HOURS} hours."
        )
        if st.button("Sign out", icon=":material/logout:"):
            account.sign_out()
            st.rerun()
    else:
        card_title("Sign in to edit", "For the offpeak team")
        st.caption(
            "Everyone can explore the app. Signed-in editors save changes to the site and "
            "the cockpit for everyone; without signing in, changes stay in this browser tab."
        )
        with st.form("sign_in", border=False):
            email = st.text_input("Email", max_chars=200, autocomplete="email")
            password = st.text_input(
                "Password", type="password", max_chars=200, autocomplete="current-password"
            )
            if st.form_submit_button("Sign in", type="primary", icon=":material/login:"):
                problem = account.sign_in(email, password)
                if problem:
                    st.error(problem)
                else:
                    st.session_state["just_signed_in"] = datetime.now(UTC)
                    st.rerun()
if who and st.session_state.pop("just_signed_in", None):
    st.toast("Signed in. Your changes are now saved for everyone.", icon=":material/check:")
