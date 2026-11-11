"""offpeak dashboard. Start with:  uv run streamlit run app/main.py"""

import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent
# Streamlit only puts app/ on the import path; add the repo root so pages can import offpeak.
sys.path.insert(0, str(HERE.parent))

from ui.components import inject_css  # noqa: E402

st.set_page_config(page_title="offpeak", page_icon="⚡", layout="wide")
st.logo(str(HERE / "assets" / "logo.svg"), size="large")
inject_css()

pages = {
    "Overview": [
        st.Page(
            HERE / "pages" / "dashboard.py",
            title="Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(HERE / "pages" / "analytics.py", title="Analytics", icon=":material/insights:"),
    ],
    "Setup": [
        st.Page(HERE / "pages" / "settings.py", title="Settings", icon=":material/settings:"),
    ],
}
st.navigation(pages, position="sidebar").run()
