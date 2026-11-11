from datetime import UTC, date, datetime
from unittest.mock import Mock

import pandas as pd
import pytest

from offpeak.markets import energy_charts
from offpeak.markets.energy_charts import PriceSourceError, fetch_day_ahead, parse_prices


def test_normal_day_has_96_quarter_hours_in_utc(load_fixture):
    df = parse_prices(load_fixture("prices_sample.json"))
    assert len(df) == 96
    assert list(df.columns) == ["ts", "eur_mwh", "resolution_min", "source"]
    assert str(df["ts"].dt.tz) == "UTC"
    # 10 Nov 2026 00:00 in Berlin (UTC+1) is 9 Nov 23:00 UTC
    assert df["ts"].iloc[0] == pd.Timestamp("2026-11-09 23:00", tz="UTC")
    assert (df["resolution_min"] == 15).all()
    assert (df["source"] == "energy-charts").all()
    assert df["ts"].diff().dropna().eq(pd.Timedelta(minutes=15)).all()


@pytest.mark.parametrize(
    "fixture, slots", [("prices_spring_forward.json", 92), ("prices_fall_back.json", 100)]
)
def test_clock_change_days_have_no_gap_or_duplicate_in_utc(load_fixture, fixture, slots):
    df = parse_prices(load_fixture(fixture))
    assert len(df) == slots
    assert df["ts"].is_unique
    assert df["ts"].diff().dropna().eq(pd.Timedelta(minutes=15)).all()


def test_negative_prices_stay_negative(load_fixture):
    df = parse_prices(load_fixture("prices_spring_forward.json"))
    assert df["eur_mwh"].min() < 0


def test_hourly_history_before_october_2025(load_fixture):
    df = parse_prices(load_fixture("prices_hourly_2025.json"))
    assert len(df) == 24
    assert (df["resolution_min"] == 60).all()


def test_missing_price_is_skipped_not_zero(load_fixture):
    payload = load_fixture("prices_sample.json")
    payload["data"][5]["values"]["day_ahead_price"] = None
    df = parse_prices(payload)
    assert len(df) == 95
    assert (df["eur_mwh"] != 0).all()


def fake_response(status, json_body=None, text=""):
    return Mock(status_code=status, json=Mock(return_value=json_body), text=text)


def test_not_yet_published_returns_empty_table(monkeypatch):
    # Real behaviour, see tests/fixtures/prices_not_published.txt: HTTP 404 "no content available"
    not_published = fake_response(404, text="no content available")
    monkeypatch.setattr(energy_charts.http, "get", Mock(return_value=not_published))
    df = fetch_day_ahead("DE-LU", date(2026, 11, 13), date(2026, 11, 13))
    assert df.empty
    assert list(df.columns) == ["ts", "eur_mwh", "resolution_min", "source"]


def test_server_error_raises(monkeypatch):
    monkeypatch.setattr(energy_charts.http, "get", Mock(return_value=fake_response(500, text="x")))
    with pytest.raises(PriceSourceError):
        fetch_day_ahead("DE-LU", date(2026, 11, 13), date(2026, 11, 13))


def test_tomorrow_uses_market_date_not_utc_date(monkeypatch):
    get = Mock(return_value=fake_response(404))
    monkeypatch.setattr(energy_charts.http, "get", get)
    # 23:30 UTC on 11 Nov is already 12 Nov in Berlin, so tomorrow is 13 Nov
    energy_charts.fetch_tomorrow("DE-LU", now=datetime(2026, 11, 11, 23, 30, tzinfo=UTC))
    assert get.call_args.kwargs["params"]["start"] == "2026-11-13"


def test_history_is_fetched_month_by_month(monkeypatch, load_fixture):
    sample = parse_prices(load_fixture("prices_sample.json"))
    calls = []

    def fake_fetch(zone, start, end):
        calls.append((start, end))
        return sample

    monkeypatch.setattr(energy_charts, "fetch_day_ahead", fake_fetch)
    df = energy_charts.fetch_history("DE-LU", date(2026, 1, 15), date(2026, 3, 10), pause_s=0)
    assert calls == [
        (date(2026, 1, 15), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 10)),
    ]
    assert df["ts"].is_unique
