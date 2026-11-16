"""offpeak dashboard. Start with:  uv run streamlit run app/main.py"""

import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent
# Streamlit only puts app/ on the import path; add the repo root so pages can import offpeak.
sys.path.insert(0, str(HERE.parent))

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
        page("account", "Account", "account_circle"),
    ],
}
current = st.navigation(pages, position="sidebar")
account.apply_cookie()  # after a sign-in or sign-out: write or delete the 24-hour cookie
with st.sidebar:  # who can change shared data, at the bottom of the menu
    who = account.editor()
    st.caption(f"Signed in as {who}" if who else "View only · sign in under Account to edit")
assistant.widget()  # before the page, so it shows even when a page stops early
current.run()
