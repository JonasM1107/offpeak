"""Signing in: the login screen in front of the app, and staying signed in for 24 hours.

Two steps: first the visitor picks a role (Homeowner or Business, two cards), then signs in.
The role is stored with the account at its first sign-in (accounts table) and is part of the
signed token, so the next visit goes straight into the right portal. Signing in with the
other role's card is refused (offpeak/roles.py: sign_in_role).

The rules (password check, tokens, roles) are in offpeak/. This file keeps the result per
browser: after a login the browser stores a signed token (localStorage, through the small
component in web/token/), so the next visit within 24 hours goes straight into the app.
Streamlit Cloud does not pass cookies on to the app, which is why it is not a cookie.
"""

import os
from base64 import b64encode
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from offpeak import auth, db, roles
from offpeak.settings import lookup
from ui.web import WEB, with_field

_store = components.declare_component(
    "offpeak_token", path=str(Path(__file__).with_name("web") / "token")
)


def _setting(name: str) -> str | None:
    return lookup(st.secrets, name) or os.environ.get(name)


def _config() -> tuple[set[str], str | None, str | None]:
    return (
        auth.editors(_setting("OFFPEAK_EDITORS")),
        _setting("OFFPEAK_PASSWORD_HASH"),
        _setting("OFFPEAK_AUTH_SECRET"),
    )


def configured() -> bool:
    allowed, password_hash, secret = _config()
    return bool(allowed and password_hash and secret)


def sync_browser() -> None:
    """Read the stored token from the browser, and write or delete it after a sign-in or
    sign-out. Called once at the top of every run, so the component stays in place."""
    action, token = st.session_state.pop("token_action", (None, ""))
    answer = _store(action=action, token=token, key="token_store", default=None)
    if answer is not None:  # the browser has answered ("" = nothing stored)
        st.session_state["stored_token"] = answer


def browser_answered() -> bool:
    return "stored_token" in st.session_state or "editor_token" in st.session_state


def session() -> tuple[str, str] | None:
    """(email, role) of the signed-in account, or None. Checked on every run: an expired
    token or an email taken off the list stops working at once. A token from before roles
    existed has none: then the role stored with the account counts, else "business" (the
    only portal there was)."""
    if st.session_state.get("signed_out"):
        return None
    token = st.session_state.get("editor_token") or st.session_state.get("stored_token")
    allowed, _, secret = _config()
    found = auth.read_session(token, datetime.now(UTC), secret, allowed)
    if found is None:
        return None
    email, role = found
    return email, role or _stored_role(email)[0] or "business"


def editor() -> str | None:
    """The signed-in editor's email, or None."""
    found = session()
    return found[0] if found else None


def role() -> str | None:
    """The signed-in account's role ("home" or "business"), or None."""
    found = session()
    return found[1] if found else None


def _engine():
    from data import engine  # app/data.py; imported here, as data.py imports this file

    return engine()


def _stored_role(email: str) -> tuple[str | None, bool]:
    """(the role stored with the account or None, whether the database could be asked).
    Remembered per browser session, so the database is asked once, not on every click."""
    known = st.session_state.setdefault("stored_roles", {})
    if email in known:
        return known[email], True
    eng = _engine()
    if eng is None:
        return None, False
    try:
        stored = roles.normal_role(db.read_role(eng, email))
    except Exception as err:  # e.g. migration 006 not applied yet
        print(f"offpeak: cannot read the account's role: {err}")
        return None, False
    known[email] = stored
    return stored, True


def editor_name(email: str) -> str:
    """The name shown for a signed-in editor (from OFFPEAK_EDITORS, "Name <email>")."""
    return auth.editor_names(_setting("OFFPEAK_EDITORS")).get(email, email)


def sign_in(email: str, password: str, chosen: str | None = None) -> str | None:
    """None if signed in, else what went wrong, in words for the person. `chosen` is the
    role card the visitor picked; the account's stored role must match it."""
    if not configured():
        return "Signing in is not set up on this server yet."
    now = datetime.now(UTC)
    failures = st.session_state.setdefault("login_failures", [])
    if not auth.may_try(failures, now):
        return "Too many wrong attempts. Please wait five minutes."
    allowed, password_hash, secret = _config()
    who = auth.check_login(email, password, allowed, password_hash)
    if who is None:
        failures.append(now)
        return "That email and password do not match."
    stored, asked = _stored_role(who)
    role_now, problem = roles.sign_in_role(chosen, stored)
    if problem:
        return problem
    note = None
    if not asked:  # no database: the role holds for this browser, it cannot be stored
        note = "No database connected: your role is kept on this browser only."
    elif stored is None:  # first sign-in: the account gets the chosen role
        try:
            role_now = roles.normal_role(db.claim_role(_engine(), who, role_now)) or role_now
            st.session_state["stored_roles"][who] = role_now
        except Exception as err:
            print(f"offpeak: cannot store the account's role: {err}")
            note = "Your role could not be stored: it is kept on this browser only."
    token = auth.make_token(who, now, secret, role=role_now)
    st.session_state.update(
        editor_token=token, signed_out=False, token_action=("set", token), role_note=note
    )
    return None


def sign_out() -> None:
    st.session_state.update(
        editor_token=None, stored_token="", signed_out=True, token_action=("clear", "")
    )
    st.session_state.pop(ROLE_CHOICE, None)


# ── The login screen: choose a role, then sign in ───────────────────────────

ROLE_CHOICE = "login_role"  # the card picked on this browser, before signing in


def _icon(paths: str) -> str:
    """A small orange line drawing as an <img>: st.html removes inline <svg>, a picture
    given as a data URL stays."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#FF5F00" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        f"{paths}</svg>"
    )
    return f'<img alt="" src="data:image/svg+xml;base64,{b64encode(svg.encode()).decode()}">'


ICONS = {  # the two cards' pictures: a house with solar, and a factory hall
    "home": _icon(
        '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>'
        '<path d="M14.5 8.5l3-2.2"/>'
    ),
    "business": _icon(
        '<path d="M3 21V10l6 4V10l6 4V6l6 4v11z"/><path d="M7 17h2M12 17h2M17 17h2"/>'
    ),
}


def choose_role(role: str) -> None:
    """Remember the picked card (ignored unless it is a role)."""
    picked = roles.normal_role(role)
    if picked:
        st.session_state[ROLE_CHOICE] = picked


def _role_cards(back: Callable[[], None] | None) -> None:
    with st.container(border=True, key="card_roles"):
        st.html(
            '<div class="op-login-head"><div class="op-login-logo">off<b>peak</b></div>'
            "<h2>Sign in</h2><p>Who is offpeak for today?</p></div>"
        )
        left, right = st.columns(2, gap="medium")
        for col, role in zip((left, right), roles.ROLES, strict=True):
            with col, st.container(border=True, key=f"role_{role}"):
                st.html(
                    f'<div class="op-role">{ICONS[role]}<h3>{roles.LABELS[role]}</h3>'
                    f"<p>{roles.PITCH[role]}</p></div>"
                )
                if st.button(
                    f"Continue as {roles.LABELS[role]}",
                    key=f"choose_{role}",
                    type="primary" if role == "home" else "secondary",
                    width="stretch",
                ):
                    choose_role(role)
                    st.rerun()
        if back and st.button("← Back to the homepage", key="login_back", type="tertiary"):
            back()


def _sign_in_card(role: str, back: Callable[[], None] | None) -> None:
    with st.container(border=True, key="card_login"):  # centred by its CSS (components.py)
        st.html(
            '<div class="op-login-head"><div class="op-login-logo">off<b>peak</b></div>'
            f'<h2>Sign in</h2><p><span class="op-role-chip">{roles.LABELS[role]}</span></p>'
            "</div>"
        )
        with st.form("sign_in", border=False):
            email = st.text_input("Email", max_chars=200, autocomplete="email")
            password = st.text_input(
                "Password", type="password", max_chars=200, autocomplete="current-password"
            )
            submitted = st.form_submit_button(
                "Sign in", type="primary", icon=":material/login:", width="stretch"
            )
        if submitted:
            problem = sign_in(email, password, role)
            if problem:
                st.error(problem)
            else:
                st.rerun()
        st.caption(f"You stay signed in on this browser for {auth.SESSION_HOURS} hours.")
        if st.button("← Choose another role", key="login_change", type="tertiary"):
            st.session_state.pop(ROLE_CHOICE, None)
            st.rerun()
        if back and st.button("← Back to the homepage", key="login_back", type="tertiary"):
            back()


def login_screen(back: Callable[[], None] | None = None) -> None:
    """The login screen, alone on the page, no menu: the two role cards, then the sign-in
    form for the picked role. `back` leads to the landing page."""
    st.html(
        "<style>[data-testid=stSidebar], [data-testid=stSidebarCollapsedControl],"
        "[data-testid=stSidebarCollapseButton] { display: none !important; }</style>"
    )
    if not browser_answered():  # a moment while the browser looks for a stored sign-in
        st.html('<div class="op-login-wait">offpeak</div>')
        return
    chosen = roles.normal_role(st.session_state.get(ROLE_CHOICE))
    if chosen is None:
        _role_cards(back)  # step 1: Homeowner or Business
    else:
        _sign_in_card(chosen, back)  # step 2: email and password for that role
    # Behind the card: the power lines of the landing page (web/login_bg.html). Our own file,
    # never user input, so the frame may run its script. Its CSS: app/ui/components.py.
    with st.container(key="login_bg"):
        st.iframe(with_field((WEB / "login_bg.html").read_text()), height=10)
    # Coming from the landing page's Login, a glowing core covers the page while it is built
    # (landing.html: core). Sent last, so it bursts only once the card is complete.
    st.html(
        "<style>#op-portal { display: block !important;"
        " animation: op-portal-out .5s ease .12s forwards; }"
        "#op-portal .orb { animation: op-orb-burst .6s cubic-bezier(.2,.8,.2,1) forwards"
        " !important; }"
        "#op-portal .ring { display: none; }"
        "@keyframes op-orb-burst { to { transform: scale(3.4); opacity: 0; } }"
        "@keyframes op-portal-out { to { opacity: 0; visibility: hidden; } }</style>"
    )
