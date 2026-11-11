# Live data: weather and day-ahead prices

This is the code version of the *offpeak — Live Data Tech Setup* doc (11 Nov 2026), adjusted to the decisions in `PLAN.md`. All build steps from that doc are done except the dashboard reading via Realtime, which Streamlit does not need.

## What is built

| File | What it does |
|---|---|
| `offpeak/markets/energy_charts.py` | `fetch_day_ahead(zone, start, end)`, `fetch_tomorrow()`, `fetch_history()` (month by month, with pauses). Returns `ts, eur_mwh, resolution_min, source` |
| `offpeak/weather/open_meteo.py` | `fetch_weather(site, days)`. Returns one row per 15-minute slot: `ts, gti_wm2, ghi_wm2, precip_mm, temp_c, cloud_pct, wind_ms` |
| `offpeak/timeutils.py` | `floor_to_slot()`, `market_day_bounds()` (23/24/25-hour days), `market_today()` |
| `offpeak/http.py` | One GET helper: timeout, plus retry with backoff on 429 and 5xx |
| `offpeak/config.py` | Zone, model, URLs, timeouts, attribution texts. No secrets |
| `scripts/capture_fixtures.py` | Calls both APIs and saves the raw responses to `tests/fixtures/` |
| `offpeak/analysis.py` | Cheapest and most expensive windows, current price, daily stats, typical day |
| `app/` | First Streamlit dashboard: Dashboard, Analytics, Settings |
| `tests/` | 25 offline tests against saved responses |

Every `ts` is a timezone-aware UTC slot start.

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run python -c "from offpeak.markets.energy_charts import fetch_tomorrow; print(fetch_tomorrow())"
```

## Checked against the real API on 11 Nov 2026

**Energy-Charts.** `/v2/price`, `/v2/price_current` and `/v2/price_next_day` all work without a key. The saved fixtures are real responses:

| Fixture | Day | Slots |
|---|---|---|
| `prices_sample.json` | 10 Nov 2026 | 96 |
| `prices_spring_forward.json` | 29 Mar 2026 | 92, includes negative prices |
| `prices_fall_back.json` | 25 Oct 2026 | 100, includes a negative price |
| `prices_hourly_2025.json` | 1 Sep 2025 | 24, hourly (before 15-minute trading) |
| `prices_not_published.txt` | 13 Nov 2026, asked on 11 Nov | HTTP 404, `no content available` |

The v2 response is `{"interval_minutes": 15, "data": [{"timestamp": "2026-11-10T00:00:00+01:00", "values": {"day_ahead_price": 271.33}}, ...]}`. Each timestamp carries its own UTC offset, so clock-change days parse without special handling. The older `/price` endpoint (without `/v2`) still works but returns parallel `unix_seconds` and `price` arrays.

**Open-Meteo.** It first refused calls from our cloud container ("Daily API request limit exceeded"). The limit is counted per IP address and cloud IPs are shared. Later the same day it answered, and `tests/fixtures/weather_sample.json` is now a real two-day response for Köln. Its format matched the docs exactly. To refresh both samples, run `uv run python scripts/capture_fixtures.py` and rerun the tests.

## Where the code differs from the tech setup doc

| Tech setup doc | What we did | Why |
|---|---|---|
| Next-day prices through a Supabase Edge Function + pg_cron, pushed to the page with Realtime | Python only. A GitHub Actions job polls every 15 minutes from 11:45 to 14:00 UTC, and the Streamlit page fetches the prices itself if they are still missing | `PLAN.md` decision D1 (Streamlit) removes Edge Functions, pg_cron, Realtime and Next.js |
| Before publication, a request for tomorrow "returns nothing" | It returns **HTTP 404** with body `no content available`. We turn that into an empty table, not an error | Seen live |
| Attribution "Energy-Charts / Fraunhofer ISE" | The licence field reads "CC BY 4.0 from Bundesnetzagentur \| SMARD.de". The attribution text in `config.py` names both | CC BY requires naming the original source |
| `wind_kmh` column | `wind_ms`, requested with `wind_speed_unit=ms` | `PLAN.md` section 5.2 and the `weather_fc` table use m/s |
| `azimuth` taken from `sites` as is | Sites store a compass bearing (180 = south). `open_meteo_azimuth()` converts it to Open-Meteo's 0 = south | `PLAN.md` conventions |
| Hourly temperature, cloud cover and wind repeated across four slots | Same, plus the 15-minute radiation and rain moved back one slot to their slot start | Open-Meteo stamps them at the *end* of the 15 minutes they describe |

Two smaller points:

- **Hourly prices** from before October 2025 keep `resolution_min = 60`; they are not split into four. The price model works on hourly values anyway.
- **The forecast loses its last slot** (23:45 on the final day). After the shift, that slot would need the value stamped 00:00 the next day, which the API does not send.

## Database and scheduled jobs

The data flows like this:

```
Energy-Charts ──▶ ingest_prices  (GitHub Actions, every 15 min, 11:45-14:00 UTC) ──▶ prices_da  ──┐
Open-Meteo   ──▶ ingest_weather (GitHub Actions, every 3 hours)                 ──▶ weather_fc ──┼──▶ dashboard
every job    ──────────────────────────────────────────────────────────────────▶ job_runs   ──┘
```

| File | What it does |
|---|---|
| `db/migrations/001_live_data.sql` | Creates `prices_da`, `weather_fc` and `job_runs`. Paste it into Supabase's SQL Editor once |
| `offpeak/db.py` | The only module that talks to the database: upserts, reads, job log |
| `offpeak/jobs/` | `ingest_prices`, `ingest_weather`, `backfill_prices`, and `runner.py`, which times and logs every run |
| `.github/workflows/prices.yml`, `weather.yml` | The schedules. Both also have a "Run workflow" button |
| `.github/workflows/backfill.yml` | Run by hand once to load price history |
| `app/data.py` | The dashboard reads from the database. If something is missing there, it fetches it from the API itself and stores it |

Behaviour worth knowing:

- **Prices:** the job skips (logged as `skipped`) once all of tomorrow's slots are stored. Before publication it stores today and logs `skipped: tomorrow not published yet`; that is normal, not an error.
- **Weather:** every run is stored with its `run_at`, so later we can check old forecasts against what happened. The dashboard uses the newest run, and fetches a fresh one itself if the newest stored run is older than 6 hours.
- **No database, no problem:** without `DATABASE_URL` the jobs print a note and exit, and the dashboard calls the APIs directly.
- **Schedules only run from `main`.** GitHub starts scheduled workflows only on the default branch.

### Where DATABASE_URL goes

Use Supabase's **Session pooler** address (Connect button, then "Session pooler"). The direct address does not work from GitHub Actions.

| Where | How |
|---|---|
| Your laptop | `.env` file in the repo folder: `DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres` |
| GitHub Actions | Repo, then Settings, then Secrets and variables, then Actions, then New repository secret, named `DATABASE_URL` |
| Streamlit Cloud | App, then Settings, then Secrets: `DATABASE_URL = "postgresql://..."` |

### Tests

`uv run pytest` runs the database tests only if `TEST_DATABASE_URL` points to an empty Postgres; otherwise they are skipped. CI starts a throwaway Postgres for them. Never point `TEST_DATABASE_URL` at Supabase: the tests drop and recreate the tables.

## Attribution (must be shown in the app)

- Weather data by Open-Meteo.com (link to open-meteo.com). Free for non-commercial use, under 10,000 calls a day.
- Prices: Energy-Charts / Fraunhofer ISE, data from Bundesnetzagentur | SMARD.de, CC BY 4.0.
