"""Shared look: colours, CSS, cards and small formatting helpers."""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

TZ = "Europe/Berlin"

# Safety Orange is the accent in both modes. Night mode: Storm Grey surfaces (60 %),
# Matte Black frame and rail (30 %), orange for what matters (10 %).
ORANGE = "#FF5F00"
GREEN = "#2F9E44"

# Chart colours that read on light and dark backgrounds alike, so a chart never has to be
# redrawn when the viewer switches mode.
INK = "#8A9098"  # axis text
MUTED = "#8A9098"
LINE = "rgba(138, 144, 152, 0.22)"  # grid lines
PEAK = "#5B6168"  # the most expensive slots: storm grey
OTHER = "rgba(138, 144, 152, 0.38)"  # every other slot
ORANGE_SOFT = "rgba(255, 95, 0, 0.14)"
ORANGE_SOFT_STRONG = "rgba(255, 95, 0, 0.45)"

PALETTES = {
    "light": {
        "bg": "#E9EBEE",
        "frame": "#F4F5F7",
        "card": "#FFFFFF",
        "card2": "#F2F3F5",
        "line": "#E4E6E9",
        "ink": "#16171A",
        "muted": "#6B7079",
        "faint": "#A3A8AF",
        "accent": "#FF5F00",
        "accent-soft": "#FFEADD",
        "accent-mid": "#FFC7A6",
        "accent-ink": "#C24700",
        "rail": "#151618",
        "rail-ink": "#8C9198",
        "hero": "#151618",
        "hero-ink": "#F4F5F6",
        "hero-muted": "#9AA0A7",
        "shadow": "0 1px 2px rgba(16,17,19,.04), 0 10px 30px rgba(16,17,19,.05)",
    },
    "dark": {
        "bg": "#0E0F10",
        "frame": "#16181A",
        "card": "#1F2124",
        "card2": "#26292D",
        "line": "#2C2F33",
        "ink": "#F1F2F3",
        "muted": "#9AA0A7",
        "faint": "#6B7178",
        "accent": "#FF5F00",
        "accent-soft": "rgba(255,95,0,.14)",
        "accent-mid": "rgba(255,95,0,.38)",
        "accent-ink": "#FF8A4C",
        "rail": "#08090A",
        "rail-ink": "#7A8087",
        "hero": "#0A0B0C",
        "hero-ink": "#F4F5F6",
        "hero-muted": "#8D939A",
        "shadow": "none",
    },
}


def _vars(palette: dict) -> str:
    return "".join(f"--op-{k}:{v};" for k, v in palette.items())


CSS = (
    """
<style>
:root { """
    + _vars(PALETTES["light"])
    + """ }
body.op-dark { """
    + _vars(PALETTES["dark"])
    + """ }
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp button, .stApp input {
    font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; }
[data-testid="stHeader"] { background: transparent; }

/* the page sits in one big rounded frame, like a device screen */
[data-testid="stMain"] { padding: 14px 14px 14px 0; }
.block-container { background: var(--op-frame); border-radius: 32px; padding: 2.2rem 2.2rem 3rem;
    max-width: 1340px; margin-top: 0; box-shadow: var(--op-shadow); }

/* sidebar: a dark pill rail of icons on wide screens; labels appear on hover */
@media (min-width: 900px) {
  [data-testid="stSidebar"] { width: 92px !important; min-width: 92px !important; max-width: 92px !important;
      background: transparent !important; border: 0 !important; }
  [data-testid="stSidebar"] > div:first-child { background: var(--op-rail); border-radius: 30px;
      margin: 14px 0 14px 14px; height: calc(100vh - 28px); overflow: visible; }
  [data-testid="stSidebarContent"] { overflow: visible !important; }
  [data-testid="stSidebarHeader"] { padding: 1.2rem 0 0.6rem; justify-content: center; }
  [data-testid="stSidebarHeader"] img { height: 40px !important; width: 40px !important; }
  [data-testid="stSidebarCollapseButton"], [data-testid="stSidebar"] [data-testid="stSidebarResizer"] { display: none !important; }
  [data-testid="stSidebarNav"] { padding: 0 14px; }
  [data-testid="stNavSectionHeader"] { font-size: 0 !important; height: 1px; margin: 14px 10px !important;
      background: rgba(255,255,255,.08); }
  [data-testid="stSidebarNavLink"] { position: relative; justify-content: center; width: 50px; height: 50px;
      padding: 0 !important; margin: 6px auto !important; border-radius: 50% !important; overflow: visible; }
  [data-testid="stSidebarNavLink"] > span[label] { position: absolute; left: 62px; top: 50%;
      transform: translateY(-50%); background: var(--op-rail); color: #F1F2F3; padding: 6px 12px;
      border-radius: 999px; white-space: nowrap; opacity: 0; pointer-events: none;
      z-index: 1000; box-shadow: 0 6px 20px rgba(0,0,0,.25); }
  [data-testid="stSidebarNavLink"] > span[label] p { color: #F1F2F3 !important; font-size: .82rem; margin: 0; }
  [data-testid="stSidebarNavLink"]:hover > span[label] { opacity: 1; transition: opacity .15s; }
  [data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { color: var(--op-rail-ink) !important; font-size: 22px; }
  [data-testid="stSidebarNavLink"]:hover { background: rgba(255,255,255,.07) !important; }
  [data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--op-accent) !important;
      box-shadow: 0 0 0 5px rgba(255,95,0,.18); }
  [data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] { color: #fff !important; }
}

/* cards */
[class*="st-key-card"] { background: var(--op-card); border-radius: 22px !important;
    border-color: var(--op-line) !important; padding: 1.3rem 1.4rem !important; }
.op-eyebrow { color: var(--op-muted); font-size: 0.85rem; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.op-badge { background: var(--op-card); border: 1px solid var(--op-line); border-radius: 999px; padding: 2px 10px;
    font-size: 0.75rem; font-weight: 500; color: var(--op-muted); }
.op-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
.op-title { font-size: 2rem; font-weight: 650; letter-spacing: -0.025em; margin: 4px 0 22px; color: var(--op-ink); }
.op-kpi { background: var(--op-card); border: 1px solid var(--op-line); border-radius: 22px; padding: 20px 22px;
    height: 100%; min-height: 128px; }
.op-kpi.accent { background: var(--op-accent-soft); border-color: var(--op-accent-mid); }
.op-kpi .label { color: var(--op-muted); font-size: 0.85rem; }
.op-kpi .value { font-size: 1.9rem; font-weight: 650; letter-spacing: -0.03em; margin: 8px 0 4px; color: var(--op-ink); }
.op-kpi.accent .value { color: var(--op-accent); }
.op-kpi .unit { font-size: 0.85rem; font-weight: 500; color: var(--op-muted); margin-left: 4px; letter-spacing: 0; }
.op-kpi .note { color: var(--op-muted); font-size: 0.78rem; }
.op-h { font-weight: 600; font-size: 1.05rem; margin: 0; color: var(--op-ink); }
.op-sub { color: var(--op-muted); font-size: 0.82rem; margin: 3px 0 8px; }
.op-legend { display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: 0.8rem; color: var(--op-muted); }
.op-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 7px; vertical-align: -1px; }
.op-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0;
    border-bottom: 1px solid var(--op-line); }
.op-row:last-child { border-bottom: none; }
.op-row .name { font-weight: 600; font-size: 0.92rem; color: var(--op-ink); }
.op-row .meta { color: var(--op-muted); font-size: 0.79rem; }
.op-row > .meta { white-space: nowrap; }
.op-row a { color: var(--op-accent-ink) !important; }
.op-chip { background: var(--op-accent-soft); color: var(--op-accent-ink); font-weight: 600; font-size: 0.83rem;
    padding: 5px 11px; border-radius: 999px; white-space: nowrap; }
.op-chip.grey { background: var(--op-card2); color: var(--op-ink); }
.op-tiles { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; }
@media (max-width: 1100px) { .op-tiles { grid-template-columns: repeat(4, 1fr); } }
.op-tile { background: var(--op-card2); border: 1px solid transparent; border-radius: 16px; padding: 11px 10px 10px; min-width: 0; }
.op-tile.sunny { background: var(--op-accent-soft); border-color: var(--op-accent-mid); }
.op-tile .t { color: var(--op-muted); font-size: 0.75rem; }
.op-tile .temp { font-size: 1.3rem; font-weight: 600; margin: 4px 0 2px; color: var(--op-ink); }
.op-tile .cond { font-size: 0.78rem; color: var(--op-muted); min-height: 2.2em; }
.op-bar { height: 4px; border-radius: 4px; background: var(--op-line); margin-top: 8px; }
.op-bar span { display: block; height: 4px; border-radius: 4px; background: var(--op-accent); }
.op-days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
@media (max-width: 1100px) { .op-days { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.op-day { background: var(--op-card2); border: 1px solid transparent; border-radius: 16px; padding: 12px; min-width: 0; }
.op-day.best { background: var(--op-accent-soft); border-color: var(--op-accent-mid); }
.op-day .t { font-weight: 600; font-size: 0.9rem; color: var(--op-ink); }
.op-day .t span { font-weight: 400; color: var(--op-muted); font-size: 0.78rem; margin-left: 4px; }
.op-day .cond { font-size: 0.78rem; color: var(--op-muted); margin: 2px 0 6px; min-height: 2.3em; }
.op-day .temp { font-size: 1.35rem; font-weight: 600; color: var(--op-ink); margin-bottom: 8px; }
.op-day .temp span { font-size: 0.85rem; font-weight: 500; color: var(--op-muted); }
.op-day .kv { display: flex; justify-content: space-between; font-size: 0.76rem; color: var(--op-muted); margin-top: 8px; }
.op-day .kv b { color: var(--op-ink); font-weight: 600; }
.op-bar.dark span { background: var(--op-muted); }
.op-foot { color: var(--op-muted); font-size: 0.74rem; margin-top: 12px; line-height: 1.5; }

/* hero: always matte black, an orange glow rising from the bottom edge */
.op-hero { position: relative; overflow: hidden; background: var(--op-hero); color: var(--op-hero-ink);
    border-radius: 26px; padding: 26px 28px; min-height: 196px; display: flex; flex-direction: column;
    justify-content: space-between; gap: 18px; }
.op-hero::after { content: ""; position: absolute; left: 10%; right: 10%; bottom: -150px; height: 220px;
    border-radius: 50%; background: radial-gradient(closest-side, rgba(255,95,0,.55), rgba(255,95,0,0));
    pointer-events: none; }
.op-hero .kicker { font-size: .8rem; color: var(--op-hero-muted); display: flex; gap: 8px; align-items: center; }
.op-hero h2 { font-size: 1.75rem; font-weight: 600; letter-spacing: -.02em; margin: 6px 0 4px; color: var(--op-hero-ink); line-height: 1.2; }
.op-hero h2 em { font-style: italic; font-weight: 400; color: var(--op-accent); }
.op-hero p { color: var(--op-hero-muted); font-size: .88rem; margin: 0; max-width: 560px; }
.op-hero .facts { display: flex; flex-wrap: wrap; gap: 8px; position: relative; z-index: 1; }
.op-hero .fact { background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.08); border-radius: 999px;
    padding: 6px 12px; font-size: .8rem; color: var(--op-hero-ink); white-space: nowrap; }
.op-hero .fact.on { background: var(--op-accent); border-color: var(--op-accent); color: #fff; font-weight: 600; }

/* week strip, like a calendar card */
.op-week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; margin-top: 6px; }
.op-wkday { text-align: center; border-radius: 16px; padding: 10px 0 8px; color: var(--op-muted); font-size: .72rem; }
.op-wkday b { display: block; font-size: 1.05rem; color: var(--op-ink); font-weight: 600; margin: 3px 0; }
.op-wkday i { display: block; width: 5px; height: 5px; border-radius: 50%; margin: 0 auto; background: transparent; }
.op-wkday.has i { background: var(--op-faint); }
.op-wkday.cheap i { background: var(--op-accent); }
.op-wkday.on { background: var(--op-hero); color: var(--op-hero-muted); }
.op-wkday.on b { color: var(--op-hero-ink); }
.op-wkday .ct { display: block; font-size: .68rem; margin-top: 4px; }

/* page links styled as the orange pill button */
.st-key-hero_cta a, .st-key-hero_cta2 a { background: var(--op-accent); color: #fff !important; border-radius: 999px;
    padding: 6px 16px; font-weight: 600; }
.st-key-hero_cta a span, .st-key-hero_cta2 a span, .st-key-hero_cta a p, .st-key-hero_cta2 a p { color: #fff !important; }

/* segmented control: a quiet pill group */
[data-testid="stButtonGroup"] > div:last-child { background: var(--op-card2); border: 1px solid var(--op-line);
    border-radius: 999px; padding: 3px; gap: 0; width: fit-content; }
[data-testid="stButtonGroup"] button { border: 0 !important; background: transparent !important; border-radius: 999px !important;
    color: var(--op-muted) !important; font-weight: 500; box-shadow: none !important; min-height: 34px; }
[data-testid="stButtonGroup"] button[aria-checked="true"] { background: var(--op-card) !important; color: var(--op-ink) !important;
    box-shadow: 0 1px 3px rgba(16, 17, 19, 0.12) !important; }
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* phones: no frame margin, cards edge to edge */
@media (max-width: 899px) {
  [data-testid="stMain"] { padding: 0; }
  .block-container { border-radius: 0; padding: 3.8rem 1rem 2.4rem; box-shadow: none; }
  .op-hero h2 { font-size: 1.4rem; }
}
</style>
"""
)

# Streamlit switches light/dark itself (menu → theme) without rerunning the page. This
# script notices the switch from the page background and sets body.op-dark, so our cards
# follow immediately. The site scene reads the same class.
THEME_JS = """
<script>
(() => {
  if (window.__opTheme) return;
  window.__opTheme = true;
  const apply = () => {
    const app = document.querySelector('.stApp');
    if (!app) return;
    const m = getComputedStyle(app).backgroundColor.match(/\d+/g);
    if (!m) return;
    const lum = (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) / 255;
    document.body.classList.toggle('op-dark', lum < 0.5);
  };
  apply();
  setInterval(apply, 400);
})();
</script>
"""


def inject_css() -> None:
    st.html(CSS)
    st.html(THEME_JS, unsafe_allow_javascript=True)


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
    return f'<span class="op-dot" style="background:{GREEN if ok else "#8A9098"}"></span>'
