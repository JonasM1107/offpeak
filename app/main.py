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

# The page files live in views/, not pages/: Streamlit would turn a pages/ folder into its own
# automatic menu and show that briefly before ours.
pages = {
    "Overview": [
        st.Page(
            HERE / "views" / "dashboard.py",
            title="Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(HERE / "views" / "site.py", title="Site view", icon=":material/view_in_ar:"),
        st.Page(HERE / "views" / "analytics.py", title="Analytics", icon=":material/insights:"),
    ],
    "Setup": [
        st.Page(HERE / "views" / "settings.py", title="Settings", icon=":material/settings:"),
    ],
}
st.navigation(pages, position="sidebar").run()
