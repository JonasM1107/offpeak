"""Interactive views: an HTML template in app/ui/web/ plus one JSON payload from Python.

Every view gets the shared look (kit.css), helpers (kit.js) and ECharts. The view sizes
its own frame, so the height given here is only the first guess before it loads.
"""

import hashlib
import json
from pathlib import Path

import streamlit.components.v1 as components

WEB = Path(__file__).with_name("web")
ECHARTS = "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"
# A two-way frame (web/bridge/index.html): the view inside can send values back to Python.
_bridge = components.declare_component("offpeak_view", path=str(WEB / "bridge"))


def render_html(view: str, data: dict) -> str:
    page = (WEB / f"{view}.html").read_text()
    head = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
        '&display=swap" rel="stylesheet">'
        f"<style>{(WEB / 'kit.css').read_text()}</style>"
        f'<script src="{ECHARTS}"></script>'
        f"<script>{(WEB / 'kit.js').read_text()}</script>"
    )
    # "</" inside the JSON would end the <script> tag early
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    return page.replace("<!--KIT-->", head).replace("__DATA__", payload)


def show(view: str, data: dict, height: int = 900) -> None:
    components.html(render_html(view, data), height=height, scrolling=False)


def live(view: str, data: dict, key: str, height: int = 900, keep: tuple[str, ...] = ()):
    """Like show(), but the view can send a value back with window.parent.offpeakSend(...).
    Returns the last value sent (a dict with an "id"), or None. It is also in
    st.session_state[key] at the start of the next run.

    `keep` names data fields the view changes itself (for example its machine list): when
    only those change, the view on screen is not reloaded, so it keeps scroll and focus."""
    rest = json.dumps({k: v for k, v in data.items() if k not in keep}, default=str)
    version = hashlib.sha1(rest.encode()).hexdigest()
    return _bridge(html=render_html(view, data), version=version, height=height, key=key)
