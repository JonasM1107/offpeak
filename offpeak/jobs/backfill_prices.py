"""Load price history once, month by month.

    uv run python -m offpeak.jobs.backfill_prices 2024-11-01

Takes about 5 seconds per month because Energy-Charts rate-limits quick calls.
"""

import sys
from datetime import date

from sqlalchemy import Engine

from offpeak import db
from offpeak.config import DEFAULT_ZONE
from offpeak.jobs.runner import main
from offpeak.markets import energy_charts
from offpeak.timeutils import market_today


def backfill(start: date):
    def work(engine: Engine) -> int:
        prices = energy_charts.fetch_history(DEFAULT_ZONE, start, market_today())
        return db.upsert_prices(engine, prices, DEFAULT_ZONE)

    return work


if __name__ == "__main__":
    first_day = date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2024-11-01")
    main("backfill_prices", backfill(first_day))
