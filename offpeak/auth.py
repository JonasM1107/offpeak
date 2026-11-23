"""Who may change shared data (site components, cockpit machines): the team's editors.

How it works, in three parts:

1. The password is never stored, only a fingerprint of it (PBKDF2-SHA256 with a random salt,
   200,000 rounds). Checking a login computes the fingerprint of what was typed and compares.
   The fingerprint cannot be turned back into the password, and the many rounds make
   guessing slow.
2. After a login the browser keeps a token for 24 hours: "email|expiry|signature". The
   signature is an HMAC with a server secret, so the token cannot be changed or made up
   without that secret, and it stops working when it expires or the email is no longer an
   editor.
3. The app checks the editor where shared data is saved (app/data.py), not only by hiding
   buttons. Visitors who are not signed in can still try things: their changes stay in
   their own browser tab.

The settings (editor emails, password fingerprint, token secret) come from Streamlit secrets
or environment variables, never from the code: the repository is public.
"""

import base64
import hashlib
import hmac
import secrets
import threading
from datetime import UTC, datetime, timedelta

from offpeak.roles import normal_role

ROUNDS = 200_000
SESSION_HOURS = 24
MAX_ATTEMPTS = 5  # wrong logins (per browser session, and per email on the server) before a pause
PAUSE = timedelta(minutes=5)


def normal_email(email) -> str:
    return str(email or "").strip().lower()


def _entries(setting: str | None) -> list[tuple[str, str]]:
    """(email, name) from a comma-separated setting; each entry is "Name <email>" or just
    an email (then the name is made from the email: mika.weymann -> Mika Weymann)."""
    out = []
    for part in (setting or "").split(","):
        part = part.strip()
        if "<" in part and part.endswith(">"):
            name, email = part[:-1].split("<", 1)
            name, email = name.strip(), normal_email(email)
        else:
            email, name = normal_email(part), ""
        if email:
            local = email.split("@")[0].replace("_", ".").replace("-", ".")
            out.append((email, name or " ".join(w.capitalize() for w in local.split(".") if w)))
    return out


def editors(setting: str | None) -> set[str]:
    """The editor emails from the setting."""
    return {email for email, _ in _entries(setting)}


def editor_names(setting: str | None) -> dict[str, str]:
    """Each editor's name, by email, for showing who is signed in."""
    return dict(_entries(setting))


def hash_password(password: str, salt: str | None = None) -> str:
    """The stored form of a password: "pbkdf2_sha256$rounds$salt$fingerprint"."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ROUNDS).hex()
    return f"pbkdf2_sha256${ROUNDS}${salt}${digest}"


def password_matches(password: str, stored: str | None) -> bool:
    try:
        method, rounds, salt, digest = (stored or "").split("$")
        rounds = int(rounds)
    except ValueError:
        return False
    if method != "pbkdf2_sha256":
        return False
    typed = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), rounds).hex()
    return hmac.compare_digest(typed, digest)  # takes the same time whatever matches


def check_login(email, password, allowed: set[str], stored_hash: str | None) -> str | None:
    """The editor's email if the login is right, else None (same answer for a wrong email
    and a wrong password, so nobody can find out which emails are editors)."""
    email = normal_email(email)
    right_password = password_matches(password, stored_hash)  # always computed: same timing
    return email if email in allowed and right_password else None


def _sign(text: str, secret: str) -> str:
    return hmac.new(secret.encode(), text.encode(), hashlib.sha256).hexdigest()


def make_token(
    email: str, now: datetime, secret: str, hours: int = SESSION_HOURS, role: str | None = None
) -> str:
    """A token that proves the login until `now + hours`. With a role ("home" or
    "business") the token also proves which portal the account belongs to: the role is part
    of what is signed, so it cannot be changed in the browser."""
    expires = int((now + timedelta(hours=hours)).timestamp())
    body = f"{normal_email(email)}|{expires}" + (f"|{role}" if role else "")
    raw = f"{body}|{_sign(body, secret)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def read_session(
    token, now: datetime, secret: str | None, allowed: set[str]
) -> tuple[str, str | None] | None:
    """(email, role) if the token is genuine, not expired and the email still allowed; role
    is None for a token made without one. None for anything else."""
    if not token or not secret:
        return None
    try:
        *body, signature = base64.urlsafe_b64decode(str(token)).decode().split("|")
        email, expires, *rest = body
        expires = int(expires)
    except (ValueError, UnicodeDecodeError):
        return None
    if len(rest) > 1 or not hmac.compare_digest(signature, _sign("|".join(body), secret)):
        return None
    if now.timestamp() >= expires or email not in allowed:
        return None
    role = normal_role(rest[0]) if rest else None
    if rest and role is None:  # a signed but unknown role: not ours
        return None
    return email, role


def read_token(token, now: datetime, secret: str | None, allowed: set[str]) -> str | None:
    """The editor's email if the token is genuine, not expired and still allowed."""
    session = read_session(token, now, secret, allowed)
    return session[0] if session else None


def may_try(failures: list[datetime], now: datetime) -> bool:
    """False after MAX_ATTEMPTS wrong logins within the last PAUSE."""
    return len([t for t in failures if now - t < PAUSE]) < MAX_ATTEMPTS


# Wrong logins per typed email, for the whole server. The count kept with the browser session
# (may_try above) starts at zero in every new tab, so a script could keep guessing without ever
# pausing. The price: someone who knows an editor's email can keep that email paused by typing
# wrong passwords; browsers that are already signed in stay signed in.
_FAILED: dict[str, list[datetime]] = {}
_FAILED_LOCK = threading.Lock()  # Streamlit runs every visitor in a thread of its own


def email_may_try(email, now: datetime) -> bool:
    """False while `email` has MAX_ATTEMPTS wrong logins within the last PAUSE, whichever
    browser they came from."""
    with _FAILED_LOCK:
        return may_try(_FAILED.get(normal_email(email), []), now)


def note_failure(email, now: datetime) -> None:
    """Remember a wrong login for `email`. Emails whose tries are all older than PAUSE are
    dropped on the way, so the memory holds the last few minutes only, however many are typed."""
    with _FAILED_LOCK:
        for old in [e for e, times in _FAILED.items() if all(now - t >= PAUSE for t in times)]:
            del _FAILED[old]
        _FAILED.setdefault(normal_email(email), []).append(now)


def forget_failures() -> None:
    """Start counting from zero (the tests do this before each test)."""
    with _FAILED_LOCK:
        _FAILED.clear()


def expires_at(token) -> datetime | None:
    """When a (genuine) token stops working; for showing "signed in until"."""
    try:
        expires = base64.urlsafe_b64decode(str(token)).decode().split("|")[1]
        return datetime.fromtimestamp(int(expires), UTC)
    except (IndexError, ValueError, UnicodeDecodeError):
        return None
