import pandas as pd
import pytest

from offpeak.insights import change_pct, fit_wind_line, headline, outlook, shift_savings
from offpeak.weather.drivers import daily_wind


def make_prices(values, start="2026-11-12 00:00"):
    """Hourly prices in €/MWh, starting at local midnight in Berlin."""
    ts = pd.date_range(start, periods=len(values), freq="h", tz="Europe/Berlin").tz_convert("UTC")
    return pd.DataFrame({"ts": ts, "eur_mwh": values, "resolution_min": 60})


def test_shift_saving_is_kwh_times_price_gap():
    prices = make_prices([100.0] * 10 + [50.0] + [100.0] * 7 + [300.0] + [100.0] * 5)
    furnace = shift_savings(prices, loads=[("Furnace", 500.0, 1)])[0]
    assert furnace.cheap.start == prices["ts"].iloc[10]
    assert furnace.peak.start == prices["ts"].iloc[18]
    assert furnace.saving_eur == pytest.approx(500 * (300 - 50) / 1000)  # = €125


def test_no_saving_rows_without_prices():
    assert shift_savings(make_prices([]).astype({"eur_mwh": float})) == []


def test_change_pct():
    assert change_pct(200, 150) == -25
    assert change_pct(0, 10) is None


def test_wind_line_finds_the_slope_and_intercept():
    wind = pd.Series([float(h % 12) for h in range(24 * 8)])
    joined = pd.DataFrame({"wind_north_ms": wind, "ct_kwh": 30 - 2 * wind})
    fit = fit_wind_line(joined)
    assert fit.intercept == pytest.approx(30)
    assert fit.slope == pytest.approx(-2)
    assert fit.mae == pytest.approx(0)


def test_wind_line_needs_a_week_of_hours():
    joined = pd.DataFrame({"wind_north_ms": [1.0, 2.0] * 10, "ct_kwh": [5.0, 4.0] * 10})
    assert fit_wind_line(joined) is None


def test_outlook_labels_days_against_the_usual_price():
    wind = pd.Series([float(h % 12) for h in range(24 * 8)])
    fit = fit_wind_line(pd.DataFrame({"wind_north_ms": wind, "ct_kwh": 30 - 2 * wind}))
    fit.mae = 4  # pretend the line is off by 4 ct, so ±2 ct counts as "about usual"
    days = pd.DataFrame({"day": [1, 2, 3], "wind_north_ms": [12.0, 5.0, 1.0]})
    out = outlook(fit, days, typical_ct=20)
    assert list(out["est_ct"]) == pytest.approx([6, 20, 28])
    assert list(out["label"]) == ["likely cheaper", "about usual", "likely pricier"]


def test_headline_names_tomorrows_windows_in_local_time():
    today = make_prices([200.0] * 24, start="2026-11-11 00:00")
    tomorrow = make_prices([100.0] * 21 + [20.0] * 3)  # cheapest 3 hours: 21:00-24:00
    text = headline(today, tomorrow, "Europe/Berlin")
    assert text.startswith("Tomorrow is 55 % cheaper than today.")  # (90 - 200) / 200
    assert "21:00–24:00 (2.0 ct/kWh)" in text


def test_headline_waits_for_tomorrows_prices():
    empty = make_prices([]).astype({"eur_mwh": float})
    assert headline(make_prices([100.0] * 24), empty, "Europe/Berlin") is None


def test_daily_wind_uses_local_days():
    ts = pd.date_range("2026-11-11 23:00", periods=2, freq="h", tz="UTC")  # 00:00 and 01:00 CET
    days = daily_wind(pd.DataFrame({"ts": ts, "wind_north_ms": [4.0, 6.0]}), "Europe/Berlin")
    assert len(days) == 1 and days["wind_north_ms"].iloc[0] == 5.0
