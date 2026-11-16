"""Signing in: who is an editor in this browser, the login, and the 24-hour cookie.

The rules (password check, tokens) are in offpeak/auth.py. This file keeps the result per
browser: after a login the browser gets a cookie with a signed token, so the next visit
within 24 hours is signed in without typing the password again.
"""

import json
import os
from datetime import UTC, datetime

import streamlit as st
import streamlit.components.v1 as html_frame

from offpeak import auth

COOKIE = "offpeak_editor"


def _setting(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:  # no secrets file
        value = None
    return value or os.environ.get(name)


def _config() -> tuple[set[str], str | None, str | None]:
    return (
        auth.editors(_setting("OFFPEAK_EDITORS")),
        _setting("OFFPEAK_PASSWORD_HASH"),
        _setting("OFFPEAK_AUTH_SECRET"),
    )


def configured() -> bool:
    allowed, password_hash, secret = _config()
    return bool(allowed and password_hash and secret)


def editor() -> str | None:
    """The signed-in editor's email, or None. Checked on every call: an expired token or an
    email taken off the list stops working at once."""
    if st.session_state.get("signed_out"):
        return None
    token = st.session_state.get("editor_token") or st.context.cookies.get(COOKIE)
    allowed, _, secret = _config()
    return auth.read_token(token, datetime.now(UTC), secret, allowed)


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
    st.session_state.update(editor_token=token, signed_out=False, cookie=("set", token))
    # changes made in this tab before signing in are dropped: from now on they are shared
    for key in ("components_local", "cockpit_machines"):
        st.session_state.pop(key, None)
    return None


def sign_out() -> None:
    st.session_state.update(editor_token=None, signed_out=True, cookie=("clear", ""))


def apply_cookie() -> None:
    """Write or delete the browser cookie after a sign-in or sign-out (called on every run;
    does nothing otherwise). Streamlit cannot set cookies itself, so a tiny invisible frame
    on the same site sets it with JavaScript."""
    action = st.session_state.pop("cookie", None)
    if action is None:
        return
    kind, token = action
    age = auth.SESSION_HOURS * 3600 if kind == "set" else 0
    html_frame.html(
        f"""<script>
        const secure = location.protocol === 'https:' ? '; Secure' : '';
        window.parent.document.cookie = '{COOKIE}=' + {json.dumps(token)} +
          '; Max-Age={age}; Path=/; SameSite=Lax' + secure;
        </script>""",
        height=0,
    )
