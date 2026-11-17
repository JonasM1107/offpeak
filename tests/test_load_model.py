"""The homeowner consumption forecast (offpeak/forecast/load_model.py), on made-up data with
a clear daily and weekly rhythm and a temperature effect."""

import numpy as np
import pandas as pd
import pytest

from offpeak.forecast import load_model as L


def made_up(days: int = 70, seed: int = 0):
    """Hourly kW: evenings high, weekends higher, more power on cold days, plus noise."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-05", periods=days * 24, freq="h", tz="Europe/Berlin")
    hour, weekend = idx.hour.to_numpy(), (idx.weekday >= 5).astype(float)
    temp = 5 + 8 * np.sin(np.arange(len(idx)) / (24 * 9)) + rng.normal(0, 1, len(idx))
    kw = (
        0.25
        + 0.4 * ((hour >= 18) & (hour < 22))
        + 0.15 * weekend
        + 0.02 * np.clip(12 - temp, 0, None)
    )
    kw = kw + rng.gamma(1.5, 0.05, len(idx))
    utc = idx.tz_convert("UTC")
    return pd.Series(kw, index=utc), pd.Series(temp, index=utc)


def test_hourly_load_from_quarter_hours():
    ts = pd.date_range("2026-01-01", periods=8, freq="15min", tz="UTC")
    slots = pd.DataFrame({"ts": ts, "load_kw": [1, 2, 3, 2, 0.5, 0.5, 0.5, 0.5]})
    assert L.hourly_load(slots).tolist() == [2.0, 0.5]


def test_too_little_history_is_refused():
    history, _ = made_up(days=20)
    with pytest.raises(ValueError, match="28 days"):
        L.LoadModel().fit(history)


def test_predict_needs_a_trained_model():
    history, _ = made_up(days=40)
    with pytest.raises(ValueError, match="Fit"):
        L.LoadModel().predict(history)


def test_a_week_of_hours_after_the_last_measured_day():
    history, temp = made_up()
    out = L.LoadModel().fit(history, temp).predict(history, temp)
    assert len(out) == 7 * 24 and set(out["lead"]) == set(range(1, 8))
    assert (out["kw"] >= 0).all()
    last = history.index.max().tz_convert("Europe/Berlin").date()
    assert out["day"].min() > last
    by_hour = out.groupby("hour")["kw"].mean()
    assert by_hour[19] > by_hour[3]  # it learned the evening peak


def test_the_model_beats_last_week_in_the_backtest():
    history, temp = made_up(days=84)
    bt = L.backtest(history, temp, days=21, retrain=7)
    assert set(bt.mae_kw) == {"ML model", "Same hour last week", "Average of the last 7 days"}
    assert bt.mae_kw["ML model"] < bt.mae_kw["Same hour last week"]
    assert list(bt.by_lead.columns) == list(range(1, 8))


def test_the_backtest_needs_enough_days():
    history, _ = made_up(days=40)
    with pytest.raises(ValueError, match="Not enough"):
        L.backtest(history, days=56)


def test_without_temperature_it_still_works():
    history, _ = made_up()
    model = L.LoadModel().fit(history)
    assert "temp" not in model.columns
    assert len(model.predict(history)) == 7 * 24
