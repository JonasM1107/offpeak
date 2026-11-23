"""The dashboard's answers: what to do now, what is next, and what it brings.

Everything here works on the hours ahead from offpeak.cockpit.horizon (all-in prices in
ct/kWh, published or estimated by Offpeak Intelligence, and the site's own surplus power) and
on the cockpit's week plan, so the dashboard, the cockpit and Ollie always agree.

"Cheap" and "expensive" are relative to the coming hours, because that is the choice a
business has: run now, or later today or tomorrow. The price range of the next 36 hours is
split in three: the lowest third is cheap, the highest third expensive. If prices hardly
move (less than 1 ct/kWh apart), every hour is normal.
"""

from offpeak.cockpit import Machine, week_plan, when

LOOK_AHEAD = 36  # hours the "now" judgement compares with
BLOCK = 3  # hours of the "next cheap window"


def thresholds(prices: list[float]) -> tuple[float, float]:
    """The prices at the top of the cheap third and the bottom of the expensive third."""
    lo, hi = min(prices), max(prices)
    if hi - lo < 1.0:
        return float("-inf"), float("inf")  # flat: nothing stands out
    return lo + (hi - lo) / 3, hi - (hi - lo) / 3


def limits_now(hours: dict, now_index: int) -> tuple[float, float]:
    """The two prices every page judges an hour by: at or below the first it is cheap, at or
    above the second expensive. They come from the next LOOK_AHEAD hours, so the dashboard's
    "right now", its price band and the site view's day all say the same about an hour."""
    return thresholds(hours["buy"][now_index : now_index + LOOK_AHEAD])


def _level(price: float, low: float, high: float) -> str:
    return "cheap" if price <= low else "expensive" if price >= high else "normal"


def status_now(hours: dict, now_index: int) -> dict:
    """Is power cheap right now, for how long, and when is the next cheap window?"""
    buy = hours["buy"]
    ahead = buy[now_index : now_index + LOOK_AHEAD]
    low, high = limits_now(hours, now_index)
    price = buy[now_index]
    level = _level(price, low, high)
    end = now_index
    while end + 1 < len(buy) and end + 1 < now_index + LOOK_AHEAD:
        if _level(buy[end + 1], low, high) != level:
            break
        end += 1
    starts = range(now_index, min(len(buy), now_index + LOOK_AHEAD) - BLOCK + 1)
    best = min(starts, key=lambda s: sum(buy[s : s + BLOCK])) if len(starts) else now_index
    return {
        "price_ct": round(price, 1),
        "level": level,
        "low_ct": round(min(ahead), 1),
        "high_ct": round(max(ahead), 1),
        "until": f"{(hours['hour'][end] + 1) % 24:02d}:00",
        "until_t": hours["t"][end] + 3600,
        "next_cheap": when(hours, best, BLOCK),
        "next_cheap_t": hours["t"][best],
        "next_cheap_ct": round(sum(buy[best : best + BLOCK]) / BLOCK, 1),
        "estimate": hours["kind"][now_index] != "published",
    }


def actions(hours: dict, machines: list[dict], now_index: int) -> list[dict]:
    """Each machine's next best run, soonest first, with start and end as unix seconds."""
    fleet = [Machine(**m) for m in machines]
    out = []
    for m, p in zip(fleet, week_plan(hours, fleet, now_index), strict=True):
        if p["start"] is None:
            continue
        out.append(
            {
                "name": m.name,
                "kw": m.kw,
                "when": when(hours, p["start"], m.hours),
                "start_t": hours["t"][p["start"]],
                "end_t": hours["t"][p["end"] - 1] + 3600,
                "cost_eur": round(p["cost"], 2),
                "saving_eur": round(max(0.0, p["saving"] or 0.0), 2),
                "usual": None
                if p["usual_start"] is None
                else when(hours, p["usual_start"], m.hours),
                "estimate": p["forecast"],
            }
        )
    return sorted(out, key=lambda a: a["start_t"])


def ribbon(hours: dict, now_index: int) -> dict:
    """The next 36 hours for the price band: time, all-in price, cheap/normal/expensive,
    own surplus, and whether the price is published or an estimate."""
    end = min(len(hours["buy"]), now_index + LOOK_AHEAD)
    low, high = limits_now(hours, now_index)
    idx = range(now_index, end)
    return {
        "t": [hours["t"][i] for i in idx],
        "ct": [round(hours["buy"][i], 2) for i in idx],
        "level": [_level(hours["buy"][i], low, high) for i in idx],
        "surplus": [hours["surplus"][i] for i in idx],
        "estimate": [hours["kind"][i] != "published" for i in idx],
    }


def payload(hours: dict, now_index: int, machines: list[dict], saved: dict | None) -> dict:
    """Everything the dashboard view draws. `saved` is the savings replay summary of the last
    30 days (offpeak.savings.summary), or None while it is still being computed."""
    todo = actions(hours, machines, now_index)
    week = sum(a["saving_eur"] for a in todo)
    band = ribbon(hours, now_index)
    # the flex slider: what a kWh moved from an average hour to the cheapest window saves
    avg = sum(band["ct"]) / len(band["ct"])
    now = status_now(hours, now_index)
    return {
        "now": now,
        "actions": todo,
        "week_saving_eur": round(week, 2),
        "month_saving_eur": round(week * 30 / 7, 2),
        "saved": saved,
        "ribbon": band,
        "shift_ct_per_kwh": round(max(0.0, avg - now["next_cheap_ct"]), 2),
        "weather_missing": bool(hours.get("weather_missing")),
    }
