import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from offpeak import auth, db
from offpeak.markets import energy_charts
from offpeak.weather import open_meteo, price_drivers

APP = Path(__file__).parent.parent / "app" / "main.py"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """The pages normally call the APIs; in tests they get the saved responses instead,
    and never touch a database, even if a .env with DATABASE_URL exists."""
    monkeypatch.setattr(db, "database_url", lambda: None)
    prices = energy_charts.parse_prices(json.loads((FIXTURES / "prices_sample.json").read_text()))
    weather = open_meteo.parse_weather(json.loads((FIXTURES / "weather_sample.json").read_text()))
    monkeypatch.setattr(energy_charts, "fetch_day_ahead", lambda zone, start, end: prices)
    monkeypatch.setattr(open_meteo, "fetch_weather", lambda site, days=7, timeout=None: weather)
    check = open_meteo.parse_solar_check(
        json.loads((FIXTURES / "weather_previous_runs.json").read_text()),
        json.loads((FIXTURES / "weather_satellite.json").read_text()),
    )
    monkeypatch.setattr(open_meteo, "fetch_solar_check", lambda site, past_days=7: check)
    archive = open_meteo.parse_archive(json.loads((FIXTURES / "weather_archive.json").read_text()))
    monkeypatch.setattr(open_meteo, "fetch_archive", lambda site, start, end: archive)

    def no_drivers(start, end):  # the price outlook then runs without weather, as offline
        raise price_drivers.DriverSourceError("offline in tests")

    monkeypatch.setattr(price_drivers, "fetch_drivers", no_drivers)
    # the app is behind a login: tests sign in as a test editor (see signed_in_app)
    monkeypatch.setenv("OFFPEAK_EDITORS", "test@example.com")
    monkeypatch.setenv("OFFPEAK_PASSWORD_HASH", auth.hash_password("pw", salt="s"))
    monkeypatch.setenv("OFFPEAK_AUTH_SECRET", "test-secret")


def signed_in_app() -> AppTest:
    """The app as a signed-in team member sees it."""
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.session_state["editor_token"] = auth.make_token(
        "test@example.com", datetime.now(UTC), "test-secret"
    )
    return at


def test_app_starts_without_errors():
    at = signed_in_app().run()
    assert not at.exception


@pytest.mark.parametrize(
    "page",
    [
        "views/site.py",
        "views/analytics.py",
        "views/weather.py",
        "views/outlook.py",
        "views/cockpit.py",
        "views/savings.py",
        "views/tariff.py",
        "views/components.py",
        "views/settings.py",
        "views/account.py",
    ],
)
def test_other_pages_load(page):
    at = signed_in_app().run()
    at.switch_page(page).run()
    assert not at.exception


@pytest.mark.parametrize(
    "page",
    ["views/dashboard.py", "views/site.py", "views/analytics.py", "views/weather.py"]
    + ["views/outlook.py", "views/savings.py"],
)
def test_pages_do_not_use_the_removed_html_frame(page, monkeypatch):
    """Streamlit removes st.components.v1.html (deprecated, removal after 2026-06-01): a newer
    Streamlit would break every page still using it. Pretend it is gone already; the pages with
    an HTML view must still load (they use st.iframe)."""
    import streamlit.components.v1 as components

    def removed(*args, **kwargs):
        raise AttributeError("st.components.v1.html was removed from Streamlit")

    monkeypatch.setattr(components, "html", removed)
    at = signed_in_app().run()
    at.switch_page(page).run()
    assert not at.exception


def test_site_scene_payload_is_embedded_safely():
    import sys

    sys.path.insert(0, str(APP.parent))
    from datetime import date

    from ui import site_scene

    from offpeak import demo_site
    from offpeak.tariffs import germany_2026

    tariff = germany_2026()
    inputs = demo_site.hourly_inputs(None, None, "Europe/Berlin")
    inputs = demo_site.apply_tariff(inputs, tariff, date(2026, 11, 11))
    site = {"name": "</script><b>x</b>", "city": "Köln", "zone": "DE-LU", "date": "2026-11-11"}
    html = site_scene.render_html(site_scene.payload(inputs, site, 12, tariff))
    assert "__DATA__" not in html
    assert "</script><b>" not in html  # the JSON cannot close the script tag
    assert len(site_scene.payload(inputs, site, 12, tariff)["offpeak"]) == 24


def test_site_scene_carries_the_blender_models():
    import base64
    import gzip
    import sys

    sys.path.insert(0, str(APP.parent))
    from ui import site_scene

    models = site_scene.models()
    for name in ("furnace_hall", "main_hall", "cold_store", "battery_container", "e_truck"):
        assert name in models
    for packed in models.values():
        assert gzip.decompress(base64.b64decode(packed))[:4] == b"glTF"  # binary glTF
    # all models together stay small enough to send with every Site view
    assert sum(len(v) for v in models.values()) < 600_000
