"""The demo site. Real sites will come from the database (sites table)."""

from offpeak.models import Site

DEMO_SITE = Site(id=1, name="Demo site", lat=50.94, lon=6.96, zone="DE-LU")
DEMO_CITY = "Köln"
