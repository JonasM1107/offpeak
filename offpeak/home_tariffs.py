"""Which tariff suits a home: a fixed price, a dynamic price, or a dynamic price with the
§ 14a time-variable grid fee (offpeak/tariffs/defaults.py: germany_2026_home).

For one day, the home's devices run at their usual times on the fixed price (nothing to plan
there) and on Offpeak's plan on the two dynamic tariffs. Every bill includes the day's share of
the yearly charges (grid base price, meter, control box, § 14a reduction) and 19 % VAT.
"""

from datetime import date

import pandas as pd

from offpeak import components, demo_site
from offpeak.tariffs import germany_2026_home
from offpeak.tariffs.defaults import EEG_2023_SMALL_CT, STEERABLE_KINDS


def options(
    base: pd.DataFrame, comps, day: date, feed_in_ct: float = EEG_2023_SMALL_CT
) -> list[dict]:
    """The tariffs a home can choose, cheapest first, for one day.

    base: demo_site.hourly_inputs() for the home (spot price, solar, wind).
    Returns name, key, plan ("usual times" or "Offpeak plan"), eur_day, eur_year (the day
    times 365: a rough guide, one day is not a year), ct_per_kwh (average bought kWh) and
    available (False for § 14a without a heat pump or wallbox: shown, but not possible)."""
    comps = list(comps)
    components.check_profile(comps, "home")
    kwp = sum(c.p("kwp") for c in comps if c.kind == "pv_roof")
    steerable = any(c.kind in STEERABLE_KINDS for c in comps)
    rows = []
    for key, tariff, which in (
        ("fixed", germany_2026_home(kind="fixed", feed_in_ct=feed_in_ct, pv_kwp=kwp), "usual"),
        ("dynamic", germany_2026_home(feed_in_ct=feed_in_ct, pv_kwp=kwp), "offpeak"),
        ("module3", germany_2026_home(module3=True, feed_in_ct=feed_in_ct, pv_kwp=kwp), "offpeak"),
    ):
        inputs = demo_site.apply_tariff(base, tariff, day)
        bill = components.site_day(inputs, comps, tariff)["bill"][which]
        rows.append(
            {
                "key": key,
                "name": tariff.name.split(" · ", 1)[1],
                "plan": "usual times" if which == "usual" else "Offpeak plan",
                "eur_day": bill["total"],
                "eur_year": round(bill["total"] * 365),
                "ct_per_kwh": bill["ct_per_kwh"],
                "available": key != "module3" or steerable,
                "tariff": tariff,
            }
        )
    return sorted(rows, key=lambda r: (not r["available"], r["eur_day"]))
