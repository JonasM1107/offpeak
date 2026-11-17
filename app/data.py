"""Cached data access for the pages.

With a database (DATABASE_URL in .env or in Streamlit secrets) the pages read what the
scheduled jobs stored. If something is missing there, for example tomorrow's prices right
after publication, the page fetches it from the API itself and stores it ("fetch on view").
Without a database the pages call the APIs directly, as before.
"""

import threading
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from offpeak import components, db, http
from offpeak.analysis import covers_days
from offpeak.markets import energy_charts
from offpeak.settings import lookup
from offpeak.sites import DEMO_SITE, site_for
from offpeak.timeutils import day_slots, market_today
from offpeak.weather import open_meteo

MARKET_TZ = "Europe/Berlin"
# A visitor is waiting: one quick retry and at most 8 s per answer, instead of the jobs'
# four retries and 30 s (offpeak/http.py). When a source keeps failing, the pages fall back
# to stored data or a clear message.
http.retries = 1
http.timeout_s = 8
WEATHER_MAX_AGE = timedelta(hours=6)  # older stored forecasts are refreshed from the API


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(UTC))


def _database_url() -> str | None:
    return lookup(st.secrets, "DATABASE_URL") or db.database_url()


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
    """Prices for market days start..end: (table, when loaded, 'database' or 'API').
    Kept 5 minutes, because today's and tomorrow's prices can still arrive."""
    return _load_prices(start, end)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def past_prices(start: date, end: date) -> tuple[pd.DataFrame, datetime, str]:
    """Like prices(), for days that are over: they do not change, so they are kept 6 hours
    instead of being read again every 5 minutes (two years for the Power page)."""
    return _load_prices(start, end)


def _load_prices(start: date, end: date) -> tuple[pd.DataFrame, datetime, str]:
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


def weather(days: int = 3) -> tuple[pd.DataFrame | None, datetime, str | None, str]:
    """Forecast for the demo site from today 00:00 (German time) for `days` days (at most
    7): (table or None, forecast time, error, 'database' or 'API'). One cached 7-day load
    serves every page, so the weather is fetched once, not once per length."""
    table, run_at, error, source = _weather_week()
    if table is not None:
        end = day_slots(market_today(), MARKET_TZ)[0] + timedelta(days=days)
        table = table[table["ts"] < end].reset_index(drop=True)
    return table, run_at, error, source


@st.cache_data(ttl=600, show_spinner=False)
def _weather_week(days: int = 7) -> tuple[pd.DataFrame | None, datetime, str | None, str]:
    eng = engine()
    now = datetime.now(UTC)
    start = day_slots(market_today(), MARKET_TZ)[0]
    stored, run_at = None, None
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
        # 15 s: Open-Meteo is sometimes slow, and this runs only when nothing fresh is stored
        fetched = open_meteo.fetch_weather(DEMO_SITE, days=days, timeout=15)
    except Exception as err:  # shown on the page as a designed state, never as a traceback
        if stored is not None and not stored.empty:  # an older forecast beats none
            print(f"offpeak: weather API failed, using the forecast from {run_at}: {err}")
            return stored, run_at, None, "database"
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


# ── Who may change shared data ───────────────────────────────────────────────
# Site components and cockpit machines are shared by everyone who opens the app. Only a
# signed-in editor (ui/account.py, offpeak/auth.py) changes them in the database. Everyone
# else can still try things: their changes stay in their own browser tab ("local"). This is
# checked here, where the data is saved, not only by hiding buttons on the pages.

LOCAL_COMPONENTS = "components_local"


def can_share() -> bool:
    from ui.account import editor

    return engine() is not None and editor() is not None


# ── The signed-in role and its site ─────────────────────────────────────────
# Prices and weather are the same for both roles (Köln, DE-LU). Everything that depends on
# what is used (components, cockpit machines, the savings replay) takes the site and the
# catalogue of the signed-in account's role, read from its signed token, never from the
# page or the address.


def role() -> str:
    """The signed-in account's role; "business" before signing in (no page shows then)."""
    from ui.account import role as signed_role

    return signed_role() or "business"


def site():
    """The site of the signed-in account's role (offpeak/sites.py)."""
    return site_for(role())


def _local_key(profile: str) -> str:
    return f"{LOCAL_COMPONENTS}_{profile}"  # one list per role, kept apart in the tab too


# ── Site components ──────────────────────────────────────────────────────────


def site_components() -> tuple[list[components.Component], str]:
    """The signed-in role's components and where they come from: 'local' (changed in this
    tab by someone not signed in), 'database', 'demo' (database connected but no components
    saved yet) or 'session' (no database: kept until reload)."""
    profile, here = role(), site()
    key = _local_key(profile)
    if key in st.session_state:
        return st.session_state[key], "local" if engine() else "session"
    demo = [replace(c) for c in components.DEFAULTS[profile]]
    eng = engine()
    if eng is not None:
        try:
            rows = db.read_components(eng, here.id, profile)
        except Exception as err:  # e.g. migration 002 or 006 not applied yet
            print(f"offpeak: cannot read site_components, keeping them in the session: {err}")
        else:
            if rows:
                return [components.Component(**r) for r in rows], "database"
            return demo, "demo"
    st.session_state[key] = demo
    return st.session_state[key], "session"


def _as_row(c: components.Component) -> dict:
    return {"id": c.id, "kind": c.kind, "name": c.name, "params": c.params}


def add_component(new: components.Component) -> str:
    """Add a component; returns where it went. For an editor it is stored for everyone (the
    first change saves the demo components too, so they stay); for anyone else it is kept
    in this tab only. Raises ValueError if it does not belong to the signed-in role
    (a household device for a business, or the other way round), whatever the page sent."""
    profile, here = role(), site()
    components.check_profile([new], profile)
    current, source = site_components()
    if not can_share():
        st.session_state[_local_key(profile)] = [*current, new]
        return "local" if engine() else "session"
    rows = [_as_row(c) for c in current] if source == "demo" else []
    db.save_components(engine(), here.id, rows + [_as_row(new)], profile)
    return "database"


def remove_component(component_id: str) -> str:
    profile, here = role(), site()
    current, source = site_components()
    if not can_share():
        st.session_state[_local_key(profile)] = [c for c in current if c.id != component_id]
        return "local" if engine() else "session"
    if source == "demo":
        db.save_components(engine(), here.id, [_as_row(c) for c in current], profile)
    db.delete_component(engine(), component_id, here.id, profile)  # only from this site
    return "database"


# ── Simulation cockpit machines ──────────────────────────────────────────────


def cockpit_machines() -> tuple[list[dict] | None, str]:
    """The cockpit machines (None if never saved) and where changes go: 'database' (signed
    in), 'local' (not signed in: this tab only) or 'session' (no database)."""
    eng = engine()
    local = st.session_state.get(_machines_key())
    if eng is None:
        return local, "session"
    where = "database" if can_share() else "local"
    if local is not None and where == "local":
        return local, where
    try:
        return db.read_machines(eng, site().id, role()), where
    except Exception as err:  # e.g. migration 003 not applied yet
        print(f"offpeak: cannot read cockpit_machines, keeping them in the session: {err}")
        return local, "session"


def save_cockpit_machines(machines: list[dict]) -> str:
    """Keep the cockpit machines: for everyone if signed in, else in this tab only."""
    if can_share():
        try:
            if db.save_machines(engine(), site().id, machines, role()):
                return "database"
            print("offpeak: cockpit_machines of this site belong to another role, kept here")
        except Exception as err:
            print(f"offpeak: cannot save cockpit_machines, keeping them in the session: {err}")
    st.session_state[_machines_key()] = machines
    return "local" if engine() else "session"


def _machines_key() -> str:
    return f"cockpit_machines_{role()}"  # one list per role, kept apart in the tab too


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


def price_outlook() -> tuple[pd.Series, pd.DataFrame] | None:
    """Hourly spot history of the last two weeks (ct/kWh, up to the last published hour) and
    the Offpeak Intelligence outlook for the following days (ts, day, lead, p10, p50, p90,
    miss_ct). None if prices cannot be loaded.

    The app never trains: the forecast job (offpeak/jobs/forecast_prices.py) computes the
    outlook in the background and stores it. Once newer prices are out, the stored outlook
    still covers the days after them until the job has run again. Only with no stored
    outlook at all does the app make a quick one from simple rules (a few seconds)."""
    _, tomorrow, _, _ = today_and_tomorrow()
    return _price_outlook(market_today(), not tomorrow.empty)


@st.cache_data(ttl=900, show_spinner=False, max_entries=4)
def _price_outlook(today: date, tomorrow_published: bool):
    from offpeak.analysis import hourly
    from offpeak.forecast.outlook import quick_outlook, still_ahead

    loaded, _, _ = prices(today - timedelta(days=15), today + timedelta(days=1))
    if loaded.empty:
        return None
    history = hourly(loaded, MARKET_TZ).set_index("ts")["ct"]
    eng = engine()
    if eng is not None:
        try:
            stored = db.read_outlook(eng)
        except Exception as err:  # e.g. migration 005 not applied yet
            print(f"offpeak: cannot read price_outlook: {err}")
        else:
            ahead = still_ahead(stored, history.index.max(), MARKET_TZ)
            if not ahead.empty:
                return history, ahead
    # nothing stored: a quick outlook from ten weeks of prices, never stored (the job's is better)
    longer, _, _ = prices(today - timedelta(days=70), today + timedelta(days=1))
    try:
        out = quick_outlook(hourly(longer, MARKET_TZ).set_index("ts")["ct"], MARKET_TZ)
    except ValueError:  # too little history
        return None
    return history, out


# ── The coming days, for the cockpit and the dashboard's plan ────────────────


def hours_ahead() -> tuple[dict, int] | None:
    """The coming 7 days hour by hour (offpeak.cockpit.horizon: prices, own surplus, ...)
    and the index of the current hour. None if prices are unavailable. Without a weather
    forecast the plan still works on prices alone (no own power counted); the result then
    says so in "weather_missing"."""
    from offpeak.cockpit import horizon
    from offpeak.markets.energy_charts import PriceSourceError
    from offpeak.tariffs import germany_2026
    from offpeak.weather.outlook import generation

    try:
        found = price_outlook()
    except PriceSourceError:
        return None
    if not found:
        return None
    week, _, _, _ = weather(days=7)
    history, forecast = found
    assets, _ = components.site_model(site_components()[0])
    weather_missing = week is None or week.empty
    if weather_missing:  # plan on prices alone, counting no own solar or wind power
        gen = pd.DataFrame({"ts": pd.DatetimeIndex([], tz="UTC"), "pv_kw": [], "wind_kw": []})
    else:
        gen = generation(week, assets.pv_kwp, assets.turbine_kw * assets.turbines)
    hours = horizon(
        history,
        forecast,
        gen,
        base_kw=assets.cold_store_kw,
        tariff=germany_2026(pv_kwp=assets.pv_kwp),
        tz=MARKET_TZ,
        today=market_today(),
    )
    hours["weather_missing"] = weather_missing
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


# ── Savings replay (shared by the Savings page and the dashboard) ────────────

_REPLAYED: dict[tuple, dict] = {}  # summaries already computed, by (end, days, setup)
_RUNNING: set[tuple] = set()
_FAILED: dict[tuple, datetime] = {}  # when a background replay last failed
RETRY_AFTER = timedelta(minutes=30)
_LOCK = threading.Lock()


def setup_key(comps) -> tuple:
    """The components as a hashable key: a new machine means a fresh replay."""
    return tuple((c.id, c.kind, c.name, tuple(sorted(c.params.items())), c.profile) for c in comps)


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def savings_replay(end: date, n_days: int, setup: tuple) -> list[dict]:
    """Replay the last `n_days` days up to `end` with the real prices and measured weather:
    what the usual times cost and what the plan would have cost. About 0.3 s a day."""
    from offpeak import savings
    from offpeak.tariffs import germany_2026

    comps = [components.Component(i, k, n, dict(p), prof) for i, k, n, p, prof in setup]
    start = end - timedelta(days=n_days - 1)
    loaded, _, _ = past_prices(start, end)
    past = archive_weather(start, end)
    assets, _ = components.site_model(comps)
    days = [start + timedelta(days=i) for i in range(n_days)]
    out = savings.replay(loaded, past, comps, germany_2026(pv_kwp=assets.pv_kwp), MARKET_TZ, days)
    _REPLAYED[(end, n_days, setup)] = savings.summary(out)
    return out


def saved_recently(n_days: int = 30) -> tuple[dict | None, str]:
    """The savings summary of the last `n_days` days and its state: "ready", "running" (the
    replay runs in the background, so the dashboard never waits for it) or "failed" (past
    prices or weather could not be loaded; tried again after RETRY_AFTER)."""
    end = market_today() - timedelta(days=1)
    key = (end, n_days, setup_key(site_components()[0]))
    if key in _REPLAYED:
        return _REPLAYED[key], "ready"
    failed = _FAILED.get(key)
    if failed and datetime.now(UTC) - failed < RETRY_AFTER:
        return None, "failed"
    with _LOCK:
        if key in _RUNNING:
            return None, "running"
        _RUNNING.add(key)

    def work():
        try:
            savings_replay(*key)
        except Exception as err:  # shown as "not available right now" on the dashboard
            print(f"offpeak: background savings replay failed: {err}")
            _FAILED[key] = datetime.now(UTC)
        finally:
            with _LOCK:
                _RUNNING.discard(key)

    threading.Thread(target=work, daemon=True).start()
    return None, "running"
