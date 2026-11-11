"""Hour-by-hour energy model of the demo site, used by the 3D site view.

The site has rooftop and field solar, two small wind turbines, a battery, a production hall
with an electric furnace, a cold store and an EV fleet. Real prices and the real weather
forecast are used when available; otherwise smooth demo curves stand in.

The "Offpeak" plan tries every allowed start time for each flexible load and keeps the
cheapest, and decides whether the battery should also cover expensive hours. It never costs
more than the usual pattern, because the usual pattern is one of the options it compares.
The real optimiser (docs/PLAN.md section 9.2) replaces this later.
"""

import math
from dataclasses import dataclass

import pandas as pd

HOURS = range(24)
EXPORT_EUR_KWH = 0.08  # what exported power earns


@dataclass(frozen=True)
class Assets:
    pv_kwp: float = 60.0
    turbines: int = 2
    turbine_kw: float = 15.0
    battery_kwh: float = 120.0
    battery_kw: float = 20.0
    cold_store_kw: float = 15.0


@dataclass(frozen=True)
class FlexLoad:
    key: str
    kw: float
    hours: int  # how long it runs
    usual_start: int
    earliest: int  # earliest start hour
    latest_end: int  # must be done by this hour


Windows = dict[str, int]  # load key -> start hour


@dataclass(frozen=True)
class Plan:
    starts: Windows
    smart_battery: bool  # battery also covers hours above the day's median price


ASSETS = Assets()
FLEX_LOADS = (
    FlexLoad("furnace", 40.0, hours=8, usual_start=6, earliest=5, latest_end=21),
    FlexLoad("ev", 30.0, hours=5, usual_start=17, earliest=7, latest_end=24),
)
USUAL = Plan({f.key: f.usual_start for f in FLEX_LOADS}, smart_battery=False)


def demo_price_ct(hour: int, pv_kw: float) -> float:
    """Typical day shape: morning and evening peaks, cheaper when the sun shines."""
    morning = 14 * math.exp(-((hour - 8) ** 2) / 4)
    evening = 18 * math.exp(-((hour - 19) ** 2) / 5)
    return 24 + morning + evening - 0.18 * pv_kw


def demo_pv_kw(hour: int, assets: Assets = ASSETS) -> float:
    return max(0.0, assets.pv_kwp * math.sin(math.pi * (hour - 6) / 13))


def demo_wind_kw(hour: int, assets: Assets = ASSETS) -> float:
    return assets.turbines * assets.turbine_kw * (0.5 + 0.33 * math.sin(hour / 3))


def turbine_kw(wind_ms: float, rated_kw: float) -> float:
    """Generic small-turbine power curve: starts at 3 m/s, full power from 12 m/s."""
    if wind_ms < 3 or wind_ms > 25:
        return 0.0
    return rated_kw * min(1.0, ((wind_ms - 3) / 9) ** 3)


def hourly_inputs(
    prices: pd.DataFrame | None,
    weather: pd.DataFrame | None,
    tz: str,
    assets: Assets = ASSETS,
) -> pd.DataFrame:
    """One row per local hour: price (ct/kWh), solar and wind output (kW), and which are real.

    `prices` needs ts (UTC) and eur_mwh for one market day; `weather` needs ts, gti_wm2 and
    wind_ms. Hours missing from either fall back to the demo curves.
    """
    out = pd.DataFrame({"hour": list(HOURS)})
    out["pv_kw"] = [demo_pv_kw(h, assets) for h in HOURS]
    out["wind_kw"] = [demo_wind_kw(h, assets) for h in HOURS]
    out["weather_real"] = False
    if weather is not None and not weather.empty:
        w = weather.assign(hour=weather["ts"].dt.tz_convert(tz).dt.hour)
        w = w[
            weather["ts"].dt.tz_convert(tz).dt.date == weather["ts"].dt.tz_convert(tz).dt.date.min()
        ]
        by_hour = w.groupby("hour").agg(gti=("gti_wm2", "mean"), wind=("wind_ms", "mean"))
        real = out["hour"].isin(by_hour.index)
        hours = out.loc[real, "hour"]
        # 0.85 covers inverter, wiring and temperature losses
        out.loc[real, "pv_kw"] = (
            by_hour.loc[hours, "gti"].fillna(0) / 1000 * assets.pv_kwp * 0.85
        ).values
        # forecast wind is at 10 m; the hub sits higher, where it blows roughly 30 % harder
        out.loc[real, "wind_kw"] = [
            assets.turbines * turbine_kw(v * 1.3, assets.turbine_kw)
            for v in by_hour.loc[hours, "wind"].fillna(0)
        ]
        out.loc[real, "weather_real"] = True
    out["price_ct"] = [
        demo_price_ct(h, pv) for h, pv in zip(out["hour"], out["pv_kw"], strict=True)
    ]
    out["price_real"] = False
    if prices is not None and not prices.empty:
        p = (
            prices.assign(hour=prices["ts"].dt.tz_convert(tz).dt.hour)
            .groupby("hour")["eur_mwh"]
            .mean()
        )
        real = out["hour"].isin(p.index)
        out.loc[real, "price_ct"] = (p.loc[out.loc[real, "hour"]] / 10).values
        out.loc[real, "price_real"] = True
    return out


def simulate(
    inputs: pd.DataFrame,
    plan: Plan,
    assets: Assets = ASSETS,
    loads: tuple[FlexLoad, ...] = FLEX_LOADS,
) -> pd.DataFrame:
    """Run the site through one day. Positive battery_kw charges, positive grid_kw buys.

    The battery always stores surplus own power; with smart_battery it also discharges in
    hours priced above the day's median. Energy balance every hour:
    pv + wind + grid = cold + every flexible load + battery. Each flexible load gets a column
    named after its key, e.g. furnace_kw.
    """
    median_price = inputs["price_ct"].median()
    soc_kwh = assets.battery_kwh / 2
    rows = []
    for r in inputs.itertuples():
        running = {
            f.key: f.kw if plan.starts[f.key] <= r.hour < plan.starts[f.key] + f.hours else 0.0
            for f in loads
        }
        load = assets.cold_store_kw + sum(running.values())
        gen = r.pv_kw + r.wind_kw
        battery = 0.0
        if gen > load:
            battery = min(gen - load, assets.battery_kw, assets.battery_kwh - soc_kwh)
        elif plan.smart_battery and r.price_ct > median_price:
            battery = -min(load - gen, assets.battery_kw, soc_kwh)
        soc_kwh += battery
        grid = load - gen + battery
        cost = grid * r.price_ct / 100 if grid > 0 else grid * EXPORT_EUR_KWH
        rows.append(
            {
                "hour": r.hour,
                "price_ct": r.price_ct,
                "pv_kw": r.pv_kw,
                "wind_kw": r.wind_kw,
                "cold_kw": assets.cold_store_kw,
                **{f"{key}_kw": kw for key, kw in running.items()},
                "load_kw": load,
                "battery_kw": battery,
                "soc_pct": soc_kwh / assets.battery_kwh * 100 if assets.battery_kwh else 0.0,
                "grid_kw": grid,
                "cost_eur": cost,
            }
        )
    return pd.DataFrame(rows)


def usual_plan(loads: tuple[FlexLoad, ...] = FLEX_LOADS) -> Plan:
    """Every load at the time it usually runs, battery only stores surplus."""
    return Plan({f.key: f.usual_start for f in loads}, smart_battery=False)


def cost(
    inputs: pd.DataFrame,
    plan: Plan,
    assets: Assets = ASSETS,
    loads: tuple[FlexLoad, ...] = FLEX_LOADS,
) -> float:
    return float(simulate(inputs, plan, assets, loads)["cost_eur"].sum())


def plan_day(
    inputs: pd.DataFrame,
    assets: Assets = ASSETS,
    loads: tuple[FlexLoad, ...] = FLEX_LOADS,
) -> Plan:
    """Cheapest plan found: for each load (largest first) try every allowed start."""
    usual = usual_plan(loads)
    best = usual
    for smart in (False, True):
        starts = dict(usual.starts)
        for f in sorted(loads, key=lambda f: -f.kw):
            options = range(f.earliest, f.latest_end - f.hours + 1)
            starts[f.key] = min(
                options,
                key=lambda s: cost(inputs, Plan({**starts, f.key: s}, smart), assets, loads),
            )
        candidate = Plan(starts, smart)
        if cost(inputs, candidate, assets, loads) < cost(inputs, best, assets, loads):
            best = candidate
    return best


def windows(plan: Plan, loads: tuple[FlexLoad, ...] = FLEX_LOADS) -> dict[str, str]:
    """Run times per flexible load as text, e.g. {'furnace': '09–17'}."""
    return {f.key: f"{plan.starts[f.key]:02d}–{plan.starts[f.key] + f.hours:02d}" for f in loads}
