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
MUTED = "#77726A"
PEAK = "#4A4640"
OTHER = "#D6D2CB"
LINE = "#ECE9E4"
GREEN = "#2F9E44"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp button, .stApp input {{
    font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased;
}}
.block-container {{ padding: 2.4rem 2.2rem 3rem; max-width: 1320px; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* sidebar: white, quiet, one orange accent on the active page */
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {LINE}; }}
[data-testid="stSidebarHeader"] {{ padding: 1.6rem 1.4rem 1rem; }}
[data-testid="stSidebarNav"] {{ padding: 0 0.6rem; }}
[data-testid="stNavSectionHeader"] {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: #A39E96; margin: 1.1rem 0 0.35rem 0.55rem; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 10px; padding: 0.5rem 0.7rem; margin: 1px 0; }}
[data-testid="stSidebarNavLink"] span {{ font-size: 0.92rem; color: #4A4640; }}
[data-testid="stSidebarNavLink"]:hover {{ background: #F6F5F2; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {ORANGE_SOFT}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: {INK}; font-weight: 600; }}
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] {{ color: {ORANGE}; }}

/* cards */
[class*="st-key-card"] {{ background: #FFFFFF; border-radius: 20px !important; border-color: {LINE} !important;
    padding: 1.3rem 1.4rem !important; }}
.op-eyebrow {{ color: {MUTED}; font-size: 0.85rem; display: flex; gap: 10px; align-items: center; }}
.op-badge {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 999px; padding: 2px 10px;
    font-size: 0.75rem; font-weight: 500; color: {MUTED}; }}
.op-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }}
.op-title {{ font-size: 2rem; font-weight: 650; letter-spacing: -0.025em; margin: 4px 0 22px; color: {INK}; }}
.op-kpi {{ background: #fff; border: 1px solid {LINE}; border-radius: 20px; padding: 20px 22px; height: 100%; min-height: 128px; }}
.op-kpi.accent {{ background: {ORANGE_SOFT}; border-color: {ORANGE_SOFT_STRONG}; }}
.op-kpi .label {{ color: {MUTED}; font-size: 0.85rem; }}
.op-kpi .value {{ font-size: 1.85rem; font-weight: 600; letter-spacing: -0.025em; margin: 8px 0 4px; color: {INK}; }}
.op-kpi.accent .value {{ color: {ORANGE}; }}
.op-kpi .unit {{ font-size: 0.85rem; font-weight: 500; color: {MUTED}; margin-left: 4px; }}
.op-kpi .note {{ color: {MUTED}; font-size: 0.78rem; }}
.op-h {{ font-weight: 600; font-size: 1.05rem; margin: 0; color: {INK}; }}
.op-sub {{ color: {MUTED}; font-size: 0.82rem; margin: 3px 0 8px; }}
.op-legend {{ display: flex; gap: 20px; font-size: 0.8rem; color: {MUTED}; }}
.op-legend i {{ display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 7px; vertical-align: -1px; }}
.op-row {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid {LINE}; }}
.op-row:last-child {{ border-bottom: none; }}
.op-row .name {{ font-weight: 600; font-size: 0.92rem; color: {INK}; }}
.op-row .meta {{ color: {MUTED}; font-size: 0.79rem; }}
.op-row > .meta {{ white-space: nowrap; }}
.op-chip {{ background: {ORANGE_SOFT}; color: #B8430A; font-weight: 600; font-size: 0.83rem; padding: 5px 11px; border-radius: 999px; white-space: nowrap; }}
.op-chip.grey {{ background: #F1EFEB; color: {INK}; }}
.op-tiles {{ display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; }}
@media (max-width: 1100px) {{ .op-tiles {{ grid-template-columns: repeat(4, 1fr); }} }}
.op-tile {{ background: #FAF9F7; border: 1px solid transparent; border-radius: 14px; padding: 11px 10px 10px; min-width: 0; }}
.op-tile.sunny {{ background: {ORANGE_SOFT}; border-color: {ORANGE_SOFT_STRONG}; }}
.op-tile .t {{ color: {MUTED}; font-size: 0.75rem; }}
.op-tile .temp {{ font-size: 1.3rem; font-weight: 600; margin: 4px 0 2px; color: {INK}; }}
.op-tile .cond {{ font-size: 0.78rem; color: #4A4640; min-height: 2.2em; }}
.op-bar {{ height: 4px; border-radius: 4px; background: #ECE8E2; margin-top: 8px; }}
.op-bar span {{ display: block; height: 4px; border-radius: 4px; background: {ORANGE}; }}
.op-foot {{ color: {MUTED}; font-size: 0.74rem; margin-top: 12px; line-height: 1.5; }}

/* segmented control: a quiet pill group like in the site view */
[data-testid="stButtonGroup"] {{ background: #F6F5F2; border: 1px solid {LINE}; border-radius: 12px; padding: 3px; gap: 0; width: fit-content; }}
[data-testid="stButtonGroup"] button {{ border: 0 !important; background: transparent !important; border-radius: 9px !important;
    color: {MUTED} !important; font-weight: 500; box-shadow: none !important; min-height: 34px; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] {{ background: #FFFFFF !important; color: {INK} !important;
    box-shadow: 0 1px 3px rgba(28, 27, 25, 0.08) !important; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
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
