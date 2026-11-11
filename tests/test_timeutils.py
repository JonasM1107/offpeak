from datetime import date

import pandas as pd
import pytest

from offpeak.timeutils import day_slots, to_local


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
