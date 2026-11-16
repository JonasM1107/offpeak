"""Only signed-in editors change shared data, checked where it is saved (app/data.py)."""

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


def add_component(at: AppTest) -> AppTest:
    at.switch_page("views/components.py").run()
    at.text_input[0].input("Test panel")
    next(b for b in at.button if b.label == "Add to site").click()
    return at.run()


def test_visitor_changes_stay_in_the_tab(fake_db):
    at = add_component(AppTest.from_file(str(APP), default_timeout=60))
    assert not at.exception
    assert fake_db == []  # nothing written to the shared database
    assert any("Test panel" in str(df.value) for df in at.dataframe)  # but visible in this tab
    assert any("not signed in" in c.value for c in at.caption)


def test_editor_changes_are_saved_for_everyone(fake_db):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["editor_token"] = auth.make_token("ann@example.com", datetime.now(UTC), SECRET)
    at = add_component(at)
    assert not at.exception
    assert len(fake_db) == 1 and any(r["name"] == "Test panel" for r in fake_db[0])


def test_a_forged_token_is_not_an_editor(fake_db):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["editor_token"] = auth.make_token("ann@example.com", datetime.now(UTC), "x")
    add_component(at)
    assert fake_db == []


def test_signing_in_on_the_account_page(fake_db):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.switch_page("views/account.py").run()
    at.text_input[0].input("ANN@example.com")
    at.text_input[1].input("wrong")
    next(b for b in at.button if b.label == "Sign in").click()
    at.run()
    assert "do not match" in at.error[0].value
    at.text_input[0].input("ANN@example.com")
    at.text_input[1].input("pw")
    next(b for b in at.button if b.label == "Sign in").click()
    at.run()
    assert not at.exception
    assert any(c.value == "Signed in as ann@example.com" for c in at.caption)
    assert any(b.label == "Sign out" for b in at.button)
