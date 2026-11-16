"""Account: who is signed in, and signing out. Signing in happens on the login screen in
front of the app (app/ui/account.py)."""

import streamlit as st
from ui import account
from ui.components import card_title, header

from offpeak import auth

header("Setup", "Account", live=True)
left, _ = st.columns([1.1, 1])
with left, st.container(border=True, key="card_account"):
    card_title("You are signed in", f"as {account.editor()}")
    st.markdown(
        "Changes to the site's components and the cockpit machines are saved for everyone. "
        f"You stay signed in on this browser for {auth.SESSION_HOURS} hours after signing in."
    )
    if st.button("Sign out", icon=":material/logout:"):
        account.sign_out()
        st.rerun()
