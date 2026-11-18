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
    monkeypatch.setattr(db, "read_components", lambda engine, site_id, profile="business": [])
    monkeypatch.setattr(
        db,
        "save_components",
        lambda engine, site_id, rows, profile="business": saved.append(rows),
    )
    monkeypatch.setenv("OFFPEAK_EDITORS", "ann@example.com")
    monkeypatch.setenv("OFFPEAK_PASSWORD_HASH", auth.hash_password("pw", salt="s"))
    monkeypatch.setenv("OFFPEAK_AUTH_SECRET", SECRET)
    return saved


def visitor(page: str = "views/components.py", stored: str = "") -> AppTest:
    """A browser that is not signed in; `stored` is what its storage holds."""
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["stored_token"] = stored
    at.session_state["login_role"] = "business"  # step 1 of signing in: the Business card
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
    # the login starts again at step 1: the two role cards
    cards = [b.key for b in at.button if (b.key or "").startswith("choose_")]
    assert not shows_the_app(at) and cards == ["choose_home", "choose_business"]


# ── "Edit site" on the site view ─────────────────────────────────────────────


def site_editor(fake_db, monkeypatch, role: str = "business") -> tuple[AppTest, list]:
    """A signed-in editor on the Edit site page; returns the app and what replace_components
    got."""
    replaced = []
    monkeypatch.setattr(
        db,
        "replace_components",
        lambda e, site_id, rows, profile="business": replaced.append((profile, rows)),
    )
    at = AppTest.from_file(str(APP), default_timeout=60)
    token = auth.make_token("ann@example.com", datetime.now(UTC), SECRET, role=role)
    at.session_state["editor_token"] = token
    at.switch_page("views/site_edit.py").run()
    return at, replaced


def click(at: AppTest, label: str) -> None:
    next(b for b in at.button if b.label == label).click()
    at.run()
    assert not at.exception


def test_edit_site_starts_empty_and_saves_what_was_built(fake_db, monkeypatch):
    at, replaced = site_editor(fake_db, monkeypatch)
    assert any("Your site is empty" in i.value for i in at.info)
    click(at, "Heat pump")
    click(at, "Heat pump")  # a second one gets its own name
    click(at, "Rooftop solar")
    click(at, "Save site")
    assert len(replaced) == 1
    profile, rows = replaced[0]
    assert profile == "business"
    assert [r["name"] for r in rows] == ["Heat pump", "Heat pump 2", "Rooftop solar"]
    assert "Saved for everyone" in at.success[0].value


def test_edit_site_does_not_save_an_empty_site_or_a_duplicate_name(fake_db, monkeypatch):
    at, replaced = site_editor(fake_db, monkeypatch)
    click(at, "Save site")
    assert "Add at least one component" in at.error[0].value
    click(at, "Battery storage")
    click(at, "Battery storage")
    next(t for t in at.text_input if t.value == "Battery storage 2").input("battery storage")
    at.run()
    click(at, "Save site")
    assert "two components have this name" in at.error[0].value
    assert replaced == [] and fake_db == []  # nothing reached the database


def test_cancel_leaves_the_site_as_it_was(fake_db, monkeypatch):
    at, replaced = site_editor(fake_db, monkeypatch)
    click(at, "Wind turbine")
    click(at, "Cancel")
    assert replaced == [] and not any(b.label == "Save site" for b in at.button)  # left


def test_without_a_database_the_edited_site_is_kept_in_the_tab(fake_db, monkeypatch):
    monkeypatch.setattr(db, "database_url", lambda: None)
    at, replaced = site_editor(fake_db, monkeypatch)
    click(at, "Cold store")
    click(at, "Save site")
    assert replaced == []
    assert [c.name for c in at.session_state["components_local_business"]] == ["Cold store"]


def test_edit_site_is_only_for_the_business_portal(fake_db, monkeypatch):
    # a homeowner's menu has no Edit site page, so Streamlit does not open it at all
    at, replaced = site_editor(fake_db, monkeypatch, role="home")
    assert not at.exception
    assert not any(b.label == "Save site" for b in at.button) and replaced == []


def test_the_site_view_itself_has_no_editor(fake_db, monkeypatch):
    """The original site view stays as it was: the editor is only on its own page."""
    at, _ = site_editor(fake_db, monkeypatch)
    at.switch_page("views/site.py").run()
    assert not at.exception
    assert not any(b.label in ("Edit site", "Save site") for b in at.button)


def test_saving_a_site_is_refused_for_a_home_account(fake_db, monkeypatch):
    """The check sits where the site is saved (data.replace_site), not only on the page."""
    import sys

    sys.path.insert(0, str(APP.parent))
    import data

    from offpeak import components

    monkeypatch.setattr(data, "role", lambda: "home")
    replaced = []
    monkeypatch.setattr(db, "replace_components", lambda *a, **k: replaced.append(a))
    battery = components.new_component("battery", "Battery")
    where, problems = data.replace_site([battery])
    assert where is None and problems == ["Edit site is part of the Business portal."]
    assert replaced == []


def test_a_saved_site_with_repeated_names_can_be_moved_and_saved(fake_db, monkeypatch):
    """The live bug: a site saved on Site & components (two parts with one name, an extra
    setting) could not be saved again after moving a part in Edit site."""
    import sys

    sys.path.insert(0, str(APP.parent))  # the app's own folders (ui), as Streamlit has them
    from ui import layout_designer

    saved_before = [
        {"id": "pv-a", "kind": "pv_field", "name": "Solar field", "params": {"kwp": 40}},
        {"id": "pv-b", "kind": "pv_field", "name": "Solar field", "params": {"kwp": 20}},
        {"id": "bat", "kind": "battery", "name": "Battery", "params": {"kwh": 120, "note": "x"}},
    ]
    monkeypatch.setattr(
        db,
        "read_components",
        lambda engine, site_id, profile="business": [
            r | {"profile": profile} for r in saved_before
        ],
    )
    events = []
    monkeypatch.setattr(layout_designer, "show", lambda *a, **k: events[-1] if events else None)
    at, replaced = site_editor(fake_db, monkeypatch)  # opens on the saved site
    names = [c.name for c in at.session_state["site_draft"]]
    assert names == ["Solar field", "Solar field 2", "Battery"]
    battery = next(c for c in at.session_state["site_draft"] if c.kind == "battery")
    events.append({"action": "move", "id": battery.id, "col": 20, "row": 50, "n": "1"})
    at.run()
    click(at, "Save site")
    assert not at.error and len(replaced) == 1
    profile, rows = replaced[0]
    moved = next(r for r in rows if r["id"] == "bat")
    assert (moved["params"]["col"], moved["params"]["row"]) == (20, 50)
