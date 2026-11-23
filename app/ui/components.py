"""Shared look: colours, CSS, cards and small formatting helpers."""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

TZ = "Europe/Berlin"

ORANGE = "#FF5F00"
ORANGE_SOFT = "#FFE9DC"
ORANGE_SOFT_STRONG = "#FFC4A0"
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

/* sidebar: white, quiet, one orange accent on the active page. Hovering a page lifts it a
   little: a warm background, the icon turns orange and an orange bar grows on the left. */
[data-testid="stSidebar"] {{ border-right: 1px solid {LINE};
    background: radial-gradient(420px 260px at 0% 0%, rgba(255, 95, 0, 0.06), transparent 70%), #FFFFFF; }}
[data-testid="stSidebarHeader"] {{ padding: 1.6rem 1.4rem 1rem; }}
[data-testid="stSidebarNav"] {{ padding: 0 0.6rem; }}
[data-testid="stSidebarNavSeparator"] {{ display: none; }}  /* no line under the menu */
[data-testid="stNavSectionHeader"] {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: #A39E96; margin: 1.1rem 0 0.35rem 0.55rem; }}
[data-testid="stSidebarNavLink"] {{ position: relative; border-radius: 12px; padding: 0.5rem 0.7rem;
    margin: 2px 0; transition: background 0.2s, transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1),
    box-shadow 0.2s; }}
[data-testid="stSidebarNavLink"]::before {{ content: ""; position: absolute; left: 0; top: 50%;
    width: 3px; height: 0; border-radius: 3px; background: {ORANGE}; transform: translateY(-50%);
    transition: height 0.2s cubic-bezier(0.2, 0.8, 0.2, 1); }}
[data-testid="stSidebarNavLink"] span {{ font-size: 0.92rem; color: #4A4640; transition: color 0.2s; }}
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] {{ transition: color 0.2s, transform 0.2s; }}
[data-testid="stSidebarNavLink"]:hover {{ background: #FFF4EC; transform: translateX(3px);
    box-shadow: 0 4px 14px rgba(255, 95, 0, 0.08); }}
[data-testid="stSidebarNavLink"]:hover::before {{ height: 45%; }}
[data-testid="stSidebarNavLink"]:hover span {{ color: {INK}; }}
[data-testid="stSidebarNavLink"]:hover [data-testid="stIconMaterial"] {{ color: {ORANGE}; transform: scale(1.1); }}
[data-testid="stSidebarNavLink"]:active {{ transform: translateX(3px) scale(0.98); }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {ORANGE_SOFT};
    box-shadow: 0 6px 18px rgba(255, 95, 0, 0.12); }}
[data-testid="stSidebarNavLink"][aria-current="page"]::before {{ height: 60%;
    box-shadow: 0 0 10px rgba(255, 95, 0, 0.6); }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: {INK}; font-weight: 600; }}
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] {{ color: {ORANGE}; }}

/* Ask Ollie: the robot and its chat window float at the bottom right, above Streamlit
   Cloud's own badge; the frame sizes itself (app/ui/web/ollie/index.html) */
.st-key-ollie {{ position: fixed; right: 14px; bottom: 54px; z-index: 999990; width: 432px !important; }}
/* While Ollie answers, Streamlit fades the elements it is about to redraw ("stale"); the
   chat would turn see-through over the page. Keep it fully visible. */
.st-key-ollie, .st-key-ollie * {{ opacity: 1 !important; }}
.st-key-ollie iframe {{ background: transparent; color-scheme: normal; }}

/* the signed-in name at the very bottom of the sidebar */
[data-testid="stSidebarContent"] {{ display: flex; flex-direction: column; }}
[data-testid="stSidebarUserContent"] {{ margin-top: auto; padding-bottom: 1.2rem; }}
.st-key-account_link {{ padding: 0 0.6rem; }}
.st-key-account_link a {{ border-radius: 14px; background: #F6F5F2; border: 1px solid transparent;
    transition: background 0.2s, border-color 0.2s, transform 0.2s, box-shadow 0.2s; }}
.st-key-account_link a:hover {{ background: #FFF4EC; border-color: rgba(255, 95, 0, 0.35);
    transform: translateY(-2px); box-shadow: 0 8px 20px rgba(255, 95, 0, 0.12); }}
.st-key-account_link a:hover [data-testid="stIconMaterial"] {{ color: {ORANGE}; }}

/* account page */
.op-profile {{ display: flex; gap: 16px; align-items: center; margin-bottom: 10px; }}
.op-avatar {{ width: 56px; height: 56px; border-radius: 18px; background: linear-gradient(135deg, {ORANGE}, #FF8A3D);
    color: #fff; font-weight: 700; font-size: 1.2rem; display: grid; place-items: center; }}
.op-name {{ font-weight: 650; font-size: 1.1rem; color: {INK}; }}
.op-mail {{ color: {MUTED}; font-size: 0.84rem; margin: 2px 0 6px; }}
.op-plan {{ display: flex; justify-content: space-between; align-items: center; background: {ORANGE_SOFT};
    border-radius: 16px; padding: 14px 16px; margin: 4px 0 12px; }}
.op-plan-name {{ font-weight: 700; font-size: 1.15rem; color: {INK}; }}
.op-plan-price {{ font-weight: 700; font-size: 1.6rem; color: {ORANGE}; }}
.op-plan-price small {{ font-size: 0.8rem; color: {MUTED}; font-weight: 500; }}
.op-incl {{ padding: 7px 0 7px 26px; position: relative; font-size: 0.9rem; color: {INK}; }}
.op-incl::before {{ content: '✓'; position: absolute; left: 4px; color: {ORANGE}; font-weight: 700; }}
.op-conn-head {{ display: flex; gap: 14px; align-items: center; margin-bottom: 16px; }}
.op-conn-icon {{ width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; font-weight: 700; font-size: 1.2rem; }}
.op-conn-head.good .op-conn-icon {{ background: #E3F6E8; color: #1E8E3E; }}
.op-conn-head.bad .op-conn-icon {{ background: #FDE7E7; color: #C62828; }}
.op-tiles2 {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
.op-tile2 {{ border: 1px solid {LINE}; border-radius: 16px; padding: 14px 16px; background: #FCFBF9; }}
.op-tile2 .t {{ font-weight: 600; font-size: 0.92rem; color: {INK}; }}
.op-tile2 .d {{ color: {MUTED}; font-size: 0.78rem; margin: 3px 0 10px; min-height: 2.2em; }}
.op-tile2 .s {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
.op-tile2 .pill {{ font-size: 0.74rem; font-weight: 600; border-radius: 999px; padding: 3px 9px; }}
.op-tile2.ok .pill {{ background: #E3F6E8; color: #1E8E3E; }}
.op-tile2.bad {{ border-color: #F5C2C2; background: #FFF8F8; }}
.op-tile2.bad .pill {{ background: #FDE7E7; color: #C62828; }}
.op-tile2 .n {{ color: {MUTED}; font-size: 0.76rem; }}

/* "Connect your consumption data" (app/ui/connect.py): a card that stands out, with one tile
   per way of connecting; planned ones are dashed, so nobody takes them for working ones */
/* doubled class: wins over the general card rule further down ([class*=st-key-card]) */
.st-key-card_connect.st-key-card_connect {{ border: 1.5px solid {ORANGE} !important;
    background: linear-gradient(160deg, #FFF4EC, #FFFFFF 45%) !important;
    box-shadow: 0 14px 40px rgba(255, 95, 0, 0.10); }}
.op-conns {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; margin: 6px 0 4px; }}
.op-conn {{ border: 1px solid {LINE}; border-radius: 14px; padding: 12px 14px; background: #FFFFFF;
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s; }}
.op-conn:hover {{ transform: translateY(-2px); border-color: #FFC4A0; box-shadow: 0 10px 24px rgba(255, 95, 0, 0.10); }}
.op-conn .top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
.op-conn .t {{ font-weight: 600; font-size: 0.92rem; color: {INK}; }}
.op-conn .k {{ color: {MUTED}; font-size: 0.76rem; margin: 2px 0 6px; }}
.op-conn .d {{ color: {MUTED}; font-size: 0.78rem; line-height: 1.45; }}
.op-conn .pill {{ font-size: 0.7rem; font-weight: 600; border-radius: 999px; padding: 2px 9px; white-space: nowrap; }}
.op-conn.on .pill {{ background: #E3F6E8; color: #1E8E3E; }}
.op-conn.ok .pill {{ background: {ORANGE_SOFT}; color: #B84300; }}
.op-conn.plan {{ border-style: dashed; background: #FCFBF9; }}
.op-conn.plan .pill {{ background: #F1EFEB; color: {MUTED}; }}
.st-key-card_connect [data-testid=stFileUploaderDropzone] {{ border: 2px dashed #FFC4A0;
    background: #FFF8F3; border-radius: 14px; padding: 1.4rem; transition: border-color 0.2s, background 0.2s; }}
.st-key-card_connect [data-testid=stFileUploaderDropzone]:hover {{ border-color: {ORANGE}; background: #FFF1E7; }}

/* login screen */
.op-login-head {{ text-align: center; margin: 6px 0 10px; }}
.op-login-logo {{ font-size: 1.9rem; font-weight: 700; letter-spacing: -0.03em; color: {ORANGE}; }}
.op-login-logo b {{ color: {INK}; font-weight: 700; }}
.op-login-head h2 {{ font-size: 1.35rem; font-weight: 650; margin: 14px 0 4px; color: {INK}; }}
.op-login-head p {{ color: {MUTED}; font-size: 0.88rem; margin: 0; }}
/* The sign-in card: a fixed width in the middle, where the landing page's Login puts its
   glowing core (landing.html: coreAt). It grows out of that core: from blurred and small to
   sharp, then a light runs once around its edge. A soft light follows the cursor (--mx,
   --my, set by web/login_bg.html). */
/* "\\3C angle\\3E" is the type "angle" in angle brackets, written as CSS escapes: st.html
   drops a whole style block whose text has a "less than" sign followed by a letter */
@property --op-trace {{ syntax: "\\3C angle\\3E"; inherits: false; initial-value: 0deg; }}
.st-key-card_login, .st-key-card_roles {{ margin: 12vh auto 0 !important;
    position: relative; z-index: 2; overflow: visible !important;
    background: radial-gradient(480px circle at var(--mx, 50%) var(--my, -30%),
        rgba(255, 95, 0, 0.07), transparent 45%), #fff !important;
    box-shadow: 0 30px 80px rgba(28, 27, 25, 0.10);
    animation: op-card-in 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both; }}
@keyframes op-card-in {{
    from {{ opacity: 0; transform: scale(0.86); filter: blur(14px); }}
    60% {{ filter: blur(0); }} }}
.st-key-card_login::before, .st-key-card_roles::before {{ content: ""; position: absolute; inset: -1.5px; padding: 1.5px;
    border-radius: 21px; pointer-events: none;
    background: conic-gradient(from var(--op-trace), transparent 0 62%, #FFB27A 78%,
        {ORANGE} 88%, transparent 97%);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
    animation: op-trace 1.7s cubic-bezier(0.45, 0, 0.2, 1) 0.45s both; }}
@keyframes op-trace {{
    0% {{ --op-trace: 0deg; opacity: 0; }} 12% {{ opacity: 1; }} 80% {{ opacity: 1; }}
    100% {{ --op-trace: 360deg; opacity: 0; }} }}
.st-key-card_login::after, .st-key-card_roles::after {{ content: ""; position: absolute; inset: 0; border-radius: 20px;
    pointer-events: none; box-shadow: 0 0 70px rgba(255, 95, 0, 0.35);
    animation: op-card-glow 1.6s ease 0.2s both; }}
@keyframes op-card-glow {{ from {{ opacity: 0; }} 30% {{ opacity: 1; }} to {{ opacity: 0; }} }}
.st-key-card_login {{ width: min(420px, 100%) !important; }}
/* step 1 of signing in: two cards side by side, Homeowner and Business (account.py) */
.st-key-card_roles {{ width: min(760px, 100%) !important; }}
.st-key-role_home, .st-key-role_business {{ border-radius: 18px !important; padding: 18px !important;
    transition: transform 0.25s, box-shadow 0.25s, border-color 0.25s; height: 100%; }}
.st-key-role_home:hover, .st-key-role_business:hover {{ transform: translateY(-3px);
    border-color: {ORANGE} !important; box-shadow: 0 18px 44px rgba(255, 95, 0, 0.14); }}
.op-role img {{ width: 42px; height: 42px; display: block; }}
.op-role h3 {{ font-size: 1.25rem; font-weight: 650; margin: 10px 0 6px; color: {INK}; }}
.op-role p {{ color: {MUTED}; font-size: 0.88rem; line-height: 1.5; margin: 0 0 4px;
    min-height: 4.4em; }}
.op-role-chip {{ display: inline-block; padding: 4px 12px; border-radius: 999px;
    background: {ORANGE_SOFT}; color: #B84300; font-weight: 600; font-size: 0.85rem; }}
/* behind the card: the power lines (web/login_bg.html), over the whole window */
.st-key-login_bg {{ position: fixed !important; inset: 0; z-index: 0; pointer-events: none; }}
.st-key-login_bg iframe {{ position: fixed; inset: 0; width: 100vw !important; border: 0;
    height: 100vh !important; height: 100dvh !important; pointer-events: none; }}
/* The glowing core that the landing page's Login leaves (landing.html: core) is hidden
   everywhere; the landing page shows it, the sign-in page bursts it (account.py). */
#op-portal {{ display: none !important; }}
/* the sign-in page is dark, like the night scene of the landing page: an orange glow on top,
   the gravity well and the power lines (web/login_bg.html) behind the glass cards */
[data-testid=stAppViewContainer]:has(.st-key-card_login),
[data-testid=stAppViewContainer]:has(.st-key-card_roles) {{
    background: radial-gradient(900px 520px at 50% 0%, rgba(255, 95, 0, 0.16), transparent 70%),
        #07080A; color-scheme: dark; }}
[data-testid=stAppViewContainer]:has(.st-key-card_login) [data-testid=stHeader],
[data-testid=stAppViewContainer]:has(.st-key-card_roles) [data-testid=stHeader] {{ background: transparent; }}
/* liquid glass: the cards, light text, dark fields, orange glowing buttons */
.st-key-card_login, .st-key-card_roles {{
    background: radial-gradient(480px circle at var(--mx, 50%) var(--my, -30%),
        rgba(255, 138, 61, 0.14), transparent 45%),
        linear-gradient(135deg, rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.02) 55%,
        rgba(255, 255, 255, 0.05)) !important;
    border-color: rgba(255, 255, 255, 0.12) !important;
    backdrop-filter: blur(18px) saturate(1.6); -webkit-backdrop-filter: blur(18px) saturate(1.6);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 40px 100px rgba(0, 0, 0, 0.6) !important; }}
.st-key-card_login .op-login-logo b, .st-key-card_roles .op-login-logo b,
.st-key-card_login .op-login-head h2, .st-key-card_roles .op-login-head h2,
.st-key-card_roles .op-role h3 {{ color: #EEF0F2; }}
.st-key-card_login .op-login-head p, .st-key-card_roles .op-login-head p,
.st-key-card_roles .op-role p, .st-key-card_login [data-testid=stCaptionContainer],
.st-key-card_login label p {{ color: rgba(238, 240, 242, 0.62) !important; }}
.st-key-card_login .op-login-logo, .st-key-card_roles .op-login-logo {{
    text-shadow: 0 0 34px rgba(255, 95, 0, 0.55); }}
.st-key-card_login .op-role-chip {{ background: rgba(255, 95, 0, 0.18); color: #FFB27A;
    border: 1px solid rgba(255, 95, 0, 0.4); }}
.st-key-card_login [data-testid=stTextInputRootElement] {{
    background: rgba(255, 255, 255, 0.05) !important; border-color: rgba(255, 255, 255, 0.14) !important;
    border-radius: 12px !important; transition: box-shadow 0.25s, border-color 0.25s; }}
.st-key-card_login [data-testid=stTextInputRootElement]:focus-within {{ border-color: {ORANGE} !important;
    box-shadow: 0 0 0 4px rgba(255, 95, 0, 0.16), 0 0 28px rgba(255, 95, 0, 0.3); }}
.st-key-card_login [data-testid=stTextInputRootElement] * {{ background-color: transparent !important; }}
.st-key-card_login input {{ color: #EEF0F2 !important; caret-color: {ORANGE}; }}
.st-key-card_login [data-testid=stTextInputRootElement] button {{ color: rgba(238, 240, 242, 0.62) !important; }}
.st-key-card_login button[kind=primaryFormSubmit], .st-key-card_roles button[kind=primary] {{
    background: linear-gradient(135deg, #FF8A3D, {ORANGE} 55%, #E04E00) !important;
    border: 0 !important; color: #fff !important; border-radius: 12px !important;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.35), 0 10px 30px rgba(255, 95, 0, 0.4);
    transition: transform 0.2s, box-shadow 0.25s; }}
.st-key-card_login button[kind=primaryFormSubmit]:hover, .st-key-card_roles button[kind=primary]:hover {{
    transform: translateY(-1px);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.35), 0 14px 44px rgba(255, 95, 0, 0.65); }}
.st-key-card_roles button[kind=secondary] {{ background: rgba(255, 255, 255, 0.05) !important;
    color: #EEF0F2 !important; border-color: rgba(255, 255, 255, 0.18) !important; border-radius: 12px !important; }}
.st-key-card_roles button[kind=secondary]:hover {{ border-color: {ORANGE} !important; color: #FFB27A !important; }}
.st-key-card_login button[kind=tertiary], .st-key-card_roles button[kind=tertiary] {{
    color: rgba(238, 240, 242, 0.62) !important; }}
.st-key-card_login button[kind=tertiary]:hover, .st-key-card_roles button[kind=tertiary]:hover {{ color: #FFB27A !important; }}
/* the role cards: glass that leans towards the cursor (--rx, --ry from web/login_bg.html) with a
   light where the cursor is (--gx, --gy) */
.st-key-card_roles [data-testid=stHorizontalBlock] {{ perspective: 900px; }}
.st-key-role_home, .st-key-role_business {{ background: radial-gradient(260px circle at var(--gx, 50%) var(--gy, 0%),
        rgba(255, 138, 61, 0.16), transparent 60%), rgba(255, 255, 255, 0.035) !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
    transform: rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg)); transform-style: preserve-3d; }}
.st-key-role_home:hover, .st-key-role_business:hover {{ border-color: rgba(255, 95, 0, 0.7) !important;
    transform: rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg)) translateY(-3px);
    box-shadow: 0 24px 60px rgba(255, 95, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.14); }}
.st-key-card_roles .op-role img {{ filter: drop-shadow(0 0 14px rgba(255, 95, 0, 0.6)); }}
.st-key-card_login [data-testid=stAlert] {{ background: rgba(255, 77, 77, 0.12); }}
.st-key-card_login [data-testid=InputInstructions] {{ color: rgba(238, 240, 242, 0.4); }}
.st-key-card_login input::placeholder {{ color: rgba(238, 240, 242, 0.35); }}
/* the app's logo in the corner has dark letters: on the dark sign-in page only its light shows */
.stApp:has(.st-key-card_login) [data-testid=stHeaderLogo],
.stApp:has(.st-key-card_roles) [data-testid=stHeaderLogo] {{ filter: brightness(0) invert(0.92); }}
.op-login-wait {{ text-align: center; margin-top: 30vh; font-size: 1.6rem; font-weight: 700;
    color: {ORANGE}; opacity: 0.5; animation: op-pulse 1.2s ease-in-out infinite alternate; }}
@keyframes op-pulse {{ to {{ opacity: 1; }} }}

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
.op-chip {{ background: {ORANGE_SOFT}; color: #C24700; font-weight: 600; font-size: 0.83rem; padding: 5px 11px; border-radius: 999px; white-space: nowrap; }}
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
.op-days {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }}
@media (max-width: 1100px) {{ .op-days {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }} }}
.op-day {{ background: #FAF9F7; border: 1px solid transparent; border-radius: 14px; padding: 12px; min-width: 0; }}
.op-day.best {{ background: {ORANGE_SOFT}; border-color: {ORANGE_SOFT_STRONG}; }}
.op-day .t {{ font-weight: 600; font-size: 0.9rem; color: {INK}; }}
.op-day .t span {{ font-weight: 400; color: {MUTED}; font-size: 0.78rem; margin-left: 4px; }}
.op-day .cond {{ font-size: 0.78rem; color: {MUTED}; margin: 2px 0 6px; min-height: 2.3em; }}
.op-day .temp {{ font-size: 1.35rem; font-weight: 600; color: {INK}; margin-bottom: 8px; }}
.op-day .temp span {{ font-size: 0.85rem; font-weight: 500; color: {MUTED}; }}
.op-day .kv {{ display: flex; justify-content: space-between; font-size: 0.76rem; color: {MUTED}; margin-top: 8px; }}
.op-day .kv b {{ color: {INK}; font-weight: 600; }}
.op-bar.dark span {{ background: {PEAK}; }}
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
