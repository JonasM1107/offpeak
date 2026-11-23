"""Two portals, one app: choosing a role, signing in with it, and each role seeing only its
own site. Pages run offline (saved API answers, see tests/test_app.py); the database is a
small fake that keeps what is written, so the checks where data is saved run for real."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from offpeak import auth, db
from tests.test_app import offline  # noqa: F401 (autouse: every page runs on saved answers)

APP = Path(__file__).parent.parent / "app" / "main.py"
SECRET = "test-secret"  # the one tests/test_app.py's offline fixture sets


@pytest.fixture
def fake_db(monkeypatch):
    """A pretend database: accounts with their role, and components per site and profile."""
    store = {"roles": {}, "components": []}
    monkeypatch.setattr(db, "database_url", lambda: "postgresql://fake")
    monkeypatch.setattr(db, "get_engine", lambda url: object())
    monkeypatch.setattr(db, "read_role", lambda engine, email: store["roles"].get(email))

    def claim(engine, email, role):
        store["roles"].setdefault(email, role)
        return store["roles"][email]

    def save(engine, site_id, rows, profile="business"):
        store["components"] += [r | {"site_id": site_id, "profile": profile} for r in rows]

    monkeypatch.setattr(db, "claim_role", claim)
    monkeypatch.setattr(db, "read_components", lambda engine, site_id, profile="business": [])
    monkeypatch.setattr(db, "save_components", save)
    monkeypatch.setattr(db, "read_machines", lambda engine, site_id, profile="business": None)
    return store


def login() -> AppTest:
    """A visitor who pressed Login on the landing page: the two role cards."""
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["stored_token"] = ""
    at.query_params["login"] = ""
    return at.run()


def press(at: AppTest, key: str) -> AppTest:
    next(b for b in at.button if b.key == key).click()
    return at.run()


def sign_in(at: AppTest, email: str = "test@example.com", password: str = "pw") -> AppTest:
    at.text_input[0].input(email)
    at.text_input[1].input(password)
    return press(at, "FormSubmitter:sign_in-Sign in")


def cards(at: AppTest) -> list[str]:
    return [b.key for b in at.button if (b.key or "").startswith("choose_")]


def inside_the_app(at: AppTest) -> bool:
    """The account link at the bottom of the menu exists only for a signed-in account."""
    return bool(at.get("page_link"))


def titles(at: AppTest) -> set[str]:
    """The titles of the pages that differ between the roles, as their headers show them
    (escaped like the page shows them: "&" is "&amp;")."""
    from html import unescape

    found = set()
    for page in ("views/site.py", "views/components.py", "views/cockpit.py"):
        at.switch_page(page).run()
        for h in at.get("html"):
            if 'class="op-title"' in h.proto.body:
                found.add(unescape(h.proto.body.split('class="op-title">')[1].split("<")[0]))
    return found


def signed_in(role: str | None) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["editor_token"] = auth.make_token(
        "test@example.com", datetime.now(UTC), SECRET, role=role
    )
    return at


# ── step 1: choosing a role ──────────────────────────────────────────────────


def test_login_starts_with_the_two_role_cards():
    at = login()
    assert not at.exception
    assert cards(at) == ["choose_home", "choose_business"]
    assert not at.text_input  # no email or password before a role is chosen


def test_a_card_opens_the_sign_in_for_that_role():
    at = press(login(), "choose_home")
    assert [t.label for t in at.text_input] == ["Email", "Password"]
    assert any("Homeowner" in h.proto.body for h in at.get("html"))
    at = press(at, "login_change")  # "Choose another role"
    assert cards(at) == ["choose_home", "choose_business"]


def test_back_from_the_cards_returns_to_the_landing_page():
    at = press(login(), "login_back")
    assert any("Peak prices" in f.proto.srcdoc for f in at.get("iframe"))


@pytest.mark.parametrize("forged", ["admin", "", None, "HOME; drop table accounts"])
def test_a_role_that_is_not_one_shows_the_cards_again(forged):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["stored_token"] = ""
    at.session_state["login_role"] = forged
    at.query_params["login"] = ""
    at.run()
    assert not at.exception and cards(at) == ["choose_home", "choose_business"]


# ── step 2: signing in with a role ──────────────────────────────────────────


@pytest.mark.parametrize(
    "role, view, setup, planner",
    [
        ("home", "Home view", "Home & devices", "Appliance planner"),
        ("business", "Site view", "Site & components", "Simulation cockpit"),
    ],
)
def test_first_sign_in_stores_the_role_and_opens_its_portal(fake_db, role, view, setup, planner):
    at = sign_in(press(login(), f"choose_{role}"))
    assert not at.exception
    assert fake_db["roles"] == {"test@example.com": role}
    assert inside_the_app(at)
    token = at.session_state["editor_token"]
    assert auth.read_session(token, datetime.now(UTC), SECRET, {"test@example.com"})[1] == role
    assert titles(at) == {view, setup, planner}


def test_the_other_role_is_refused_with_a_clear_message(fake_db):
    fake_db["roles"]["test@example.com"] = "home"
    at = sign_in(press(login(), "choose_business"))
    assert not at.exception
    assert "Homeowner account" in at.error[0].value
    assert not inside_the_app(at) and fake_db["roles"]["test@example.com"] == "home"


def test_a_wrong_password_is_refused_whatever_the_role(fake_db):
    at = sign_in(press(login(), "choose_home"), password="wrong")
    assert "do not match" in at.error[0].value and not fake_db["roles"]


def test_without_a_database_the_role_holds_for_this_browser():
    at = sign_in(press(login(), "choose_home"))
    assert not at.exception
    assert inside_the_app(at)
    assert any("this browser" in t.proto.body for t in at.get("toast"))
    assert "Home view" in titles(at)


def test_a_signed_in_account_goes_straight_to_its_portal():
    at = signed_in("home").run()
    assert not at.exception and inside_the_app(at) and not cards(at)
    assert titles(at) == {"Home view", "Home & devices", "Appliance planner"}


def test_a_token_from_before_roles_opens_the_business_portal():
    at = signed_in(None).run()
    assert not at.exception and inside_the_app(at)
    assert titles(at) == {"Site view", "Site & components", "Simulation cockpit"}


def test_wrong_passwords_pause_the_email_even_from_fresh_browsers():
    """Five wrong tries, each from a new browser (so the count kept per browser never fills
    up): the email is paused on the server, and even the right password has to wait."""
    for _ in range(auth.MAX_ATTEMPTS):
        at = sign_in(press(login(), "choose_business"), password="a wrong guess")
        assert "do not match" in at.error[0].value
    at = sign_in(press(login(), "choose_business"), password="pw")  # the right password
    assert not at.exception
    assert "Too many wrong attempts" in at.error[0].value and not inside_the_app(at)


# ── each role sees and changes only its own site ────────────────────────────


@pytest.mark.parametrize(
    "page",
    [
        "views/dashboard.py",
        "views/site.py",
        "views/analytics.py",
        "views/weather.py",
        "views/outlook.py",
        "views/cockpit.py",
        "views/savings.py",
        "views/components.py",
        "views/settings.py",
        "views/account.py",
    ],
)
def test_every_page_opens_in_the_home_portal(page):
    at = signed_in("home")
    at.switch_page(page).run()
    assert not at.exception


def shown(at: AppTest) -> str:
    """Everything the page wrote as HTML (card titles, the rows of facts)."""
    return " ".join(h.proto.body for h in at.get("html"))


@pytest.mark.parametrize(
    "role, own, other", [("home", "Demo home", "Demo site"), ("business", "Demo site", "Demo home")]
)
def test_the_account_page_names_the_roles_own_site(role, own, other):
    at = signed_in(role)
    at.switch_page("views/account.py").run()
    assert not at.exception
    assert f"{own} · Köln" in shown(at) and other not in shown(at)


def test_the_home_settings_name_the_roofs_real_direction():
    """The demo home's roof faces 145 degrees: south-east, not the business site's south."""
    at = signed_in("home")
    at.switch_page("views/settings.py").run()
    assert "facing 145° (south-east)" in shown(at)
    assert "devices are changed under Home &amp; devices" in shown(at)


@pytest.mark.parametrize(
    "role, title, view",
    [("home", "Home layout", "home view"), ("business", "Site layout", "site view")],
)
def test_the_designer_speaks_the_roles_words(role, title, view):
    at = signed_in(role)
    at.switch_page("views/components.py").run()
    assert not at.exception
    assert title in shown(at) and f"shows up in the {view}." in shown(at)
    # both buttons of the designer are still there, side by side
    assert any(b.label == "Clear field" for b in at.button)
    assert any(b.key == "designer_reset" for b in at.button)


def test_the_home_portal_offers_household_devices_only():
    at = signed_in("home")
    at.switch_page("views/components.py").run()
    options = set(at.selectbox[0].options)
    assert {"Wallbox", "Home battery", "Household appliance"} <= options
    assert not options & {"Electric furnace", "Cold store", "Wind turbine", "Solar field"}
    names = set(at.dataframe[0].value["Name"])
    assert {"Washing machine", "Wallbox"} <= names and "Electric furnace" not in names


def test_a_home_device_is_saved_for_the_home_only(fake_db):
    at = signed_in("home")
    at.switch_page("views/components.py").run()
    at.selectbox[0].select("Household appliance").run()
    at.text_input[0].input("Dishwasher")
    next(b for b in at.button if b.label == "Add to home").click()
    at.run()
    assert not at.exception
    saved = fake_db["components"]
    assert saved and {r["profile"] for r in saved} == {"home"}
    assert {r["site_id"] for r in saved} == {2}  # the demo home, not the business site
    assert "Dishwasher" in {r["name"] for r in saved}


def test_a_device_name_is_saved_as_text_only_and_not_endless(fake_db):
    """Checked where the device is saved (app/data.py), whatever the form sent: a script
    typed as a name is stored without its tags, and a name is never longer than allowed."""
    from offpeak.components import MAX_NAME

    at = signed_in("home")
    at.switch_page("views/components.py").run()
    at.selectbox[0].select("Household appliance").run()
    at.text_input[0].input('<img src=x onerror="steal()">Dishwasher' + "y" * 300)
    next(b for b in at.button if b.label == "Add to home").click()
    at.run()
    assert not at.exception
    name = next(r["name"] for r in fake_db["components"] if "Dishwasher" in r["name"])
    assert "<" not in name and ">" not in name and len(name) <= MAX_NAME


def test_saving_refuses_a_device_of_the_other_role(monkeypatch):
    """The check where data is saved, not only on the page: a business machine sent for a
    home account is refused, whatever a page or a browser sends."""
    import sys

    sys.path.insert(0, str(APP.parent))
    import data

    from offpeak.components import new_component

    monkeypatch.setattr(data, "role", lambda: "home")
    furnace = new_component("furnace", "Furnace")  # a business kind
    with pytest.raises(ValueError):
        data.add_component(furnace)


def test_counts_stay_whole_numbers_in_the_form():
    """A wallbox has 1 or 2 chargers, never 1.5: only kW values get 0.1 steps."""
    at = signed_in("home")
    at.switch_page("views/components.py").run()
    at.selectbox[0].select("Wallbox").run()
    steps = {n.label: n.step for n in at.number_input}
    assert steps["Chargers"] == 1 and steps["Charging power (kW)"] == 1
    at.selectbox[0].select("Household appliance").run()
    steps = {n.label: n.step for n in at.number_input}
    assert steps["Electrical power (kW)"] == 0.1 and steps["Run time (h)"] == 1


def test_every_planner_template_passes_the_cockpit_check():
    """The planner's "Add" templates (offpeak/roles.py) are saved through clean_machines like
    anything from the browser: each must come back unchanged, for both roles."""
    from offpeak.cockpit import clean_machines
    from offpeak.roles import PLANNER_PRESETS, words

    keys = ["name", "kw", "hours", "earliest", "latest_end", "usual_start"]
    for role, presets in PLANNER_PRESETS.items():
        machines = [dict(zip(keys, p, strict=True)) for p in presets]
        assert clean_machines(machines) == machines, role
    assert words("home")["machine"] == "device" and words("business")["machine"] == "machine"
