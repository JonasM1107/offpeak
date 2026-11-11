"""Day-ahead prices from Energy-Charts (Fraunhofer ISE), API version 2.

Response shape (checked against tests/fixtures/prices_sample.json):

    {"bidding_zone": "DE-LU", "interval_minutes": 15, "unit": "EUR / MWh",
     "data": [{"timestamp": "2026-11-10T00:00:00+01:00",
               "values": {"day_ahead_price": 271.33}}, ...],
     "license": "CC BY 4.0 ... from Bundesnetzagentur | SMARD.de"}

Timestamps carry their own UTC offset, so the clock-change days parse correctly.
Before ~13:00 CET, asking for tomorrow returns HTTP 404 "no content available".
That is the normal state, not an error: we return an empty table.
"""

import time
from datetime import date, datetime, timedelta

import pandas as pd

from offpeak import http
from offpeak.config import DEFAULT_ZONE, ENERGY_CHARTS_SOURCE, ENERGY_CHARTS_URL
from offpeak.timeutils import market_today

COLUMNS = ["ts", "eur_mwh", "resolution_min", "source"]
PRICE_SERIES = "day_ahead_price"


class PriceSourceError(RuntimeError):
    """The source answered with something we cannot use."""


def empty_prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.Series(dtype="datetime64[ns, UTC]"),
            "eur_mwh": pd.Series(dtype="float64"),
            "resolution_min": pd.Series(dtype="int64"),
            "source": pd.Series(dtype="object"),
        }
    )


def parse_prices(payload: dict) -> pd.DataFrame:
    """One v2 /price response -> rows of ts (UTC slot start), eur_mwh, resolution_min, source."""
    rows = payload.get("data") or []
    if not rows:
        return empty_prices()
    df = pd.DataFrame(
        {
            "ts": pd.to_datetime([r["timestamp"] for r in rows], utc=True),
            "eur_mwh": [r["values"].get(PRICE_SERIES) for r in rows],
        }
    )
    df = df.dropna(subset=["eur_mwh"])  # a missing price is skipped, never stored as 0
    df["eur_mwh"] = df["eur_mwh"].astype(float)
    df["resolution_min"] = int(payload["interval_minutes"])
    df["source"] = ENERGY_CHARTS_SOURCE
    return df[COLUMNS].reset_index(drop=True)


def fetch_day_ahead(zone: str, start: date, end: date) -> pd.DataFrame:
    """Prices for every market day from start to end, both inclusive.

    Returns an empty table if the days are not published yet.
    """
    response = http.get(
        f"{ENERGY_CHARTS_URL}/v2/price",
        params={"bzn": zone, "start": start.isoformat(), "end": end.isoformat()},
    )
    if response.status_code == 404:
        return empty_prices()
    if response.status_code != 200:
        raise PriceSourceError(f"Energy-Charts HTTP {response.status_code}: {response.text[:200]}")
    return parse_prices(response.json())


def fetch_tomorrow(zone: str = DEFAULT_ZONE, now: datetime | None = None) -> pd.DataFrame:
    """Tomorrow's prices in market time, or an empty table before publication."""
    tomorrow = market_today(now) + timedelta(days=1)
    return fetch_day_ahead(zone, tomorrow, tomorrow)


def fetch_history(zone: str, start: date, end: date, pause_s: float = 5.0) -> pd.DataFrame:
    """Backfill month by month, pausing between calls because Energy-Charts rate-limits."""
    parts = []
    month_start = start
    while month_start <= end:
        next_month = (month_start.replace(day=1) + timedelta(days=32)).replace(day=1)
        month_end = min(next_month - timedelta(days=1), end)
        parts.append(fetch_day_ahead(zone, month_start, month_end))
        month_start = next_month
        if month_start <= end:
            time.sleep(pause_s)
    parts = [p for p in parts if not p.empty]
    if not parts:
        return empty_prices()
    return pd.concat(parts, ignore_index=True).drop_duplicates("ts").reset_index(drop=True)
