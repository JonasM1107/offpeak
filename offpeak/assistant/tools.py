"""What Ollie can look up: plain Python functions over the app's own data.

The language model never computes prices or times itself. It asks for them through these
tools, and every number in its answer comes from here: the hours ahead from
offpeak.cockpit.horizon (published prices, then the Offpeak Intelligence outlook, plus the
site's own solar and wind surplus) and the cockpit's planning rules.

Everything the model sends is checked before use, like any other user input: unknown days,
hours out of range or a job longer than its window give a clear error back to the model,
which then tells the person or asks.
"""

import json
from dataclasses import dataclass
from datetime import date

from offpeak.cockpit import Machine, describe_plan, job_cost, starts, week_plan, when


@dataclass
class Context:
    hours: dict  # offpeak.cockpit.horizon(): buy/sell ct/kWh, surplus kW, kind, days, ...
    now_index: int  # index of the current hour in `hours`
    machines: list[dict]  # the cockpit machines (name, kw, hours, earliest, latest_end, ...)
    site: list[dict]  # the site's components: name, kind, params
    today: date


class ToolError(ValueError):
    """Invalid arguments from the model; the message goes back to it."""


# ── Helpers ──────────────────────────────────────────────────────────────────


def known_days(ctx: Context) -> list[dict]:
    """The days of the horizon with their date, first hour index and end index."""
    out = []
    starts_ = [d["start"] for d in ctx.hours["days"]] + [len(ctx.hours["buy"])]
    for i, d in enumerate(ctx.hours["days"]):
        out.append(
            {
                "name": d["name"],
                "date": date.fromordinal(ctx.today.toordinal() + i),
                "start": d["start"],
                "end": starts_[i + 1],
            }
        )
    return out


def _day(ctx: Context, value) -> dict:
    """The horizon day for an ISO date string."""
    try:
        wanted = date.fromisoformat(str(value))
    except ValueError as err:
        raise ToolError(f"'{value}' is not a date like 2026-11-14") from err
    for d in known_days(ctx):
        if d["date"] == wanted:
            return d
    known = ", ".join(f"{d['date']} ({d['name']})" for d in known_days(ctx))
    raise ToolError(f"No prices for {wanted}. Known days: {known}")


def _int(args: dict, key: str, low: int, high: int, default=None) -> int:
    value = args.get(key, default)
    if value is None:
        raise ToolError(f"'{key}' is missing")
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError) as err:
        raise ToolError(f"'{key}' must be a whole number") from err
    if not low <= number <= high:
        raise ToolError(f"'{key}' must be between {low} and {high}")
    return number


def _machine(ctx: Context, name) -> dict | None:
    if not name:
        return None
    wanted = str(name).lower().strip()
    for m in ctx.machines:
        if wanted in m["name"].lower() or m["name"].lower() in wanted:
            return m
    return None


def _source(ctx: Context, start: int, length: int) -> str:
    kinds = ctx.hours["kind"][start : start + length]
    return "Offpeak Intelligence estimate" if "forecast" in kinds else "published prices"


def _eur(x: float) -> float:
    return round(x, 2)


# ── The tools ────────────────────────────────────────────────────────────────


def find_best_time(ctx: Context, args: dict) -> dict:
    """Cheapest start for one job: on one day or across all known days, inside a time window
    (local hours), with its cost, the alternatives and how much it saves."""
    m = _machine(ctx, args.get("machine"))
    kw = args.get("power_kw")
    if kw is None and m is None:
        names = ", ".join(x["name"] for x in ctx.machines) or "none"
        raise ToolError(f"Unknown power. Give power_kw, or one of the site's machines: {names}")
    try:
        kw = float(kw) if kw is not None else float(m["kw"])
    except (TypeError, ValueError) as err:
        raise ToolError("'power_kw' must be a number") from err
    if not 0 < kw <= 2000:
        raise ToolError("'power_kw' must be between 0 and 2000")
    length = _int(args, "duration_hours", 1, 24, m["hours"] if m else None)
    earliest = _int(args, "earliest_start", 0, 23, 0)
    finish_by = _int(args, "finish_by", 1, 24, 24)
    if earliest + length > finish_by:
        raise ToolError(
            f"A {length} h job cannot start at {earliest}:00 or later and end by {finish_by}:00"
        )
    days = [_day(ctx, args["day"])] if args.get("day") else known_days(ctx)
    job = Machine(m["name"] if m else "job", kw, length, earliest, finish_by, earliest)
    h = ctx.hours
    options = [
        (job_cost(s, job, h["buy"], h["sell"], h["surplus"]), s)
        for d in days
        for s in starts(d["start"], job, len(h["buy"]), not_before=ctx.now_index)
    ]
    if not options:
        raise ToolError("No start left in that window (it may already have passed).")
    options.sort()
    cost, best = options[0]
    worst_cost, worst = options[-1]
    own = sum(min(kw, h["surplus"][i]) for i in range(best, best + length)) / (kw * length)
    lo = job_cost(best, job, h["buy_lo"], h["sell"], h["surplus"])
    hi = job_cost(best, job, h["buy_hi"], h["sell"], h["surplus"])
    result = {
        "machine": m["name"] if m else None,
        "power_kw": kw,
        "best": when(h, best, length),
        "cost_eur": _eur(cost),
        "likely_cost_range_eur": [_eur(min(lo, hi)), _eur(max(lo, hi))],
        "average_price_ct_kwh": round(sum(h["buy"][best : best + length]) / length, 1),
        "own_solar_wind_share_pct": round(own * 100),
        "prices_from": _source(ctx, best, length),
        "most_expensive_in_window": when(h, worst, length),
        "saving_vs_most_expensive_eur": _eur(worst_cost - cost),
        "alternatives": [
            {"when": when(h, s, length), "cost_eur": _eur(c)} for c, s in options[1:4]
        ],
    }
    if m is not None:  # compare with the machine's usual start on the same day
        day_start = next(d["start"] for d in known_days(ctx) if d["start"] <= best < d["end"])
        usual = day_start + m["usual_start"]
        if usual >= ctx.now_index and usual + length <= len(h["buy"]):
            usual_cost = job_cost(usual, job, h["buy"], h["sell"], h["surplus"])
            result["usual_start"] = when(h, usual, length)
            result["saving_vs_usual_eur"] = _eur(usual_cost - cost)
    return result


def day_prices(ctx: Context, args: dict) -> dict:
    """One day hour by hour: all-in price (ct/kWh) and own surplus (kW), plus a summary."""
    d = _day(ctx, args.get("day"))
    h = ctx.hours
    idx = range(d["start"], d["end"])
    hours = [
        {
            "hour": f"{h['hour'][i]:02d}:00",
            "price_ct_kwh": h["buy"][i],
            "own_surplus_kw": h["surplus"][i],
            "from": "published" if h["kind"][i] == "published" else "estimate",
        }
        for i in idx
    ]
    cheap = min(idx, key=lambda i: h["buy"][i])
    dear = max(idx, key=lambda i: h["buy"][i])
    window = min(
        (i for i in idx if i + 3 <= d["end"]),
        key=lambda i: sum(h["buy"][i : i + 3]),
        default=None,
    )
    return {
        "day": d["name"],
        "prices_from": _source(ctx, d["start"], d["end"] - d["start"]),
        "average_ct_kwh": round(sum(h["buy"][i] for i in idx) / len(idx), 1),
        "cheapest_hour": f"{h['hour'][cheap]:02d}:00 ({h['buy'][cheap]} ct/kWh)",
        "dearest_hour": f"{h['hour'][dear]:02d}:00 ({h['buy'][dear]} ct/kWh)",
        "cheapest_3_hours": when(h, window, 3) if window is not None else None,
        "own_surplus_kwh": round(sum(h["surplus"][i] for i in idx), 1),
        "hours": hours,
    }


def week_overview(ctx: Context, args: dict) -> dict:
    """Every known day in one line: average price, cheapest 3 hours, own surplus."""
    out = []
    for d in known_days(ctx):
        p = day_prices(ctx, {"day": d["date"].isoformat()})
        out.append({k: v for k, v in p.items() if k != "hours"} | {"date": str(d["date"])})
    return {"days": out}


def plan_week(ctx: Context, args: dict) -> dict:
    """The site's machines, each at its best time in the coming days, with the saving."""
    if not ctx.machines:
        return {"machines": [], "note": "No machines are set up in the Simulation cockpit."}
    fleet = [Machine(**m) for m in ctx.machines]
    plan = describe_plan(ctx.hours, week_plan(ctx.hours, fleet, ctx.now_index), fleet)
    return {
        "machines": [
            {k: (_eur(v) if isinstance(v, float) else v) for k, v in row.items()}
            for row in plan["rows"]
        ],
        "total_saving_eur": _eur(plan["total"]),
    }


def site_info(ctx: Context, args: dict) -> dict:
    """The site's components and the machines the planner knows."""
    return {"components": ctx.site, "machines": ctx.machines}


TOOLS = {
    "find_best_time": find_best_time,
    "day_prices": day_prices,
    "week_overview": week_overview,
    "plan_week": plan_week,
    "site_info": site_info,
}

_DAY = {"type": "string", "description": "Date as YYYY-MM-DD"}
SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "find_best_time",
            "description": (
                "Cheapest time to run a device or job: on one day (day) or across all known "
                "days (leave day out). Window in local hours. Use machine for a device of "
                "the site (its power is known), or power_kw for anything else."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "machine": {"type": "string", "description": "e.g. Heat pump"},
                    "power_kw": {"type": "number", "description": "Power in kW"},
                    "duration_hours": {"type": "integer", "description": "Job length, h"},
                    "day": _DAY,
                    "earliest_start": {"type": "integer", "description": "0-23, default 0"},
                    "finish_by": {"type": "integer", "description": "1-24, default 24"},
                },
                "required": ["duration_hours"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "day_prices",
            "description": "One day hour by hour: all-in price and own solar/wind surplus.",
            "parameters": {
                "type": "object",
                "properties": {"day": _DAY},
                "required": ["day"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "week_overview",
            "description": "All known days: average price, cheapest 3 hours, own surplus.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_week",
            "description": "Best time this week for every machine of the site, and savings.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "site_info",
            "description": "The site's components (solar, wind, battery, ...) and machines.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_tool(ctx: Context, name: str, arguments: str | dict | None) -> dict:
    """Run one tool call from the model; errors come back as {"error": ...}, never raise."""
    if name not in TOOLS:
        return {"error": f"Unknown tool {name}"}
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
    except (TypeError, ValueError):
        return {"error": "Arguments must be a JSON object"}
    if not isinstance(args, dict):
        return {"error": "Arguments must be a JSON object"}
    try:
        return TOOLS[name](ctx, args)
    except ToolError as err:
        return {"error": str(err)}
