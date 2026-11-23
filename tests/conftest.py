import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text())

    return _load


@pytest.fixture(autouse=True)
def fresh_server_counters():
    """Wrong logins and Ollie's questions are counted for the whole server (offpeak/auth.py,
    offpeak/assistant/agent.py). Every test starts at zero, so one test's wrong logins never
    pause the next test's sign-in."""
    from offpeak import auth
    from offpeak.assistant import agent

    auth.forget_failures()
    agent._asked.clear()


@pytest.fixture
def engine():
    """A clean test database. Needs TEST_DATABASE_URL (CI starts a Postgres for this);
    without it the database tests are skipped."""
    import os

    from sqlalchemy import text

    from offpeak.db import get_engine

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = get_engine(url)
    migrations = sorted((Path(__file__).parent.parent / "db" / "migrations").glob("*.sql"))
    with eng.begin() as conn:
        tables = (
            "prices_da, weather_fc, job_runs, site_components, cockpit_machines, weather_drivers, "
            "price_outlook, accounts, site_measurements"
        )
        conn.execute(text(f"drop table if exists {tables}"))
        for migration in migrations:
            conn.exec_driver_sql(migration.read_text())
    return eng
