import pandas as pd
import pytest

from offpeak.analysis import (
    best_window,
    ct_kwh,
    current_price,
    daily_stats,
    hourly_profile,
    hourly_with_drivers,
    price_by_wind,
    wind_price_correlation,
    window_mask,
)
from offpeak.markets.energy_charts import parse_prices


def make_prices(values, start="2026-11-12 00:00", minutes=15):
    ts = pd.date_range(start, periods=len(values), freq=f"{minutes}min", tz="UTC")
    return pd.DataFrame({"ts": ts, "eur_mwh": values, "resolution_min": minutes})


def test_cheapest_and_most_expensive_hour():
    prices = make_prices([50, 50, 50, 50, 10, 10, 10, 10, 90, 90, 90, 90])
    cheap = best_window(prices, hours=1)
    assert cheap.start == pd.Timestamp("2026-11-12 01:00", tz="UTC")
    assert cheap.end == pd.Timestamp("2026-11-12 02:00", tz="UTC")
    assert cheap.avg_eur_mwh == 10
    peak = best_window(prices, hours=1, cheapest=False)
    assert peak.start == pd.Timestamp("2026-11-12 02:00", tz="UTC")
    assert window_mask(prices, peak).sum() == 4


def test_window_never_spans_a_gap():
    prices = make_prices([5, 5, 100, 100, 100, 100])
    prices = prices.drop(index=2).reset_index(drop=True)  # 00:30 missing
    w = best_window(prices, hours=0.5)
    assert w.start == pd.Timestamp("2026-11-12 00:00", tz="UTC")
    assert best_window(make_prices([1, 2]), hours=1) is None


def test_negative_prices_win(load_fixture):
    prices = parse_prices(load_fixture("prices_spring_forward.json"))
    w = best_window(prices, hours=1)
    assert w.avg_eur_mwh == prices["eur_mwh"].rolling(4).mean().min()
    assert w.avg_eur_mwh < 0


def test_works_on_hourly_prices(load_fixture):
    prices = parse_prices(load_fixture("prices_hourly_2025.json"))
    w = best_window(prices, hours=3)
    assert w.end - w.start == pd.Timedelta(hours=3)


def test_current_price():
    prices = make_prices([10, 20, 30])
    row = current_price(prices, pd.Timestamp("2026-11-12 00:20", tz="UTC"))
    assert row["eur_mwh"] == 20
    assert current_price(prices, pd.Timestamp("2026-11-12 01:00", tz="UTC")) is None
    assert ct_kwh(123.4) == 12.34


def test_daily_stats_and_hourly_profile(load_fixture):
    prices = parse_prices(load_fixture("prices_fall_back.json"))  # Sunday, 25 hours
    daily = daily_stats(prices)
    assert len(daily) == 1
    assert daily["max"].iloc[0] == prices["eur_mwh"].max() / 10
    profile = hourly_profile(prices)
    assert len(profile) == 24  # the repeated 02:00 hour is averaged, not duplicated
    assert profile["workday"].isna().all()


def _hours(n, start="2026-11-10 00:00"):
    return pd.date_range(start, periods=n, freq="h", tz="UTC")


def test_hourly_with_drivers_averages_quarter_hours_and_joins():
    ts = pd.date_range("2026-11-10 00:00", periods=8, freq="15min", tz="UTC")
    prices = pd.DataFrame({"ts": ts, "eur_mwh": [100, 200, 300, 400, 0, 0, 0, 40]})
    drivers = pd.DataFrame(
        {"ts": _hours(3), "wind_north_ms": [2.0, 9.0, 5.0], "sun_south_wm2": [0.0, 0.0, 0.0]}
    )
    joined = hourly_with_drivers(prices, drivers)
    assert list(joined["ct_kwh"]) == [25.0, 1.0]  # (100+200+300+400)/4/10, (0+0+0+40)/4/10
    assert list(joined["wind_north_ms"]) == [2.0, 9.0]  # the third hour has no price


def test_price_by_wind_sorts_hours_into_bands():
    joined = pd.DataFrame(
        {"ts": _hours(4), "ct_kwh": [30.0, 20.0, 10.0, 12.0], "wind_north_ms": [1, 5, 9, 11]}
    )
    bands = price_by_wind(joined)
    assert list(bands["hours"]) == [1, 1, 2]
    assert list(bands["ct_kwh"]) == [30.0, 20.0, 11.0]


def test_correlation_needs_a_day_of_hours_and_is_negative_when_wind_lowers_prices():
    wind = list(range(24))
    joined = pd.DataFrame(
        {"ts": _hours(24), "wind_north_ms": wind, "ct_kwh": [30 - w for w in wind]}
    )
    assert wind_price_correlation(joined) == pytest.approx(-1.0)
    assert wind_price_correlation(joined.head(10)) is None
