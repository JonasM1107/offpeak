"""Experiment: find the PV roof's orientation and tilt from measured production.

Usage: uv run python fit_orientation.py <csv> <lat> <lon>
Writes hourly weather to a cache next to this script, prints the best fits.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import requests

csv, lat, lon = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
HERE = Path(__file__).parent
CACHE = Path("data/fronius/weather_archive.json")  # git-ignored, like the measurements

# 1. measured production, hourly mean kW, keyed on the hour start (UTC)
df = pd.read_csv(csv, parse_dates=["ts_utc"]).set_index("ts_utc")
pv = (df["FromGen"].fillna(0) / 1000).resample("1h").mean()
start, end = pv.index.min().date(), (pv.index.max() - pd.Timedelta(days=1)).date()

# 2. measured weather from Open-Meteo's archive (ERA5-based reanalysis)
if not CACHE.exists():
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": str(start),
            "end_date": str(end),
            "hourly": ",".join(
                [
                    "shortwave_radiation",
                    "direct_normal_irradiance",
                    "diffuse_radiation",
                    "temperature_2m",
                    "wind_speed_10m",
                ]
            ),
            "timezone": "GMT",
            "timeformat": "unixtime",
            "wind_speed_unit": "ms",
        },
        timeout=60,
    )
    r.raise_for_status()
    CACHE.write_text(r.text)
h = json.loads(CACHE.read_text())["hourly"]
w = pd.DataFrame(
    {k: v for k, v in h.items() if k != "time"}, index=pd.to_datetime(h["time"], unit="s", utc=True)
)
# radiation is the mean of the hour BEFORE the timestamp: move it to the hour start
rad = w[["shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation"]].shift(-1)
w = w.assign(ghi=rad.iloc[:, 0], dni=rad.iloc[:, 1], dhi=rad.iloc[:, 2]).dropna()
data = w.join(pv.rename("pv"), how="inner").dropna()

# sun position at the middle of each hour
mid = data.index + pd.Timedelta(minutes=30)
sun = pvlib.solarposition.get_solarposition(mid, lat, lon)
day = (sun["apparent_elevation"].to_numpy() > 5) & (data["ghi"].to_numpy() > 20)
data, sun = data[day], sun[day]
print(f"{len(data)} daylight hours from {data.index.min():%Y-%m-%d} to {data.index.max():%Y-%m-%d}")


def poa(az, tilt):
    return pvlib.irradiance.get_total_irradiance(
        tilt,
        az,
        sun["apparent_zenith"].to_numpy(),
        sun["azimuth"].to_numpy(),
        data["dni"].to_numpy(),
        data["ghi"].to_numpy(),
        data["dhi"].to_numpy(),
    )["poa_global"]


def fit(x, y):
    """Best scale k for y ≈ k·x, and the share of variance explained."""
    k = float(x @ y / (x @ x))
    res = y - k * x
    return k, 1 - float(res @ res) / float(((y - y.mean()) ** 2).sum())


y = data["pv"].to_numpy()
rows = []
for az in range(0, 360, 5):
    for tilt in range(0, 62, 2):
        x = np.asarray(poa(az, tilt))
        k, r2 = fit(x, y)
        rows.append((az, tilt, r2, k * 1000))  # k·1000 ≈ kW per 1000 W/m², i.e. effective kWp
res = pd.DataFrame(rows, columns=["azimuth", "tilt", "r2", "kwp_eff"]).sort_values(
    "r2", ascending=False
)
print("\nbest single plane (azimuth: 90 east, 135 south-east, 180 south):")
print(res.head(8).to_string(index=False))
for name, az, tilt in (
    ("cadastre south-east 34°", 135, 34),
    ("south 34°", 180, 34),
    ("north 34°", 0, 34),
):
    r = res[(res.azimuth == az) & (res.tilt == tilt)].iloc[0]
    print(f"{name:24s} r2 {r.r2:.3f}  effective kWp {r.kwp_eff:.2f}")

# peak hour check: in which local hour does production peak on clear days?
local = data.index.tz_convert("Europe/Berlin")
clear = data["dni"] > 500
print("\nmean kW by local hour on clear hours (summer, Apr–Sep):")
summer = clear & local.month.isin([4, 5, 6, 7, 8, 9])
print(data[summer].groupby(local[summer].hour)["pv"].mean().round(2).to_string())
res.to_csv("data/fronius/orientation_fit.csv", index=False)
