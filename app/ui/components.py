"""Shared look: colours, CSS, cards and small formatting helpers."""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

TZ = "Europe/Berlin"

ORANGE = "#E8590C"
ORANGE_SOFT = "#FDEBDF"
ORANGE_SOFT_STRONG = "#F8C9A8"
INK = "#1C1B19"
MUTED = "#6F6A62"
PEAK = "#4A4640"
OTHER = "#D6D2CB"
LINE = "#E7E4DE"
GREEN = "#2F9E44"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp button {{
    font-family: 'Inter', sans-serif;
}}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
[data-testid="stSidebar"] {{ border-right: 1px solid {LINE}; }}
[data-testid="stSidebarNav"] a span {{ font-size: 0.95rem; }}
[class*="st-key-card"] {{ background: #FFFFFF; border-radius: 16px !important; }}
.st-key-price_view {{ display: flex; justify-content: flex-end; }}
.op-eyebrow {{ color: {MUTED}; font-size: 0.9rem; display: flex; gap: 10px; align-items: center; }}
.op-badge {{ border: 1px solid {LINE}; background: #fff; border-radius: 999px;
    padding: 2px 10px; font-size: 0.78rem; font-weight: 600; color: {INK}; }}
.op-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    margin-right: 6px; vertical-align: middle; }}
.op-title {{ font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; margin: 2px 0 18px; }}
.op-kpi {{ background: #fff; border: 1px solid {LINE}; border-radius: 16px; padding: 18px 20px;
    height: 100%; min-height: 124px; }}
.op-kpi.accent {{ background: {ORANGE_SOFT}; border-color: #F8C9A8; }}
.op-kpi .label {{ color: {MUTED}; font-size: 0.9rem; }}
.op-kpi .value {{ font-size: 1.85rem; font-weight: 700; letter-spacing: -0.02em; margin: 6px 0 4px; }}
.op-kpi.accent .value {{ color: {ORANGE}; }}
.op-kpi .unit {{ font-size: 0.9rem; font-weight: 500; color: {MUTED}; margin-left: 4px; }}
.op-kpi .note {{ color: {MUTED}; font-size: 0.8rem; }}
.op-h {{ font-weight: 650; font-size: 1.1rem; margin: 0; }}
.op-sub {{ color: {MUTED}; font-size: 0.85rem; margin: 2px 0 6px; }}
.op-legend {{ display: flex; gap: 22px; font-size: 0.82rem; color: {INK}; }}
.op-legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px;
    margin-right: 7px; vertical-align: -1px; }}
.op-row {{ display: flex; justify-content: space-between; align-items: center;
    padding: 11px 0; border-bottom: 1px solid {LINE}; }}
.op-row:last-child {{ border-bottom: none; }}
.op-row .name {{ font-weight: 600; font-size: 0.95rem; }}
.op-row .meta {{ color: {MUTED}; font-size: 0.8rem; }}
.op-chip {{ background: {ORANGE_SOFT}; color: #B8430A; font-weight: 600; font-size: 0.85rem;
    padding: 4px 10px; border-radius: 8px; white-space: nowrap; }}
.op-chip.grey {{ background: #F1EFEB; color: {INK}; }}
.op-chip.plain {{ background: #fff; color: {MUTED}; border: 1px solid {LINE}; }}
.op-insight {{ background: #fff; border: 1px solid {LINE}; border-left: 4px solid {ORANGE};
    border-radius: 12px; padding: 14px 18px; font-size: 1.02rem; line-height: 1.5;
    margin: -4px 0 18px; }}
.op-insight-tag {{ display: inline-block; background: {ORANGE_SOFT}; color: #B8430A;
    font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 2px 8px; border-radius: 6px; margin-right: 10px; vertical-align: 1px; }}
.op-tiles {{ display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; }}
.op-tiles.week {{ grid-template-columns: repeat(7, 1fr); }}
@media (max-width: 1100px) {{ .op-tiles, .op-tiles.week {{ grid-template-columns: repeat(4, 1fr); }} }}
.op-tile {{ border: 1px solid {LINE}; border-radius: 12px; padding: 10px 10px 9px; min-width: 0; }}
.op-tile.sunny {{ background: #FFF6EF; border-color: #F8C9A8; }}
.op-tile .t {{ color: {MUTED}; font-size: 0.8rem; }}
.op-tile .temp {{ font-size: 1.35rem; font-weight: 700; margin: 4px 0 2px; }}
.op-tile .cond {{ font-size: 0.82rem; min-height: 2.2em; }}
.op-bar {{ height: 4px; border-radius: 4px; background: #EEEBE6; margin-top: 8px; }}
.op-bar span {{ display: block; height: 4px; border-radius: 4px; background: {ORANGE}; }}
.op-foot {{ color: {MUTED}; font-size: 0.75rem; margin-top: 10px; }}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def local(ts: pd.Timestamp | datetime) -> pd.Timestamp:
    return pd.Timestamp(ts).tz_convert(TZ)


def hhmm(ts: pd.Timestamp | datetime, is_end: bool = False) -> str:
    """Local clock time; a window ending at midnight reads 24:00, not 00:00."""
    t = local(ts)
    if is_end and t.hour == 0 and t.minute == 0:
        return "24:00"
    return t.strftime("%H:%M")


def header(eyebrow: str, title: str, live: bool) -> None:
    dot = GREEN if live else ORANGE
    badge = "Live data" if live else "Data unavailable"
    st.html(
        f'<div class="op-eyebrow">{escape(eyebrow)}<span class="op-badge">'
        f'<span class="op-dot" style="background:{dot}"></span>{badge}</span></div>'
        f'<div class="op-title">{escape(title)}</div>'
    )


def kpi(label: str, value: str, unit: str = "", note: str = "", accent: bool = False) -> None:
    unit_html = f'<span class="unit">{escape(unit)}</span>' if unit else ""
    st.html(
        f'<div class="op-kpi{" accent" if accent else ""}"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(value)}{unit_html}</div>'
        f'<div class="note">{escape(note)}</div></div>'
    )


def card_title(title: str, subtitle: str = "") -> None:
    sub = f'<div class="op-sub">{escape(subtitle)}</div>' if subtitle else ""
    st.html(f'<div class="op-h">{escape(title)}</div>{sub}')


def legend(items: list[tuple[str, str]]) -> None:
    spans = "".join(f'<span><i style="background:{c}"></i>{escape(t)}</span>' for t, c in items)
    st.html(f'<div class="op-legend">{spans}</div>')


def status_dot(ok: bool) -> str:
    return f'<span class="op-dot" style="background:{GREEN if ok else "#C9C4BC"}"></span>'
