"""Experiment: the app's PV model (offpeak.generation.pv) against the measured production.

Usage (from the repo root): PYTHONPATH=. uv run python solar_check.py <csv> <lat> <lon> <out.html>
Uses the weather cache written by fit_orientation.py.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
from plotly.subplots import make_subplots

from offpeak.generation.pv import pv_kw

csv, lat, lon, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
CACHE = Path("data/fronius/weather_archive.json")  # written by fit_orientation.py
KWP = 8.0

df = pd.read_csv(csv, parse_dates=["ts_utc"]).set_index("ts_utc")
gen_w = df["FromGen"].fillna(0)
pv = (gen_w / 1000).resample("1h").mean()

h = json.loads(CACHE.read_text())["hourly"]
w = pd.DataFrame(
    {k: v for k, v in h.items() if k != "time"}, index=pd.to_datetime(h["time"], unit="s", utc=True)
)
rad = w[["shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation"]].shift(-1)
w = w.assign(ghi=rad.iloc[:, 0], dni=rad.iloc[:, 1], dhi=rad.iloc[:, 2]).dropna()
data = w.join(pv.rename("pv"), how="inner").dropna()
mid = data.index + pd.Timedelta(minutes=30)
sun = pvlib.solarposition.get_solarposition(mid, lat, lon).set_axis(
    data.index
)  # same index as data


def model(az, tilt):
    poa = (
        pvlib.irradiance.get_total_irradiance(
            tilt, az, sun["apparent_zenith"], sun["azimuth"], data["dni"], data["ghi"], data["dhi"]
        )["poa_global"]
        .fillna(0)
        .clip(lower=0)
    )
    return pv_kw(
        pd.Series(poa.to_numpy(), index=data.index),
        KWP,
        data["temperature_2m"],
        data["wind_speed_10m"],
    )


data["cadastre"] = model(135, 34).to_numpy()
data["fitted"] = model(145, 26).to_numpy()
local = data.index.tz_convert("Europe/Berlin")

# monthly and yearly energy (kWh): hourly mean kW × 1 h
month = data[["pv", "cadastre", "fitted"]].groupby(local.to_period("M")).sum()
month = month[month.index.to_timestamp() >= pd.Timestamp("2023-10-01")]  # whole months only
month = month[month.index.to_timestamp() < pd.Timestamp("2026-11-01")]
year = data[["pv", "cadastre", "fitted"]].groupby(local.year).sum()
print("yearly kWh (measured / model cadastre / model fitted):")
print(year.round(0).to_string())
full = month.sum()
print(
    f"\nwhole months Oct 2023–Oct 2026: measured {full.pv:.0f} kWh, "
    f"model {full.cadastre:.0f} kWh (cadastre), "
    f"ratio {full.pv / full.cadastre:.2f}"
)
mape = ((month.cadastre - month.pv).abs() / month.pv).mean() * 100
print(f"monthly error before correction: {mape:.0f} % on average")
factor = full.pv / full.cadastre
corr = ((month.cadastre * factor - month.pv).abs() / month.pv).mean() * 100
print(f"monthly error after one constant factor ({factor:.2f}): {corr:.0f} % on average")

# daily scatter
daily = data[["pv", "cadastre"]].groupby(local.date).sum()
r = np.corrcoef(daily.pv, daily.cadastre)[0, 1]
print(f"daily kWh correlation measured vs model: {r:.3f}")

# heat: peak power by month from the 5-minute data, and power at strong sun vs temperature
l5 = gen_w.index.tz_convert("Europe/Berlin")
peak = (gen_w / 1000).groupby([l5.year, l5.month]).max()
peak_by_month = (gen_w / 1000).groupby(l5.month).quantile(0.999)
print("\nhighest power by calendar month (99.9 % quantile of 5-minute values, kW):")
print(peak_by_month.round(2).to_string())
print(
    f"absolute maximum: {gen_w.max() / 1000:.2f} kW "
    f"on {gen_w.idxmax().tz_convert('Europe/Berlin'):%Y-%m-%d %H:%M}"
)
strong = data["dni"] > 600
poa = pvlib.irradiance.get_total_irradiance(
    34, 135, sun["apparent_zenith"], sun["azimuth"], data["dni"], data["ghi"], data["dhi"]
)["poa_global"]
sel = strong & (poa > 700)
d = data[sel].assign(per_poa=data.loc[sel, "pv"] / poa[sel] * 1000)  # kW per 1000 W/m² on the panel
bins = pd.cut(d["temperature_2m"], [-10, 5, 10, 15, 20, 25, 30, 40])
print("\nmeasured kW per 1000 W/m² on the panel, by air temperature (strong sun only):")
print(d.groupby(bins, observed=True)["per_poa"].agg(["mean", "count"]).round(2).to_string())

fig = make_subplots(
    rows=2,
    cols=1,
    subplot_titles=("Monthly production: measured vs model (kWh)", "Highest power by month (kW)"),
    vertical_spacing=0.14,
)
x = month.index.to_timestamp()
fig.add_bar(x=x, y=month.pv, name="Measured", marker_color="#3A3733", row=1, col=1)
fig.add_scatter(
    x=x,
    y=month.cadastre,
    name="Model (south-east 34°, 8 kWp)",
    line=dict(color="#FF5F00", width=3),
    row=1,
    col=1,
)
fig.add_scatter(
    x=x,
    y=month.cadastre * factor,
    name=f"Model × {factor:.2f} (site losses)",
    line=dict(color="#FF5F00", dash="dot"),
    row=1,
    col=1,
)
fig.add_bar(
    x=[f"{y}-{m:02d}" for y, m in peak.index],
    y=peak.values,
    marker_color="#C9C4BB",
    name="Monthly peak",
    row=2,
    col=1,
)
fig.update_layout(
    template="plotly_white",
    height=760,
    font=dict(family="Inter, sans-serif"),
    legend=dict(orientation="h", y=1.08),
)
fig.write_html(out, include_plotlyjs="cdn")
print("chart:", out)
