"""The app is only for signed-in team members, and only they change shared data."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from offpeak import auth, db

APP = Path(__file__).parent.parent / "app" / "main.py"
SECRET = "test-secret"


@pytest.fixture
def fake_db(monkeypatch):
    """A pretend database that records writes; nothing real is touched."""
    saved = []
    monkeypatch.setattr(db, "database_url", lambda: "postgresql://fake")
    monkeypatch.setattr(db, "get_engine", lambda url: object())
    monkeypatch.setattr(db, "read_components", lambda engine, site_id: [])
    monkeypatch.setattr(db, "save_components", lambda engine, site_id, rows: saved.append(rows))
    monkeypatch.setenv("OFFPEAK_EDITORS", "ann@example.com")
    monkeypatch.setenv("OFFPEAK_PASSWORD_HASH", auth.hash_password("pw", salt="s"))
    monkeypatch.setenv("OFFPEAK_AUTH_SECRET", SECRET)
    return saved


def visitor(page: str = "views/components.py", stored: str = "") -> AppTest:
    """A browser that is not signed in; `stored` is what its storage holds."""
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["stored_token"] = stored
    at.switch_page(page)
    return at.run()


def shows_the_app(at: AppTest) -> bool:
    """Page links (the menu's account link, links on pages) exist only inside the app."""
    return bool(at.get("page_link")) or bool(at.dataframe)


def test_without_signing_in_only_the_login_is_shown(fake_db):
    at = visitor()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Email", "Password"]
    assert not shows_the_app(at)  # no page, no menu content, no chat


def test_a_forged_or_expired_stored_sign_in_is_not_accepted(fake_db):
    forged = auth.make_token("ann@example.com", datetime.now(UTC), "guessed")
    expired = auth.make_token("ann@example.com", datetime(2020, 1, 1, tzinfo=UTC), SECRET)
    for token in (forged, expired, "junk"):
        assert not shows_the_app(visitor(stored=token))


def test_a_stored_sign_in_opens_the_app_directly(fake_db):
    token = auth.make_token("ann@example.com", datetime.now(UTC), SECRET)
    at = visitor(stored=token)
    assert shows_the_app(at)
    assert any(link.proto.label == "Ann" for link in at.get("page_link"))  # name in the menu


def test_signing_in_wrong_then_right_opens_the_page_asked_for(fake_db):
    at = visitor()
    at.text_input[0].input("ANN@example.com")
    at.text_input[1].input("wrong")
    next(b for b in at.button if b.label == "Sign in").click()
    at.run()
    assert "do not match" in at.error[0].value and not shows_the_app(at)
    at.text_input[0].input("ANN@example.com")
    at.text_input[1].input("pw")
    next(b for b in at.button if b.label == "Sign in").click()
    at.run()
    assert not at.exception and shows_the_app(at)
    assert any(b.label == "Add to site" for b in at.button)  # the components page, as asked


def test_an_editors_change_is_saved_for_everyone(fake_db):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["editor_token"] = auth.make_token("ann@example.com", datetime.now(UTC), SECRET)
    at.switch_page("views/components.py").run()
    at.text_input[0].input("Test panel")
    next(b for b in at.button if b.label == "Add to site").click()
    at.run()
    assert not at.exception
    assert len(fake_db) == 1 and any(r["name"] == "Test panel" for r in fake_db[0])


def test_signing_out_shows_the_login_again(fake_db):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["editor_token"] = auth.make_token("ann@example.com", datetime.now(UTC), SECRET)
    at.switch_page("views/account.py").run()
    next(b for b in at.button if b.label == "Sign out").click()
    at.run()
    assert not shows_the_app(at) and [t.label for t in at.text_input] == ["Email", "Password"]
