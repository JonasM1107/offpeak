import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from offpeak import db
from offpeak.markets import energy_charts
from offpeak.weather import open_meteo

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
    monkeypatch.setattr(open_meteo, "fetch_weather", lambda site, days=7: weather)
    check = open_meteo.parse_solar_check(
        json.loads((FIXTURES / "weather_previous_runs.json").read_text()),
        json.loads((FIXTURES / "weather_satellite.json").read_text()),
    )
    monkeypatch.setattr(open_meteo, "fetch_solar_check", lambda site, past_days=7: check)


def test_app_starts_without_errors():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception


@pytest.mark.parametrize(
    "page",
    [
        "views/site.py",
        "views/analytics.py",
        "views/weather.py",
        "views/outlook.py",
        "views/tariff.py",
        "views/components.py",
        "views/settings.py",
    ],
)
def test_other_pages_load(page):
    at = AppTest.from_file(str(APP), default_timeout=30).run()
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
