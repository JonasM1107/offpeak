"""The landing page in front of the app: visitors see it first, Login leads to the sign-in."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from offpeak import auth, db

APP = Path(__file__).parent.parent / "app" / "main.py"
PAGE = Path(__file__).parent.parent / "app" / "ui" / "web" / "landing.html"
SECRET = "test-secret"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    """Sign-in configured as on the server; no database is touched."""
    monkeypatch.setattr(db, "database_url", lambda: None)
    monkeypatch.setenv("OFFPEAK_EDITORS", "ann@example.com")
    monkeypatch.setenv("OFFPEAK_PASSWORD_HASH", auth.hash_password("pw", salt="s"))
    monkeypatch.setenv("OFFPEAK_AUTH_SECRET", SECRET)


def visitor(stored: str = "", query: dict | None = None) -> AppTest:
    """A browser at the app's plain address; `stored` is the sign-in its storage holds."""
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["stored_token"] = stored
    for key, value in (query or {}).items():
        at.query_params[key] = value
    return at.run()


def landing_shown(at: AppTest) -> bool:
    frames = at.get("iframe")
    return any("Peak prices" in f.proto.srcdoc for f in frames)


def login_shown(at: AppTest) -> bool:
    """The login screen: step 1 (the two role cards) or step 2 (email and password)."""
    cards = [b.key for b in at.button if (b.key or "").startswith("choose_")]
    form = [t.label for t in at.text_input] == ["Email", "Password"]
    return cards == ["choose_home", "choose_business"] or form


def press(at: AppTest, key: str) -> AppTest:
    next(b for b in at.button if b.key == key).click()
    return at.run()


def test_a_visitor_sees_the_landing_page_not_the_app():
    at = visitor()
    assert not at.exception
    assert landing_shown(at)
    assert not login_shown(at)
    assert not at.get("page_link")  # no menu, nothing of the app


def test_login_on_the_landing_page_opens_the_sign_in():
    at = press(visitor(), "landing_login")
    assert not at.exception
    assert login_shown(at) and not landing_shown(at)


def test_the_address_with_login_opens_the_sign_in_directly():
    at = visitor(query={"login": ""})
    assert login_shown(at) and not landing_shown(at)


def test_back_from_the_sign_in_returns_to_the_landing_page():
    at = press(press(visitor(), "landing_login"), "login_back")
    assert not at.exception
    assert landing_shown(at) and not login_shown(at)


def test_back_also_clears_login_from_the_address():
    at = press(visitor(query={"login": ""}), "login_back")
    assert landing_shown(at)
    assert "login" not in at.query_params


def test_signing_in_after_the_landing_page_opens_the_app():
    at = press(press(visitor(), "landing_login"), "choose_business")  # the Business card
    at.text_input[0].input("ann@example.com")
    at.text_input[1].input("pw")
    at = press(at, "FormSubmitter:sign_in-Sign in")
    assert not at.exception
    assert at.get("page_link") and not landing_shown(at)


def test_a_signed_in_visitor_skips_the_landing_page():
    token = auth.make_token("ann@example.com", datetime.now(UTC), SECRET)
    at = visitor(stored=token)
    assert not landing_shown(at) and at.get("page_link")


def test_before_the_browser_answers_neither_page_flashes_by():
    """Until the browser says whether it holds a sign-in, only a short wait is shown."""
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert not landing_shown(at) and not login_shown(at)


def test_the_landing_page_and_the_sign_in_share_the_power_lines():
    """Both pages get web/field.js put in; no placeholder is left behind."""
    at = visitor()
    landing = next(f.proto.srcdoc for f in at.get("iframe") if "Peak prices" in f.proto.srcdoc)
    assert "function PowerField" in landing and "<!--FIELD-->" not in landing
    at = press(at, "landing_login")
    background = [
        f.proto.srcdoc for f in at.get("iframe") if "PowerField(document" in f.proto.srcdoc
    ]
    assert len(background) == 1 and "<!--FIELD-->" not in background[0]


def test_no_style_block_is_dropped_by_the_html_cleaner():
    """st.html removes a whole <style> block whose text contains "<" followed by a letter,
    "/" or "!" (it looks like a tag). That once took away every style of the app, so check
    each style block the sign-in and landing page send."""
    at = press(visitor(), "landing_login")  # the sign-in page, after the landing page
    styles = [h.proto.body for h in at.get("html") if "<style>" in h.proto.body]
    styles += [h.proto.body for h in visitor().get("html") if "<style>" in h.proto.body]
    assert len(styles) >= 4
    for block in styles:
        for css in re.findall(r"<style>(.*?)</style>", block, flags=re.S):
            assert not re.search(r"<[/\w!]", css), css[:80]


def test_every_menu_link_has_a_section_to_scroll_to():
    """Product, Pricing, ... scroll to a part of the page; each needs that part to exist."""
    html = PAGE.read_text()
    targets = set(re.findall(r'href="#([\w-]+)"', html))
    ids = set(re.findall(r'id="([\w-]+)"', html))
    assert {"product", "how", "for", "pricing"} <= targets
    assert targets <= ids


def test_every_screenshot_on_the_page_exists_and_is_served():
    """The look inside the app shows files from app/static/, which Streamlit only serves
    when static serving is switched on in .streamlit/config.toml."""
    import tomllib

    root = Path(__file__).parent.parent
    images = re.findall(r'src="app/static/([^"]+)"', PAGE.read_text())
    assert len(images) == 3
    assert all((root / "app" / "static" / name).is_file() for name in images)
    config = tomllib.loads((root / ".streamlit" / "config.toml").read_text())
    assert config["server"]["enableStaticServing"] is True


def test_the_page_runs_no_outside_scripts_and_every_login_link_works_alone():
    """The landing page is our own file: no scripts from elsewhere, and each Login link also
    works when the page is opened outside the app (it then goes to the sign-in)."""
    html = PAGE.read_text()
    assert not re.search(r"<script[^>]+src=", html)
    links = re.findall(r"<a [^>]*data-login[^>]*>", html)
    assert len(links) >= 3
    assert all('href="https://offpeak.streamlit.app/?login"' in a for a in links)
