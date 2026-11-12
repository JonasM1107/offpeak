"""Compute the Offpeak Intelligence price outlook in the background and store it.

    uv run python -m offpeak.jobs.forecast_prices

GitHub Actions runs this after tomorrow's prices are published and after the morning weather
update. Training and the backtest take about half a minute, which visitors of the app
should never wait for: the app reads the stored outlook (app/data.py) and only computes one
itself if none fits the latest published prices.

The log of each run shows how good the outlook was in the backtest and what it relies on,
for the team; the app does not show these details.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from offpeak import db
from offpeak.analysis import hourly
from offpeak.config import DEFAULT_ZONE
from offpeak.forecast.insight import what_matters
from offpeak.forecast.model import WeatherPriceModel
from offpeak.forecast.outlook import run_outlook
from offpeak.jobs.runner import Skip, main
from offpeak.timeutils import market_today

MARKET_TZ = "Europe/Berlin"
HISTORY_DAYS = 365


def load_inputs(engine: Engine):
    """A year of hourly prices (ct/kWh) and the weather drivers around it, from the database."""
    today = market_today()
    start = datetime.combine(today - timedelta(days=HISTORY_DAYS), datetime.min.time(), UTC)
    end = datetime.combine(today + timedelta(days=2), datetime.min.time(), UTC)
    prices = db.read_prices(engine, DEFAULT_ZONE, start, end)
    history = hourly(prices, MARKET_TZ).set_index("ts")["ct"] if not prices.empty else None
    drivers = db.read_drivers(engine, start - timedelta(days=8), end + timedelta(days=8))
    return history, drivers


def forecast(engine: Engine) -> int:
    history, drivers = load_inputs(engine)
    if history is None:
        raise Skip("no prices stored yet")
    stored = db.read_outlook(engine)
    if not stored.empty and stored["based_on"].iloc[0] == history.index.max():
        made = stored["made_at"].iloc[0]
        if made.date() == datetime.now(UTC).date():
            raise Skip("today's outlook for the latest prices is already stored")
    out, test = run_outlook(history, MARKET_TZ, drivers)
    rows = db.save_outlook(engine, out, history.index.max().to_pydatetime())

    # for the team, in the job log: backtest scores and what the outlook relies on
    print(test.scores.round(2).to_string(index=False))
    if drivers is not None and not drivers.empty:
        found = what_matters(history, WeatherPriceModel(drivers))
        if found:
            print(f"average miss on the last {found['days']} unseen days: {found['mae']} ct/kWh")
            for g in found["groups"]:
                print(f"  without {g['label'].lower()}: +{g['ct']} ct/kWh")
    return rows


if __name__ == "__main__":
    main("forecast_prices", forecast)
