"""Cached data access for the pages.

With a database (DATABASE_URL in .env or in Streamlit secrets) the pages read what the
scheduled jobs stored. If something is missing there, for example tomorrow's prices right
after publication, the page fetches it from the API itself and stores it ("fetch on view").
Without a database the pages call the APIs directly, as before.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from offpeak import components, db
from offpeak.analysis import covers_days
from offpeak.markets import energy_charts
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import day_slots, market_today
from offpeak.weather import open_meteo

MARKET_TZ = "Europe/Berlin"
WEATHER_MAX_AGE = timedelta(hours=6)  # older stored forecasts are refreshed from the API


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(UTC))


def _database_url() -> str | None:
    try:
        url = st.secrets.get("DATABASE_URL")
    except Exception:  # no secrets file at all
        url = None
    return url or db.database_url()


def engine() -> Engine | None:
    url = _database_url()
    return db.get_engine(url) if url else None


def _store_quietly(write) -> None:
    """Fetch-on-view writes are a bonus; a failed write must never break the page."""
    try:
        write()
    except Exception as err:
        print(f"offpeak: could not store fetched data: {err}")


@st.cache_data(ttl=300, show_spinner=False)
def prices(start: date, end: date) -> tuple[pd.DataFrame, datetime, str]:
    """Prices for market days start..end: (table, when loaded, 'database' or 'API')."""
    eng = engine()
    first = day_slots(start, MARKET_TZ)[0]
    after = day_slots(end, MARKET_TZ)[-1] + timedelta(minutes=15)
    if eng is not None:
        try:
            stored = db.read_prices(eng, DEMO_SITE.zone, first, after)
        except Exception as err:
            print(f"offpeak: database read failed, using the API: {err}")
        else:
            # history before October 2025 is hourly, so count hours per day, not slots
            if covers_days(stored, start, end, MARKET_TZ):
                return stored, datetime.now(UTC), "database"
    fetched = energy_charts.fetch_day_ahead(DEMO_SITE.zone, start, end)
    if eng is not None and not fetched.empty:
        _store_quietly(lambda: db.upsert_prices(eng, fetched, DEMO_SITE.zone))
    return fetched, datetime.now(UTC), "API"


def today_and_tomorrow() -> tuple[pd.DataFrame, pd.DataFrame, datetime, str]:
    """Today's and tomorrow's prices. Tomorrow is empty before ~13:00 CET."""
    today = market_today()
    both, loaded_at, source = prices(today, today + timedelta(days=1))
    local_day = both["ts"].dt.tz_convert(MARKET_TZ).dt.date
    return both[local_day == today], both[local_day > today], loaded_at, source


@st.cache_data(ttl=600, show_spinner=False)
def weather() -> tuple[pd.DataFrame | None, datetime, str | None, str]:
    """Forecast for the demo site: (table or None, forecast time, error, 'database' or 'API')."""
    eng = engine()
    now = datetime.now(UTC)
    if eng is not None:
        try:
            stored, run_at = db.read_latest_weather(
                eng, DEMO_SITE.id, now - timedelta(hours=1), now + timedelta(days=3)
            )
        except Exception as err:
            print(f"offpeak: database read failed, using the API: {err}")
        else:
            if run_at is not None and now - run_at < WEATHER_MAX_AGE:
                return stored, run_at, None, "database"
    try:
        fetched = open_meteo.fetch_weather(DEMO_SITE, days=3)
    except Exception as err:  # shown on the page as a designed state, never as a traceback
        return None, now, str(err), "API"
    if eng is not None:
        _store_quietly(lambda: db.upsert_weather(eng, fetched, DEMO_SITE.id, now))
    return fetched, now, None, "API"


@st.cache_data(ttl=60, show_spinner=False)
def job_runs() -> pd.DataFrame | None:
    """Recent job runs, or None without a database."""
    eng = engine()
    if eng is None:
        return None
    try:
        return db.recent_job_runs(eng, limit=10)
    except Exception:
        return None


# ── Site components ──────────────────────────────────────────────────────────


def _session_components() -> list[components.Component]:
    if "components" not in st.session_state:
        st.session_state["components"] = [replace(c) for c in components.DEFAULT_COMPONENTS]
    return st.session_state["components"]


def site_components() -> tuple[list[components.Component], str]:
    """The demo site's components and where they come from: 'database', 'demo' (database
    connected but no components saved yet) or 'session' (no database: kept until reload)."""
    eng = engine()
    if eng is not None:
        try:
            rows = db.read_components(eng, DEMO_SITE.id)
        except Exception as err:  # e.g. migration 002 not applied yet
            print(f"offpeak: cannot read site_components, keeping them in the session: {err}")
        else:
            if rows:
                return [components.Component(**r) for r in rows], "database"
            return [replace(c) for c in components.DEFAULT_COMPONENTS], "demo"
    return _session_components(), "session"


def _as_row(c: components.Component) -> dict:
    return {"id": c.id, "kind": c.kind, "name": c.name, "params": c.params}


def add_component(new: components.Component) -> str:
    """Store a new component. The first change saves the demo components too, so they stay."""
    current, source = site_components()
    if source == "session":
        _session_components().append(new)
        return source
    rows = [_as_row(c) for c in current] if source == "demo" else []
    db.save_components(engine(), DEMO_SITE.id, rows + [_as_row(new)])
    return "database"


def remove_component(component_id: str) -> str:
    current, source = site_components()
    if source == "session":
        st.session_state["components"] = [c for c in current if c.id != component_id]
        return source
    if source == "demo":
        db.save_components(engine(), DEMO_SITE.id, [_as_row(c) for c in current])
    db.delete_component(engine(), component_id)
    return "database"
