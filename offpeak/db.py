"""The only module that talks to the database (Supabase Postgres).

The connection string comes from the DATABASE_URL environment variable (locally from .env,
in GitHub Actions from a secret, on Streamlit Cloud from st.secrets via app/data.py).
Every write is an upsert: running a job twice never creates duplicate rows.
"""

import json
import math
import os
from datetime import datetime
from functools import cache

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text


def database_url() -> str | None:
    """DATABASE_URL from the environment or .env, or None if it is not set."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or None


@cache
def get_engine(url: str) -> Engine:
    """One connection pool per database address."""
    # Supabase shows "postgresql://..."; SQLAlchemy needs to be told to use psycopg 3.
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)


def _clean(value):
    """NaN becomes NULL in the database, never 0."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


# ── Prices ───────────────────────────────────────────────────────────────────

UPSERT_PRICES = text("""
    insert into prices_da (ts, zone, eur_mwh, resolution_min, source)
    values (:ts, :zone, :eur_mwh, :resolution_min, :source)
    on conflict (ts, zone) do update set
        eur_mwh = excluded.eur_mwh,
        resolution_min = excluded.resolution_min,
        source = excluded.source
""")


def upsert_prices(engine: Engine, prices: pd.DataFrame, zone: str) -> int:
    """Write prices (ts, eur_mwh, resolution_min, source). Returns the number of rows."""
    rows = [
        {
            "ts": r.ts.to_pydatetime(),
            "zone": zone,
            "eur_mwh": round(float(r.eur_mwh), 2),
            "resolution_min": int(r.resolution_min),
            "source": r.source,
        }
        for r in prices.itertuples()
    ]
    if rows:
        with engine.begin() as conn:
            conn.execute(UPSERT_PRICES, rows)
    return len(rows)


def read_prices(engine: Engine, zone: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Prices with start <= ts < end, oldest first."""
    query = text("""
        select ts, eur_mwh::float as eur_mwh, resolution_min::int as resolution_min, source
        from prices_da
        where zone = :zone and ts >= :start and ts < :end
        order by ts
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"zone": zone, "start": start, "end": end})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


# ── Weather ──────────────────────────────────────────────────────────────────

WEATHER_COLUMNS = [
    "gti_wm2",
    "ghi_wm2",
    "precip_mm",
    "temp_c",
    "cloud_pct",
    "wind_ms",
    "weather_code",
]

UPSERT_WEATHER = text(f"""
    insert into weather_fc (site_id, run_at, ts, {", ".join(WEATHER_COLUMNS)})
    values (:site_id, :run_at, :ts, {", ".join(":" + c for c in WEATHER_COLUMNS)})
    on conflict (site_id, run_at, ts) do update set
        {", ".join(f"{c} = excluded.{c}" for c in WEATHER_COLUMNS)}
""")


def upsert_weather(engine: Engine, weather: pd.DataFrame, site_id: int, run_at: datetime) -> int:
    """Write one forecast run for one site. Returns the number of rows."""
    rows = []
    for r in weather.to_dict("records"):
        row = {"site_id": site_id, "run_at": run_at, "ts": r["ts"].to_pydatetime()}
        row |= {c: _clean(r.get(c)) for c in WEATHER_COLUMNS}
        if row["weather_code"] is not None:
            row["weather_code"] = int(row["weather_code"])
        rows.append(row)
    if rows:
        with engine.begin() as conn:
            conn.execute(UPSERT_WEATHER, rows)
    return len(rows)


def read_latest_weather(
    engine: Engine, site_id: int, start: datetime, end: datetime
) -> tuple[pd.DataFrame, datetime | None]:
    """For each slot the newest forecast we have, plus when that newest run was fetched."""
    query = text(f"""
        select distinct on (ts) ts, run_at, {", ".join(WEATHER_COLUMNS)}
        from weather_fc
        where site_id = :site_id and ts >= :start and ts < :end
        order by ts, run_at desc
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"site_id": site_id, "start": start, "end": end})
    if df.empty:
        return df, None
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    latest_run = pd.to_datetime(df["run_at"], utc=True).max().to_pydatetime()
    return df.drop(columns="run_at"), latest_run


# ── Job log ──────────────────────────────────────────────────────────────────


def log_job(
    engine: Engine,
    job: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    rows_written: int = 0,
    message: str | None = None,
) -> None:
    """One row per job run, success or failure, for the status page."""
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into job_runs (job, started_at, finished_at, status, rows_written, message)
                values (:job, :started_at, :finished_at, :status, :rows_written, :message)
            """),
            {
                "job": job,
                "started_at": started_at,
                "finished_at": finished_at,
                "status": status,
                "rows_written": rows_written,
                "message": message[:1000] if message else None,
            },
        )


def recent_job_runs(engine: Engine, limit: int = 10) -> pd.DataFrame:
    query = text("""
        select job, started_at, finished_at, status, rows_written, message
        from job_runs order by started_at desc limit :limit
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"limit": limit})
    for col in ("started_at", "finished_at"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


# ── Site components ──────────────────────────────────────────────────────────


def read_components(engine: Engine, site_id: int) -> list[dict]:
    """The site's components, oldest first: dicts with id, kind, name, params."""
    query = text("""
        select id, kind, name, params from site_components
        where site_id = :site_id order by created_at, id
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"site_id": site_id}).mappings().all()
    return [dict(r) for r in rows]


def save_components(engine: Engine, site_id: int, components: list[dict]) -> None:
    """Insert or update components (dicts with id, kind, name, params)."""
    query = text("""
        insert into site_components (id, site_id, kind, name, params)
        values (:id, :site_id, :kind, :name, cast(:params as jsonb))
        on conflict (id) do update set
            kind = excluded.kind, name = excluded.name, params = excluded.params
    """)
    rows = [
        {
            "id": c["id"],
            "site_id": site_id,
            "kind": c["kind"],
            "name": c["name"],
            "params": json.dumps(c["params"]),
        }
        for c in components
    ]
    if rows:
        with engine.begin() as conn:
            conn.execute(query, rows)


def delete_component(engine: Engine, component_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("delete from site_components where id = :id"), {"id": component_id})
