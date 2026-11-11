"""offpeak dashboard. Start with:  uv run streamlit run app/main.py"""

import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent
# Streamlit only puts app/ on the import path; add the repo root so pages can import offpeak.
sys.path.insert(0, str(HERE.parent))

from ui.components import inject_css  # noqa: E402

st.set_page_config(page_title="offpeak", page_icon="⚡", layout="wide")
st.logo(str(HERE / "assets" / "mark.svg"), size="large")
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
    "Forecasts": [
        page("analytics", "Prices", "show_chart"),
        page("weather", "Weather & solar", "partly_cloudy_day"),
    ],
    "Results": [
        page("tariff", "Tariff calculator", "receipt_long"),
    ],
    "Setup": [
        page("components", "Site & components", "precision_manufacturing"),
        page("settings", "Settings", "settings"),
    ],
}
st.navigation(pages, position="sidebar").run()
