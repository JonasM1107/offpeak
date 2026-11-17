"""The landing page: what a visitor who is not signed in sees at the app's address.

Like a SaaS start-up's homepage: what offpeak is, how it works, pricing, and a Login button.
The page is static HTML (web/landing.html), with no data calls, so it opens fast and cannot
break when a price or weather source is down. It covers the whole window; the visitor
scrolls inside it.

Its Login buttons press the hidden Streamlit button "Login" below (the frame may reach this
page because both come from the same server). That sets "login_open", and the sign-in
screen takes over (see main.py).
"""

import streamlit as st

from ui.web import WEB, with_field

PAGE = WEB / "landing.html"

# The frame fills the window, above Streamlit's own header; the Login button stays hidden.
CSS = """<style>
[data-testid=stSidebar], [data-testid=stSidebarCollapsedControl], [data-testid=stHeader],
[data-testid=stToolbar], [data-testid=stDecoration] { display: none !important; }
.st-key-landing iframe { position: fixed; inset: 0; width: 100vw !important;
    height: 100vh !important; height: 100dvh !important; border: 0; z-index: 999990; }
.st-key-landing_login { display: none !important; }
#op-portal { display: block !important; }  /* the Login core (landing.html: core) */
</style>"""

LOGIN_OPEN = "login_open"


def login_wanted() -> bool:
    """True once the visitor pressed Login, or opened the address with ?login."""
    if "login" in st.query_params:
        st.session_state[LOGIN_OPEN] = True
    return bool(st.session_state.get(LOGIN_OPEN))


def back_home() -> None:
    """From the sign-in screen back to the landing page."""
    st.session_state[LOGIN_OPEN] = False
    if "login" in st.query_params:
        del st.query_params["login"]


def show() -> None:
    st.html(CSS)
    if st.button("Login", key="landing_login"):
        st.session_state[LOGIN_OPEN] = True
        st.rerun()
    with st.container(key="landing"):
        # Our own file, never user input, so the frame may run its script.
        st.iframe(with_field(PAGE.read_text()), height=900)
