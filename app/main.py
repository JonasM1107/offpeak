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

from ui import account, assistant  # noqa: E402
from ui.components import inject_css  # noqa: E402

st.set_page_config(page_title="offpeak", page_icon="⚡", layout="wide")
st.logo(str(HERE / "assets" / "logo.svg"), size="large")
inject_css()


def page(file: str, title: str, icon: str, default: bool = False) -> st.Page:
    return st.Page(
        HERE / "views" / f"{file}.py", title=title, icon=f":material/{icon}:", default=default
    )


# The page files live in views/, not pages/: Streamlit would turn a pages/ folder into its own
# automatic menu and show that briefly before ours.
pages = {
    "Overview": [
        page("dashboard", "Dashboard", "dashboard", default=True),
        page("site", "Site view", "view_in_ar"),
    ],
    "Analytics": [
        page("analytics", "Power", "show_chart"),
        page("weather", "Weather & solar", "partly_cloudy_day"),
        page("outlook", "Price outlook", "online_prediction"),
        page("cockpit", "Simulation cockpit", "tune"),
    ],
    "Results": [
        page("savings", "Savings", "savings"),
        page("tariff", "Tariff calculator", "receipt_long"),
    ],
    "Setup": [
        page("components", "Site & components", "precision_manufacturing"),
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
account.sync_browser()  # stored sign-in from this browser; saves a new one after a sign-in
who = account.editor()
current = st.navigation(pages, position="sidebar" if who else "hidden")
if not who:
    account.login_screen()
    st.stop()
with st.sidebar, st.container(key="account_link"):  # the editor's name, at the very bottom
    st.page_link(account_page, label=account.editor_name(who), icon=":material/account_circle:")
assistant.widget()  # before the page, so it shows even when a page stops early
with perf.timed(current.title):  # server time per page, shown on the Account page
    current.run()
