"""The ways an account's consumption data reaches offpeak, for the "Connect your data" card.

Today data arrives as a file: a Fronius Solar.web history for homes (offpeak/load/fronius.py)
and a consumption export from a smart meter app or an ERP for everyone (offpeak/load/meter.py).
Direct connections, which bring new data every day without a file, are the next step: the card
shows them as planned, with what each needs, so nobody mistakes them for something that runs
today. When one is built, it writes into the same 15-minute slots the file import fills, and
the daily jobs (offpeak/jobs/) pick it up like the prices and the weather.
"""

from dataclasses import dataclass

AVAILABLE = "available"
PLANNED = "planned"


@dataclass(frozen=True)
class Connector:
    key: str
    name: str
    kind: str  # what sort of system, in words
    status: str  # AVAILABLE or PLANNED
    how: str  # what it needs and how the data would flow, for the person reading the card
    roles: tuple[str, ...]


CONNECTORS = (
    Connector(
        "file",
        "File upload",
        "CSV from any meter or system",
        AVAILABLE,
        "Drop an export with a time and a kWh or kW column. It is checked before anything is kept.",
        ("home", "business"),
    ),
    Connector(
        "fronius",
        "Fronius Solar.web",
        "Solar inverter",
        AVAILABLE,
        "Your system's 5-minute history from Solar.web as a CSV file: solar, consumption, "
        "battery and grid, every quarter-hour.",
        ("home",),
    ),
    Connector(
        "smart_meter",
        "Smart meter",
        "Metering operator or meter app",
        PLANNED,
        "Read-only access to your smart meter's 15-minute values, with your consent. offpeak "
        "fetches yesterday's values every morning.",
        ("home", "business"),
    ),
    Connector(
        "sap",
        "SAP S/4HANA",
        "ERP",
        PLANNED,
        "A read-only connection to the energy and production data in your ERP. Consumption comes "
        "in every day; offpeak's plan can go back into production scheduling.",
        ("business",),
    ),
    Connector(
        "ems",
        "Energy management system",
        "API or data export",
        PLANNED,
        "Systems that already log your machines send their data through our API, or drop a "
        "daily file in a shared folder.",
        ("business",),
    ),
)


def for_role(role: str) -> list[Connector]:
    """The connectors shown to this role, available ones first."""
    shown = [c for c in CONNECTORS if role in c.roles]
    return sorted(shown, key=lambda c: c.status != AVAILABLE)
