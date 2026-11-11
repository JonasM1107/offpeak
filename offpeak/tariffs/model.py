"""What an electricity tariff is made of.

A tariff is a list of building blocks, so the German and the Portuguese formula are two
configurations of the same engine (docs/PLAN.md section 9.1):

- the energy price: the spot price plus the supplier's margin (dynamic tariff), or one fixed
  price (fixed tariff); in Portugal multiplied by a loss factor
- per-kWh charges: grid fees, levies and taxes, flat or depending on the time period
- demand charges: paid per kW of peak power, not per kWh
- fixed charges: euros per year, such as metering
- what exported power earns

All prices are net of VAT: businesses deduct VAT, so it does not change their cost.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

GROUPS = ("energy", "grid", "levies", "tax")  # how the price breakdown is grouped


@dataclass(frozen=True)
class Charge:
    """A charge per kWh bought from the grid."""

    name: str
    group: str  # one of GROUPS, except "energy"
    ct_kwh: float = 0.0
    by_period: dict[str, float] | None = None  # ct/kWh per time period, overrides ct_kwh
    source: str = ""


@dataclass(frozen=True)
class DemandCharge:
    """A charge per kW. basis 'peak': the highest average kW of any slot (German
    Leistungspreis, Portuguese contracted power). basis 'period:<name>': the average kW
    over the slots of that period (Portuguese power in peak hours)."""

    name: str
    eur_per_kw_year: float
    basis: str = "peak"
    source: str = ""


@dataclass(frozen=True)
class FixedCharge:
    name: str
    eur_year: float
    source: str = ""


@dataclass(frozen=True)
class Export:
    """What exported power earns. kind 'fixed': ct_kwh; 'spot': spot price × spot_share;
    'none': nothing."""

    kind: str = "none"
    ct_kwh: float = 0.0
    spot_share: float = 1.0
    paid_when_negative: bool = False  # German rule for new plants: no payment at negative prices
    source: str = ""


@dataclass(frozen=True)
class Tariff:
    name: str
    country: str
    tz: str
    kind: str  # "dynamic" or "fixed"
    supplier_margin_ct: float = 0.0  # dynamic: added to the spot price
    fixed_energy_ct: float = 0.0  # fixed: the energy price, replaces spot + margin
    loss_factor: float = 0.0  # energy price × (1 + loss_factor)
    charges: tuple[Charge, ...] = ()
    demand: tuple[DemandCharge, ...] = ()
    fixed: tuple[FixedCharge, ...] = ()
    export: Export = field(default_factory=Export)
    period_of: Callable[[pd.Timestamp], str] | None = None  # local time -> period name
    vat: float = 0.0  # shown for information only
    valid_from: date | None = None
    notes: tuple[str, ...] = ()
