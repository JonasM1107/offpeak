"""Roles: the rules in offpeak/ (role choice at sign-in, signed roles, separate catalogues)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from offpeak import auth
from offpeak import components as C
from offpeak.roles import normal_role, sign_in_role
from offpeak.sites import DEMO_HOME, DEMO_SITE, site_for

NOW = datetime(2026, 11, 18, 12, tzinfo=UTC)
SECRET = "s"
ALLOWED = {"ann@example.com"}


# ── choosing a role ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("value, role", [("home", "home"), (" Business ", "business")])
def test_normal_role_accepts_the_two_roles(value, role):
    assert normal_role(value) == role


@pytest.mark.parametrize("value", [None, "", "admin", "homeowner", 3, "home; drop table"])
def test_normal_role_rejects_anything_else(value):
    assert normal_role(value) is None


def test_first_sign_in_takes_the_chosen_role():
    assert sign_in_role("home", None) == ("home", None)


def test_the_stored_role_signs_in():
    assert sign_in_role("business", "business") == ("business", None)


def test_the_other_role_is_refused_and_named():
    role, problem = sign_in_role("business", "home")
    assert role is None and "Homeowner account" in problem


@pytest.mark.parametrize("chosen", [None, "", "admin"])
def test_without_a_valid_choice_there_is_no_role(chosen):
    role, problem = sign_in_role(chosen, "home")
    assert role is None and "Choose" in problem


def test_each_role_has_its_own_site():
    assert site_for("business") is DEMO_SITE and site_for("home") is DEMO_HOME
    assert DEMO_SITE.id != DEMO_HOME.id and DEMO_HOME.profile == "home"
    with pytest.raises(ValueError):
        site_for("admin")


# ── the role in the token ────────────────────────────────────────────────────


def test_a_token_carries_its_role():
    token = auth.make_token("ann@example.com", NOW, SECRET, role="home")
    assert auth.read_session(token, NOW, SECRET, ALLOWED) == ("ann@example.com", "home")
    assert auth.read_token(token, NOW, SECRET, ALLOWED) == "ann@example.com"
    assert auth.expires_at(token) == NOW + timedelta(hours=auth.SESSION_HOURS)


def test_an_old_token_without_a_role_still_reads():
    token = auth.make_token("ann@example.com", NOW, SECRET)
    assert auth.read_session(token, NOW, SECRET, ALLOWED) == ("ann@example.com", None)


def test_the_role_in_a_token_cannot_be_changed():
    import base64

    token = auth.make_token("ann@example.com", NOW, SECRET, role="home")
    raw = base64.urlsafe_b64decode(token).decode().replace("|home|", "|business|")
    forged = base64.urlsafe_b64encode(raw.encode()).decode()
    assert auth.read_session(forged, NOW, SECRET, ALLOWED) is None


def test_a_signed_unknown_role_is_refused():
    token = auth.make_token("ann@example.com", NOW, SECRET, role="admin")
    assert auth.read_session(token, NOW, SECRET, ALLOWED) is None


# ── one catalogue per role ───────────────────────────────────────────────────


def test_the_home_catalogue_has_household_devices_only():
    home = set(C.HOME_CATALOGUE)
    assert {"pv_roof", "battery", "heat_pump", "ev_charger", "appliance", "household"} == home
    assert not home & {"pv_field", "wind", "furnace", "cold_store"}
    assert not set(C.CATALOGUE) & {"appliance", "household"}
    assert C.HOME_CATALOGUE["ev_charger"].label == "Wallbox"


def test_demo_home_works_in_the_energy_model():
    assets, loads = C.site_model(C.DEFAULT_HOME_COMPONENTS)
    assert assets.pv_kwp == 8 and assets.battery_kwh == 10 and assets.turbines == 0
    assert assets.cold_store_kw == pytest.approx(0.35)  # the household base load
    assert {f.key for f in loads} == {"home-heat-pump", "home-wallbox", "home-washer", "home-dryer"}
    wallbox = next(f for f in loads if f.key == "home-wallbox")
    assert wallbox.kw == 11  # one charger


def test_a_whole_day_for_the_demo_home():
    """The day the Home view draws: every device gets its own power series, and the base
    load is the household's (not a cold store)."""
    from offpeak import demo_site

    assets, _ = C.site_model(C.DEFAULT_HOME_COMPONENTS)
    inputs = demo_site.hourly_inputs(None, None, "Europe/Berlin", assets)
    day = C.site_day(inputs, C.DEFAULT_HOME_COMPONENTS)
    assert set(day["series"]["offpeak"]) == {c.id for c in C.DEFAULT_HOME_COMPONENTS}
    base = day["series"]["offpeak"]["home-base"]
    assert len(base) == 24 and base[0] == pytest.approx(0.35)
    labels = {c["id"]: c["kind_label"] for c in day["components"]}
    assert labels["home-wallbox"] == "Wallbox" and labels["home-battery"] == "Home battery"


def test_check_profile_accepts_the_own_catalogue():
    C.check_profile(C.DEFAULT_HOME_COMPONENTS, "home")
    C.check_profile(C.DEFAULT_COMPONENTS, "business")


@pytest.mark.parametrize(
    "components, profile",
    [
        (C.DEFAULT_COMPONENTS, "home"),  # a business's components in a home
        (C.DEFAULT_HOME_COMPONENTS, "business"),  # a home's devices in a business
        ([replace(C.DEFAULT_HOME_COMPONENTS[0], kind="furnace")], "home"),  # foreign kind
        ([], "admin"),  # no such profile
    ],
)
def test_check_profile_refuses_the_other_role(components, profile):
    with pytest.raises(ValueError):
        C.check_profile(components, profile)


def test_validate_refuses_a_kind_from_the_other_catalogue():
    assert C.validate("appliance", {}, "home") == []
    assert C.validate("appliance", {}, "business") == [
        "This kind of component is not available here"
    ]
    assert C.validate("furnace", {}, "home") == ["This kind of component is not available here"]


def test_new_home_component_takes_household_defaults():
    c = C.new_component("battery", "Battery", profile="home")
    assert c.profile == "home" and c.params["kwh"] == 10 and c.spec.label == "Home battery"
