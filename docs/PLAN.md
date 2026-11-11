# Offpeak — Build Plan v2

**Team:** Jonas, Mika, Noa · **Course:** Introduction to Programming, Nova SBE · **Written:** 11 Nov 2026
**Status:** draft for team review. Nothing in here is built yet. Dashboard technology decided on 11 Nov: **Streamlit**.
**Based on:** *EnergyPilot — 20-Day Build Plan* (4 Nov 2026). This version replaces it. "EnergyPilot" was the working name; this plan uses the repo name, **Offpeak**.

Offpeak tells a small business every afternoon **when to use electricity tomorrow and how much that saves**. It combines tomorrow's spot prices, a forecast of the site's own solar (and optionally wind) generation, and the site's consumption. Germany is the first market; the design lets us switch on Portugal and any other EU price zone without rewriting code.

---

## Contents

1. [What changed from the EnergyPilot PDF, and why](#1-what-changed-from-the-energypilot-pdf-and-why)
2. [Product and scope](#2-product-and-scope)
3. [Decisions to confirm at kickoff](#3-decisions-to-confirm-at-kickoff)
4. [Architecture and stack](#4-architecture-and-stack)
5. [Data sources and API checklist](#5-data-sources-and-api-checklist)
6. [Multi-market design: Germany, Portugal, EU](#6-multi-market-design-germany-portugal-eu)
7. [Data model](#7-data-model)
8. [Module contracts](#8-module-contracts)
9. [Core logic: tariffs, optimiser, forecasts, ML](#9-core-logic-tariffs-optimiser-forecasts-ml)
10. [Dashboard](#10-dashboard)
11. [Team split](#11-team-split)
12. [GitHub and Claude workflow](#12-github-and-claude-workflow)
13. [Timeline: 20 days, 5 phases, 5 gates](#13-timeline-20-days-5-phases-5-gates)
14. [Testing and quality](#14-testing-and-quality)
15. [Limits and constraints](#15-limits-and-constraints)
16. [Risks, fallbacks and cut list](#16-risks-fallbacks-and-cut-list)
17. [Budget](#17-budget)
18. [Presentation and demo](#18-presentation-and-demo)
19. [Appendices](#19-appendices)

---

## 1. What changed from the EnergyPilot PDF, and why

The PDF is a solid outline. These are the points where this plan deliberately differs. The first three matter most.

| # | Concern with the PDF | What this plan does instead |
|---|---|---|
| 1 | **It is built for Portugal.** Prices come from OMIE, load data from E-REDES, fuel prices from DGEG/ERSE, tariffs follow the Portuguese formula. | Germany first: prices from Energy-Charts/SMARD, load shapes from BDEW standard profiles, German tariff components. Portugal becomes the second market, switched on by configuration (section 6). |
| 2 | **The stack is heavy for this team and course.** Next.js (TypeScript), Supabase Edge Functions (Deno), pg_cron and Realtime, plus Python. That is three languages and five services. Our course taught Python, Streamlit, uv and pytest. | Decided: Python everywhere, a Streamlit dashboard, Supabase used as a plain Postgres database, GitHub Actions for scheduled jobs. One language, one place for logic. See decision D1; Appendix A records what Next.js would have changed. |
| 3 | **Role C is overloaded and the dashboard comes last.** C owns the schema, auth, tariff engine, optimiser, the whole front end, SME recruitment, the business case and the deck. The main dashboard work is squeezed into Days 15–17. | Each person owns a vertical slice from API to their own dashboard page. The dashboard exists from Day 3 and grows every day. The tariff engine moves to Markets. Non-code work is spread across all three (section 11). |
| 4 | **"Euros saved" has no baseline.** The flexible-load table stores the allowed window but not when the load usually runs, so there is nothing to compare against. | Every flexible load stores a `usual_start`. Saving = cost at the usual time − cost at the recommended time. |
| 5 | **The optimiser can raise the bill.** Larger German business customers pay a demand charge on their highest 15-minute peak of the year. Moving everything into the cheapest slot can create a new peak that costs more than the shift saves. It also ignores what exported solar earns. | The optimiser has a peak cap per site and prices imports and exports separately (section 9.2). |
| 6 | **The target market is narrow.** Only businesses already on a spot-linked tariff benefit. Most small German businesses are on fixed prices. | Three customer modes (section 2.2): dynamic tariff, fixed tariff with solar, and a tariff check that answers "would a dynamic tariff have been cheaper for you?". |
| 7 | **Three ML models in six days.** Price, consumption and a solar correction model. | One ML model done properly (price outlook for D+2 to D+7) with an honest baseline comparison. Consumption starts as "same weekday last week" and only gets a model if we have enough real data. Solar stays physical. |
| 8 | **The demo depends on live timing and on sunshine.** It needs prices to publish during the slot, and in late November German solar output is small. | A replay mode: pick any past date and see what Offpeak would have recommended and saved. It is also the backtest. The live update becomes a bonus, not a dependency. |
| 9 | **The heat-cost comparison is a second product.** Gas vs LPG vs heating oil vs heat pump needs four more data sources and has nothing to do with load shifting. | Moved to the bottom of the stretch list. |
| 10 | **The bakery example is weak.** A bakery cannot bake at 13:00 when the bread is needed at 06:00. | Target loads that really can move: vehicle charging, cold storage, compressed air, hot water, laundry, pumps (section 2.1). |
| 11 | **Waiting 14 days to collect forecasts.** | Not needed for weather: Open-Meteo's previous-runs API returns what the forecast said 1 to 7 days earlier (tested). Price history is also fully backfillable. |

---

## 2. Product and scope

### 2.1 Who it is for

A small or medium business in Germany with electrical loads it can move in time, with or without rooftop solar or a small wind turbine. Good first pilots, because their loads really are flexible:

- farms (milk cooling, feed mixing, irrigation; often have solar, sometimes wind)
- workshops and small manufacturers (compressed air, electric vehicle or forklift charging)
- hotels and laundries (washing, drying, hot water)
- food retail and cold storage (pre-cooling)

### 2.2 Three customer modes

| Mode | Who | What Offpeak optimises |
|---|---|---|
| **Dynamic** | Business on a spot-linked tariff | Run flexible loads in the cheapest allowed 15-minute slots, using own solar first |
| **Fixed + solar** | Business on a fixed price with its own generation | Move loads into hours with solar surplus, because self-used solar is worth far more than exported solar |
| **Tariff check** | Business deciding whether to switch | "With your load profile, a dynamic tariff would have cost €X against your fixed €Y over the last 30 days" |

Since 2025 German suppliers have to offer a dynamic tariff to customers with a smart meter, so the third mode is a natural way in.

### 2.3 What it outputs

- **Tomorrow:** price per 15-minute slot and a schedule ("charge the vans 11:30–15:30 instead of 18:00–22:00"), with the saving in euros
- **Solar:** a 7-day generation forecast against expected consumption
- **Week:** a 7-day price outlook. Day+1 is published prices; Day+2 to Day+7 come from our model, shown as a range
- **Savings:** what following the schedule would have saved over the last 30 days

### 2.4 Scope

| Priority | Items |
|---|---|
| **Must** | German day-ahead prices (15-minute) · weather and solar forecast · load import plus standard-profile fallback · German tariff engine · optimiser with savings · pages: Tomorrow, Solar & Load, Site setup, Data & status · seeded demo site · scheduled jobs · tests and CI · zone-agnostic code |
| **Should** | Portugal switched on · price outlook model with baseline comparison · Week page · replay mode and 30-day backtest · tariff check · German/English toggle |
| **Could** | Wind generation · battery what-if · CO₂ / renewable-share signal · daily email or calendar feed of the schedule · solar payback estimate for sites without panels · heat-cost comparison |
| **Not now** | Controlling devices automatically · intraday market · billing-grade accuracy · mobile app |

### 2.5 Definition of done

- Scheduled jobs have run unattended for at least 10 consecutive days before the presentation
- Recommendations for tomorrow appear on their own after prices are published
- A 30-day backtest on one real (or clearly labelled synthetic) business shows euros saved
- The price model is compared to a naive baseline, and we report the result whichever way it goes
- A second price zone (Portugal) works without changing dashboard code
- Every teammate can explain every module they own, line by line

---

## 3. Decisions to confirm at kickoff

| # | Decision | Recommendation | Why it matters |
|---|---|---|---|
| **D1** | Dashboard technology: Streamlit or Next.js | **Decided 11 Nov: Streamlit** | Changes who builds what. See below. |
| **D2** | Who takes role A, B and C | Jonas takes C; Mika and Noa pick A or B by interest (section 11) | Needed before issues are assigned |
| **D3** | Presentation date, slot length, and the grading rules | Find out on Day 1 | The PDF is dated 4 Nov. If fewer than 20 days are left, the cut list (section 16) says what to drop. Also check: may parts be non-Python, is ML graded, must each of us explain our code? |
| **D4** | Pilot business | Each of us asks three contacts on Day 1 | The biggest risk in the project is having no real load data |
| **D5** | Repo stays public | Yes | Branch protection and unlimited Actions minutes are free on public repos. Consequence: no secrets and no pilot data in the repo, ever |

**D1 in detail (decided: Streamlit).** Both options use the same database, the same Python package and the same jobs. Only the screen layer differs. The comparison stays here as the record of why.

| | Streamlit (chosen) | Next.js on Vercel (as in the PDF) |
|---|---|---|
| Language | Python, same as the course | TypeScript and React, new to the team |
| Who can build pages | All three, each their own | Realistically one person |
| "Change a load window and see the schedule update" | Free: the page calls the optimiser directly | Needs a separate Python API, or the optimiser written twice |
| Live update when prices publish | Page re-checks every 60 seconds | True push via Supabase Realtime |
| Look | Clean data app; professional with a theme and good charts | Full product look, best mobile layout |
| Login and multi-customer | Simple (demo site open, pilot behind a passcode) | Proper accounts with row-level security |
| Explaining the code in an exam | Straightforward | Hard for code we did not learn to read |
| Extra effort | — | Roughly 4–5 person-days more |

The rest of this plan is written for Streamlit. Appendix A lists what would change with Next.js, in case we ever revisit the choice.

---

## 4. Architecture and stack

```
 Data sources                 Scheduled jobs                Database              Dashboard
 ─────────────                (GitHub Actions, Python)      (Supabase Postgres)   (Streamlit)

 Energy-Charts / SMARD ──┐
 ENTSO-E / OMIE ─────────┼──▶ ingest_prices ───────────▶ prices_da ──────┐
 Open-Meteo ─────────────┼──▶ ingest_weather ──────────▶ weather_fc      │
 Load CSV upload ────────┼──▶ (via Site setup page) ───▶ load_actuals    ├──▶ Tomorrow
 PVGIS ──────────────────┘                                               │    Week
                              run_forecasts ───────────▶ pv_fc, load_fc, │    Solar & Load
                              train_price_model (weekly)   price_fc      │    Savings / Replay
                              run_optimizer ───────────▶ recommendations ┘    Site setup
                              every job ───────────────▶ job_runs             Data & status
```

All logic lives in one Python package, `offpeak/`. Jobs and dashboard pages both import it. Nothing is implemented twice.

| Layer | Tool | Why |
|---|---|---|
| Language and tooling | Python 3.12, `uv`, `ruff`, `pytest` | Same as the course |
| Data work | pandas, requests | |
| Solar model | `pvlib` | Standard physical model, no training needed |
| Load shapes | `demandlib` (BDEW standard load profiles) | German fallback when there is no meter data |
| ML | scikit-learn, LightGBM | Fast, good on tabular data, gives quantiles |
| Holidays | `holidays` | Covers every EU country and each German state |
| Database | Supabase Postgres, region Frankfurt | Free, reachable from both jobs and dashboard, EU-hosted |
| Database access | SQLAlchemy + psycopg, all inside `offpeak/db.py` | `pd.read_sql` works; one module owns every query |
| Scheduling and CI | GitHub Actions | Free on a public repo |
| Dashboard | Streamlit + Plotly | Decided (D1): the language we know, and all three of us can build pages |
| Hosting | Streamlit Community Cloud | Free, deploys from the repo |

**What we drop from the PDF's stack:** Supabase Edge Functions, pg_cron, Realtime, Vercel, and the Supabase JavaScript client. With a Python dashboard none of them is needed.

**How prices arrive on time without Edge Functions.** The German day-ahead auction publishes around 13:00 CET (12:00 in Lisbon).

1. A GitHub Actions job runs every 15 minutes between 12:45 and 15:00 CET. It does nothing if tomorrow's prices are already stored.
2. GitHub's schedule can start late. So the dashboard has a fallback: if tomorrow's prices are missing after 12:45 CET, the page calls the same Python fetch function itself, stores the result, and shows it.
3. The workflow also has a manual "Run workflow" button for the demo.

**Conventions**

- Every timestamp is stored as UTC `timestamptz`, one row per 15-minute slot start. Local time appears only on screen.
- Market prices are stored in €/MWh, tariffs in €/kWh. The dashboard shows **ct/kWh**, which is what a business owner reads on an invoice.
- Panel direction is stored as a compass bearing (180 = south). Open-Meteo and PVGIS use 0 = south, `pvlib` uses 180 = south; each adapter converts.
- Every job writes a row to `job_runs`, success or failure, so problems are visible on the Data & status page.
- Database connections use Supabase's **session pooler** address. The direct address is IPv6-only and GitHub's runners cannot reach it.
- Secrets live in GitHub Actions secrets, Streamlit secrets and each person's local `.env`. `.env.example` is committed, `.env` is not.

---

## 5. Data sources and API checklist

All calls marked "Tested" were made on 11 Nov 2026 and returned data. Everything is free.

### 5.1 Prices

| Source | What we take | Access | Status | Owner |
|---|---|---|---|---|
| **Energy-Charts** (Fraunhofer ISE) — primary for Germany | Day-ahead price, zone DE-LU, 15-minute | `api.energy-charts.info/price?bzn=DE-LU&start=…&end=…`, no key. Licence CC BY 4.0 for DE-LU | **Tested.** 96 slots per day. Tomorrow's prices were available at 14:57 CET | B |
| **SMARD** (Bundesnetzagentur) — backup for Germany | Same prices (series 4169), plus national load and generation | `smard.de/app/chart_data/4169/DE-LU/…`, no key, CC BY 4.0. An index file lists weekly data files | **Tested** (index) | B |
| **ENTSO-E Transparency** — any EU zone | Day-ahead prices for every zone; day-ahead load, wind and solar forecasts | Free token. Register, then request API access. Python library `entsoe-py` | **Needs token** (endpoint answers 401 without one). Request on Day 1; it can take several working days | B |
| **OMIE** — Portugal and Spain | Day-ahead price | Public text files, no key | **Tested.** The file has two price columns (Portugal and Spain); confirm the order | B |
| aWATTar | German day-ahead price | No key | Tested, but hourly only. Not used | — |

Two findings from testing:

- **Energy-Charts rate-limits quickly.** The sixth call in a few seconds was refused ("Too Many Requests"). One call per job run, a pause between backfill calls, and retry with backoff.
- **Energy-Charts returns Portuguese and Spanish prices but marks them "for private and internal use only".** For Iberia we use OMIE or ENTSO-E instead.

A fact worth opening the pitch with: between 10 and 12 Nov 2026 the German day-ahead price ranged from **€122 to €535 per MWh** (12 to 53 ct/kWh before fees), a spread of more than four times within three days.

### 5.2 Weather and generation

| Source | What we take | Access | Status | Owner |
|---|---|---|---|---|
| **Open-Meteo forecast** | Irradiance on the tilted panel (GTI), temperature, cloud cover, wind speed at 80–120 m | `api.open-meteo.com/v1/forecast`, no key. Free for non-commercial use, under 10,000 calls a day, attribution required | **Tested**, including 15-minute values | A |
| **Open-Meteo previous runs** | What the forecast said 1 to 7 days before | `previous-runs-api.open-meteo.com` | **Tested.** Lets us measure forecast error immediately | A |
| **Open-Meteo archive and satellite radiation** | Actual weather and irradiance, for backtests | `archive-api…` and `satellite-api.open-meteo.com` | **Tested**, both | A |
| **PVGIS 5.3** (EU Joint Research Centre) | Typical annual yield, for sanity checks and payback | `re.jrc.ec.europa.eu/api/v5_3/PVcalc`, no key, server-side calls only | **Tested.** 30 kWp in Munich → about 33,900 kWh a year (1,130 kWh per kWp) | A |

Notes: ask Open-Meteo for wind in m/s (the default is km/h). Use the 15-minute values for the next 48 hours and hourly values split into four beyond that.

### 5.3 Consumption

| Source | What we take | Access | Status | Owner |
|---|---|---|---|---|
| **Pilot business meter data** | 15-minute load profile ("Lastgang") | The business exports CSV or Excel from its supplier's or metering operator's portal. Sites above 100,000 kWh a year are metered every 15 minutes; smaller ones need a smart meter | **Open.** Ask on Day 1 | A |
| **BDEW standard load profiles** | Typical shape by sector (G0–G6 business, L0–L2 farms), scaled to annual kWh | Python package `demandlib`, works offline | Not tested yet | A |
| **Open Power System Data, "household data"** | Measured profiles of a few small businesses with solar in southern Germany | Free download | Not tested yet. Candidate for a realistic stand-in if no pilot appears | A |

Formats differ between suppliers, so the importer lets the user map columns (timestamp, value, unit) instead of assuming one layout. If the file gives average kW per 15 minutes, kWh = kW × 0.25.

### 5.4 Optional

| Source | Use | Status |
|---|---|---|
| Energy-Charts `/signal` and `/public_power` | Renewable share and "green hours" badge | Not tested |
| EU Weekly Oil Bulletin, gas hub prices | Heat-cost comparison (stretch) | Not tested |

### 5.5 What to ask a pilot business for

1. The 15-minute load profile, ideally 12 months, at least 30 days
2. The latest invoice or contract summary: tariff type and every price component
3. Solar system, if any: kWp, tilt, direction, and an inverter export if they have one
4. Loads they could move: name, power in kW, duration, earliest start, latest end, **usual start time**
5. One sentence of written consent to use the data, anonymised, in a university project

---

## 6. Multi-market design: Germany, Portugal, EU

The rule: **a market is data, not code.** No `if country == "DE"` anywhere outside the adapter files.

| Layer | Germany (now) | Portugal (next) | Any other EU zone |
|---|---|---|---|
| Day-ahead prices | Energy-Charts, SMARD as backup | OMIE files | ENTSO-E API |
| Weather, solar, wind | Open-Meteo, PVGIS | same | same |
| Fallback load shape | BDEW profiles | E-REDES consumption profiles | Generic profile or upload |
| Meter data | "Lastgang" CSV/Excel | E-REDES Excel export | Upload with column mapping |
| Tariff formula | spot + margin + grid fee + levies + electricity tax | (OMIE + margin) × (1 + losses) + grid access tariff | Built from the same component types |
| Holidays | `holidays`, per federal state | `holidays`, PT | `holidays` |
| Time zone | Europe/Berlin | Europe/Lisbon | From the zone row |

How it is built:

- A `zones` table holds one row per price zone: code, country, time zone, ENTSO-E code, which price source to use, default tariff components.
- Every site points to a zone. Every function takes the zone as an argument.
- Each price source is one file implementing the same function (section 8). Adding a source means adding a file.
- Tariffs are a list of components stored as JSON, so the German and Portuguese formulas are two configurations of one engine.

**Acceptance test:** add a second demo site in Lisbon and the Tomorrow page works with no change to page code.

Things that differ per market and need care: the "delivery day" runs midnight to midnight in *market* time (CET for both Germany and Iberia, although Portugal's clocks are an hour behind); 15-minute prices only exist since October 2025, older history is hourly; taxes and levies change every January.

---

## 7. Data model

Twelve tables. Every time series is keyed on the slot start in UTC.

| Table | Purpose | Key columns | Written by |
|---|---|---|---|
| `zones` | One row per price zone | `code`, `country`, `tz`, `eic`, `price_source`, `tariff_defaults` (json) | C (seed) |
| `sites` | One row per business location | `id`, `name`, `zone`, `lat`, `lon`, `state`, `sector`, `annual_kwh`, `peak_cap_kw`, `has_pv`, `pv_kwp`, `tilt_deg`, `azimuth_deg`, `has_wind`, `wind_kw`, `hub_height_m` | Site setup page |
| `tariffs` | Price formula per site | `site_id`, `type` (dynamic / fixed), `components` (json), `fixed_eur_kwh`, `export_type`, `export_eur_kwh`, `valid_from` | Site setup page |
| `flexible_loads` | Loads the optimiser may move | `site_id`, `name`, `kw`, `duration_min`, `earliest`, `latest`, **`usual_start`**, `weekdays` | Site setup page |
| `prices_da` | Published day-ahead prices | `ts`, `zone`, `eur_mwh`, `resolution_min`, `source` — key (`ts`, `zone`) | B |
| `weather_fc` | Weather forecast per site | `site_id`, `run_at`, `ts`, `gti_wm2`, `temp_c`, `cloud_pct`, `wind_ms` | A |
| `load_actuals` | Metered or profile consumption | `site_id`, `ts`, `kwh`, `source` (meter / profile) | A |
| `pv_fc`, `load_fc` | Generation and consumption forecasts | `site_id`, `run_at`, `ts`, `kw` or `kwh`, `model_version` | A |
| `price_fc` | Price outlook D+2 to D+7 | `run_at`, `ts`, `zone`, `p10`, `p50`, `p90`, `model_version` | B |
| `recommendations` | What the business should do | `site_id`, `for_date`, `load_id`, `start_ts`, `end_ts`, `usual_cost_eur`, `cost_eur`, `saving_eur`, `details` (json) | C |
| `job_runs` | Log of every job and model run | `job`, `started_at`, `finished_at`, `status`, `rows_written`, `mae`, `baseline_mae`, `message` | all |

Differences from the PDF: `zones` is new; `sites` gains zone, sector, peak cap and wind fields; `flexible_loads` gains `usual_start`; `tariffs` handles fixed prices and export; `fuel_prices` is dropped with the heat comparison; the two log tables become one.

Forecast tables keep `run_at` so we can later check a forecast against what happened. To stay small, keep one run per day.

Migrations are numbered SQL files in `db/migrations/`. Only C merges them, and each one is applied to Supabase by hand until that becomes annoying.

---

## 8. Module contracts

These signatures are agreed on Day 2 and then treated as fixed. Everyone codes against them and against the seeded demo data, so nobody waits for anyone else's pipeline.

```python
# offpeak/markets/  (B) — one file per source, same function
fetch_day_ahead(zone: str, start: date, end: date) -> DataFrame   # ts, eur_mwh, resolution_min, source

# offpeak/tariffs/  (B)
slot_prices(site: Site, tariff: Tariff, prices: DataFrame) -> DataFrame   # ts, import_eur_kwh, export_eur_kwh

# offpeak/weather/ and offpeak/generation/  (A)
fetch_weather(site: Site, days: int = 7) -> DataFrame             # ts, gti_wm2, temp_c, cloud_pct, wind_ms
pv_forecast(site: Site, weather: DataFrame) -> DataFrame          # ts, kw

# offpeak/load/  (A)
import_load_file(file, mapping: dict) -> DataFrame                # ts, kwh
profile_load(site: Site, start: date, end: date) -> DataFrame     # ts, kwh  (standard profile)
load_forecast(site: Site, history: DataFrame, days: int) -> DataFrame   # ts, kwh

# offpeak/forecast/  (B)
price_outlook(zone: str, run_at: datetime) -> DataFrame           # ts, p10, p50, p90

# offpeak/optimizer/  (C)
optimize(slots: DataFrame, loads: list[FlexibleLoad], peak_cap_kw: float | None) -> Schedule
#   slots: ts, import_eur_kwh, export_eur_kwh, pv_kw, base_load_kw
#   Schedule: recommendations, usual_cost_eur, cost_eur, saving_eur
```

Rules: all `ts` columns are timezone-aware UTC at slot start; functions in `offpeak/` never import Streamlit; only `offpeak/db.py` talks to the database.

---

## 9. Core logic: tariffs, optimiser, forecasts, ML

### 9.1 Tariff engine (B)

Turns a market price into what this site actually pays and earns per slot.

- **Dynamic tariff, Germany:** import price = spot + supplier margin + grid energy fee + levies + electricity tax. Businesses reclaim VAT, so everything is shown net.
- **Dynamic tariff, Portugal:** import price = (OMIE + margin) × (1 + loss factor) + grid access tariff for that period.
- **Fixed tariff:** one price, or a day/night pair.
- **Export price:** a fixed feed-in rate, the spot price minus a fee, or zero. New German solar systems get no feed-in payment in hours with negative prices.

Each formula is a list of components (`per_kwh`, `per_kwh_by_period`, `multiplier`, `per_kw_peak`) stored on the tariff. Default values per country are seeded and must be checked against a real invoice; they change every January.

The fixed per-kWh parts do not change *which* hours are cheapest, but they decide how much self-used solar is worth and how large the saving is in percent, so they need to be right.

### 9.2 Optimiser (C)

Version 1 is a search that anyone on the team can explain:

1. Build tomorrow's 96 slots: import price, export price, solar forecast, base load forecast.
2. Cost of a slot = energy bought × import price − energy exported × export price.
3. Take the flexible loads, largest first. For each one, try every start time inside its allowed window. Skip starts that would push the site above its peak cap. Keep the cheapest. A load placed on solar surplus only "costs" the lost export revenue, so solar hours win automatically.
4. Saving = cost with every load at its `usual_start` − cost with the recommended starts.
5. Write one recommendation per load, with the numbers behind it.

Checks the tests enforce: every load stays inside its window; the recommended plan never costs more than the usual plan; the peak cap is never broken.

Version 2 (stretch) formulates the same problem as a mixed-integer programme with `scipy.optimize.milp`, which is what a battery or interruptible loads need.

**Backtest assumption, stated openly:** a meter shows total consumption, not individual machines. For the 30-day backtest we assume each flexible load ran at its usual time, subtract it to get the base load, and add it back at the recommended time.

### 9.3 Forecasts without ML

- **Solar (A):** `pvlib` converts irradiance on the panel and air temperature into kW, using the PVWatts model. Sanity check: yearly total should land near the PVGIS figure. Known blind spots: snow on panels, fog, shading.
- **Wind (A, stretch):** wind speed at hub height through a generic turbine power curve.
- **Consumption (A):** "same slot, same weekday, last week". With a standard profile instead of meter data, the forecast is the profile itself.

### 9.4 The ML model (B)

One model: the day-ahead price for D+2 to D+7, **hourly**. Forecasting 15-minute detail that far ahead is noise.

- **Model:** LightGBM, trained three times for the 10 %, 50 % and 90 % quantiles so the dashboard can show a range.
- **Features:** hour, weekday, holiday; prices of the last days and the same hour last week; wind speed at 100 m at 6–8 points across northern Germany and solar radiation at points in the south (the two things that move German prices most); temperature.
- **Train on forecasts, not on measured weather.** In use, the model only ever sees forecast weather. The previous-runs API gives historical forecasts, so training matches reality.
- **Validation:** walk forward through time. Never shuffle; that leaks the future.
- **Baselines to beat:** same hour last week, and yesterday's price.
- **Two scores:** mean absolute error, and a decision score: "how often are the model's four cheapest hours of a day among the six truly cheapest?" The second one is what a scheduler cares about.
- **Go / no-go on Day 11:** if the model does not beat the baseline, the Week page shows the baseline and we present that result as it is. Tomorrow's schedule uses published prices and is unaffected.

A consumption model (LightGBM on slot, weekday, holiday, temperature) is only worth building with at least eight weeks of real meter data.

---

## 10. Dashboard

The dashboard and the data connections are the two things the project is judged on, so the dashboard is built from Day 3, not at the end.

### 10.1 Pages

| Page | Owner | What it shows |
|---|---|---|
| **Tomorrow** (start page) | C | One sentence with the answer on top. Cards: saving, cheapest window, most expensive window, expected solar kWh. Chart: price per 15 minutes coloured cheap / normal / expensive, solar forecast behind it, usual and recommended run times as bands. Below: edit a load's window and watch the schedule and saving update. Before publication: "Waiting for tomorrow's prices (around 13:00 CET)" |
| **Week** | B | Seven-day price outlook with the 10–90 % range, clearly labelled as a forecast. Best day and time for a big job. Daily solar outlook |
| **Solar & Load** | A | Solar forecast against consumption, share of solar used on site, expected export. A small panel with recent forecast accuracy |
| **Savings** | C | Replay: pick a past date. Cumulative saving over the last 30 days |
| **Tariff check** (should) | B | Fixed against dynamic cost for this load profile |
| **Site setup** | A + C | Site, zone, solar, tariff, flexible loads (with presets), meter file upload with column mapping |
| **Data & status** | C | Every source with its attribution and last update; recent job runs |

### 10.2 Design rules

- **Answer first.** The top of every page is a sentence a business owner can act on. Charts support it.
- **Their units.** ct/kWh, kWh, euros, local time. Never €/MWh or UTC on screen.
- **Three colours for price**, used the same way everywhere. Negative prices get their own highlight.
- **Every number has a freshness note** ("prices published 13:02"; "solar forecast from 06:00").
- **Every chart has one or two plain sentences** under it saying what it means.
- **No raw errors.** Each page has a designed state for: no load data yet, prices not yet published, a job failed.
- **Demo site is always there.** A seeded farm or workshop near Munich with 30 kWp of solar, usable without login.
- **Presets for flexible loads** (vehicle charging, cold store, compressor, water heater, laundry, pump) so setup takes two minutes.
- **German and English** via one dictionary of strings from the start; adding it later is tedious.

### 10.3 Streamlit specifics

One theme in `.streamlit/config.toml`; shared chart and card functions in `app/ui/` so pages look alike; Plotly for charts; `st.cache_data` with a short lifetime on database reads; a fragment that re-runs every 60 seconds for the "waiting for prices" state; `st.session_state` for what-if edits. The demo site is open; a pilot site sits behind a passcode kept in Streamlit secrets.

---

## 11. Team split

The split is loose. Its only job is that everyone builds a real part and can explain it. Swap tasks whenever it makes sense.

### 11.1 Rough roles

| | **A — Site & Sun** | **B — Markets & ML** | **C — Platform & Optimiser** |
|---|---|---|---|
| Owns | Everything about one site: weather, generation, consumption | Everything about the market: prices, tariffs, the price model | The foundation and the brain: database, jobs, optimiser, app shell |
| Code | `offpeak/weather`, `generation`, `load` | `offpeak/markets`, `tariffs`, `forecast` | `offpeak/db.py`, `optimizer`, `jobs` wiring, `db/`, `.github/`, `app/ui` |
| Pages | Solar & Load, upload part of Site setup | Week, Tariff check | Tomorrow, Savings, Data & status, rest of Site setup |
| Jobs | `ingest_weather`, `run_forecasts` | `ingest_prices`, `train_price_model` | `run_optimizer`, CI |
| Beyond code | Pilot business: data, consent, follow-up | Business case and market size | Integration, demo script, deck lead |
| Suits someone who | likes physical models and talking to the pilot | likes statistics and markets | likes structure and tying things together |

**Suggestion for D2:** Jonas takes C, since he set up the repo and wrote the first plan. Mika and Noa choose A and B by interest.

Shared by all three: write tests for what you build, and have someone else look at your pull request before it is merged.

---

## 12. GitHub and Claude workflow

Mika (`mika-weymann`) and Noa (`noafhintz`) already have access to the repo.

### 12.1 One-time setup (Day 1)

1. Merge a starter commit to `main`: `README.md`, `pyproject.toml` and `uv.lock`, `.gitignore`, `.env.example`, `AGENTS.md`, `CLAUDE.md`, a CI workflow, `CODEOWNERS`, a pull-request template. `main` does not exist until this is pushed.
2. Protect `main`: pull request required, one approval, CI must pass, no force pushes.
3. Turn on secret scanning and push protection (free on public repos).
4. Create labels (`area:site-sun`, `area:markets`, `area:platform`, `stretch`), one milestone per gate, and a project board: Backlog → This phase → In progress → In review → Done.
5. Create the Phase 0 and Phase 1 issues from section 13.
6. Each person: clone, run `uv sync`, copy `.env.example` to `.env`, fill in the database address.

### 12.2 Daily loop

1. Pull the latest `main`.
2. Pick your issue. Create a branch: `feat/<area>-<topic>` or `fix/<area>-<topic>`.
3. Work with Claude in that branch: "implement issue 12, tests first".
4. Run `uv run pytest` and `uv run ruff check`.
5. Ask Claude to open a pull request. It closes the issue.
6. A teammate reviews. Claude can answer review comments and fix CI.
7. Squash-merge. Delete the branch.

### 12.3 Rules

- Keep pull requests small and branches short-lived; it avoids merge conflicts.
- Say in the group chat before changing a shared file (`offpeak/models.py`, `db/migrations/`, `pyproject.toml`).
- Never commit secrets, `.env`, or any pilot data. The repo is public.

### 12.4 Making three Claudes behave like one

- `AGENTS.md` holds the project rules: use `uv`, never `pip`; timestamps are UTC; logic goes in `offpeak/`, never in pages; never edit a test to make it pass; one issue per branch; explain changes in plain language.
- `CLAUDE.md` contains one line, `@AGENTS.md`, so Claude and Codex read the same rules.
- `.claude/settings.json` holds shared permissions so nobody is asked the same questions repeatedly.

### 12.5 Repo layout

```
offpeak/
├── app/                     Streamlit dashboard
│   ├── main.py              navigation and theme
│   ├── pages/               tomorrow.py, week.py, solar_load.py, savings.py, tariff_check.py, site_setup.py, status.py
│   └── ui/                  shared charts, cards, texts (de/en)
├── offpeak/                 all logic, no Streamlit imports
│   ├── models.py  db.py  timeutils.py  config.py
│   ├── markets/             base.py, energy_charts.py, smard.py, entsoe.py, omie.py      (B)
│   ├── tariffs/             engine.py, defaults.py                                       (B)
│   ├── forecast/            features.py, price_model.py, baselines.py, evaluate.py       (B)
│   ├── weather/             open_meteo.py                                                (A)
│   ├── generation/          pv.py, wind.py, pvgis.py                                     (A)
│   ├── load/                importer.py, profiles.py, forecast.py                        (A)
│   ├── optimizer/           schedule.py, savings.py, backtest.py                         (C)
│   └── jobs/                ingest_prices.py, ingest_weather.py, run_forecasts.py, run_optimizer.py, train_price_model.py
├── db/migrations/           001_init.sql, …                                              (C)
├── seed/                    demo sites and demo data                                     (C)
├── tests/                   mirrors offpeak/, plus fixtures/ with saved API responses
├── docs/                    PLAN.md, DATA_DICTIONARY.md, DECISIONS.md
├── .github/                 workflows/ (ci, prices, daily, weekly-train), CODEOWNERS, pull_request_template.md
├── .streamlit/config.toml
└── AGENTS.md  CLAUDE.md  README.md  pyproject.toml  uv.lock  .env.example  .gitignore
```

---

## 13. Timeline: 20 days, 5 phases, 5 gates

Days are working days. If Day 1 is Thursday 12 Nov and we work every day, Day 20 is Tuesday 1 Dec. Move the dates once D3 is known.

### Phase 0 — Setup, access, contracts (Days 1–2)

**Day 1, together (about 90 minutes):** settle D2–D5; merge the starter commit and protect `main`; create the Supabase project in Frankfurt and share the connection details through a password manager; create the issues; request the ENTSO-E token; each person messages three possible pilot businesses using the list in 5.5.

| Day | A — Site & Sun | B — Markets & ML | C — Platform & Optimiser |
|---|---|---|---|
| 1 | Call Open-Meteo for the demo site; turn one day of irradiance into kW with `pvlib`; call PVGIS; plot one BDEW profile with `demandlib` | Download three years of German prices to a local file, one year per call with pauses; compare one day against SMARD; register on ENTSO-E | Migration 001 with all tables; `db.py`; seed script with a demo site and plausible data in every table; Streamlit skeleton reading one table; deploy it |
| 2 | `ingest_weather` job writing `weather_fc` | `ingest_prices` job: backfill, then daily upsert into `prices_da` | CI on pull requests; scheduled workflows for both jobs; `job_runs` helper; app navigation and theme |

Day 2, all: review and agree `models.py` (section 8); fill in the status column in section 5.

**Gate G0:** every source tested or given a fallback · `main` protected and CI running · both jobs have run once from GitHub Actions · the app is live at a public address showing a real price · at least nine businesses contacted · D2–D5 decided.

### Phase 1 — From skeleton to real pipelines (Days 3–8)

| Day | A — Site & Sun | B — Markets & ML | C — Platform & Optimiser |
|---|---|---|---|
| 3 | Solar forecast with `pvlib` into `pv_fc`; check the yearly total against PVGIS | Common adapter interface; Energy-Charts adapter with retry and backoff; SMARD adapter as fallback; clock-change tests | **Tomorrow page v0:** real prices in ct/kWh and local time, with the "waiting" state |
| 4 | Load file importer with column mapping into `load_actuals` | Tariff engine: German components, fixed and dynamic, import and export price per slot | Optimiser v0: cost per slot, cheapest and most expensive windows, first answer sentence |
| 5 | BDEW profile fallback by sector; "same weekday last week" forecast into `load_fc` | Publication-window job (every 15 min, 12:45–15:00 CET) and the fetch-on-view fallback | Site setup page: site, solar, tariff, flexible loads with presets |
| 6 | **Solar & Load page** | Baselines and the walk-forward evaluation script; start the feature table | Optimiser v1: place each load in its cheapest allowed window, with peak cap and solar surplus |
| 7 | Solar backtest against satellite irradiance, using previous runs for forecast error | **Portugal:** OMIE adapter, zone row, Portuguese tariff defaults | Savings calculation; recommendations writer; Tomorrow page shows the schedule and saving |
| 8 | Integration day | Integration day | Integration day |

**Integration day:** run the whole chain for the demo site and, if we have it, the pilot site. Fix what breaks. Write down every manual step.

**Gate G1:** tables fill daily with no manual help for three days running · the Tomorrow page shows real prices, solar, load and a schedule with a saving · baseline errors are measured · Portuguese prices are in the database.

### Phase 2 — Intelligence (Days 9–14)

| Day | A — Site & Sun | B — Markets & ML | C — Platform & Optimiser |
|---|---|---|---|
| 9 | Consumption model if we have eight weeks of real data; otherwise improve the profile blend | Price model v1: LightGBM, D+2 to D+7, walk-forward | Replay mode: any past date → recommendation and saving |
| 10 | Error report against "same day last week"; calibrate solar losses if inverter data exists | Quantiles (10/50/90 %); the decision score | What-if editing on the Tomorrow page |
| 11 | Stretch: wind model, or solar payback for sites without panels | **Week page**; model go / no-go | 30-day backtest (A and B review the assumptions); **Savings page** |
| 12 | Daily forecast job scheduled and logged | Weekly retraining scheduled and logged; Tariff check page | **Data & status page**; failure banners; error states |
| 13 | End-to-end on schedule, bug fixing | End-to-end on schedule, bug fixing | End-to-end on schedule, bug fixing |
| 14 | Scope freeze, gate review | Scope freeze, gate review | Scope freeze, gate review |

**Gate G2:** tomorrow's recommendations appear automatically after publication · the price model has been compared to the baseline and either beats it or is replaced by it · replay works for any date in the last 60 days · every job run is logged · **scope is frozen: from here only fixes and polish.**

### Phase 3 — Polish and usability (Days 15–17)

Because pages were built alongside the models, this phase is polish, not construction.

- **Day 15:** one design pass led by C (theme, spacing, units, wording); each owner polishes their page; German/English toggle complete.
- **Day 16:** empty and error states on every page; check on a phone; a plain explanation under every chart; attributions on the Data & status page.
- **Day 17:** watch two people from outside the team use it for five minutes each; fix the five worst problems.

**Gate G3:** someone who did not build it can set up a site and read tomorrow's schedule in under five minutes without help · no page shows a raw error.

### Phase 4 — Proof, deck, rehearsal (Days 18–20)

- **Day 18:** A and B produce the results: 30-day backtest in euros, and one table of forecast error against baseline. B writes the business case. C scripts the demo.
- **Day 19:** build the deck; record a three-minute backup video of the full demo; freeze the code, tag `v1.0`, deploy the tag.
- **Day 20:** two timed run-throughs, each person presenting their own part; prepare answers to the likely questions (section 18).

**Gate G4:** `v1.0` tagged and deployed · backup video recorded · two rehearsals done.

---

## 14. Testing and quality

- **Saved API responses.** Each adapter is tested against a response file in `tests/fixtures/`, so tests run offline and never hit rate limits.
- **Clock-change days.** Tests for the last Sunday of March (92 slots) and of October (100 slots), in both Berlin and Lisbon time.
- **Tariff engine.** Hand-calculated examples, one of them taken from a real invoice.
- **Optimiser.** The three guarantees in 9.2, plus cases with no solar, with surplus solar, and with negative prices.
- **Forecasts.** The evaluation script is the test; it prints model error next to baseline error.
- **Pages.** A smoke test that every page loads against the seeded database.
- **CI on every pull request:** `ruff check`, `ruff format --check`, `pytest`.
- **Never** change a test to make it pass. If a test looks wrong, raise it.

---

## 15. Limits and constraints

| Area | Limit | What we do about it |
|---|---|---|
| Energy-Charts | Refuses rapid calls (hit after about five in a few seconds) | One call per job, pauses while backfilling, retry with backoff, SMARD as fallback |
| Open-Meteo | Free tier is for non-commercial use; under 10,000 calls a day; attribution required | Fine for a course project. One call per site per run. Show the attribution. A real business would need the paid plan: say so in the business case |
| ENTSO-E | Needs a token that takes days to arrive | Request on Day 1; nothing in "Must" depends on it |
| PVGIS | No calls from a browser | We only call it from Python |
| Supabase free tier | Small database quota; a project pauses after about a week without activity | Our data is tiny; daily jobs keep it awake. Check current limits when creating the project |
| GitHub Actions schedules | Run in UTC; can start late, sometimes by more than half an hour; switch off after 60 days without repo activity | A wide polling window, minutes away from the full hour, the fetch-on-view fallback, a manual run button |
| Streamlit Community Cloud | App sleeps when unused and takes a while to wake; limited memory | Open the app before presenting. Never train models inside the app |
| Price data | 15-minute prices only since October 2025; hourly before | Detect resolution from the data; train the outlook model on hourly values |
| Time | Days with 23 or 25 hours; "delivery day" is in market time | UTC storage, tests on clock-change days |
| Forecast quality | Solar forecasts are poor in fog and snow; prices a week ahead are uncertain | Show ranges, label forecasts as forecasts, report measured error |
| Winter | Little solar output in late November | Replay mode on a summer date for the demo |
| Meter data | Formats differ by supplier; some sites have no 15-minute data | Column-mapping importer; standard-profile fallback |
| Privacy | A sole trader's consumption can count as personal data | Written consent, anonymise in the demo, EU-hosted database, never in the repo |
| What we claim | Savings are estimates from forecasts and assumptions | Say so on the Savings page. This is decision support, not billing and not advice |

---

## 16. Risks, fallbacks and cut list

| Risk | Fallback | Owner |
|---|---|---|
| No pilot data by Day 8 | A BDEW profile scaled to a realistic annual consumption, or an open dataset; present it clearly as a synthetic business | A |
| A price source changes or blocks us | Second source behind the same interface (SMARD for Germany, ENTSO-E for all) | B |
| ENTSO-E token never arrives | Skip it; Germany and Portugal work without it | B |
| Prices late on demo day | Fetch-on-view fallback; replay mode; backup video | B, C |
| Price model does not beat the baseline | Show the baseline on the Week page and present the comparison as measured | B |
| Time-zone bugs | UTC only, clock-change tests, one `timeutils.py` | C |
| Database unreachable from Actions | Use the session pooler address | C |
| One of us is ill or stuck | Small pull requests mean little is ever half-finished; anyone can pick up a task | all |
| Scope creep | Scope freeze on Day 14, cut list below | all |
| Code we cannot explain | Ask Claude to explain your own code until you can explain it yourself; walk each other through your parts before the presentation | all |

**Cut list — first to go when behind:**

1. Heat-cost comparison
2. Battery what-if
3. Wind generation
4. Solar payback for sites without panels
5. Tariff check page
6. Consumption ML model (keep "same weekday last week")
7. Price quantiles (keep the median)
8. Third price zone via ENTSO-E (keep Germany and Portugal)

Never cut: German prices, solar forecast, optimiser with savings, the Tomorrow page, the demo site, tests.

---

## 17. Budget

The whole system runs on free tiers: **€0.** Optional extras, none needed: a custom domain (about €10); a short promo video (€15–20). Explanations under each recommendation are written from templates, which is free and always says the same thing for the same numbers; an LLM for this is not worth the cost or the unpredictability.

---

## 18. Presentation and demo

Timings assume ten minutes; adjust once the format is known.

1. **Hook (1 min):** the price swing. "Last week the same kilowatt-hour cost between 12 and 53 cents depending on the quarter-hour."
2. **Problem (1 min):** large companies have energy managers. Small ones have a monthly invoice.
3. **Solution (2 min):** the architecture picture, one sentence per layer.
4. **Demo (3 min):** script below.
5. **Results (2 min):** euros saved in the 30-day backtest; model error against baseline, shown as measured.
6. **Business and next steps (1 min):** who pays, how it reaches small businesses, what comes next (automatic control, more countries).

**Demo script**

1. Tomorrow page for the demo or pilot site: the sentence, the chart, the saving.
2. Change one load's allowed window; the schedule and saving update.
3. Replay a sunny summer day: loads move into the solar hours.
4. Week page: the price range for the coming days.
5. Switch to the Lisbon site: same pages, Portuguese prices.
6. If anything fails, switch to the backup video and carry on.

German prices publish around 13:00 CET, which is 12:00 in Lisbon. Any slot after about 12:15 Lisbon time can show tomorrow's real prices; a slot just before can show them arriving.

**Questions to prepare for:** how accurate are the forecasts; why is the supplier's own app not enough; what about data privacy; how does this scale to 1,000 sites (real accounts, row-level security, paid weather data); what is the business model; why did you choose this stack.

---

## 19. Appendices

### Appendix A — Not chosen: what Next.js would change

We chose Streamlit (D1). If we ever switch, everything in sections 5–9 stays the same and these things change:

- C owns the whole front end. A and B hand over chart specifications instead of building pages.
- The what-if feature needs the optimiser behind a small Python web endpoint (FastAPI), deployed alongside the site.
- Add Supabase Auth, row-level security and Realtime; the browser uses the public key, jobs use the service key.
- Add `apps/web/` to the repo, and `eslint` plus a type check to CI.
- Add roughly four to five person-days. To pay for them, drop cut-list items 1–5 from the start and move the Tariff check and Savings pages to "Could".
- The one-person front-end dependency is the main risk.

### Appendix B — Day 1 checklist

- [x] D1 decided: Streamlit
- [ ] D2–D5 decided and written into `docs/DECISIONS.md`
- [ ] Presentation date and grading rules confirmed
- [ ] Starter commit merged, `main` protected, secret scanning on
- [ ] Supabase project created in Frankfurt; connection details shared safely
- [ ] ENTSO-E registration and token request sent
- [ ] Nine pilot requests sent
- [ ] Issues for Phases 0 and 1 created and assigned
- [ ] Everyone has cloned the repo, run `uv sync`, and run the tests once
