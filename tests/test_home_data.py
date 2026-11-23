"""A home's own measurements in the app: the measured day ("Yesterday at home"), the scene's
third plan, the My data page and the dashboard card. Made-up data from tests/fixtures/."""

from datetime import date

import pytest

from offpeak import components as C
from offpeak import demo_site
from offpeak.load import fronius, measured
from offpeak.tariffs import tariff_for
from tests.conftest import FIXTURES
from tests.test_app import offline  # noqa: F401 (autouse: pages run on saved answers)
from tests.test_app_roles import signed_in

TZ = "Europe/Berlin"


@pytest.fixture
def slots():
    return fronius.read_csv(FIXTURES / "fronius_sample.csv")


def test_full_days_and_the_newest_before_today(slots):
    assert measured.full_days(slots, TZ) == [date(2026, 6, 2), date(2026, 6, 3)]
    assert measured.last_full_day(slots, TZ, date(2026, 6, 4)) == date(2026, 6, 3)
    assert measured.last_full_day(slots, TZ, date(2026, 6, 2)) is None
    assert measured.full_days(slots.iloc[:0], TZ) == []


def test_a_measured_day_by_the_hour(slots):
    day = measured.hourly_day(slots, date(2026, 6, 2), TZ)
    assert len(day) == 24 and list(day["hour"]) == list(range(24))
    assert day.loc[3, "pv_kw"] == 0 and day.loc[13, "pv_kw"] > 3  # night and midday
    # every hour balances: solar + grid = house + battery
    balance = day["pv_kw"] + day["grid_kw"] - day["load_kw"] - day["battery_kw"]
    assert balance.abs().max() < 0.05


def measured_plan(slots):
    comps = list(C.DEFAULT_HOME_COMPONENTS)
    tariff = tariff_for("home", comps)
    assets, _ = C.site_model(comps)
    inputs = demo_site.apply_tariff(
        demo_site.hourly_inputs(None, None, TZ, assets), tariff, date(2026, 6, 2)
    )
    return comps, C.measured_day(
        inputs, comps, measured.hourly_day(slots, date(2026, 6, 2), TZ), tariff
    )


def test_a_measured_day_has_the_shape_of_a_plan(slots):
    comps, m = measured_plan(slots)
    assert len(m["rows"]) == 24 and set(m["series"]) == {c.id for c in comps}
    # a meter sees the house, not each device: all consumption is the base load's
    assert sum(m["series"]["home-base"]) == pytest.approx(sum(r["load_kw"] for r in m["rows"]))
    assert sum(m["series"]["home-wallbox"]) == 0
    # a sunny June day: selling earns more than buying costs, so the bill can be negative
    assert isinstance(m["bill"]["total"], float) and len(m["price_class"]) == 24


def test_the_scene_gets_a_third_plan(slots):
    import sys

    from tests.test_app import APP

    sys.path.insert(0, str(APP.parent))
    from ui import site_scene

    comps, m = measured_plan(slots)
    m["date"] = "Tue 2 Jun"
    tariff = tariff_for("home", comps)
    inputs = demo_site.apply_tariff(
        demo_site.hourly_inputs(None, None, TZ, C.site_model(comps)[0]), tariff, date(2026, 6, 2)
    )
    site = {"name": "Demo home", "city": "Köln", "zone": "DE-LU", "date": "2026-06-02"}
    data = site_scene.payload(inputs, site, 12, tariff, comps, m)
    assert set(data["rows"]) == {"offpeak", "usual", "measured"}
    assert data["measured"]["date"] == "Tue 2 Jun" and "measured" in data["bill"]
    assert all("measured" in c["analytics"] for c in data["components"])
    plain = site_scene.payload(inputs, site, 12, tariff, comps)
    assert "measured" not in plain and set(plain["rows"]) == {"offpeak", "usual"}


# ── in the app ──────────────────────────────────────────────────────────────


def test_my_data_opens_for_a_home_without_data():
    """No code for customers on the page (the Solar.web script is in docs/), only the card to
    drop a file and connect."""
    at = signed_in("home")
    at.switch_page("views/my_data.py").run()
    assert not at.exception
    assert not at.code
    assert at.get("file_uploader")
    assert any("Connect your consumption data" in h.proto.body for h in at.get("html"))


def test_my_data_shows_what_this_tab_keeps(slots):
    at = signed_in("home")
    at.session_state["measurements_home"] = slots
    at.switch_page("views/my_data.py").run()
    assert not at.exception and not at.code
    body = " ".join(h.proto.body for h in at.get("html"))
    assert "in this tab only" in body and "Connected" in body  # the Fronius tile


def test_a_business_sees_that_its_data_is_an_example():
    """No client is connected yet: the page says the data is an example, never measured, and
    offers to connect (file or planned connections)."""
    at = signed_in("business")
    at.switch_page("views/my_data.py").run()
    assert not at.exception and not at.code
    assert any("Example data" in i.value for i in at.info)
    assert at.get("file_uploader")


def test_a_home_is_told_whose_data_it_is():
    at = signed_in("home")
    at.switch_page("views/my_data.py").run()
    note = " ".join(i.value for i in at.info)
    assert "Jonas's home" in note and "16 September 2023" in note


def test_home_pages_open_with_measurements(slots):
    for page in ("views/site.py", "views/dashboard.py"):
        at = signed_in("home")
        at.session_state["measurements_home"] = slots
        at.switch_page(page).run()
        assert not at.exception, page


@pytest.mark.parametrize("role", ["home", "business"])
def test_settings_lets_every_account_connect_its_data(role):
    """The card is on Settings for both roles: the drop field and the connectors, with the
    direct connections clearly planned (never shown as working)."""
    at = signed_in(role)
    at.switch_page("views/settings.py").run()
    assert not at.exception
    assert at.get("file_uploader")
    body = " ".join(h.proto.body for h in at.get("html"))
    assert "Connect your consumption data" in body and "Smart meter" in body
    assert ("SAP S/4HANA" in body) == (role == "business")
    assert "Planned" in body
