"""Turns market prices into what a site pays and earns, and adds up a bill.

slot_prices(): price per slot, split into energy, grid, levies and tax.
bill(): the cost of a load profile under a tariff, line by line.
"""

from dataclasses import dataclass

import pandas as pd

from offpeak.tariffs.model import GROUPS, Tariff


def slot_prices(prices: pd.DataFrame, tariff: Tariff) -> pd.DataFrame:
    """One row per slot of `prices` (columns ts in UTC and eur_mwh).

    Returns ts, period, spot_ct, energy_ct, grid_ct, levies_ct, tax_ct, import_ct (the sum,
    what one kWh from the grid costs) and export_ct (what one exported kWh earns). All ct/kWh.
    """
    out = pd.DataFrame(
        {"ts": prices["ts"].reset_index(drop=True), "spot_ct": prices["eur_mwh"].to_numpy() / 10}
    )
    local = out["ts"].dt.tz_convert(tariff.tz)
    out["period"] = local.map(tariff.period_of) if tariff.period_of else "all"

    if tariff.kind == "fixed":
        energy = pd.Series(tariff.fixed_energy_ct, index=out.index, dtype=float)
    else:
        energy = out["spot_ct"] + tariff.supplier_margin_ct
    out["energy_ct"] = energy * (1 + tariff.loss_factor)

    for group in GROUPS[1:]:
        out[f"{group}_ct"] = 0.0
    for charge in tariff.charges:
        if charge.by_period:
            value = out["period"].map(charge.by_period).fillna(0.0)
        else:
            value = charge.ct_kwh
        out[f"{charge.group}_ct"] += value
    out["import_ct"] = out[[f"{g}_ct" for g in GROUPS]].sum(axis=1)

    ex = tariff.export
    if ex.kind == "fixed":
        earn = pd.Series(ex.ct_kwh, index=out.index, dtype=float)
    elif ex.kind == "spot":
        earn = out["spot_ct"] * ex.spot_share
    else:
        earn = pd.Series(0.0, index=out.index)
    if not ex.paid_when_negative:
        earn = earn.where(out["spot_ct"] >= 0, 0.0)
    out["export_ct"] = earn
    return out


def slot_hours(ts: pd.Series) -> float:
    """Length of one slot in hours (0.25 for 15-minute data, 1 for hourly)."""
    if len(ts) < 2:
        return 1.0
    return (ts.iloc[1] - ts.iloc[0]).total_seconds() / 3600


def demand_costs(import_kw: pd.Series, periods: pd.Series, tariff: Tariff, days: float):
    """Demand charges for `days` days of the profile, prorated from the yearly price.

    import_kw: average kW bought in each slot. The German Leistungspreis is billed on the
    year's highest slot; counting each day's own peak, prorated, is the right signal for
    planning a day: a new peak costs money, a lower one saves it.
    """
    lines = []
    for d in tariff.demand:
        if d.basis == "peak":
            kw = float(import_kw.max()) if len(import_kw) else 0.0
        elif d.basis.startswith("period:"):
            in_period = import_kw[periods == d.basis.split(":", 1)[1]]
            kw = float(in_period.mean()) if len(in_period) else 0.0
        else:
            raise ValueError(f"unknown demand basis {d.basis!r}")
        lines.append((d.name, max(kw, 0.0) * d.eur_per_kw_year * days / 365, kw))
    return lines


@dataclass
class Bill:
    lines: dict[str, float]  # euros per line: energy, grid, levies, tax, demand, fixed, export
    kwh_bought: float
    kwh_sold: float
    peak_kw: float

    @property
    def total(self) -> float:
        return sum(self.lines.values())

    @property
    def ct_per_kwh(self) -> float:
        """Average cost of a bought kWh, everything included except the export credit."""
        bought = self.total - self.lines.get("export", 0.0)
        return bought / self.kwh_bought * 100 if self.kwh_bought else 0.0


def bill(grid_kw: pd.Series, prices: pd.DataFrame, tariff: Tariff) -> Bill:
    """Cost of a grid profile: grid_kw per slot (positive buys, negative sells), aligned
    with `prices` from slot_prices(). Fixed charges are prorated to the profile's length."""
    hours = slot_hours(prices["ts"])
    kw = pd.Series(grid_kw.values, index=prices.index, dtype=float)
    bought_kwh, sold_kwh = kw.clip(lower=0) * hours, (-kw).clip(lower=0) * hours
    days = len(prices) * hours / 24
    lines = {g: float((bought_kwh * prices[f"{g}_ct"]).sum() / 100) for g in GROUPS}
    demand = demand_costs(kw.clip(lower=0), prices["period"], tariff, days)
    lines["demand"] = sum(eur for _, eur, _ in demand)
    lines["fixed"] = sum(f.eur_year for f in tariff.fixed) * days / 365
    lines["export"] = -float((sold_kwh * prices["export_ct"]).sum() / 100)
    return Bill(lines, float(bought_kwh.sum()), float(sold_kwh.sum()), float(kw.max()))
