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


# ── The site designer on Site & components ───────────────────────────────────


def site_designer(fake_db, monkeypatch, role="business", saved=()) -> tuple[AppTest, list, list]:
    """A signed-in editor on Site & components with the site `saved` in the database.
    Returns the app, what replace_components got, and a list: append a designer action to
    it and run the app, as if the browser had sent it."""
    import sys

    sys.path.insert(0, str(APP.parent))  # the app's own folders (ui), as Streamlit has them
    from ui import layout_designer

    rows = [dict(r) for r in saved]
    monkeypatch.setattr(
        db,
        "read_components",
        lambda engine, site_id, profile="business": [r | {"profile": profile} for r in rows],
    )
    replaced = []

    def replace(engine, site_id, new_rows, profile="business"):
        replaced.append((profile, new_rows))
        rows[:] = new_rows  # what the next read gets, like the real database

    monkeypatch.setattr(db, "replace_components", replace)
    events = []
    monkeypatch.setattr(layout_designer, "show", lambda *a, **k: events[-1] if events else None)
    at = AppTest.from_file(str(APP), default_timeout=60)
    token = auth.make_token("ann@example.com", datetime.now(UTC), SECRET, role=role)
    at.session_state["editor_token"] = token
    at.switch_page("views/components.py").run()
    assert not at.exception
    return at, replaced, events


BATTERY = {"id": "bat", "kind": "battery", "name": "Battery", "params": {"kwh": 120}}
SOLAR = {"id": "pv", "kind": "pv_field", "name": "Solar field", "params": {"kwp": 40}}


def act(at: AppTest, events: list, **event) -> None:
    events.append({**event, "n": str(len(events))})
    at.run()
    assert not at.exception


def test_a_part_dragged_onto_the_site_is_saved_at_once(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=[BATTERY])
    act(at, events, action="add", kind="heat_pump")
    assert len(replaced) == 1
    profile, rows = replaced[0]
    assert profile == "business" and [r["name"] for r in rows] == ["Battery", "Heat pump"]
    assert all("col" in r["params"] for r in rows)  # every part has its square
    # the table below the designer shows it right away
    assert "Heat pump" in at.dataframe[0].value["Name"].tolist()


def test_a_moved_part_keeps_its_new_square(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=[BATTERY, SOLAR])
    act(at, events, action="move", id="bat", col=20, row=50)
    moved = next(r for r in replaced[-1][1] if r["id"] == "bat")
    assert (moved["params"]["col"], moved["params"]["row"]) == (20, 50)


def test_a_move_that_does_not_fit_is_refused_and_nothing_saved(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=[BATTERY])
    act(at, events, action="move", id="bat", col=0, row=0)  # the corner is outside the fence
    assert replaced == []
    assert any("fence" in w.value for w in at.warning)


def test_the_last_part_cannot_be_removed(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=[BATTERY])
    act(at, events, action="remove", id="bat")
    assert replaced == []
    assert any("Add at least one component" in w.value for w in at.warning)


def test_a_part_added_with_the_form_gets_a_square_too(fake_db, monkeypatch):
    """So the designer and the site view show it where it stays, not somewhere new on
    every visit."""
    at, _, _ = site_designer(fake_db, monkeypatch)
    at.text_input[0].input("Test panel")
    next(b for b in at.button if b.label == "Add to site").click()
    at.run()
    assert not at.exception
    added = next(r for r in fake_db[-1] if r["name"] == "Test panel")
    assert "col" in added["params"] and "row" in added["params"]


def test_size_and_hours_are_saved_when_valid(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=[BATTERY, SOLAR])
    act(at, events, action="select", id="bat")
    assert replaced == []  # tapping a part changes nothing
    next(t for t in at.text_input if t.key == "designer_bat_name").input("Solar field")
    at.run()
    assert replaced == []  # two parts with one name: refused
    assert any("two components have this name" in w.value for w in at.warning)
    next(t for t in at.text_input if t.key == "designer_bat_name").input("Big battery")
    at.run()
    assert [r["name"] for r in replaced[-1][1]] == ["Big battery", "Solar field"]


def test_without_a_database_the_site_is_kept_in_the_tab(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=[BATTERY])
    monkeypatch.setattr(db, "database_url", lambda: None)
    at.run()
    act(at, events, action="add", kind="cold_store")
    assert replaced == []
    assert "Cold store" in [c.name for c in at.session_state["components_local_business"]]


def test_a_home_has_no_site_designer(fake_db, monkeypatch):
    at, replaced, events = site_designer(fake_db, monkeypatch, role="home")
    act(at, events, action="add", kind="heat_pump")
    assert replaced == [] and "card_designer" not in str(at.main)


def test_the_site_view_itself_has_no_editor(fake_db, monkeypatch):
    """The site view stays as it was: the designer is on Site & components only."""
    at, _, _ = site_designer(fake_db, monkeypatch)
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


def test_a_saved_site_with_repeated_names_can_be_moved(fake_db, monkeypatch):
    """A site saved on Site & components before (two parts with one name, an extra setting)
    is tidied when the designer saves it, instead of refusing the move."""
    saved = [
        {"id": "pv-a", "kind": "pv_field", "name": "Solar field", "params": {"kwp": 40}},
        {"id": "pv-b", "kind": "pv_field", "name": "Solar field", "params": {"kwp": 20}},
        {"id": "bat", "kind": "battery", "name": "Battery", "params": {"kwh": 120, "note": "x"}},
    ]
    at, replaced, events = site_designer(fake_db, monkeypatch, saved=saved)
    act(at, events, action="move", id="bat", col=20, row=50)
    assert len(replaced) == 1
    rows = replaced[0][1]
    assert [r["name"] for r in rows] == ["Solar field", "Solar field 2", "Battery"]
    moved = next(r for r in rows if r["id"] == "bat")
    assert (moved["params"]["col"], moved["params"]["row"]) == (20, 50)


def test_a_failed_save_says_why(fake_db, monkeypatch):
    """On the live app the logs are hard to reach: the editor sees the database's reason."""

    def fails(*a, **k):
        raise RuntimeError("something the database said\nmore detail")

    at, _, events = site_designer(fake_db, monkeypatch, saved=[BATTERY, SOLAR])
    monkeypatch.setattr(db, "replace_components", fails)
    act(at, events, action="move", id="bat", col=20, row=50)
    assert any(
        "could not be saved right now (RuntimeError: something the database said)" in w.value
        for w in at.warning
    )
