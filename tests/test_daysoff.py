"""Days off work in Germany (offpeak/forecast/daysoff.py), checked against the calendar."""

from datetime import date

import pandas as pd
import pytest

from offpeak.forecast.daysoff import day_off, easter
from offpeak.forecast.model import daily_matrix, features
from tests.test_forecast import weekly_history


@pytest.mark.parametrize(
    "year, sunday",
    [
        (2019, date(2019, 4, 21)),
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),
    ],
)
def test_easter_sunday(year, sunday):
    assert easter(year) == sunday


@pytest.mark.parametrize(
    "day, share",
    [
        (date(2026, 1, 1), 1.0),  # New Year
        (date(2026, 4, 3), 1.0),  # Good Friday 2026
        (date(2026, 4, 6), 1.0),  # Easter Monday 2026
        (date(2026, 5, 14), 1.0),  # Ascension Day 2026
        (date(2026, 5, 25), 1.0),  # Whit Monday 2026
        (date(2026, 10, 3), 1.0),
        (date(2026, 12, 24), 1.0),
        (date(2026, 12, 31), 1.0),
        (date(2026, 6, 4), 0.5),  # Corpus Christi 2026: only some states
        (date(2026, 11, 1), 0.5),
        (date(2026, 12, 29), 0.5),  # between the years
        (date(2026, 11, 18), 0.0),  # an ordinary Wednesday
        (date(2026, 4, 7), 0.0),  # the Tuesday after Easter
    ],
)
def test_day_off(day, share):
    assert day_off(day) == share


def test_the_model_sees_a_holiday_and_the_holiday_a_week_before():
    """Standing at the end of a day, guessing Easter Monday 2026 and the Monday after it."""
    h = weekly_history(weeks=40)  # starts 3 Aug 2026: long enough to hold Easter 2027
    table = daily_matrix(h)
    m, days = table.to_numpy(), [pd.Timestamp(d).date() for d in table.index]
    d0 = days.index(date(2027, 3, 27))  # Saturday before Easter 2027
    easter_monday = features(m, d0, 2, date(2027, 3, 29))
    week_after = features(m, d0, 9 - 7, date(2027, 4, 5))
    assert (easter_monday["day_off"] == 1.0).all() and (easter_monday["day_off_week"] == 0).all()
    assert (week_after["day_off"] == 0).all() and (week_after["day_off_week"] == 1.0).all()
