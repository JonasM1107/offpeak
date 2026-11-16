"""Signing in: the login screen in front of the app, and staying signed in for 24 hours.

The rules (password check, tokens) are in offpeak/auth.py. This file keeps the result per
browser: after a login the browser stores a signed token (localStorage, through the small
component in web/token/), so the next visit within 24 hours goes straight into the app.
Streamlit Cloud does not pass cookies on to the app, which is why it is not a cookie.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from offpeak import auth
from offpeak.settings import lookup

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


def editor() -> str | None:
    """The signed-in editor's email, or None. Checked on every run: an expired token or an
    email taken off the list stops working at once."""
    if st.session_state.get("signed_out"):
        return None
    token = st.session_state.get("editor_token") or st.session_state.get("stored_token")
    allowed, _, secret = _config()
    return auth.read_token(token, datetime.now(UTC), secret, allowed)


def editor_name(email: str) -> str:
    """The name shown for a signed-in editor (from OFFPEAK_EDITORS, "Name <email>")."""
    return auth.editor_names(_setting("OFFPEAK_EDITORS")).get(email, email)


def sign_in(email: str, password: str) -> str | None:
    """None if signed in, else what went wrong, in words for the person."""
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
    token = auth.make_token(who, now, secret)
    st.session_state.update(editor_token=token, signed_out=False, token_action=("set", token))
    return None


def sign_out() -> None:
    st.session_state.update(
        editor_token=None, stored_token="", signed_out=True, token_action=("clear", "")
    )


def login_screen() -> None:
    """The page everyone sees before the app: only the sign-in form, no menu."""
    st.html(
        "<style>[data-testid=stSidebar], [data-testid=stSidebarCollapsedControl],"
        "[data-testid=stSidebarCollapseButton] { display: none !important; }</style>"
    )
    if not browser_answered():  # a moment while the browser looks for a stored sign-in
        st.html('<div class="op-login-wait">offpeak</div>')
        return
    _, middle, _ = st.columns([1, 1.1, 1])
    with middle, st.container(border=True, key="card_login"):
        st.html(
            '<div class="op-login-head"><div class="op-login-logo">off<b>peak</b></div>'
            "<h2>Sign in</h2><p>When to use electricity, and what that saves.</p></div>"
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
            problem = sign_in(email, password)
            if problem:
                st.error(problem)
            else:
                st.rerun()
        st.caption(f"You stay signed in on this browser for {auth.SESSION_HOURS} hours.")
