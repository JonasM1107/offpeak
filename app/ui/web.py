"""Interactive views: an HTML template in app/ui/web/ plus one JSON payload from Python.

Every view gets the shared look (kit.css), helpers (kit.js) and ECharts. The view sizes
its own frame, so the height given here is only the first guess before it loads.
"""

import json
from pathlib import Path

import streamlit.components.v1 as components

WEB = Path(__file__).with_name("web")
ECHARTS = "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"


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
