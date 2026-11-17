"""Tariff values for 2026 with their sources. Net of VAT.

Values change every 1 January. Check them against the grid operator's price sheet and a real
invoice before relying on them. Supplier margins and fixed prices are assumptions.
"""

from datetime import date

import pandas as pd

from offpeak.tariffs.model import Charge, DemandCharge, Export, FixedCharge, Tariff

SRC_RHEINNETZ = "https://www.rheinnetz.de/netzentgelte-strom-ab-dem-01.01.2026.pdfx"
# Levies 2026, one page each on netztransparenz.de (the transmission system operators)
_NT = "https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/"
SRC_KWKG = _NT + "KWKG/KWKG-Umlage/KWKG-Umlagen-%C3%9Cbersicht/KWKG-Umlage-2026"
SRC_OFFSHORE = _NT + "Sonstige-Umlagen/Offshore-Netzumlage/Offshore-Netzumlagen-Uebersicht"
SRC_P19 = (
    _NT + "Sonstige-Umlagen/Aufschlag-f%C3%BCr-besondere-Netznutzung-19-StromNEV-Umlage/"
    "%C3%9Cbersicht-Aufschlag-f%C3%BCr-besondere-Netznutzung/"
    "Aufschlag-f%C3%BCr-besondere-Netznutzung-2026"
)
SRC_KAV = "https://www.gesetze-im-internet.de/kav/__2.html"
# Electricity tax: § 3 StromStG sets 20.50 EUR/MWh; § 9b refunds 20 EUR/MWh to
# manufacturing, agriculture and forestry, which leaves 0.05 ct/kWh
SRC_STROMSTEUER = "https://www.gesetze-im-internet.de/stromstg/__3.html"
SRC_STROMSTEUER_REDUCED = "https://www.gesetze-im-internet.de/stromstg/__9b.html"
SRC_EEG = "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/ErneuerbareEnergien/EEG_Foerderung/start.html"
SRC_ERSE_TAR = "https://www.erse.pt/media/lamnmp31/diretiva-erse-10-2025-tep-se-2026.pdf"
SRC_ERSE_CYCLES = "https://www.erse.pt/atividade/regulacao/tarifas-e-precos-eletricidade/"

# RheinNetz (Köln) 2026, Preisblatt 4: customers with load-profile metering (RLM),
# yearly price system. (Leistungspreis EUR/kW/a, Arbeitspreis ct/kWh) by voltage level and
# yearly utilisation below / from 2,500 hours.
RHEINNETZ_RLM = {
    ("low", False): (33.36, 7.40),
    ("low", True): (172.43, 1.84),
    ("medium", False): (21.41, 4.56),
    ("medium", True): (103.84, 1.26),
}
RHEINNETZ_SLP = (150.00, 3.78)  # Preisblatt 1: Grundpreis EUR/a, Arbeitspreis ct/kWh
# Preisblatt "Entgelte für Messstellenbetrieb" (RLM), EUR/a: the meter itself (Messstellenbetrieb
# einschließlich Messung) plus its communication device (Zusatzgerät Kommunikationseinrichtung).
RHEINNETZ_RLM_METERING = 221.28
RHEINNETZ_RLM_COMMUNICATION = 219.24


# ── Households in Köln (RheinNetz 2026, net of VAT) ─────────────────────────
# Preisblatt 3, Modul 3 (§ 14a EnWG): grid fee per kWh by time of day, for a household that
# lets the grid operator dim its heat pump or wallbox when the grid is full. HT 17:00-19:30,
# NT 23:45-5:45 (all four quarters of 2026), ST the rest. Modul 3 comes with Modul 1: a flat
# reduction of 95.58 EUR a year.
RHEINNETZ_MODULE3_CT = {"NT": 1.13, "ST": 3.78, "HT": 6.64}
RHEINNETZ_MODULE1_EUR = -95.58
KAV_KOELN_TARIF_CT = 2.39  # Preisblatt 14: concession fee for household customers in Köln
METER_CONVENTIONAL_EUR = 8.69  # Preisblatt 8: modern meter (EDL21), read once a year
# Smart meter (intelligentes Messsystem) for a household below 6,000 kWh a year: price cap
# 30 EUR gross a year (§ 30 MsbG); the control box a § 14a device needs, about 50 EUR gross
# a year more. Caps as summarised by the BNetzA; a metering operator may charge less.
SMART_METER_EUR = 30 / 1.19
CONTROL_BOX_EUR = 50 / 1.19
SRC_MSBG = "https://www.gesetze-im-internet.de/msbg/__30.html"
EEG_2023_SMALL_CT = 8.2  # partial feed-in, up to 10 kWp, commissioned Feb 2023 to Jan 2024


def module3_period(local: pd.Timestamp) -> str:
    """The RheinNetz 2026 time window (NT, ST or HT) a local time falls into."""
    minutes = local.hour * 60 + local.minute
    if 17 * 60 <= minutes < 19 * 60 + 30:
        return "HT"
    if minutes >= 23 * 60 + 45 or minutes < 5 * 60 + 45:
        return "NT"
    return "ST"


def germany_2026_home(
    *,
    kind: str = "dynamic",
    module3: bool = False,
    supplier_margin_ct: float = 1.5,
    fixed_energy_ct: float = 16.5,
    feed_in_ct: float | None = None,
    pv_kwp: float = 8.0,
) -> Tariff:
    """A household in Köln (RheinNetz) without load-profile metering. Prices include 19 %
    VAT, which a household cannot deduct (Tariff.gross).

    kind "fixed": one energy price all year and a conventional meter; "dynamic": the spot
    price plus the supplier's margin, which needs a smart meter.
    module3: the household has a heat pump or a wallbox under § 14a EnWG and chose the
    time-variable grid fee (needs a dynamic tariff's smart meter and a control box).
    feed_in_ct: what the house earns per exported kWh; default the rate of a new plant.
    The default fixed energy price makes about 33 ct/kWh all in, a typical 2026 offer.
    """
    if module3 and kind != "dynamic":
        raise ValueError("The time-variable grid fee needs a smart meter, so a dynamic tariff")
    base, grid_ct = RHEINNETZ_SLP
    fixed = [FixedCharge("Grid base price (Grundpreis)", base, SRC_RHEINNETZ)]
    if kind == "dynamic":
        fixed.append(FixedCharge("Smart meter (price cap)", SMART_METER_EUR, SRC_MSBG))
    else:
        fixed.append(FixedCharge("Meter (modern meter)", METER_CONVENTIONAL_EUR, SRC_RHEINNETZ))
    if module3:
        fixed += [
            FixedCharge("Control box for § 14a", CONTROL_BOX_EUR, SRC_MSBG),
            FixedCharge("§ 14a reduction (Modul 1)", RHEINNETZ_MODULE1_EUR, SRC_RHEINNETZ),
        ]
        grid = Charge(
            "Grid fee per kWh, by time (§ 14a Modul 3)",
            "grid",
            by_period=RHEINNETZ_MODULE3_CT,
            source=SRC_RHEINNETZ,
        )
    else:
        grid = Charge("Grid fee per kWh (Arbeitspreis)", "grid", grid_ct, source=SRC_RHEINNETZ)
    old_plant = feed_in_ct is not None
    label = {"fixed": "fixed price", "dynamic": "dynamic"}[kind]
    return Tariff(
        name=f"Household Köln 2026 · {label}{' + § 14a time-variable grid fee' if module3 else ''}",
        country="DE",
        tz="Europe/Berlin",
        kind=kind,
        supplier_margin_ct=supplier_margin_ct,
        fixed_energy_ct=fixed_energy_ct,
        charges=(
            grid,
            Charge(
                "Concession fee (household)", "levies", KAV_KOELN_TARIF_CT, source=SRC_RHEINNETZ
            ),
            Charge("CHP levy (KWKG-Umlage)", "levies", 0.446, source=SRC_KWKG),
            Charge("Offshore grid levy", "levies", 0.941, source=SRC_OFFSHORE),
            Charge("Special grid use levy (§ 19)", "levies", 1.559, source=SRC_P19),
            Charge("Electricity tax (Stromsteuer)", "tax", 2.05, source=SRC_STROMSTEUER),
        ),
        fixed=tuple(fixed),
        # plants from before 25 Feb 2025 are also paid at negative prices
        export=Export(
            "fixed",
            feed_in_ct if old_plant else eeg_partial_feed_in_ct(pv_kwp),
            paid_when_negative=old_plant,
            source=SRC_EEG,
        ),
        period_of=module3_period if module3 else None,
        vat=0.19,
        gross=True,
        valid_from=date(2026, 1, 1),
        notes=(
            "RheinNetz (Köln) 2026, households without load-profile metering, incl. 19 % VAT.",
            "Smart meter and control box: legal price caps; your metering operator may differ.",
            "Supplier margin and fixed energy price are assumptions; use your contract.",
        ),
    )


STEERABLE_KINDS = {"heat_pump", "ev_charger"}  # devices that can join § 14a


def tariff_for(profile: str, components) -> Tariff:
    """The tariff a site's pages use. A business: the RLM business tariff. A home: dynamic,
    with the § 14a time-variable grid fee as soon as it has a heat pump or a wallbox, and
    the feed-in rate of the demo home's plant (commissioned 2023). Components that are not
    a home's must not be passed with profile "home" (offpeak/components.check_profile)."""
    kwp = sum(c.p("kwp") for c in components if c.kind in ("pv_field", "pv_roof"))
    if profile == "home":
        steerable = any(c.kind in STEERABLE_KINDS for c in components)
        return germany_2026_home(module3=steerable, feed_in_ct=EEG_2023_SMALL_CT, pv_kwp=kwp)
    return germany_2026(pv_kwp=kwp)


def eeg_partial_feed_in_ct(kwp: float) -> float:
    """Average EEG payment for a new rooftop plant with partial feed-in, commissioned
    1 Aug 2026 to 31 Jan 2027: 7.70 ct up to 10 kWp, 6.66 ct for 10-40 kWp, 5.44 ct for
    40-100 kWp. Above 100 kWp plants must sell on the market instead."""
    bands = [(10, 7.70), (40, 6.66), (100, 5.44)]
    paid, lower = 0.0, 0.0
    for upper, ct in bands:
        share = max(0.0, min(kwp, upper) - lower)
        paid += share * ct
        lower = upper
    return paid / min(kwp, 100) if kwp > 0 else 0.0


def germany_2026(
    *,
    kind: str = "dynamic",
    voltage: str = "low",
    load_metered: bool = True,
    high_utilisation: bool = True,
    reduced_electricity_tax: bool = False,
    supplier_margin_ct: float = 1.5,
    fixed_energy_ct: float = 14.0,
    pv_kwp: float = 60.0,
) -> Tariff:
    """A business in Köln (grid operator RheinNetz) on a special contract.

    load_metered: sites above 100,000 kWh a year have load-profile metering (RLM) and pay a
    demand charge; smaller sites pay a yearly base price instead. high_utilisation: the
    site's yearly kWh divided by its peak kW is at least 2,500 hours.
    reduced_electricity_tax: manufacturing, agriculture and forestry pay 0.05 instead of
    2.05 ct/kWh from 2026, on application to the customs office.
    """
    if load_metered:
        kw_price, grid_ct = RHEINNETZ_RLM[(voltage, high_utilisation)]
        demand = (
            DemandCharge("Grid fee per kW (Leistungspreis)", kw_price, "peak", SRC_RHEINNETZ),
        )
        fixed = (
            FixedCharge("Metering (load-profile meter)", RHEINNETZ_RLM_METERING, SRC_RHEINNETZ),
            FixedCharge("Meter communication device", RHEINNETZ_RLM_COMMUNICATION, SRC_RHEINNETZ),
        )
    else:
        base, grid_ct = RHEINNETZ_SLP
        demand = ()
        fixed = (FixedCharge("Grid base price (Grundpreis)", base, SRC_RHEINNETZ),)
    tax = 0.05 if reduced_electricity_tax else 2.05
    return Tariff(
        name=f"Germany 2026 · {'dynamic' if kind == 'dynamic' else 'fixed price'}",
        country="DE",
        tz="Europe/Berlin",
        kind=kind,
        supplier_margin_ct=supplier_margin_ct,
        fixed_energy_ct=fixed_energy_ct,
        charges=(
            Charge("Grid fee per kWh (Arbeitspreis)", "grid", grid_ct, source=SRC_RHEINNETZ),
            Charge("Concession fee (special contract)", "levies", 0.11, source=SRC_KAV),
            Charge("CHP levy (KWKG-Umlage)", "levies", 0.446, source=SRC_KWKG),
            Charge("Offshore grid levy", "levies", 0.941, source=SRC_OFFSHORE),
            Charge("Special grid use levy (§ 19)", "levies", 1.559, source=SRC_P19),
            Charge(
                "Electricity tax (Stromsteuer)",
                "tax",
                tax,
                source=SRC_STROMSTEUER_REDUCED if reduced_electricity_tax else SRC_STROMSTEUER,
            ),
        ),
        demand=demand,
        fixed=fixed,
        export=Export("fixed", eeg_partial_feed_in_ct(pv_kwp), source=SRC_EEG),
        vat=0.19,
        valid_from=date(2026, 1, 1),
        notes=(
            "Grid fees are RheinNetz (Köln) 2026; other areas differ.",
            "The § 19 levy is 1.559 ct for the first 1 GWh a year; above that it is lower.",
            "Supplier margin and fixed energy price are assumptions; use your contract.",
            "Feed-in pays the EEG rate for new plants and nothing when the spot price is negative.",
        ),
    )


def portugal_period(local: pd.Timestamp) -> str:
    """ERSE weekly cycle (ciclo semanal) for Portugal mainland, used for BTE customers until
    31 March 2027. Winter and summer follow the legal clock change."""
    minute = local.hour * 60 + local.minute
    if 2 * 60 <= minute < 6 * 60:
        return "super_vazio"
    summer = bool(local.dst())
    weekday = local.weekday()

    def within(*spans: tuple[float, float]) -> bool:
        return any(a * 60 <= minute < b * 60 for a, b in spans)

    if weekday == 6:  # Sunday
        return "vazio_normal"
    if weekday == 5:  # Saturday
        busy = ((9, 14), (20, 22)) if summer else ((9.5, 13), (18.5, 22))
        return "cheias" if within(*busy) else "vazio_normal"
    if summer:
        if within((9.25, 12.25)):
            return "ponta"
        return "cheias" if within((7, 9.25), (12.25, 24)) else "vazio_normal"
    if within((9.5, 12), (18.5, 21)):
        return "ponta"
    return "cheias" if within((7, 9.5), (12, 18.5), (21, 24)) else "vazio_normal"


def portugal_bte_2026(
    *,
    kind: str = "dynamic",
    supplier_margin_ct: float = 0.8,
    loss_factor: float = 0.08,
    fixed_energy_ct: float = 11.0,
) -> Tariff:
    """A business on special low voltage (BTE) on an OMIE-indexed tariff:
    (OMIE + margin) × (1 + losses) + network access tariff (TAR) for the time period."""
    days = 365
    return Tariff(
        name=f"Portugal 2026 · BTE · {'indexed' if kind == 'dynamic' else 'fixed price'}",
        country="PT",
        tz="Europe/Lisbon",
        kind=kind,
        supplier_margin_ct=supplier_margin_ct,
        fixed_energy_ct=fixed_energy_ct,
        loss_factor=loss_factor,
        charges=(
            Charge(
                "Network access tariff (TAR), energy",
                "grid",
                by_period={
                    "ponta": 3.97,
                    "cheias": 3.53,
                    "vazio_normal": 2.85,
                    "super_vazio": 2.37,
                },
                source=SRC_ERSE_TAR,
            ),
            Charge("Special consumption tax (IEC)", "tax", 0.1, source="Código dos IEC, art. 92.º"),
        ),
        demand=(
            DemandCharge("Power in peak hours (TAR)", 0.5521 * days, "period:ponta", SRC_ERSE_TAR),
            DemandCharge("Contracted power (TAR)", 0.0563 * days, "peak", SRC_ERSE_TAR),
        ),
        export=Export("spot", spot_share=0.9, source="Typical surplus contract: 90 % of OMIE"),
        period_of=portugal_period,
        vat=0.23,
        valid_from=date(2026, 1, 1),
        notes=(
            "TAR values are ERSE Directive 10/2025 for 2026; time periods are the weekly cycle.",
            "Loss factor, supplier margin and the export share are assumptions.",
            "New time periods apply from 1 April 2027 and are not in this table yet.",
        ),
    )
