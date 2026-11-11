"""Fetch the weather forecasts the price model uses and store them.

    uv run python -m offpeak.jobs.ingest_drivers          # daily: last 8 days, next 9 days
    uv run python -m offpeak.jobs.ingest_drivers 372      # backfill: the last 372 days too

Why the last 8 days again: for an hour that lies ahead, Open-Meteo fills the "forecast made
k days before" columns whose run has not happened yet with the latest forecast. Once those
runs happened, fetching again replaces them with the real ones.
"""

import sys
from datetime import timedelta

from sqlalchemy import Engine

from offpeak import db
from offpeak.jobs.runner import main
from offpeak.timeutils import market_today
from offpeak.weather.price_drivers import fetch_drivers

DAYS_BACK, DAYS_AHEAD = 8, 9


def ingest(days_back: int = DAYS_BACK):
    def work(engine: Engine) -> int:
        today = market_today()
        drivers = fetch_drivers(today - timedelta(days=days_back), today + timedelta(DAYS_AHEAD))
        return db.upsert_drivers(engine, drivers)

    return work


if __name__ == "__main__":
    main("ingest_drivers", ingest(int(sys.argv[1]) if len(sys.argv) > 1 else DAYS_BACK))
