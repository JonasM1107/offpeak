"""Fetch the weather forecast for every site and store it as one forecast run.

uv run python -m offpeak.jobs.ingest_weather
"""

from datetime import UTC, datetime

from sqlalchemy import Engine

from offpeak import db
from offpeak.config import FORECAST_DAYS
from offpeak.jobs.runner import main
from offpeak.sites import DEMO_HOME, DEMO_SITE
from offpeak.weather import open_meteo

# Both demo sites: the same place, but each roof is tilted and turned its own way, and the
# forecast gives the sun on that roof. Later: read from the sites table.
SITES = [DEMO_SITE, DEMO_HOME]


def ingest(engine: Engine) -> int:
    run_at = datetime.now(UTC).replace(second=0, microsecond=0)
    rows = 0
    for site in SITES:
        weather = open_meteo.fetch_weather(site, days=FORECAST_DAYS)
        rows += db.upsert_weather(engine, weather, site.id, run_at)
    return rows


if __name__ == "__main__":
    main("ingest_weather", ingest)
