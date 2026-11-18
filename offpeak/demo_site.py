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
from datetime import date

import pandas as pd

from offpeak.generation.pv import pv_kw
from offpeak.tariffs import Tariff, bill, slot_prices

HOURS = range(24)
EXPORT_EUR_KWH = 0.08  # what exported power earns when no tariff is applied


@dataclass(frozen=True)
class Assets:
    pv_kwp: float = 60.0
    turbines: int = 2
    turbine_kw: float = 15.0
    battery_kwh: float = 120.0
    battery_kw: float = 20.0
    cold_store_kw: float = 15.0  # the load that runs around the clock (a home: its base load)
    # how that load varies over the day: 24 factors with a mean of 1, or None for flat
    base_shape: tuple[float, ...] | None = None


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
    wind_ms, and temp_c if it has it (the solar model then knows how warm the panels get).
    Hours missing from either fall back to the demo curves.
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
        if "temp_c" not in w:
            w = w.assign(temp_c=float("nan"))  # pv_kw then takes the panels to be at 25 °C
        by_hour = w.groupby("hour").agg(
            gti=("gti_wm2", "mean"), wind=("wind_ms", "mean"), temp=("temp_c", "mean")
        )
        real = out["hour"].isin(by_hour.index)
        hours = out.loc[real, "hour"]
        sel = by_hour.loc[hours]
        temp = None if sel["temp"].isna().all() else sel["temp"]
        out.loc[real, "pv_kw"] = pv_kw(sel["gti"], assets.pv_kwp, temp, sel["wind"]).values
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
    buy_ct = inputs["import_ct"] if "import_ct" in inputs else inputs["price_ct"]
    sell_ct = inputs["export_ct"] if "export_ct" in inputs else EXPORT_EUR_KWH * 100
    median_price = buy_ct.median()
    soc_kwh = assets.battery_kwh / 2
    rows = []
    for r, buy, sell in zip(
        inputs.itertuples(), buy_ct, pd.Series(sell_ct, index=inputs.index), strict=True
    ):
        running = {
            f.key: f.kw if plan.starts[f.key] <= r.hour < plan.starts[f.key] + f.hours else 0.0
            for f in loads
        }
        base = assets.cold_store_kw * (assets.base_shape[r.hour] if assets.base_shape else 1.0)
        load = base + sum(running.values())
        gen = r.pv_kw + r.wind_kw
        battery = 0.0
        if gen > load:
            battery = min(gen - load, assets.battery_kw, assets.battery_kwh - soc_kwh)
        elif plan.smart_battery and buy > median_price:
            battery = -min(load - gen, assets.battery_kw, soc_kwh)
        soc_kwh += battery
        grid = load - gen + battery
        cost = grid * (buy if grid > 0 else sell) / 100
        rows.append(
            {
                "hour": r.hour,
                "price_ct": r.price_ct,
                "pv_kw": r.pv_kw,
                "wind_kw": r.wind_kw,
                "cold_kw": base,
                **{f"{key}_kw": kw for key, kw in running.items()},
                "load_kw": load,
                "battery_kw": battery,
                "soc_pct": soc_kwh / assets.battery_kwh * 100 if assets.battery_kwh else 0.0,
                "grid_kw": grid,
                "cost_eur": cost,
            }
        )
    return pd.DataFrame(rows)


def apply_tariff(inputs: pd.DataFrame, tariff: Tariff, day: date) -> pd.DataFrame:
    """Add what each hour really costs: the spot price becomes the all-in import price
    (energy, grid fees, levies, tax) and the export price, per the tariff."""
    ts = pd.date_range(pd.Timestamp(day, tz=tariff.tz), periods=len(inputs), freq="h")
    prices = pd.DataFrame({"ts": ts.tz_convert("UTC"), "eur_mwh": inputs["price_ct"] * 10})
    priced = slot_prices(prices, tariff)
    out = inputs.copy()
    for col in [
        "ts",
        "period",
        "energy_ct",
        "grid_ct",
        "levies_ct",
        "tax_ct",
        "import_ct",
        "export_ct",
    ]:
        out[col] = priced[col].set_axis(out.index)
    return out


def day_bill(
    inputs: pd.DataFrame,
    plan: Plan,
    tariff: Tariff,
    assets: Assets = ASSETS,
    loads: tuple[FlexLoad, ...] = FLEX_LOADS,
):
    """The day's bill under a tariff, including the demand charge for the day's peak."""
    day = simulate(inputs, plan, assets, loads)
    return bill(day["grid_kw"], inputs.reset_index(drop=True), tariff)


def usual_plan(loads: tuple[FlexLoad, ...] = FLEX_LOADS) -> Plan:
    """Every load at the time it usually runs, battery only stores surplus."""
    return Plan({f.key: f.usual_start for f in loads}, smart_battery=False)


def cost(
    inputs: pd.DataFrame,
    plan: Plan,
    tariff: Tariff | None = None,
    assets: Assets = ASSETS,
    loads: tuple[FlexLoad, ...] = FLEX_LOADS,
) -> float:
    if tariff is not None:
        return day_bill(inputs, plan, tariff, assets, loads).total
    return float(simulate(inputs, plan, assets, loads)["cost_eur"].sum())


class QuickCost:
    """cost() for many plans of the same day, fast.

    plan_day() prices about 90 plans per day, and the Savings page replays 30 or 90 days.
    cost() builds a pandas table per plan (simulate) and adds up the bill with pandas
    (tariffs.bill); for 24 rows pandas spends nearly all its time on bookkeeping, about
    7 ms per plan. Here everything that is the same for every plan (prices, own power,
    the tariff's ct per kWh) is read out of the tables once, and each plan is then worked
    out with plain Python numbers: the same steps as simulate() and bill(), in the same
    order, about 50 times faster. tests/test_quick_cost.py checks that both give the same
    euros for every plan plan_day tries."""

    def __init__(self, inputs, tariff, assets, loads):
        self.assets, self.loads, self.tariff = assets, loads, tariff
        buy_ct = inputs["import_ct"] if "import_ct" in inputs else inputs["price_ct"]
        sell_ct = inputs["export_ct"] if "export_ct" in inputs else EXPORT_EUR_KWH * 100
        self.median = buy_ct.median()  # pandas' median, exactly as simulate() takes it
        self.buy = buy_ct.tolist()
        self.sell = pd.Series(sell_ct, index=inputs.index).tolist()
        self.hour = inputs["hour"].tolist()
        self.gen = [p + w for p, w in zip(inputs["pv_kw"], inputs["wind_kw"], strict=True)]
        shape = assets.base_shape
        self.base = [assets.cold_store_kw * (shape[h] if shape else 1.0) for h in self.hour]
        if tariff is not None:  # what bill() reads from the price table, read once
            from offpeak.tariffs.engine import slot_hours
            from offpeak.tariffs.model import GROUPS

            prices = inputs.reset_index(drop=True)
            self.slot_h = slot_hours(prices["ts"])
            self.days = len(prices) * self.slot_h / 24
            self.group_ct = [prices[f"{g}_ct"].tolist() for g in GROUPS]
            self.export_ct = prices["export_ct"].tolist()
            self.period = prices["period"].tolist()
            self.vat = 1 + tariff.vat if tariff.gross else 1.0
            self.fixed = sum(f.eur_year for f in tariff.fixed) * self.days / 365 * self.vat

    def grid(self, plan: Plan) -> list[float]:
        """grid_kw per hour, step by step as in simulate()."""
        a = self.assets
        soc_kwh = a.battery_kwh / 2
        out = []
        for i, h in enumerate(self.hour):
            load = self.base[i] + sum(
                f.kw if plan.starts[f.key] <= h < plan.starts[f.key] + f.hours else 0.0
                for f in self.loads
            )
            gen = self.gen[i]
            battery = 0.0
            if gen > load:
                battery = min(gen - load, a.battery_kw, a.battery_kwh - soc_kwh)
            elif plan.smart_battery and self.buy[i] > self.median:
                battery = -min(load - gen, a.battery_kw, soc_kwh)
            soc_kwh += battery
            out.append(load - gen + battery)
        return out

    def __call__(self, plan: Plan) -> float:
        grid = self.grid(plan)
        if self.tariff is None:  # simulate()'s cost_eur, summed
            return sum(
                g * (b if g > 0 else s) / 100
                for g, b, s in zip(grid, self.buy, self.sell, strict=True)
            )
        # bill(): energy, grid, levies and tax per bought kWh, demand charges, fixed
        # charges, minus what exported kWh earn
        bought = [max(g, 0.0) for g in grid]
        sold = [max(-g, 0.0) for g in grid]
        total = sum(
            sum(b * self.slot_h * ct for b, ct in zip(bought, cts, strict=True)) / 100
            for cts in self.group_ct
        )
        demand = 0.0
        for d in self.tariff.demand:
            if d.basis == "peak":
                kw = max(bought) if bought else 0.0
            elif d.basis.startswith("period:"):
                name = d.basis.split(":", 1)[1]
                inside = [b for b, p in zip(bought, self.period, strict=True) if p == name]
                kw = sum(inside) / len(inside) if inside else 0.0
            else:
                raise ValueError(f"unknown demand basis {d.basis!r}")
            demand += max(kw, 0.0) * d.eur_per_kw_year * self.days / 365
        total += demand * self.vat + self.fixed
        total -= sum(s * self.slot_h * ct for s, ct in zip(sold, self.export_ct, strict=True)) / 100
        return total


def plan_day(
    inputs: pd.DataFrame,
    tariff: Tariff | None = None,
    assets: Assets = ASSETS,
    loads: tuple[FlexLoad, ...] = FLEX_LOADS,
) -> Plan:
    """Cheapest plan found: for each load (largest first) try every allowed start.

    With a tariff the comparison uses the full bill, so a start time that stacks two
    machines into a new peak pays for it through the demand charge.
    """
    usual = usual_plan(loads)
    best = usual

    quick = QuickCost(inputs, tariff, assets, loads)  # same euros as cost(), much faster

    def price(p: Plan) -> float:
        # rounded to a millionth of a cent: two starts that cost the same must stay equal,
        # whatever order the sums were added in, so the earlier start keeps winning
        return round(quick(p), 8)

    for smart in (False, True):
        starts = dict(usual.starts)
        for f in sorted(loads, key=lambda f: -f.kw):
            options = range(f.earliest, f.latest_end - f.hours + 1)
            starts[f.key] = min(options, key=lambda s: price(Plan({**starts, f.key: s}, smart)))
        candidate = Plan(starts, smart)
        if price(candidate) < price(best):
            best = candidate
    return best


def windows(plan: Plan, loads: tuple[FlexLoad, ...] = FLEX_LOADS) -> dict[str, str]:
    """Run times per flexible load as text, e.g. {'furnace': '09–17'}."""
    return {f.key: f"{plan.starts[f.key]:02d}–{plan.starts[f.key] + f.hours:02d}" for f in loads}
