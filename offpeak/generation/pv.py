"""Solar power from the weather, with pvlib's PVWatts model (docs/PLAN.md section 9.3).

Before, one fixed factor (0.85) stood for every loss. PVWatts splits the losses up, so each
one can be explained and the result changes with the weather:

1. Light on the panel: Open-Meteo already gives the irradiance on the tilted, turned panel
   (GTI, W/m²), so the geometry (where the sun stands, how the panel faces it) is done.
2. Module temperature (Faiman model): the panel gets hotter than the air in strong sun and
   cooler again in wind. A hot module makes less power.
3. DC power (pvwatts_dc): kWp × irradiance / 1000, minus 0.37 % for every °C the module is
   above 25 °C (plus for every °C below). 0.37 %/°C is PVWatts' standard modern module.
4. System losses (pvwatts_losses): dirt, cable resistance, modules that differ a little,
   ageing in the first year, ratings slightly above the real output. About 8.7 % in total.
   Shading and outages are set to 0: they depend on the site, and we know nothing about them.
5. Inverter (pvlib.inverter.pvwatts): turns DC into AC at about 96 % efficiency, and never
   delivers more than its own rating. Many sites have more panel kWp than inverter kW, so
   the midday peak gets cut off ("clipping").

What it leaves out: snow on the panels, shading, and light reflected away at low sun angles.
The wind we have is at 10 m; the panels sit lower, where it blows less, so the model cools
them slightly too much (about 1-2 % too much power on a windy, sunny day).

Example for 8 kWp at 1000 W/m² (before: always 6.8 kW, factor 0.85):
- module at 25 °C: 7.0 kW (0.88)
- air at 30 °C, little wind: the module reaches about 61 °C, 6.1 kW (0.76)
- air at 0 °C: the module reaches about 31 °C, 6.9 kW (0.86)
Weak winter sun warms the module much less: 400 W/m² at 2 °C gives 2.9 kW (before: 2.7 kW).
"""

import numpy as np
import pandas as pd
import pvlib

TEMP_COEFF = -0.0037  # power change per °C above 25 °C (PVWatts "standard" module)
INVERTER_EFFICIENCY = 0.96  # PVWatts' nominal inverter efficiency
SYSTEM_LOSSES_PCT = pvlib.pvsystem.pvwatts_losses(shading=0, availability=0)  # about 8.7 %


def pv_kw(
    poa_wm2: pd.Series,
    kwp: float,
    temp_c: pd.Series | None = None,
    wind_ms: pd.Series | None = None,
    inverter_kw: float | None = None,
) -> pd.Series:
    """AC power in kW for each value of `poa_wm2` (irradiance on the panel, W/m²).

    temp_c: air temperature, °C. Without it the module is taken to be at 25 °C (the rating
    temperature), so only the system and inverter losses apply.
    wind_ms: wind speed, m/s; without it 1 m/s, the Faiman model's default.
    inverter_kw: the inverter's AC rating; without it the same as kwp (no clipping in practice).
    Missing or negative irradiance counts as no sun (0 kW).
    """
    poa = pd.Series(poa_wm2, dtype=float)
    index = poa.index
    poa = poa.fillna(0).clip(lower=0).to_numpy()
    if kwp <= 0 or (inverter_kw is not None and inverter_kw <= 0):
        return pd.Series(0.0, index=index)  # no panels or no inverter: no power
    if temp_c is None:
        temp_cell = np.full(len(poa), 25.0)
    else:
        air = pd.Series(temp_c, dtype=float).to_numpy()
        wind = 1.0 if wind_ms is None else pd.Series(wind_ms, dtype=float).fillna(1.0).to_numpy()
        # hours without a temperature: module at 25 °C, as if no temperature were given
        temp_cell = np.where(np.isnan(air), 25.0, pvlib.temperature.faiman(poa, air, wind))
    dc = pvlib.pvsystem.pvwatts_dc(poa, temp_cell, pdc0=kwp, gamma_pdc=TEMP_COEFF)
    dc = dc * (1 - SYSTEM_LOSSES_PCT / 100)
    # pvlib's inverter takes its DC input limit; its AC limit is that × the efficiency
    ac_limit = kwp if inverter_kw is None else inverter_kw
    ac = pvlib.inverter.pvwatts(dc, pdc0=ac_limit / INVERTER_EFFICIENCY)
    return pd.Series(np.clip(ac, 0, None), index=index, dtype=float)
