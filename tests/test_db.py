from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from offpeak import db
from offpeak.markets.energy_charts import parse_prices
from offpeak.weather.open_meteo import parse_weather


def test_prices_round_trip_and_no_duplicates(engine, load_fixture):
    prices = parse_prices(load_fixture("prices_spring_forward.json"))  # 92 slots, negatives
    assert db.upsert_prices(engine, prices, "DE-LU") == 92
    db.upsert_prices(engine, prices, "DE-LU")  # second run must not duplicate
    stored = db.read_prices(engine, "DE-LU", prices["ts"].min(), prices["ts"].max() + timedelta(1))
    assert len(stored) == 92
    assert stored["eur_mwh"].min() < 0
    assert stored["ts"].tolist() == prices["ts"].tolist()
    assert str(stored["ts"].dt.tz) == "UTC"


def test_rerun_updates_a_changed_price(engine, load_fixture):
    prices = parse_prices(load_fixture("prices_sample.json"))
    db.upsert_prices(engine, prices, "DE-LU")
    prices.loc[0, "eur_mwh"] = 1.23
    db.upsert_prices(engine, prices, "DE-LU")
    stored = db.read_prices(engine, "DE-LU", prices["ts"].min(), prices["ts"].max() + timedelta(1))
    assert stored["eur_mwh"].iloc[0] == 1.23


def test_latest_weather_run_wins_and_nulls_stay_null(engine, load_fixture):
    raw = load_fixture("weather_sample.json")
    raw["hourly"]["temperature_2m"][5] = None
    old = parse_weather(raw)
    new = old.copy()
    new["temp_c"] = new["temp_c"] + 1
    t0 = datetime(2026, 11, 11, 6, tzinfo=UTC)
    db.upsert_weather(engine, old, 1, t0)
    db.upsert_weather(engine, new, 1, t0 + timedelta(hours=3))
    weather, latest = db.read_latest_weather(
        engine, 1, old["ts"].min(), old["ts"].max() + timedelta(1)
    )
    assert latest == t0 + timedelta(hours=3)
    assert len(weather) == len(old)
    assert weather["temp_c"].isna().sum() == 4  # stored as NULL, not 0
    pd.testing.assert_series_equal(
        weather["temp_c"].dropna().reset_index(drop=True),
        new["temp_c"].dropna().reset_index(drop=True),
        check_names=False,
        check_dtype=False,
        atol=1e-4,
    )


def test_job_log(engine):
    now = datetime.now(UTC)
    db.log_job(engine, "ingest_prices", now, now, "skipped", 0, "tomorrow already stored")
    runs = db.recent_job_runs(engine)
    assert runs.iloc[0]["status"] == "skipped"


def test_components_round_trip(engine):
    from offpeak.components import new_component

    pv = new_component("pv_field", "New solar", {"kwp": 55})
    row = {"id": pv.id, "kind": pv.kind, "name": pv.name, "params": pv.params}
    db.save_components(engine, 1, [row])
    db.save_components(engine, 1, [row | {"name": "Renamed"}])  # update, no duplicate
    stored = db.read_components(engine, 1)
    assert len(stored) == 1
    assert stored[0]["name"] == "Renamed" and stored[0]["params"]["kwp"] == 55
    db.delete_component(engine, pv.id)
    assert db.read_components(engine, 1) == []


def test_cockpit_machines_round_trip(engine):
    assert db.read_machines(engine, 1) is None  # nothing saved yet
    oven = {"name": "Oven", "kw": 30.0, "hours": 5, "earliest": 5, "latest_end": 22}
    db.save_machines(engine, 1, [oven])
    assert db.read_machines(engine, 1) == [oven]
    db.save_machines(engine, 1, [])  # removing every machine is kept, not reset to the demo
    assert db.read_machines(engine, 1) == []
    assert db.read_machines(engine, 2) is None


def test_outlook_is_replaced_as_a_whole(engine):
    def outlook(start: str, hours: int, p50: float) -> pd.DataFrame:
        ts = pd.date_range(start, periods=hours, freq="h", tz="UTC")
        return pd.DataFrame(
            {
                "ts": ts,
                "day": ts.tz_convert("Europe/Berlin").date,
                "lead": 1,
                "p10": p50 - 2,
                "p50": p50,
                "p90": p50 + 2,
                "miss_ct": [float("nan")] + [4.2] * (hours - 1),
            }
        )

    assert db.read_outlook(engine).empty
    based_on = datetime(2026, 11, 12, 22, tzinfo=UTC)
    assert db.save_outlook(engine, outlook("2026-11-12 23:00", 48, 10.0), based_on) == 48
    db.save_outlook(engine, outlook("2026-11-13 23:00", 24, 20.0), based_on + timedelta(days=1))
    stored = db.read_outlook(engine)
    assert len(stored) == 24 and (stored["p50"] == 20.0).all()  # the older run is gone
    assert stored["based_on"].iloc[0] == based_on + timedelta(days=1)
    assert pd.isna(stored["miss_ct"].iloc[0]) and stored["miss_ct"].iloc[1] == pytest.approx(4.2)
