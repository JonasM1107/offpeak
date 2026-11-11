from datetime import date

import pandas as pd

from offpeak.timeutils import floor_to_slot, market_day_bounds


def test_floor_to_slot_converts_to_utc():
    ts = pd.Series(["2026-11-10T13:07:00+01:00", "2026-11-10T13:15:00+01:00"])
    assert list(floor_to_slot(ts)) == [
        pd.Timestamp("2026-11-10 12:00", tz="UTC"),
        pd.Timestamp("2026-11-10 12:15", tz="UTC"),
    ]


def test_market_day_lengths():
    for day, hours in [(date(2026, 11, 10), 24), (date(2026, 3, 29), 23), (date(2026, 10, 25), 25)]:
        start, end = market_day_bounds(day)
        assert (end - start).total_seconds() == hours * 3600
