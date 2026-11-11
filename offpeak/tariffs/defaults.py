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
