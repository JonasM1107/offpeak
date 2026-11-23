"""The demo sites: one business and one home. Real sites will come from the database.

Each role has its own site, so its components and cockpit machines are stored apart (by site
id, and with the profile on every row). Prices and weather are the same for both: the market
price does not depend on who buys, and both sites are in Köln.
"""

from datetime import date

from offpeak.models import Site

DEMO_SITE = Site(id=1, name="Demo site", lat=50.94, lon=6.96, zone="DE-LU")
# The demo home: Köln city centre, not a real address. The roof is the measured one: south-east
# (145 degrees) at 26 degrees, found from its production (branch experiment/fronius-data).
DEMO_HOME = Site(
    id=2,
    name="Demo home",
    lat=50.94,
    lon=6.96,
    zone="DE-LU",
    tilt_deg=26.0,
    azimuth_deg=145.0,
    profile="home",
)
DEMO_CITY = "Köln"
# The Homeowner demo shows real measurements: the house of Jonas, one of the team, with a
# Fronius inverter (solar and battery). This is the first day that inverter recorded.
DEMO_HOME_SINCE = date(2023, 9, 16)

SITES = {"business": DEMO_SITE, "home": DEMO_HOME}


def site_for(role: str) -> Site:
    """The site of a role; ValueError for anything else (the role comes from a sign-in)."""
    if role not in SITES:
        raise ValueError(f"Unknown role: {role!r}")
    return SITES[role]
