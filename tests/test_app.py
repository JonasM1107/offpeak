import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from offpeak.markets import energy_charts
from offpeak.weather import open_meteo

APP = Path(__file__).parent.parent / "app" / "main.py"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """The pages normally call the APIs; in tests they get the saved responses instead."""
    prices = energy_charts.parse_prices(json.loads((FIXTURES / "prices_sample.json").read_text()))
    weather = open_meteo.parse_weather(json.loads((FIXTURES / "weather_sample.json").read_text()))
    monkeypatch.setattr(energy_charts, "fetch_day_ahead", lambda zone, start, end: prices)
    monkeypatch.setattr(open_meteo, "fetch_weather", lambda site, days=7: weather)


def test_app_starts_without_errors():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception


@pytest.mark.parametrize("page", ["pages/analytics.py", "pages/settings.py"])
def test_other_pages_load(page):
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.switch_page(page).run()
    assert not at.exception
