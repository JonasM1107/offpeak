"""Days off work in Germany, for the price model (offpeak/forecast/model.py).

On a public holiday factories and offices stand still, so less power is used and prices
fall, like on a Sunday. The weekday alone cannot tell: Easter Monday is a Monday. Each day
gets a number for how much of Germany is off work:

- 1.0: a holiday everywhere in Germany, and 24 and 31 December (most firms are closed)
- 0.5: a holiday in some large states only (Epiphany, Corpus Christi, Reformation Day,
  All Saints' Day), and the working days between Christmas and New Year
- 0.0: an ordinary day

Easter moves every year; it is worked out with the usual calendar rule (below), and the other
moving holidays are a fixed number of days after it. No library is needed for this.
"""

from datetime import date, timedelta


def easter(year: int) -> date:
    """Easter Sunday in the Gregorian calendar (the "anonymous Gregorian" rule, also known as
    Meeus/Jones/Butcher): only whole-number arithmetic, valid for every year from 1583."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 (the rule's own name)
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def days_off(year: int) -> dict[date, float]:
    """Every day off in `year` with its share (1.0 or 0.5); other days are not listed."""
    e = easter(year)
    everywhere = [
        date(year, 1, 1),  # New Year
        e - timedelta(days=2),  # Good Friday
        e + timedelta(days=1),  # Easter Monday
        date(year, 5, 1),  # Labour Day
        e + timedelta(days=39),  # Ascension Day
        e + timedelta(days=50),  # Whit Monday
        date(year, 10, 3),  # German Unity Day
        date(year, 12, 24),  # Christmas Eve (not a holiday by law, but most firms close)
        date(year, 12, 25),
        date(year, 12, 26),
        date(year, 12, 31),  # New Year's Eve (as Christmas Eve)
    ]
    some_states = [
        date(year, 1, 6),  # Epiphany: Baden-Württemberg, Bavaria, Saxony-Anhalt
        e + timedelta(days=60),  # Corpus Christi: the south and west, NRW included
        date(year, 10, 31),  # Reformation Day: the north and east
        date(year, 11, 1),  # All Saints' Day: the south and west, NRW included
        *(date(year, 12, d) for d in range(27, 31)),  # between the years
    ]
    out = {d: 0.5 for d in some_states}
    out.update({d: 1.0 for d in everywhere})  # a day in both lists counts fully
    return out


def day_off(day: date) -> float:
    """How much of Germany is off work on `day`: 1.0, 0.5 or 0.0."""
    return days_off(day.year).get(day, 0.0)
