"""Tests for offpeak/generation/pv.py: solar power with pvlib's PVWatts model."""

import pandas as pd
import pytest

from offpeak.generation.pv import SYSTEM_LOSSES_PCT, pv_kw


def one(poa, kwp=8.0, temp=None, wind=None, inverter_kw=None) -> float:
    temp = None if temp is None else pd.Series([temp])
    wind = None if wind is None else pd.Series([wind])
    return float(pv_kw(pd.Series([poa]), kwp, temp, wind, inverter_kw).iloc[0])


def test_rating_conditions():
    # 1000 W/m², module at 25 °C: only system losses (8.7 %) and the inverter (about 96 %)
    assert SYSTEM_LOSSES_PCT == pytest.approx(8.68, abs=0.01)
    assert one(1000) == pytest.approx(8 * 0.8777, abs=0.01)


def test_hot_air_costs_power_cold_air_less():
    hot, mild, cold = one(1000, temp=30), one(1000, temp=15), one(1000, temp=0)
    assert hot < mild < cold
    assert hot == pytest.approx(6.08, abs=0.01)  # module near 61 °C
    assert cold == pytest.approx(6.86, abs=0.01)  # module near 31 °C


def test_weak_winter_sun_beats_the_old_fixed_factor():
    # the old model always took 0.85 of the irradiance: 400 W/m² on 8 kWp gave 2.72 kW
    assert one(400, temp=2) == pytest.approx(2.91, abs=0.01)
    assert one(400, temp=2) > 400 / 1000 * 8 * 0.85


def test_wind_cools_the_module():
    assert one(1000, temp=25, wind=8) > one(1000, temp=25, wind=0.5)


def test_inverter_cuts_the_peak():
    # 10 kWp of panels on an 8 kW inverter: a cold, clear noon would give more than 8 kW
    assert one(1000, kwp=10, temp=0) > 8
    assert one(1000, kwp=10, temp=0, inverter_kw=8) == pytest.approx(8.0)


def test_no_sun_no_power():
    out = pv_kw(pd.Series([None, -5.0, 0.0]), 8, pd.Series([20.0, 20.0, 20.0]))
    assert out.tolist() == [0.0, 0.0, 0.0]


def test_missing_temperature_counts_as_25_degrees():
    out = pv_kw(pd.Series([1000.0, 1000.0]), 8, pd.Series([None, 25.0]))
    assert out.iloc[0] == pytest.approx(one(1000))
    assert out.iloc[1] < out.iloc[0]  # 25 °C air makes a module far warmer than 25 °C


def test_no_panels_and_index_kept():
    index = pd.date_range("2026-07-01", periods=3, freq="15min", tz="UTC")
    out = pv_kw(pd.Series(800.0, index=index), 0)
    assert out.tolist() == [0.0, 0.0, 0.0]
    assert out.index.equals(index)
    assert pv_kw(pd.Series(800.0, index=index), 8).index.equals(index)


def test_zero_inverter_means_no_power():
    assert one(1000, inverter_kw=0) == 0.0
