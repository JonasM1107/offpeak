"""offpeak dashboard. Start with:  uv run streamlit run app/main.py"""

import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent
# Streamlit only puts app/ on the import path; add the repo root so pages can import offpeak.
sys.path.insert(0, str(HERE.parent))

import freshness  # noqa: E402
import perf  # noqa: E402

freshness.refresh()  # after a deploy: load the new versions of our modules (see freshness.py)

from ui import account, assistant, landing  # noqa: E402
from ui.components import inject_css  # noqa: E402

from offpeak import roles  # noqa: E402

st.set_page_config(page_title="offpeak", page_icon="⚡", layout="wide")
st.logo(str(HERE / "assets" / "logo.svg"), size="large")
inject_css()


def page(file: str, title: str, icon: str, default: bool = False) -> st.Page:
    return st.Page(
        HERE / "views" / f"{file}.py", title=title, icon=f":material/{icon}:", default=default
    )


# The page files live in views/, not pages/: Streamlit would turn a pages/ folder into its own
# automatic menu and show that briefly before ours.
#
# Both roles get the same pages (one file per purpose, never a copy per role); only some titles
# differ (offpeak/roles.py: WORDS), and every page takes its site and its components from the
# signed-in account's role (app/data.py: site, site_components), never from the address.
account.sync_browser()  # stored sign-in from this browser; saves a new one after a sign-in
who = account.editor()
words = roles.words(account.role() or "business")
home = page("dashboard", "Dashboard", "dashboard", default=True)
pages = {
    "Overview": [
        home,
        page("site", words["view"], "view_in_ar" if words["site"] == "site" else "cottage"),
        page("savings", "Savings", "savings"),
    ],
    "Analytics": [
        page("analytics", "Power", "show_chart"),
        page("weather", "Weather & solar", "partly_cloudy_day"),
        page("outlook", "Price outlook", "online_prediction"),
        page("cockpit", words["planner"], "tune"),
    ],
    "Setup": [
        page("components", words["setup"], "precision_manufacturing"),
        page("my_data", "My data", "monitoring"),
        page("settings", "Settings", "settings"),
    ],
}
# not in the menu: reached through the name at the bottom of the sidebar
account_page = st.Page(
    HERE / "views" / "account.py",
    title="Account",
    icon=":material/account_circle:",
    visibility="hidden",
)
pages["Setup"].append(account_page)
# Sign in first: the app is only for the team. The page asked for in the address stays
# selected, so after signing in it opens where the link pointed.
current = st.navigation(pages, position="sidebar" if who else "hidden")
# One slot for everything shown before signing in (landing page or sign-in card). Streamlit
# keeps an element of the last run on screen until this run draws something in its place, so
# without the slot the sign-in card would stand over the dashboard for the seconds the
# dashboard needs to load. Signed in, the slot stays empty and clears the card at once.
gate = st.empty()
if not who:
    # The app's plain address shows the landing page until the visitor presses Login. A link
    # to a page inside the app goes straight to the sign-in. While the browser still looks for
    # a stored sign-in, login_screen shows a short wait, so a signed-in visitor never sees the
    # landing page flash by.
    with gate.container():
        if current is home and account.browser_answered() and not landing.login_wanted():
            landing.show()
        else:

            def back_home() -> None:
                landing.back_home()
                st.session_state.pop(account.ROLE_CHOICE, None)  # Login starts with the cards
                st.switch_page(home)

            account.login_screen(back=back_home)
    st.stop()
note = st.session_state.pop("role_note", None)  # e.g. no database: the role holds here only
if note:
    st.toast(note, icon=":material/info:")
with st.sidebar, st.container(key="account_link"):  # the editor's name, at the very bottom
    st.page_link(account_page, label=account.editor_name(who), icon=":material/account_circle:")
assistant.widget()  # before the page, so it shows even when a page stops early
with perf.timed(current.title):  # server time per page, shown on the Account page
    current.run()
