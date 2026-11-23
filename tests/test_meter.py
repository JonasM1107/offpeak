"""Consumption exports (offpeak/load/meter.py) and the list of connectors
(offpeak/load/connectors.py). Made-up files in tests/fixtures/."""

import pandas as pd
import pytest

from offpeak.load import connectors, meter
from tests.conftest import FIXTURES


def frame(times, values, value_col="consumption_kwh", time_col="timestamp"):
    return pd.DataFrame({time_col: times, value_col: values}).astype(str)


# ── accepted ────────────────────────────────────────────────────────────────


def test_a_german_excel_export_with_hourly_kwh():
    """Semicolons, decimal commas, day first, German local time, one kWh value per hour."""
    slots = meter.read_csv(FIXTURES / "meter_hourly_de.csv")
    assert len(slots) == 2 * 24 * 4  # every hour spread over its four quarter-hours
    # 1 March 00:00 in Berlin is 23:00 UTC the day before (winter time, UTC+1)
    assert slots["ts"].iloc[0] == pd.Timestamp("2026-02-28 23:00", tz="UTC")
    assert slots["load_kw"].iloc[0] == pytest.approx(10.0)  # 10 kWh in an hour = 10 kW
    first_hour = slots["load_kw"].iloc[:4]
    assert (first_hour == 10.0).all()


def test_a_15_minute_export_in_kw_with_offsets():
    slots = meter.read_csv(FIXTURES / "meter_15min.csv")
    assert len(slots) == 96
    assert slots["ts"].iloc[0] == pd.Timestamp("2026-05-31 22:00", tz="UTC")
    assert slots["load_kw"].iloc[1] == 3  # kW stays kW


def test_5_minute_kwh_values_become_quarter_hour_means():
    times = pd.date_range("2026-06-01 10:00", periods=6, freq="5min", tz="UTC")
    raw = frame([t.isoformat() for t in times], [0.1] * 6)  # 0.1 kWh in 5 min = 1.2 kW
    slots = meter.read_csv(raw)
    assert len(slots) == 2
    assert slots["load_kw"].tolist() == pytest.approx([1.2, 1.2])


def test_the_summary_of_a_file():
    found = meter.summary(meter.read_csv(FIXTURES / "meter_hourly_de.csv"))
    assert found["days"] == 2
    day_kwh = sum(10 + h * 0.5 for h in range(24))  # 378 kWh a day
    assert found["kwh"] == pytest.approx(2 * day_kwh)
    assert found["kwh_per_day"] == pytest.approx(day_kwh)
    assert found["peak_kw"] == pytest.approx(21.5)
    assert len(found["by_hour"]) == 24 and found["by_hour"][0] == pytest.approx(10.0)


# ── rejected ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        (frame(["2026-06-01T10:00Z"] * 5, [1] * 5, time_col="when"), "no time column"),
        (frame(["2026-06-01T10:00Z"] * 5, [1] * 5, value_col="amount"), "kWh or kW"),
        (frame(["not a time"] * 5, [1] * 5), "no valid time"),
        (frame(["2026-06-01T10:00Z", "2026-06-01T10:15Z"], [1, 1]), "fewer than four"),
    ],
)
def test_files_that_cannot_be_read_say_why(raw, why):
    with pytest.raises(meter.MeterFileError, match=why):
        meter.read_csv(raw)


def test_negative_or_huge_values_are_refused():
    times = [t.isoformat() for t in pd.date_range("2026-06-01", periods=4, freq="15min", tz="UTC")]
    with pytest.raises(meter.MeterFileError, match="negative"):
        meter.read_csv(frame(times, [1, -1, 1, 1], value_col="load_kw"))
    with pytest.raises(meter.MeterFileError, match="W or Wh"):
        meter.read_csv(frame(times, [50_000] * 4, value_col="load_kw"))  # watts, not kW


def test_a_file_that_is_not_csv(tmp_path):
    path = tmp_path / "picture.csv"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe")
    with pytest.raises(meter.MeterFileError):
        meter.read_csv(path)


# ── edge cases ──────────────────────────────────────────────────────────────


def test_empty_values_are_dropped_not_filled():
    times = [t.isoformat() for t in pd.date_range("2026-06-01", periods=6, freq="15min", tz="UTC")]
    slots = meter.read_csv(frame(times, ["1", "", "1", "1", "nan", "1"], value_col="load_kw"))
    assert len(slots) == 4


def test_the_october_hour_that_happens_twice():
    """25 Oct 2026: 02:00 happens twice in Berlin. A file listing it twice gets both, an hour
    apart in UTC; nothing is lost or merged."""
    times = ["25.10.2026 01:00", "25.10.2026 02:00", "25.10.2026 02:00", "25.10.2026 03:00"]
    slots = meter.read_csv(frame(times, [1, 2, 3, 4]))
    hours = slots.set_index("ts")["load_kw"].resample("1h").mean()
    assert hours.tolist() == [1, 2, 3, 4]
    assert hours.index[0] == pd.Timestamp("2026-10-24 23:00", tz="UTC")


def test_the_march_hour_that_does_not_exist_is_not_a_crash():
    """29 Mar 2026: Berlin jumps from 02:00 to 03:00. A row at 02:00 moves to 03:00; the file
    is still read."""
    times = [f"29.03.2026 {h:02d}:00" for h in range(6)]
    slots = meter.read_csv(frame(times, [1] * 6))
    assert not slots.empty and slots["ts"].is_unique


def test_an_empty_summary():
    assert meter.summary(pd.DataFrame(columns=["ts", "load_kw"]))["days"] == 0


# ── connectors ──────────────────────────────────────────────────────────────


def test_each_role_sees_its_connectors_available_first():
    home = [c.key for c in connectors.for_role("home")]
    business = [c.key for c in connectors.for_role("business")]
    assert home[:2] == ["file", "fronius"] and "sap" not in home
    assert "sap" in business and "fronius" not in business
    for role in ("home", "business"):
        status = [c.status for c in connectors.for_role(role)]
        assert status == sorted(status, key=lambda s: s != connectors.AVAILABLE)


def test_only_the_file_import_is_offered_as_working():
    """Direct connections are not built yet: they must never look available."""
    working = {c.key for c in connectors.CONNECTORS if c.status == connectors.AVAILABLE}
    assert working == {"file", "fronius"}
