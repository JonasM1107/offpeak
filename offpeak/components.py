"""Site components: the machines a business has on site, and what we know about each.

A component has a kind from CATALOGUE (solar field, wind turbine, battery, heat pump, ...),
a name and a few parameters. From the list of components we derive:

- the inputs of the site energy model in offpeak/demo_site.py (one model for the whole site),
- each component's share of that model's result, hour by hour,
- a fact sheet: key facts, a parts list with raw materials, and embodied CO2,
- per-component analytics for one day and advice on when it should run or charge.

Material masses and CO2 factors are typical values from the literature, scaled with the
component's size. They are rough estimates for a first overview, not a bill of materials.
"""

from dataclasses import dataclass, field
from uuid import uuid4

import pandas as pd

from offpeak.demo_site import (
    EXPORT_EUR_KWH,
    Assets,
    FlexLoad,
    Plan,
    day_bill,
    plan_day,
    simulate,
    usual_plan,
)
from offpeak.tariffs import Tariff

# ── The catalogue of kinds ───────────────────────────────────────────────────


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    unit: str
    default: float
    min: float
    max: float


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    role: str  # generation, storage, flexible or base
    description: str
    lifetime_years: int
    params: tuple[Param, ...]


# Parameters shared by every flexible load: how long it needs to run and when it may.
SCHEDULE = (
    Param("hours", "Run time per day", "h", 4, 1, 24),
    Param("earliest", "Earliest start", "h", 0, 0, 23),
    Param("latest_end", "Must be done by", "h", 24, 1, 24),
    Param("usual_start", "Usually starts at", "h", 8, 0, 23),
)

CATALOGUE: dict[str, Kind] = {
    k.key: k
    for k in (
        Kind(
            "pv_field",
            "Solar field",
            "generation",
            "Ground-mounted crystalline solar modules on steel racks, with string inverters.",
            30,
            (Param("kwp", "Peak power", "kWp", 40, 1, 2000),),
        ),
        Kind(
            "pv_roof",
            "Rooftop solar",
            "generation",
            "Solar modules on the hall roof, on aluminium rails, with a string inverter.",
            30,
            (Param("kwp", "Peak power", "kWp", 20, 1, 1000),),
        ),
        Kind(
            "wind",
            "Wind turbine",
            "generation",
            "Small three-blade turbine on a steel tower; starts at 3 m/s, full power from 12 m/s.",
            20,
            (
                Param("kw", "Rated power", "kW", 15, 1, 500),
                Param("hub_m", "Hub height", "m", 24, 10, 80),
            ),
        ),
        Kind(
            "battery",
            "Battery storage",
            "storage",
            "Lithium iron phosphate (LFP) racks in a container, with converter and cooling.",
            15,
            (
                Param("kwh", "Capacity", "kWh", 120, 5, 5000),
                Param("kw", "Power", "kW", 20, 1, 2000),
            ),
        ),
        Kind(
            "heat_pump",
            "Heat pump",
            "flexible",
            "Air-to-water heat pump with a buffer tank, so heating can move to cheaper hours.",
            20,
            (Param("kw", "Electrical power", "kW", 8, 1, 300),)
            + (
                Param("hours", "Run time per day", "h", 6, 1, 24),
                Param("earliest", "Earliest start", "h", 0, 0, 23),
                Param("latest_end", "Must be done by", "h", 24, 1, 24),
                Param("usual_start", "Usually starts at", "h", 5, 0, 23),
            ),
        ),
        Kind(
            "ev_charger",
            "EV chargers",
            "flexible",
            "Wall-box chargers for the company fleet; cars only need to be full by morning.",
            12,
            (
                Param("count", "Chargers", "", 3, 1, 50),
                Param("kw", "Power per charger", "kW", 10, 3, 150),
                Param("hours", "Charging time per day", "h", 5, 1, 24),
                Param("earliest", "Earliest start", "h", 7, 0, 23),
                Param("latest_end", "Must be done by", "h", 24, 1, 24),
                Param("usual_start", "Usually starts at", "h", 17, 0, 23),
            ),
        ),
        Kind(
            "furnace",
            "Electric furnace",
            "flexible",
            "Resistance-heated industrial furnace in the production hall.",
            25,
            (
                Param("kw", "Electrical power", "kW", 40, 1, 2000),
                Param("hours", "Run time per day", "h", 8, 1, 24),
                Param("earliest", "Earliest start", "h", 5, 0, 23),
                Param("latest_end", "Must be done by", "h", 21, 1, 24),
                Param("usual_start", "Usually starts at", "h", 6, 0, 23),
            ),
        ),
        Kind(
            "cold_store",
            "Cold store",
            "base",
            "Insulated cold room with roof-mounted condensing units; runs around the clock.",
            20,
            (Param("kw", "Electrical power", "kW", 15, 1, 500),),
        ),
    )
}


@dataclass
class Component:
    id: str
    kind: str
    name: str
    params: dict = field(default_factory=dict)

    @property
    def spec(self) -> Kind:
        return CATALOGUE[self.kind]

    def p(self, key: str) -> float:
        """A parameter, or the kind's default if it was never set."""
        default = next(x.default for x in self.spec.params if x.key == key)
        return float(self.params.get(key, default))


def new_component(kind: str, name: str, params: dict | None = None) -> Component:
    spec = CATALOGUE[kind]
    values = {p.key: p.default for p in spec.params} | (params or {})
    return Component(id=f"{kind}-{uuid4().hex[:6]}", kind=kind, name=name, params=values)


DEFAULT_COMPONENTS = (
    Component("pv-field", "pv_field", "Solar field", {"kwp": 40}),
    Component("pv-roof", "pv_roof", "Hall roof solar", {"kwp": 20}),
    Component("wind-1", "wind", "Wind turbine 1", {"kw": 15, "hub_m": 24}),
    Component("wind-2", "wind", "Wind turbine 2", {"kw": 15, "hub_m": 24}),
    Component("battery", "battery", "Battery storage", {"kwh": 120, "kw": 20}),
    Component(
        "heat-pump",
        "heat_pump",
        "Heat pump",
        {"kw": 8, "hours": 6, "earliest": 0, "latest_end": 24, "usual_start": 5},
    ),
    Component("furnace", "furnace", "Electric furnace", {"kw": 40, "hours": 8}),
    Component("ev", "ev_charger", "EV fleet chargers", {"count": 3, "kw": 10, "hours": 5}),
    Component("cold-store", "cold_store", "Cold store", {"kw": 15}),
)


def validate(kind: str, params: dict) -> list[str]:
    """Problems with a new component's parameters, in plain words (empty list = fine)."""
    spec = CATALOGUE[kind]
    problems = [
        f"{p.label} must be between {p.min:g} and {p.max:g} {p.unit}".strip()
        for p in spec.params
        if not p.min <= float(params.get(p.key, p.default)) <= p.max
    ]
    if spec.role == "flexible":
        hours = params.get("hours", 0)
        earliest, latest = params.get("earliest", 0), params.get("latest_end", 24)
        usual = params.get("usual_start", earliest)
        if latest - earliest < hours:
            problems.append("The allowed hours are shorter than the run time")
        if not earliest <= usual <= latest - hours:
            problems.append("The usual start must fit inside the allowed hours")
    return problems


# ── From components to the site energy model ────────────────────────────────


def _total(components, kind_keys, param) -> float:
    return sum(c.p(param) for c in components if c.kind in kind_keys)


def site_model(components) -> tuple[Assets, tuple[FlexLoad, ...]]:
    """The whole site as the energy model sees it: summed assets plus every flexible load."""
    wind_kw = _total(components, {"wind"}, "kw")
    assets = Assets(
        pv_kwp=_total(components, {"pv_field", "pv_roof"}, "kwp"),
        # the power curve is linear in the rated power, so one turbine with the summed
        # rating produces exactly what all turbines together produce
        turbines=1 if wind_kw else 0,
        turbine_kw=wind_kw,
        battery_kwh=_total(components, {"battery"}, "kwh"),
        battery_kw=_total(components, {"battery"}, "kw"),
        cold_store_kw=_total(components, {"cold_store"}, "kw"),
    )
    loads = tuple(
        FlexLoad(
            key=c.id,
            kw=c.p("kw") * (c.p("count") if c.kind == "ev_charger" else 1),
            hours=int(c.p("hours")),
            usual_start=int(c.p("usual_start")),
            earliest=int(c.p("earliest")),
            latest_end=int(c.p("latest_end")),
        )
        for c in components
        if c.spec.role == "flexible"
    )
    return assets, loads


def _share(c: Component, components, kinds, param) -> float:
    total = _total(components, kinds, param)
    return c.p(param) / total if total else 0.0


def component_series(day: pd.DataFrame, components) -> dict[str, list[float]]:
    """Each component's power per hour (kW). Generation and load positive; battery positive
    while charging. Shared quantities are split by size."""
    out = {}
    for c in components:
        if c.kind in ("pv_field", "pv_roof"):
            s = day["pv_kw"] * _share(c, components, {"pv_field", "pv_roof"}, "kwp")
        elif c.kind == "wind":
            s = day["wind_kw"] * _share(c, components, {"wind"}, "kw")
        elif c.kind == "battery":
            s = day["battery_kw"] * _share(c, components, {"battery"}, "kwh")
        elif c.kind == "cold_store":
            s = day["cold_kw"] * _share(c, components, {"cold_store"}, "kw")
        else:
            s = day[f"{c.id}_kw"]
        out[c.id] = [round(float(v), 3) for v in s]
    return out


# ── Parts and raw materials ─────────────────────────────────────────────────

# kg CO2-equivalent per kg of material, typical cradle-to-gate values (rough)
CO2_PER_KG = {
    "Steel": 2.0,
    "Aluminium": 9.0,
    "Copper": 4.0,
    "Glass": 1.2,
    "Silicon": 120.0,
    "Silver": 200.0,
    "Polymers": 3.0,
    "Concrete": 0.13,
    "Glass fibre composite": 8.0,
    "Rare-earth magnets": 30.0,
    "LFP cathode": 10.0,
    "Graphite": 5.0,
    "Electrolyte": 6.0,
    "Electronics": 60.0,
    "Refractory ceramic": 0.9,
    "Mineral wool": 1.3,
    "PU foam": 4.0,
    "Refrigerant": 3.0,
    "FeCrAl alloy": 6.0,
}


@dataclass(frozen=True)
class Part:
    key: str  # matches the part of the 3D model that gets highlighted
    name: str
    qty: int
    materials: dict  # material -> kg for all pieces together


def _scaled(per_unit: dict, units: float) -> dict:
    return {m: round(kg * units, 1) for m, kg in per_unit.items()}


def parts(c: Component) -> list[Part]:
    """The main parts of a component and what they are made of (typical values, scaled)."""
    k = c.kind
    if k in ("pv_field", "pv_roof"):
        kwp = c.p("kwp")
        modules = max(1, round(kwp / 0.42))  # 420 W modules
        mount = {"Steel": 35, "Aluminium": 5} if k == "pv_field" else {"Aluminium": 8, "Steel": 1}
        return [
            Part(
                "modules",
                "Solar modules (420 W)",
                modules,
                _scaled(
                    {
                        "Glass": 15.0,
                        "Aluminium": 2.5,
                        "Polymers": 1.6,
                        "Silicon": 0.7,
                        "Copper": 0.2,
                        "Silver": 0.008,
                    },
                    modules,
                ),
            ),
            Part("mounting", "Mounting structure", 1, _scaled(mount, kwp)),
            Part(
                "inverter",
                "String inverter",
                max(1, round(kwp / 25)),
                _scaled({"Aluminium": 1.2, "Copper": 0.3, "Electronics": 0.5}, kwp),
            ),
            Part("cabling", "DC and AC cabling", 1, _scaled({"Copper": 1.0, "Polymers": 0.5}, kwp)),
        ]
    if k == "wind":
        kw = c.p("kw")
        return [
            Part(
                "foundation", "Concrete foundation", 1, _scaled({"Concrete": 600, "Steel": 30}, kw)
            ),
            Part("tower", "Tower (3 sections)", 3, _scaled({"Steel": 120}, kw)),
            Part(
                "nacelle",
                "Nacelle with generator",
                1,
                _scaled({"Steel": 15, "Copper": 3, "Rare-earth magnets": 0.6, "Aluminium": 2}, kw),
            ),
            Part("blades", "Rotor blades", 3, _scaled({"Glass fibre composite": 10}, kw)),
            Part(
                "converter",
                "Converter and cabinet",
                1,
                _scaled({"Steel": 1.5, "Copper": 0.8, "Electronics": 0.4}, kw),
            ),
        ]
    if k == "battery":
        kwh, kw = c.p("kwh"), c.p("kw")
        return [
            Part(
                "cells",
                "LFP cells and modules",
                max(1, round(kwh / 5)),
                _scaled(
                    {
                        "LFP cathode": 2.0,
                        "Graphite": 1.1,
                        "Aluminium": 1.4,
                        "Copper": 0.9,
                        "Electrolyte": 1.0,
                        "Polymers": 0.2,
                    },
                    kwh,
                ),
            ),
            Part(
                "racks",
                "Racks and battery management",
                max(1, round(kwh / 30)),
                _scaled({"Steel": 2.5, "Electronics": 0.1}, kwh),
            ),
            Part(
                "container",
                "Container",
                max(1, round(kwh / 250 + 0.4)),
                {"Steel": round(2200 * max(1, round(kwh / 250 + 0.4)), 1)},
            ),
            Part(
                "pcs",
                "Power converter",
                1,
                _scaled({"Steel": 1.5, "Copper": 0.6, "Electronics": 0.5}, kw),
            ),
            Part(
                "hvac",
                "Cooling unit",
                1,
                {"Steel": 60, "Copper": 8, "Aluminium": 6, "Refrigerant": 1.5},
            ),
        ]
    if k == "heat_pump":
        kw = c.p("kw")
        return [
            Part(
                "unit",
                "Outdoor unit",
                max(1, round(kw / 10 + 0.4)),
                _scaled({"Steel": 8, "Aluminium": 2, "Copper": 2.5, "Electronics": 0.3}, kw),
            ),
            Part(
                "fans",
                "Fans",
                max(1, round(kw / 10 + 0.4)) * 2,
                _scaled({"Polymers": 0.4, "Copper": 0.2, "Steel": 0.3}, kw),
            ),
            Part("tank", "Buffer tank", 1, _scaled({"Steel": 12, "PU foam": 1.2}, kw)),
            Part("pipes", "Insulated pipes", 1, _scaled({"Copper": 1.0, "Polymers": 0.6}, kw)),
            Part("refrigerant", "Refrigerant (R290)", 1, _scaled({"Refrigerant": 0.15}, kw)),
        ]
    if k == "ev_charger":
        n, kw = int(c.p("count")), c.p("kw")
        return [
            Part(
                "chargers",
                "Charging stations",
                n,
                _scaled({"Steel": 9, "Aluminium": 3, "Polymers": 3, "Electronics": 1.5}, n),
            ),
            Part(
                "cables",
                "Charging cables",
                n,
                _scaled({"Copper": 0.5 * kw / 10 * 4, "Polymers": 1.5}, n),
            ),
            Part(
                "feeder",
                "Feeder cable and switchgear",
                1,
                _scaled({"Copper": 2.0, "Steel": 1.0, "Polymers": 0.8}, n * kw),
            ),
        ]
    if k == "furnace":
        kw = c.p("kw")
        return [
            Part("shell", "Furnace shell", 1, _scaled({"Steel": 15}, kw)),
            Part(
                "lining",
                "Refractory lining",
                1,
                _scaled({"Refractory ceramic": 20, "Mineral wool": 3}, kw),
            ),
            Part(
                "elements",
                "Heating elements",
                max(3, round(kw / 5)),
                _scaled({"FeCrAl alloy": 0.5}, kw),
            ),
            Part(
                "busbars",
                "Power supply and busbars",
                1,
                _scaled({"Copper": 0.5, "Steel": 0.5, "Electronics": 0.1}, kw),
            ),
            Part("chimney", "Exhaust chimney", 1, {"Steel": 180}),
        ]
    if k == "cold_store":
        kw = c.p("kw")
        return [
            Part("panels", "Insulated wall panels", 1, _scaled({"Steel": 18, "PU foam": 12}, kw)),
            Part(
                "condensers",
                "Condensing units",
                2,
                _scaled({"Steel": 6, "Copper": 3, "Aluminium": 3, "Refrigerant": 0.3}, kw),
            ),
            Part("door", "Insulated door", 1, {"Steel": 90, "PU foam": 15, "Polymers": 10}),
        ]
    return []


def materials(part_list: list[Part]) -> list[tuple[str, float, float]]:
    """(material, kg, kg CO2e) for all parts together, heaviest first."""
    totals: dict[str, float] = {}
    for part in part_list:
        for m, kg in part.materials.items():
            totals[m] = totals.get(m, 0) + kg
    return sorted(
        ((m, round(kg, 1), round(kg * CO2_PER_KG.get(m, 2.0), 1)) for m, kg in totals.items()),
        key=lambda x: -x[1],
    )


def facts(c: Component) -> list[tuple[str, str]]:
    """Key facts for the fact sheet."""
    out = [("Type", c.spec.label)]
    for p in c.spec.params:
        if p.key in ("earliest", "latest_end", "usual_start"):
            continue
        out.append((p.label, f"{c.p(p.key):g} {p.unit}".strip()))
    if c.spec.role == "flexible":
        out.append(("Allowed hours", f"{c.p('earliest'):02.0f}:00–{c.p('latest_end'):02.0f}:00"))
    out.append(("Typical lifetime", f"{c.spec.lifetime_years} years"))
    return out


# ── Analytics and advice per component ──────────────────────────────────────


def hour_ranges(flags) -> str:
    """[F, T, T, F, T] -> '01–03, 04–05'. Empty string if no hour is set."""
    out, start = [], None
    for h, on in enumerate(list(flags) + [False]):
        if on and start is None:
            start = h
        elif not on and start is not None:
            out.append(f"{start:02d}–{h:02d}")
            start = None
    return ", ".join(out)


def price_classes(prices_ct: list[float]) -> list[str]:
    """The cheapest third of the hours is 'cheap', the dearest third 'dear'."""
    ranked = sorted(prices_ct)
    low, high = ranked[len(ranked) // 3 - 1], ranked[-(len(ranked) // 3)]
    return ["cheap" if p <= low else "dear" if p >= high else "" for p in prices_ct]


def buy_ct(day: pd.DataFrame) -> pd.Series:
    """What a kWh from the grid costs each hour: the all-in tariff price if the inputs were
    priced with a tariff (offpeak/tariffs), otherwise the spot price."""
    return day["import_ct"] if "import_ct" in day else day["price_ct"]


def sell_ct(day: pd.DataFrame) -> pd.Series:
    """What an exported kWh earns each hour."""
    if "export_ct" in day:
        return day["export_ct"]
    return pd.Series(EXPORT_EUR_KWH * 100, index=day.index)


def _grid_share(day: pd.DataFrame) -> pd.Series:
    """Per hour: which part of the site's consumption is bought from the grid."""
    return (day["grid_kw"].clip(lower=0) / day["load_kw"].where(day["load_kw"] > 0)).fillna(0)


def _used_share(day: pd.DataFrame) -> pd.Series:
    """Per hour: which part of own generation is used on site (rest is exported)."""
    gen = day["pv_kw"] + day["wind_kw"]
    used = gen.clip(upper=day["load_kw"] + day["battery_kw"].clip(lower=0))
    return (used / gen.where(gen > 0)).fillna(0)


def _load_stats(kw: pd.Series, day: pd.DataFrame) -> dict:
    grid = _grid_share(day)
    energy = float(kw.sum())
    # own power is valued at what it would have earned when exported
    cost = float((kw * (grid * buy_ct(day) + (1 - grid) * sell_ct(day)) / 100).sum())
    own = float((kw * (1 - grid)).sum())
    return {
        "energy_kwh": round(energy, 1),
        "cost_eur": round(cost, 2),
        "avg_ct": round(cost / energy * 100, 1) if energy else 0.0,
        "own_pct": round(own / energy * 100) if energy else 0,
    }


def analytics(c: Component, kw: list[float], day: pd.DataFrame) -> dict:
    """Numbers for one component on one day (one plan)."""
    s = pd.Series(kw, index=day.index)
    role = c.spec.role
    if role == "generation":
        used = _used_share(day)
        rated = c.p("kwp") if "kwp" in c.params else c.p("kw")
        energy = float(s.sum())
        value = float((s * (used * buy_ct(day) + (1 - used) * sell_ct(day)) / 100).sum())
        return {
            "energy_kwh": round(energy, 1),
            "peak_kw": round(float(s.max()), 1),
            "capacity_pct": round(energy / (rated * 24) * 100) if rated else 0,
            "used_pct": round(float((s * used).sum()) / energy * 100) if energy else 0,
            "value_eur": round(value, 2),
        }
    if role == "storage":
        charged, discharged = float(s.clip(lower=0).sum()), float((-s).clip(lower=0).sum())
        avoided = float(((-s).clip(lower=0) * buy_ct(day) / 100).sum())
        lost_export = float((s.clip(lower=0) * sell_ct(day) / 100).sum())
        return {
            "charged_kwh": round(charged, 1),
            "discharged_kwh": round(discharged, 1),
            "cycles": round(discharged / c.p("kwh"), 2) if c.p("kwh") else 0,
            "value_eur": round(avoided - lost_export, 2),
            "soc_pct": [round(float(v)) for v in day["soc_pct"]],
        }
    return _load_stats(s, day)


def _block_avg(prices, start, hours) -> float:
    return sum(prices[start : start + hours]) / hours


def advice(c: Component, kw_plan: list[float], kw_usual: list[float], day: pd.DataFrame) -> dict:
    """When this component should run or charge, and why, in plain words."""
    prices = list(buy_ct(day))
    surplus = list((day["pv_kw"] + day["wind_kw"]) > day["cold_kw"] + 1)
    role = c.spec.role
    if role == "flexible":
        on = [v > 0 for v in kw_plan]
        hours = int(c.p("hours"))
        run = [h for h, x in enumerate(on) if x]
        solar_hours = sum(surplus[h] for h in run)
        cheapest = min(range(0, 25 - hours), key=lambda s: _block_avg(prices, s, hours))
        dearest = max(range(0, 25 - hours), key=lambda s: _block_avg(prices, s, hours))
        if run and solar_hours >= len(run) / 2:
            reason = "runs mostly on the site's own solar and wind power"
        elif run and abs(run[0] - cheapest) <= 1:
            reason = "these are the cheapest grid hours in its allowed time"
        else:
            reason = "the best mix of own power and grid price in its allowed time"
        return {
            "best": hour_ranges(on),
            "usual": hour_ranges(v > 0 for v in kw_usual),
            "avoid": f"{dearest:02d}–{dearest + hours:02d}",
            "reason": reason,
        }
    if role == "storage":
        return {
            "best": hour_ranges(v > 0.5 for v in kw_plan),
            "discharge": hour_ranges(v < -0.5 for v in kw_plan),
            "reason": "charges from surplus own power, gives it back when power is expensive",
        }
    if role == "generation":
        peak = [v >= max(kw_plan) * 0.6 and v > 0.5 for v in kw_plan]
        return {
            "best": hour_ranges(peak),
            "reason": "plan heavy loads into these hours to use this power on site",
        }
    return {"best": "all day", "reason": "runs around the clock; not moved by the plan"}


# ── Everything the site view needs ───────────────────────────────────────────


PRICE_COLUMNS = ["energy_ct", "grid_ct", "levies_ct", "tax_ct", "import_ct", "export_ct"]


def _bill_dict(b) -> dict:
    return {
        "lines": {k: round(v, 2) for k, v in b.lines.items()},
        "total": round(b.total, 2),
        "peak_kw": round(b.peak_kw, 1),
        "ct_per_kwh": round(b.ct_per_kwh, 2),
    }


def site_day(inputs: pd.DataFrame, components, tariff: Tariff | None = None) -> dict:
    """Run the site with the Offpeak plan and the usual pattern; return all numbers per
    component and per hour for the site view.

    With a tariff (inputs from demo_site.apply_tariff) every cost uses the all-in price,
    and the plan compares full bills, so it also avoids raising the demand charge."""
    assets, loads = site_model(components)
    usual = usual_plan(loads)
    plan = plan_day(inputs, tariff, assets, loads) if loads else Plan({}, smart_battery=True)
    plans = {"offpeak": plan, "usual": usual}
    prices = [c for c in PRICE_COLUMNS if c in inputs]
    days = {
        name: simulate(inputs, p, assets, loads).join(inputs[prices].reset_index(drop=True))
        for name, p in plans.items()
    }
    series = {name: component_series(day, components) for name, day in days.items()}
    out = []
    for c in components:
        part_list = parts(c)
        mats = materials(part_list)
        out.append(
            {
                "id": c.id,
                "kind": c.kind,
                "kind_label": c.spec.label,
                "role": c.spec.role,
                "name": c.name,
                "description": c.spec.description,
                "params": {p.key: c.p(p.key) for p in c.spec.params},
                "facts": facts(c),
                "parts": [
                    {
                        "key": p.key,
                        "name": p.name,
                        "qty": p.qty,
                        "mass_kg": round(sum(p.materials.values()), 1),
                    }
                    for p in part_list
                ],
                "materials": mats,
                "mass_kg": round(sum(m[1] for m in mats), 1),
                "co2_kg": round(sum(m[2] for m in mats)),
                "analytics": {
                    name: analytics(c, series[name][c.id], day) for name, day in days.items()
                },
                "advice": advice(
                    c, series["offpeak"][c.id], series["usual"][c.id], days["offpeak"]
                ),
            }
        )
    rows = {name: day.round(3).to_dict("records") for name, day in days.items()}
    return {
        "components": out,
        "series": series,
        "rows": rows,
        "price_class": price_classes(list(buy_ct(inputs))),
        "smart_battery": plan.smart_battery,
        "bill": (
            {
                name: _bill_dict(day_bill(inputs, p, tariff, assets, loads))
                for name, p in plans.items()
            }
            if tariff is not None
            else None
        ),
    }
