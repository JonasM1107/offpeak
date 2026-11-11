import pandas as pd
import pytest

from offpeak.demo_site import (
    ASSETS,
    FLEX_LOADS,
    USUAL,
    Plan,
    cost,
    hourly_inputs,
    plan_day,
    simulate,
    turbine_kw,
    windows,
)

TZ = "Europe/Berlin"
BERLIN_DAY = pd.date_range("2026-11-10 23:00", periods=96, freq="15min", tz="UTC")


@pytest.fixture
def demo():
    return hourly_inputs(None, None, TZ)


def test_demo_inputs_cover_every_hour(demo):
    assert list(demo["hour"]) == list(range(24))
    assert not demo["price_real"].any()
    assert demo.loc[demo["hour"] == 2, "pv_kw"].item() == 0  # no sun at night


@pytest.mark.parametrize("smart", [True, False])
def test_energy_balances_every_hour(demo, smart):
    day = simulate(demo, Plan(USUAL.starts, smart))
    supply = day["pv_kw"] + day["wind_kw"] + day["grid_kw"]
    demand = day["load_kw"] + day["battery_kw"]
    assert (supply - demand).abs().max() < 1e-9


@pytest.mark.parametrize("smart", [True, False])
def test_battery_stays_within_limits(demo, smart):
    day = simulate(demo, Plan(USUAL.starts, smart))
    assert day["soc_pct"].between(0, 100).all()
    assert day["battery_kw"].abs().max() <= ASSETS.battery_kw


def test_plan_beats_usual_on_demo_day(demo):
    assert cost(demo, plan_day(demo)) < cost(demo, USUAL)


def test_plan_never_costs_more_than_usual():
    # flat price, no own power: nothing to gain, so the plan may not make it worse
    inputs = hourly_inputs(pd.DataFrame({"ts": BERLIN_DAY, "eur_mwh": 150.0}), None, TZ)
    inputs["pv_kw"] = 0.0
    inputs["wind_kw"] = 0.0
    assert cost(inputs, plan_day(inputs)) <= cost(inputs, USUAL)


def test_plan_keeps_every_load_inside_its_allowed_hours(demo):
    plan = plan_day(demo)
    for f in FLEX_LOADS:
        assert f.earliest <= plan.starts[f.key]
        assert plan.starts[f.key] + f.hours <= f.latest_end


def test_plan_moves_loads_to_cheap_hours():
    prices = pd.DataFrame({"ts": BERLIN_DAY, "eur_mwh": 300.0})
    prices.loc[prices["ts"].dt.tz_convert(TZ).dt.hour.between(10, 17), "eur_mwh"] = 50.0
    inputs = hourly_inputs(prices, None, TZ)
    inputs["pv_kw"] = 0.0
    inputs["wind_kw"] = 0.0
    plan = plan_day(inputs)
    assert plan.starts == {"furnace": 10, "ev": 10}


def test_real_prices_replace_demo_prices():
    inputs = hourly_inputs(pd.DataFrame({"ts": BERLIN_DAY, "eur_mwh": 200.0}), None, TZ)
    assert inputs["price_real"].all()
    assert (inputs["price_ct"] == 20.0).all()


def test_real_weather_drives_solar_and_wind():
    weather = pd.DataFrame({"ts": BERLIN_DAY, "gti_wm2": 1000.0, "wind_ms": 0.0})
    inputs = hourly_inputs(None, weather, TZ)
    assert inputs["weather_real"].all()
    assert inputs["pv_kw"].round(6).eq(ASSETS.pv_kwp * 0.85).all()
    assert (inputs["wind_kw"] == 0).all()


@pytest.mark.parametrize(("ms", "kw"), [(2, 0), (12, 15), (30, 0)])
def test_turbine_power_curve(ms, kw):
    assert turbine_kw(ms, 15) == kw


def test_windows_text():
    assert windows(USUAL) == {"furnace": "06–14", "ev": "17–22"}
