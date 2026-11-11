"""Cached data access for the pages.

For now the pages call the APIs directly (the database is not built yet). Caching keeps
it to a handful of calls per hour, however often the page is opened. Once the jobs fill
Supabase, these functions read from offpeak/db.py instead and the pages stay unchanged.
"""

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import streamlit as st

from offpeak.markets import energy_charts
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import market_today
from offpeak.weather import open_meteo


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(UTC))


@st.cache_data(ttl=600, show_spinner=False)
def prices(start: date, end: date) -> tuple[pd.DataFrame, datetime]:
    """Day-ahead prices for market days start..end, plus when we fetched them."""
    return energy_charts.fetch_day_ahead(DEMO_SITE.zone, start, end), datetime.now(UTC)


def today_and_tomorrow() -> tuple[pd.DataFrame, pd.DataFrame, datetime]:
    """Today's and tomorrow's prices from one API call. Tomorrow is empty before ~13:00 CET."""
    today = market_today()
    both, fetched_at = prices(today, today + timedelta(days=1))
    local_day = both["ts"].dt.tz_convert("Europe/Berlin").dt.date
    return both[local_day == today], both[local_day > today], fetched_at


@st.cache_data(ttl=3600, show_spinner=False)
def weather() -> tuple[pd.DataFrame | None, datetime, str | None]:
    """Weather forecast for the demo site, or None and the reason if Open-Meteo fails."""
    try:
        return open_meteo.fetch_weather(DEMO_SITE, days=3), datetime.now(UTC), None
    except Exception as err:  # shown on the page as a designed state, never as a traceback
        return None, datetime.now(UTC), str(err)
