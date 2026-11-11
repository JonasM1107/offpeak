"""Solar output from the weather forecast, the simple way.

A panel rated 1 kWp gives about 1 kW when 1000 W/m² of sunlight falls on it. The forecast
already tells us the sunlight on a tilted panel (global tilted irradiance, GTI), so

    kW = GTI / 1000 × kWp × 0.85

The 0.85 ("performance ratio") covers inverter, cable and heat losses. pvlib replaces this
later (docs/PLAN.md section 9.3); this version is good enough for a weekly outlook.
"""

import pandas as pd

PERFORMANCE_RATIO = 0.85


def pv_kw(gti_wm2: pd.Series, kwp: float, performance: float = PERFORMANCE_RATIO) -> pd.Series:
    """Expected solar power in kW per slot. Missing sunlight values stay missing."""
    return gti_wm2 / 1000 * kwp * performance
