from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from offpeak import db
from offpeak.jobs import ingest_drivers, runner
from offpeak.weather.price_drivers import build_params, parse_points, turbine_share


def test_turbine_share_follows_a_power_curve():
    share = turbine_share([0, 3, 7.5, 12, 25])
    assert share[0] == share[1] == 0  # below cut-in
    assert share[3] == share[4] == 1  # full power from 12 m/s, also in a storm
    assert share[2] == pytest.approx((7.5**3 - 27) / (12**3 - 27))


def test_wind_is_averaged_as_turbine_share_and_gaps_stay_gaps(load_fixture):
    wind = parse_points(
        load_fixture("price_drivers_wind.json")["response"], "wind_speed_100m", "wind"
    )
    assert list(wind.columns) == [f"wind_{k}" for k in range(1, 8)]
    assert str(wind.index.tz) == "UTC"
    first, middle, last = wind["wind_1"]
    assert first == pytest.approx(turbine_share([4.0])[0] / 2)  # 2 m/s gives 0, 4 m/s a little
    assert middle == pytest.approx(turbine_share([7.5])[0])
    assert last == 1
    # one point is missing for k = 7: the other point's value is used, not a 0
    assert wind["wind_7"].iloc[1] == pytest.approx(turbine_share([7.5])[0])


def test_radiation_moves_back_to_the_hour_start(load_fixture):
    sun = parse_points(
        load_fixture("price_drivers_sun.json")["response"], "shortwave_radiation", "sun", 1
    )
    assert sun.index[0] == pd.Timestamp("2026-06-19 23:00", tz="UTC")
    assert sun["sun_3"].iloc[1] == 123.0


def test_params_ask_for_every_lead_from_ecmwf():
    p = build_params([(1.0, 2.0), (3.0, 4.0)], "temperature_2m", date(2026, 1, 1), date(2026, 1, 2))
    assert p["latitude"] == "1.0,3.0" and p["models"] == "ecmwf_ifs025"
    assert p["hourly"].count("temperature_2m_previous_day") == 7


def drivers(hours: int = 48) -> pd.DataFrame:
    idx = pd.date_range("2026-06-20", periods=hours, freq="h", tz="UTC")
    cols = {
        f"{v}_{k}": np.linspace(0, 1, hours) * k
        for v in ("wind", "sun", "temp")
        for k in range(1, 8)
    }
    out = pd.DataFrame(cols, index=idx)
    out.iloc[3, 0] = np.nan  # a gap
    return out


def test_drivers_round_trip(engine):
    d = drivers()
    assert db.upsert_drivers(engine, d) == 48 * 7
    db.upsert_drivers(engine, d)  # again: no duplicates
    back = db.read_drivers(engine, d.index.min(), d.index.max() + pd.Timedelta(hours=1))
    assert list(back.columns) == sorted(back.columns, key=list(d.columns).index)
    assert back.shape == d.shape
    assert np.isnan(back.iloc[3, 0]) and back.iloc[3, 1] == pytest.approx(d.iloc[3, 1])
    np.testing.assert_allclose(back.to_numpy(), d.to_numpy(), rtol=1e-6)  # stored as real


def test_driver_job_stores_the_recent_days(engine, monkeypatch):
    monkeypatch.setattr(db, "database_url", lambda: "unused")
    monkeypatch.setattr(db, "get_engine", lambda url: engine)
    with patch.object(ingest_drivers, "fetch_drivers", return_value=drivers(24)) as fetch:
        assert runner.run("ingest_drivers", ingest_drivers.ingest()) == 0
    start, end = fetch.call_args.args
    assert (end - start).days == ingest_drivers.DAYS_BACK + ingest_drivers.DAYS_AHEAD
    assert db.recent_job_runs(engine)["rows_written"].tolist() == [24 * 7]
