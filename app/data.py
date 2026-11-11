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
def weather(days: int = 3) -> tuple[pd.DataFrame | None, datetime, str | None, str]:
    """Forecast for the demo site from today 00:00 (German time) for `days` days:
    (table or None, forecast time, error, 'database' or 'API')."""
    eng = engine()
    now = datetime.now(UTC)
    start = day_slots(market_today(), MARKET_TZ)[0]
    if eng is not None:
        try:
            stored, run_at = db.read_latest_weather(
                eng, DEMO_SITE.id, start, start + timedelta(days=days)
            )
        except Exception as err:
            print(f"offpeak: database read failed, using the API: {err}")
        else:
            if run_at is not None and now - run_at < WEATHER_MAX_AGE:
                return stored, run_at, None, "database"
    try:
        fetched = open_meteo.fetch_weather(DEMO_SITE, days=days)
    except Exception as err:  # shown on the page as a designed state, never as a traceback
        return None, now, str(err), "API"
    if eng is not None:
        _store_quietly(lambda: db.upsert_weather(eng, fetched, DEMO_SITE.id, now))
    return fetched, now, None, "API"


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def archive_weather(start: date, end: date) -> pd.DataFrame:
    """Measured weather for past days (to replay savings)."""
    return open_meteo.fetch_archive(DEMO_SITE, start, end)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def solar_check(past_days: int = 7) -> pd.DataFrame | None:
    """Day-ahead solar forecast against satellite measurements, or None if unavailable."""
    try:
        return open_meteo.fetch_solar_check(DEMO_SITE, past_days)
    except Exception as err:
        print(f"offpeak: solar check unavailable: {err}")
        return None


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


# ── Simulation cockpit machines ──────────────────────────────────────────────


def cockpit_machines() -> tuple[list[dict] | None, str]:
    """The saved cockpit machines (None if never saved) and where they are kept: 'database',
    or 'session' (no database or table missing: kept until the browser tab is closed)."""
    eng = engine()
    if eng is not None:
        try:
            return db.read_machines(eng, DEMO_SITE.id), "database"
        except Exception as err:  # e.g. migration 003 not applied yet
            print(f"offpeak: cannot read cockpit_machines, keeping them in the session: {err}")
    return st.session_state.get("cockpit_machines"), "session"


def save_cockpit_machines(machines: list[dict]) -> str:
    """Keep the cockpit machines; returns where they went."""
    eng = engine()
    if eng is not None:
        try:
            db.save_machines(eng, DEMO_SITE.id, machines)
            return "database"
        except Exception as err:
            print(f"offpeak: cannot save cockpit_machines, keeping them in the session: {err}")
    st.session_state["cockpit_machines"] = machines
    return "session"


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def price_drivers(start: date, end: date) -> pd.DataFrame | None:
    """Wind, sun and temperature as forecast 1..7 days before each hour, for the price model.

    From the database, which the daily job keeps up to date. If the stored days do not reach
    far enough ahead, only the recent days are fetched again; if the history is missing (the
    first time), the whole range is fetched once and stored. None if nothing can be had: the
    forecast then runs without weather."""
    from offpeak.jobs.ingest_drivers import DAYS_BACK
    from offpeak.weather.price_drivers import fetch_drivers

    eng = engine()
    first = pd.Timestamp(start, tz="UTC")
    after = pd.Timestamp(end, tz="UTC") + timedelta(days=1)
    stored = pd.DataFrame()
    if eng is not None:
        try:
            stored = db.read_drivers(eng, first, after)
        except Exception as err:  # e.g. migration 004 not applied yet
            print(f"offpeak: cannot read weather_drivers: {err}")
    has_history = not stored.empty and stored.index.min() <= first + timedelta(days=3)
    if has_history and stored.index.max() >= after - timedelta(days=2):
        return stored
    fetch_from = market_today() - timedelta(days=DAYS_BACK) if has_history else start
    try:
        fetched = fetch_drivers(fetch_from, end)
    except Exception as err:
        print(f"offpeak: price drivers unavailable: {err}")
        return stored if has_history else None
    if eng is not None:
        _store_quietly(lambda: db.upsert_drivers(eng, fetched))
    if not has_history:
        return fetched
    return pd.concat([stored[stored.index < fetched.index.min()], fetched])


def price_forecast() -> tuple[pd.Series, pd.DataFrame, object, list] | None:
    """Hourly spot history (ct/kWh, about a year up to the last published hour), the
    outlook for the following days (ts, p10, p50, p90), the backtest behind it and the
    forecasters compared. None if there is too little history.

    The backtest trains the ML models a few times and takes about half a minute, so it only
    runs again when something new is known: a new day, or tomorrow's prices published."""
    _, tomorrow, _, _ = today_and_tomorrow()
    return _price_forecast(market_today(), not tomorrow.empty)


@st.cache_data(ttl=12 * 3600, show_spinner=False, max_entries=4)
def _price_forecast(today: date, tomorrow_published: bool):
    from offpeak.analysis import hourly
    from offpeak.forecast.model import WeatherPriceModel
    from offpeak.forecast.outlook import FORECASTERS, backtest, outlook

    loaded, _, _ = prices(today - timedelta(days=365), today + timedelta(days=1))
    if loaded.empty:
        return None
    history = hourly(loaded, MARKET_TZ).set_index("ts")["ct"]
    # the weather from a week before the history up to a week after the last published day
    drivers = price_drivers(today - timedelta(days=372), today + timedelta(days=9))
    forecasters = FORECASTERS + ([WeatherPriceModel(drivers)] if drivers is not None else [])
    try:
        test = backtest(history, MARKET_TZ, forecasters=forecasters)
    except ValueError:
        return None
    out, _ = outlook(history, MARKET_TZ, test, forecasters)
    return history, out, test, forecasters


# ── The coming days, for the cockpit and the dashboard's plan ────────────────


def hours_ahead() -> tuple[dict, int] | None:
    """The coming 7 days hour by hour (offpeak.cockpit.horizon: prices, own surplus, ...)
    and the index of the current hour. None if prices or weather are unavailable."""
    from offpeak.cockpit import horizon
    from offpeak.markets.energy_charts import PriceSourceError
    from offpeak.tariffs import germany_2026
    from offpeak.weather.outlook import generation

    try:
        found = price_forecast()
    except PriceSourceError:
        return None
    week, _, _, _ = weather(days=7)
    if not found or week is None or week.empty:
        return None
    history, forecast, _, _ = found
    assets, _ = components.site_model(site_components()[0])
    hours = horizon(
        history,
        forecast,
        generation(week, assets.pv_kwp, assets.turbine_kw * assets.turbines),
        base_kw=assets.cold_store_kw,
        tariff=germany_2026(pv_kwp=assets.pv_kwp),
        tz=MARKET_TZ,
        today=market_today(),
    )
    now = int(now_utc().floor("h").timestamp())
    return hours, next((i for i, t in enumerate(hours["t"]) if t >= now), 0)


def machines_to_plan() -> tuple[list[dict], bool, str]:
    """The cockpit machines: the saved ones, or the site's flexible components if none were
    saved yet. Also whether they were saved, and where machines are kept."""
    from offpeak.cockpit import clean_machines, site_machines

    saved, storage = cockpit_machines()
    if saved is not None:
        return clean_machines(saved), True, storage
    return site_machines(site_components()[0]), False, storage


@st.cache_data(ttl=12 * 3600, show_spinner=False, max_entries=4)
def _model_insight(today: date, tomorrow_published: bool) -> dict | None:
    from offpeak.forecast.insight import what_matters
    from offpeak.forecast.model import PriceModel

    found = _price_forecast(today, tomorrow_published)
    if found is None:
        return None
    history, _, _, forecasters = found
    models = [f for f in forecasters if isinstance(f, PriceModel)]
    return what_matters(history, models[-1]) if models else None  # the weather one if there


def model_insight() -> dict | None:
    """What the ML model relies on (offpeak/forecast/insight.py), once per new price day."""
    _, tomorrow, _, _ = today_and_tomorrow()
    return _model_insight(market_today(), not tomorrow.empty)
