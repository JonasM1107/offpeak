"""Simulation cockpit: when should each machine run in the coming days, and what does that save?

The hours ahead come with a price (published for today and tomorrow, forecast after that) and
the site's expected own surplus power (solar and wind minus the base load). For one machine,
a start time costs: for each hour it runs, the part covered by surplus at the export price
(what that power would have earned) and the rest at the all-in import price.

Machines are placed one after another, largest first; each uses up the surplus it takes, so
two machines never count the same sunshine twice. app/ui/web/cockpit.html runs the same
search in the browser, so sliders react at once; tests/test_cockpit.py pins the rules.
"""

from dataclasses import dataclass


@dataclass
class Machine:
    name: str
    kw: float
    hours: int  # job length
    earliest: int  # earliest start, local hour
    latest_end: int  # must be done by, local hour (24 = midnight)
    usual_start: int  # when it runs today, for comparison


def job_cost(
    start: int, m: Machine, buy: list[float], sell: list[float], surplus: list[float]
) -> float:
    """Euros for running `m` from hour index `start` (prices in ct/kWh, surplus in kW)."""
    cost = 0.0
    for h in range(start, start + m.hours):
        own = min(m.kw, surplus[h])
        cost += (own * sell[h] + (m.kw - own) * buy[h]) / 100
    return cost


def starts(day_start: int, m: Machine, n_hours: int) -> range:
    """Allowed start indices on the day that begins at hour index `day_start`."""
    first = day_start + m.earliest
    last = min(day_start + m.latest_end - m.hours, n_hours - m.hours)
    return range(first, last + 1)


def best_start(day_start: int, m: Machine, buy, sell, surplus) -> tuple[int, float] | None:
    """Cheapest allowed start on that day and its cost, or None if the job does not fit."""
    options = [(s, job_cost(s, m, buy, sell, surplus)) for s in starts(day_start, m, len(buy))]
    return min(options, key=lambda x: x[1]) if options else None


def plan(machines: list[Machine], day_start: int, buy, sell, surplus) -> list[dict]:
    """Place every machine on one day, largest first. Each result: name, start, cost, the
    usual cost and the saving (index of hours relative to the horizon)."""
    left = list(surplus)
    out = []
    for m in sorted(machines, key=lambda m: -m.kw):
        found = best_start(day_start, m, buy, sell, left)
        if found is None:
            out.append({"name": m.name, "start": None})
            continue
        start, cost = found
        usual = day_start + m.usual_start
        usual_cost = job_cost(usual, m, buy, sell, left) if usual + m.hours <= len(buy) else None
        for h in range(start, start + m.hours):
            left[h] = max(0.0, left[h] - m.kw)
        out.append(
            {
                "name": m.name,
                "start": start,
                "cost": cost,
                "usual_cost": usual_cost,
                "saving": None if usual_cost is None else usual_cost - cost,
            }
        )
    return out
