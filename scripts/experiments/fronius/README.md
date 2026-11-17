# Experiment: a real house from Fronius Solar.web data

Experimental, homeowner profile only. Nothing here feeds the SME models: a family home uses power differently from a business. The data and every output stay in `data/fronius/`, which Git ignores. Nothing personal is in these files; the location is passed on the command line.

## 1. Get the data

`fetch_solarweb.js`: run it in the browser console on solarweb.com while signed in as the owner. It downloads `fronius_5min.csv` with one row per 5 minutes (UTC). All values are watts, except the battery charge, which is in %.

| Column | Meaning |
|---|---|
| `FromGen` | solar production |
| `ToConsumer` | the house's consumption |
| `FromGenToConsumer` / `FromBattToConsumer` / `FromGridToConsumer` | where the consumption came from |
| `FromGenToBatt` / `FromGenToGrid` | where the solar power went |
| `StateOfChargeAggregated` | battery charge, % |

Move the file to `data/fronius/fronius_5min.csv`.

## 2. Analyse (run from the repository root)

```bash
uv run python scripts/experiments/fronius/fit_orientation.py data/fronius/fronius_5min.csv <lat> <lon>
PYTHONPATH=. uv run python scripts/experiments/fronius/solar_check.py data/fronius/fronius_5min.csv <lat> <lon> data/fronius/solar_check.html
uv run python scripts/experiments/fronius/savings.py data/fronius/fronius_5min.csv data/fronius/prices_de_lu.csv data/fronius/savings.html
```

`<lat> <lon>` are a town centre, not the address.

- **fit_orientation.py** finds the roof's orientation and tilt from the measurements.
  - pvlib models every combination: azimuth 0–355°, tilt 0–60°.
  - The weather is Open-Meteo's measured archive.
  - The best fit is the one that explains the measured hourly production best.
- **solar_check.py** puts the app's PV model (`offpeak/generation/pv.py`) against the measured production, by month and year. It also checks whether heat limits peak power.
- **savings.py** prices the house's real consumption and production on 15-minute day-ahead prices, in four scenarios:
  - A: fixed tariff;
  - B: dynamic tariff, with the house as it ran;
  - D: dynamic tariff, simulated battery on the simple rule;
  - C: dynamic tariff, battery planned by a linear programme over today and tomorrow, using the published day-ahead prices.

  The prices come from `offpeak.markets.energy_charts.fetch_history` (saved as `data/fronius/prices_de_lu.csv`).

## Results for the first house

Measured from 16 Sep 2023 to 16 Nov 2026.

- **Data quality:**
  - complete;
  - totals match Solar.web to the kWh;
  - clock-change days have 23 h and 25 h.
- **Roof:** the data point to south-east, 145° / 26°. The NRW solar cadastre says south-east, 135° / 34°.
- **Solar model against measurement:**
  - The daily correlation is 0.96.
  - The model predicts about 30 % more energy than measured. This comes from the area-wide weather data plus losses on the site.
  - With one site factor, the monthly error is 12 %.
- **Heat:** costs at most a few percent. Peaks are highest in April and May.
- **Savings:**
  - The house already covers 79 % of its own power, so the smart battery saves about 17 €/yr against the same battery on the simple rule.
  - Against the fixed tariff it saves about 30 €/yr.
  - These are upper bounds, because the programme knows the next day's consumption and production.
  - Dynamic tariffs pay off where much power is bought and loads can move: houses without a battery, electric cars, heat pumps, and SMEs.
