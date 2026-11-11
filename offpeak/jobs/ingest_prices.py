"""Fetch today's and tomorrow's day-ahead prices and store them.

    uv run python -m offpeak.jobs.ingest_prices

GitHub Actions runs this every 15 minutes around the ~13:00 CET publication. Once tomorrow's
prices are stored the job skips, so the extra runs cost one cheap database query each.
"""

from datetime import timedelta

from sqlalchemy import Engine

from offpeak import db
from offpeak.config import DEFAULT_ZONE
from offpeak.jobs.runner import Skip, main
from offpeak.markets import energy_charts
from offpeak.timeutils import day_slots, market_today

ZONE = DEFAULT_ZONE
MARKET_TZ = "Europe/Berlin"


def tomorrow_is_stored(engine: Engine) -> bool:
    """True if every slot of tomorrow (92, 96 or 100 of them) is in the database."""
    slots = day_slots(market_today() + timedelta(days=1), MARKET_TZ)
    stored = db.read_prices(engine, ZONE, slots[0], slots[-1] + timedelta(minutes=15))
    return len(stored) >= len(slots)


def ingest(engine: Engine) -> int:
    if tomorrow_is_stored(engine):
        raise Skip("tomorrow already stored")
    today = market_today()
    prices = energy_charts.fetch_day_ahead(ZONE, today, today + timedelta(days=1))
    rows = db.upsert_prices(engine, prices, ZONE)
    if not tomorrow_is_stored(engine):
        raise Skip(f"stored {rows} rows for today; tomorrow not published yet")
    return rows


if __name__ == "__main__":
    main("ingest_prices", ingest)
