"""What the Offpeak plan would have saved: replay past days with their real prices and the
weather that actually happened.

For each day the site (its components) runs twice through the energy model, once with every
machine at its usual time and once with the plan, both priced with the tariff (all-in prices
and the demand charge). The saving is the difference of the two bills.

Assumption, said openly on the page: the replay plans with the day's real weather, as if the
forecast had been perfect, so savings come out a little better than in real use.
"""

import pandas as pd

from offpeak import components as comp
from offpeak.demo_site import apply_tariff, hourly_inputs


def replay_day(day, prices: pd.DataFrame, weather: pd.DataFrame, comps, tariff, tz: str) -> dict:
    """One past day: both bills, the saving, and per flexible machine its usual and planned
    run hours and its own saving."""
    assets, _ = comp.site_model(comps)
    inputs = apply_tariff(hourly_inputs(prices, weather, tz, assets), tariff, day)
    result = comp.site_day(inputs, comps, tariff)
    bill = result["bill"]
    devices = []
    for c in result["components"]:
        if c["role"] not in ("flexible", "storage"):
            continue
        a = c["analytics"]
        if c["role"] == "flexible":
            saving = a["usual"]["cost_eur"] - a["offpeak"]["cost_eur"]
        else:  # the battery: what its smarter use is worth
            saving = a["offpeak"]["value_eur"] - a["usual"]["value_eur"]
        devices.append(
            {
                "id": c["id"],
                "name": c["name"],
                "role": c["role"],
                "saving_eur": round(saving, 2),
                "usual": c["advice"].get("usual", ""),
                "plan": c["advice"].get("best", ""),
                "offpeak_kw": result["series"]["offpeak"][c["id"]],
                "usual_kw": result["series"]["usual"][c["id"]],
            }
        )
    rows = result["rows"]["offpeak"]
    gen = sum(r["pv_kw"] + r["wind_kw"] for r in rows)
    used = sum(min(r["pv_kw"] + r["wind_kw"], r["load_kw"] + max(r["battery_kw"], 0)) for r in rows)
    return {
        "date": str(day),
        "usual_eur": round(bill["usual"]["total"], 2),
        "plan_eur": round(bill["offpeak"]["total"], 2),
        "saving_eur": round(bill["usual"]["total"] - bill["offpeak"]["total"], 2),
        "own_pct": round(used / gen * 100) if gen else 0,
        "price_ct": [round(r.get("import_ct", r["price_ct"]), 2) for r in rows],
        "spot_ct": [round(r["price_ct"], 2) for r in rows],
        "devices": devices,
    }


def replay(prices: pd.DataFrame, weather: pd.DataFrame, comps, tariff, tz: str, days) -> list[dict]:
    """Replay every given day that has a full day of prices."""
    local = prices["ts"].dt.tz_convert(tz).dt.date
    wlocal = weather["ts"].dt.tz_convert(tz).dt.date
    out = []
    for day in days:
        p = prices[local == day]
        w = weather[wlocal == day]
        if p.empty or (p["resolution_min"] / 60).sum() < 23:
            continue
        if w.empty or w["gti_wm2"].isna().mean() > 0.5:
            continue  # no measured weather for this day: skip it rather than guess
        out.append(replay_day(day, p, w, comps, tariff, tz))
    return out


def summary(days: list[dict]) -> dict:
    """Totals over the replayed days."""
    if not days:
        return {"days": 0, "saving_eur": 0.0, "usual_eur": 0.0, "plan_eur": 0.0, "share_pct": 0.0}
    saving = sum(d["saving_eur"] for d in days)
    usual = sum(d["usual_eur"] for d in days)
    best = max(days, key=lambda d: d["saving_eur"])
    by_device: dict[str, float] = {}
    for d in days:
        for dev in d["devices"]:
            by_device[dev["name"]] = by_device.get(dev["name"], 0.0) + dev["saving_eur"]
    return {
        "days": len(days),
        "saving_eur": round(saving, 2),
        "usual_eur": round(usual, 2),
        "plan_eur": round(sum(d["plan_eur"] for d in days), 2),
        "share_pct": round(saving / usual * 100, 1) if usual else 0.0,
        "per_day_eur": round(saving / len(days), 2),
        "best_day": best["date"],
        "best_day_eur": best["saving_eur"],
        "by_device": {k: round(v, 2) for k, v in sorted(by_device.items(), key=lambda x: -x[1])},
    }
