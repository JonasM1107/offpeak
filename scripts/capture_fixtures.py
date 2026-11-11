"""Call both APIs once and save the raw responses as test fixtures.

    uv run python scripts/capture_fixtures.py

Overwrites tests/fixtures/weather_sample.json and prices_sample.json. Run it when a
response format changes, then rerun the tests.
"""

import json
from datetime import date
from pathlib import Path

from offpeak import http
from offpeak.config import ENERGY_CHARTS_URL, OPEN_METEO_URL
from offpeak.models import Site
from offpeak.weather.open_meteo import build_params

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
DEMO_SITE = Site(id=1, name="Demo farm near Munich", lat=48.14, lon=11.58)


def save(name: str, payload: dict) -> None:
    (FIXTURES / name).write_text(json.dumps(payload, indent=1) + "\n")
    print("saved", name)


def main() -> None:
    weather = http.get(OPEN_METEO_URL, params=build_params(DEMO_SITE, days=2))
    weather.raise_for_status()
    save("weather_sample.json", weather.json())

    day = date.today().isoformat()
    params = {"bzn": "DE-LU", "start": day, "end": day}
    prices = http.get(f"{ENERGY_CHARTS_URL}/v2/price", params=params)
    prices.raise_for_status()
    save("prices_sample.json", prices.json())


if __name__ == "__main__":
    main()
