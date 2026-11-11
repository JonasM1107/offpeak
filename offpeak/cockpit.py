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

import pandas as pd


@dataclass
class Machine:
    name: str
    kw: float
    hours: int  # job length
    earliest: int  # earliest start, local hour
    latest_end: int  # must be done by, local hour (24 = midnight)
    usual_start: int  # when it runs today, for comparison


MAX_MACHINES = 20


def _number(value, low: float, high: float, default: float) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return default if x != x else min(high, max(low, x))  # x != x: not a number


def clean_machines(raw) -> list[dict]:
    """Check a machine list sent back by the browser before it is saved: known fields only,
    numbers inside the slider ranges, and the job fitting between earliest start and done-by."""
    if not isinstance(raw, list):
        return []
    out = []
    for m in raw[:MAX_MACHINES]:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "").strip()[:60] or "Machine"
        hours = int(_number(m.get("hours"), 1, 12, 2))
        earliest = int(_number(m.get("earliest"), 0, 23, 0))
        latest_end = int(_number(m.get("latest_end"), 1, 24, 24))
        if earliest + hours > latest_end:  # same rule as the sliders
            latest_end = min(24, earliest + hours)
            earliest = latest_end - hours
        out.append(
            {
                "name": name,
                "kw": _number(m.get("kw"), 1, 100, 10),
                "hours": hours,
                "earliest": earliest,
                "latest_end": latest_end,
                "usual_start": int(_number(m.get("usual_start"), 0, 23, 8)),
            }
        )
    return out


def job_cost(
    start: int, m: Machine, buy: list[float], sell: list[float], surplus: list[float]
) -> float:
    """Euros for running `m` from hour index `start` (prices in ct/kWh, surplus in kW)."""
    cost = 0.0
    for h in range(start, start + m.hours):
        own = min(m.kw, surplus[h])
        cost += (own * sell[h] + (m.kw - own) * buy[h]) / 100
    return cost


def starts(day_start: int, m: Machine, n_hours: int, not_before: int = 0) -> range:
    """Allowed start indices on the day that begins at hour index `day_start`; never before
    `not_before` (the current hour), since a job cannot start in the past."""
    first = max(day_start + m.earliest, not_before)
    last = min(day_start + m.latest_end - m.hours, n_hours - m.hours)
    return range(first, last + 1)


def best_start(
    day_start: int, m: Machine, buy, sell, surplus, not_before: int = 0
) -> tuple[int, float] | None:
    """Cheapest allowed start on that day and its cost, or None if the job does not fit."""
    options = [
        (s, job_cost(s, m, buy, sell, surplus)) for s in starts(day_start, m, len(buy), not_before)
    ]
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


# ── The hours ahead, for the cockpit view ───────────────────────────────────


def horizon(
    published: pd.Series,
    forecast: pd.DataFrame,
    gen: pd.DataFrame,
    base_kw: float,
    tariff,
    tz: str,
    today,
    days: int = 7,
) -> dict:
    """Hour by hour from today 00:00 (local) for `days` days: all-in buy price and export
    price (ct/kWh), a likely range on forecast days, the site's surplus own power (kW) and
    whether the price is published or forecast.

    published: hourly spot ct/kWh by UTC hour; forecast: ts, p10, p50, p90 (spot ct/kWh);
    gen: ts, pv_kw, wind_kw (any resolution)."""

    from offpeak.forecast.outlook import local_day_hours
    from offpeak.tariffs import slot_prices

    day_list = [today + pd.Timedelta(days=i) for i in range(days)]
    hours = pd.DatetimeIndex([]).tz_localize("UTC")
    day_starts = []
    for d in day_list:
        day_starts.append(len(hours))
        hours = hours.append(local_day_hours(d, tz))

    fc = forecast.set_index("ts")
    spot = published.reindex(hours)
    kind = pd.Series("published", index=hours).where(spot.notna(), "forecast")
    p50 = spot.fillna(fc["p50"].reindex(hours))
    p10 = spot.fillna(fc["p10"].reindex(hours))
    p90 = spot.fillna(fc["p90"].reindex(hours))
    known = p50.notna()
    hours, p50, p10, p90, kind = hours[known], p50[known], p10[known], p90[known], kind[known]

    priced = slot_prices(pd.DataFrame({"ts": hours, "eur_mwh": p50.values * 10}), tariff)
    fees = priced["import_ct"].values - p50.values  # grid fees, levies and tax on top of spot
    g = gen.set_index("ts").resample("h").mean().reindex(hours)
    own = (g["pv_kw"].fillna(0) + g["wind_kw"].fillna(0)).values
    local = hours.tz_convert(tz)
    return {
        "t": ((hours - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).tolist(),
        "hour": local.hour.tolist(),
        "buy": (p50.values + fees).round(2).tolist(),
        "buy_lo": (p10.values + fees).round(2).tolist(),
        "buy_hi": (p90.values + fees).round(2).tolist(),
        "sell": priced["export_ct"].round(2).tolist(),
        "surplus": [round(max(0.0, x - base_kw), 2) for x in own],
        "kind": kind.tolist(),
        "days": [
            {"name": f"{pd.Timestamp(d):%a %-d %b}", "start": s}
            for d, s in zip(day_list, day_starts, strict=True)
            if s < len(hours)
        ],
    }
