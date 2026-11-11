from datetime import UTC, date, datetime

import pandas as pd
import pytest

from offpeak.timeutils import day_slots, floor_to_slot, market_today, to_local


@pytest.mark.parametrize(
    ("day", "tz", "expected"),
    [
        (date(2026, 11, 11), "Europe/Berlin", 96),
        (date(2026, 3, 29), "Europe/Berlin", 92),  # clocks go forward
        (date(2026, 10, 25), "Europe/Berlin", 100),  # clocks go back
        (date(2026, 3, 29), "Europe/Lisbon", 92),
        (date(2026, 10, 25), "Europe/Lisbon", 100),
    ],
)
def test_day_has_right_number_of_slots(day, tz, expected):
    assert len(day_slots(day, tz)) == expected


def test_slots_are_utc_and_start_at_local_midnight():
    slots = day_slots(date(2026, 11, 11), "Europe/Berlin")
    assert str(slots.tz) == "UTC"
    assert slots[0] == pd.Timestamp("2026-11-10 23:00", tz="UTC")  # 00:00 in Berlin
    assert slots[-1] == pd.Timestamp("2026-11-11 22:45", tz="UTC")


def test_to_local_shows_berlin_time():
    slots = day_slots(date(2026, 11, 11), "Europe/Berlin")
    assert to_local(slots, "Europe/Berlin")[0].hour == 0


def test_floor_to_slot_converts_to_utc():
    ts = pd.Series(["2026-11-10T13:07:00+01:00", "2026-11-10T13:15:00+01:00"])
    assert list(floor_to_slot(ts)) == [
        pd.Timestamp("2026-11-10 12:00", tz="UTC"),
        pd.Timestamp("2026-11-10 12:15", tz="UTC"),
    ]


def test_market_today_uses_berlin_date():
    # 23:30 UTC on 11 Nov is already 12 Nov in Berlin
    assert market_today(datetime(2026, 11, 11, 23, 30, tzinfo=UTC)) == date(2026, 11, 12)
