import pandas as pd
import pytest

from offpeak.analysis import (
    best_window,
    covers_days,
    ct_kwh,
    current_price,
    daily_stats,
    hourly,
    hourly_profile,
    monthly_stats,
    price_summary,
    weekday_hour,
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


def test_hourly_mixes_15_minute_and_hourly_history(load_fixture):
    quarter = parse_prices(load_fixture("prices_sample.json"))  # 96 slots
    hourly_day = parse_prices(load_fixture("prices_hourly_2025.json"))  # 24 slots
    both = pd.concat([hourly_day, quarter], ignore_index=True)
    h = hourly(both)
    assert h["ts"].dt.minute.eq(0).all()
    # 24 hours from each day; resample fills the months between with nothing
    assert len(h) == 48
    first_hour = quarter["eur_mwh"].iloc[:4].mean() / 10
    assert h.loc[h["ts"] == quarter["ts"].iloc[0], "ct"].item() == pytest.approx(first_hour)


def test_weekday_hour_table(load_fixture):
    prices = parse_prices(load_fixture("prices_sample.json"))  # Tuesday 10 Nov 2026
    table = weekday_hour(prices)
    assert table.shape == (7, 24)
    assert table.loc[1].notna().all()  # Tuesday has every hour
    assert table.loc[0].isna().all()  # no Monday in the data


def test_monthly_stats_and_summary(load_fixture):
    prices = parse_prices(load_fixture("prices_spring_forward.json"))  # 23 hours, negatives
    month = monthly_stats(prices)
    assert len(month) == 1
    assert month["negative_hours"].iloc[0] >= 1
    s = price_summary(prices)
    assert s["hours"] == 23 and s["days"] == 1
    assert s["negative_hours"] == month["negative_hours"].iloc[0]
    assert s["avg_spread_ct"] > 0


def test_covers_days_with_any_resolution(load_fixture):
    from datetime import date

    quarter = parse_prices(load_fixture("prices_sample.json"))  # 10 Nov 2026
    hourly_day = parse_prices(load_fixture("prices_hourly_2025.json"))  # 1 Sep 2025
    spring = parse_prices(load_fixture("prices_spring_forward.json"))  # 23-hour day
    assert covers_days(quarter, date(2026, 11, 10), date(2026, 11, 10))
    assert covers_days(hourly_day, date(2025, 9, 1), date(2025, 9, 1))
    assert covers_days(spring, date(2026, 3, 29), date(2026, 3, 29))
    assert not covers_days(quarter, date(2026, 11, 10), date(2026, 11, 11))  # next day missing
    assert not covers_days(quarter.iloc[:40], date(2026, 11, 10), date(2026, 11, 10))


def test_hourly_payload_lists_line_up(load_fixture):
    from offpeak.analysis import hourly_payload

    p = hourly_payload(parse_prices(load_fixture("prices_fall_back.json")))  # 25-hour day
    assert len(p["t"]) == len(p["ct"]) == len(p["hour"]) == 25
    assert set(p["day"]) == {20261025} and set(p["wd"]) == {6}  # a Sunday
    assert p["hour"].count(2) == 2  # the repeated hour when clocks go back
    assert p["t"][0] == 1792879200  # 25 Oct 2026 00:00 in Berlin = 24 Oct 22:00 UTC
