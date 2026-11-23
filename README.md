# Offpeak

Offpeak tells a small business or a household **when to use electricity tomorrow and how much that saves**. It combines tomorrow's spot prices, a forecast of its own solar and wind power, and its consumption, and plans every machine or appliance into the cheapest quarter-hours. No hardware: just a plan, and the euros it saves.

**Live app: https://offpeak.streamlit.app**

Team project for Introduction to Programming, Nova SBE, 2026.

| Name | Student number |
|---|---|
| Jonas Matner | 77985 |
| Mika Weymann | 77944 |
| Noa Hintz | 78028 |

What the project must fulfil, including the grading criteria, is in `docs/PROJECT_STANDARDS.md`. The original build plan is in `docs/PLAN.md`, how the live data works in `docs/LIVE_DATA.md`, and the German tariffs in `docs/TARIFFS.md`.

## Objectives

Since 2025 the German power market sets a new price every quarter-hour: the same kilowatt-hour can cost 12 cents at lunchtime and 53 cents at 7 p.m. Large companies have energy managers to use this; small businesses and households only see a monthly bill. Offpeak closes that gap:

1. **Show the real price** of every quarter-hour, today and tomorrow: spot price plus grid fees, levies and taxes.
2. **Forecast what is not yet known**: prices up to a week ahead (Offpeak Intelligence, our machine-learning model), solar and wind power from the weather forecast, and for homes their own consumption.
3. **Plan** each flexible machine or appliance (heat pump, furnace, EV chargers, battery, washing machine) into the cheapest hours, using its own sun and wind first.
4. **Prove the savings in euros**, by replaying past days with the real prices and weather.
5. **Work for two kinds of users**: small businesses (SME) and homeowners, with their data kept apart.

Germany (price zone DE-LU) is the first market; Portugal and other EU zones can be switched on by configuration.

## What it does

The landing page explains the idea. **Login** asks whether you are a **Business (SME)** or a **Homeowner**; an account keeps that role. Both get the same pages, worded for their case:

| Page | The question it answers |
|---|---|
| **Dashboard** | What should I do now, what is next, and what does it bring? (price right now, next steps, savings, the next 36 hours; for homes also the consumption forecast) |
| **Site view / Home view** | Where does every kilowatt go? (3D model of the site or house, hour by hour, offpeak's plan next to the usual day) |
| **Savings** | What did it bring? (past days replayed with real prices and weather) |
| **Power** | What does power cost today and tomorrow, and how does the market behave? (15-minute prices, best block for a job, two years of patterns) |
| **Weather & solar** | How much of my own power will I have? (solar and wind for 7 days, how good the forecast is) |
| **Price outlook** | What will power cost in the days after tomorrow? (Offpeak Intelligence, checked against simple rules) |
| **Simulation cockpit / Appliance planner** | When should each machine or appliance run? (try devices, job lengths and time windows) |
| **Site & components / Home & devices** | What is on the site or in the house? (solar, wind, battery, machines) |
| **My data** (homes only) | Import measured data from a Fronius solar system (Solar.web export), see it as "yesterday at home", and delete it again |

Homes get household tariffs (fixed, dynamic, and dynamic with the reduced grid fee of § 14a EnWG, Module 3); businesses keep their commercial tariff.

**Ask Ollie**, the robot at the bottom right, answers questions like "when should I run the heat pump in 3 days, 3 hours, done by 18:00?" from the app's own data.

## How it works

```
GitHub Actions (on a schedule)  ──writes──▶  Supabase (Postgres)  ◀──reads──  Streamlit app
fetches prices and weather,                   stores everything               plans and shows it
trains the price forecast
```

- **Data sources**: day-ahead prices from Energy-Charts (Fraunhofer ISE); weather forecasts, the weather archive and satellite-measured solar radiation from Open-Meteo; optionally ENTSO-E for other price zones; tariffs from the published grid operator and legal sources (see `docs/TARIFFS.md`). Every source has a decided behaviour when it is down: the app shows a clear message instead of crashing.
- **Scheduled jobs** (`offpeak/jobs/`, run by `.github/workflows/`, started on time by a clock in Supabase once it is set up, see `docs/LIVE_DATA.md`): prices around 13:00 when tomorrow's prices are published, weather every 3 hours, price drivers every morning, and the price forecast four times a day.
- **Storage**: Supabase Postgres, reached only through `offpeak/db.py`. Times are stored in UTC, one row per 15-minute slot. The schema is in `db/migrations/`, numbered in order.
- **Forecasts**: scikit-learn gradient boosting. The price model learns how each hour differs from the week's average, from recent prices, the calendar and the weather forecast; it is backtested on days it never saw and must beat simple rules. Solar power is computed with pvlib. A home's consumption model learns only from that home's own measurements.
- **Planning**: for every machine, every allowed start time is priced with the hour-by-hour cost (own power first, then the grid) and the cheapest is kept; the battery charges from surplus sun and wind and covers the expensive hours.
- **Security**: secrets only from environment variables or Streamlit secrets (the repository is public); passwords stored only as PBKDF2 fingerprints; a signed 24-hour login token; the right to change shared data is checked where it is saved; row-level security closes the database's public API; household measurements are tagged with their profile and never used for the business models.

## Installation

You need [uv](https://docs.astral.sh/uv/), which installs the right Python and every library from the lock file. macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then open a new terminal and:

```bash
git clone https://github.com/JonasM1107/offpeak.git
cd offpeak
uv sync
```

## Running the application

```bash
uv run streamlit run app/main.py
```

It opens in the browser at http://localhost:8501 with the landing page. Without a database the app still works: it calls the public APIs directly and uses a demo site and demo home.

To sign in locally, copy the settings template and fill in at least the three login lines (the comments in `.env.example` show how to make the password fingerprint and the secret):

```bash
cp .env.example .env
```

| Setting | What it is for |
|---|---|
| `OFFPEAK_EDITORS`, `OFFPEAK_PASSWORD_HASH`, `OFFPEAK_AUTH_SECRET` | Sign-in (emails, password fingerprint, token secret) |
| `DATABASE_URL` | The shared Supabase database (team password manager). Without it the app keeps changes in the browser tab only |
| `REQUESTY_API_KEY` or `ANTHROPIC_API_KEY` | Ollie. Without them Ollie says it cannot answer and the rest works |
| `ENTSOE_TOKEN` | Optional, other EU price zones |

A scheduled job can also be run by hand (needs `DATABASE_URL`), for example:

```bash
uv run python -m offpeak.jobs.ingest_prices
```

## Tests

```bash
uv run pytest
```

The tests never call a real API (they use saved responses in `tests/fixtures/`) and never touch the shared database. The database tests need a local Postgres and are skipped without one; to include them:

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest
```

Lint and format: `uv run ruff check` and `uv run ruff format`. CI runs all three on every pull request.

## What is where

```
app/          Streamlit pages: views/ (one file per page), data.py (cached loading), ui/ (3D scene, cards)
offpeak/      all logic, no Streamlit: markets, tariffs, weather, generation, load, forecast (ML),
              cockpit (planning), savings, assistant (Ollie), auth, db.py, jobs
db/           database migrations (run once in Supabase, in order) and supabase/job_clock.sql,
              the clock that starts the scheduled jobs
tests/        tests, mirroring offpeak/, with saved API responses in tests/fixtures/
scripts/      Blender script that builds the 3D models, and the script that saves API test fixtures
docs/         project standards, the plan, live data, tariffs
.github/      CI, scheduled data jobs and the Claude review workflows
AGENTS.md     rules for AI assistants (Claude, Codex)
```

## How we work

1. `git switch main && git pull`, then `git switch -c feat/<area>-<topic>`.
2. Build it with tests. Before opening a pull request, run the review loop in `AGENTS.md`: format, lint, test, self-review, fix, repeat.
3. Open a pull request. CI runs the tests, and Claude reviews it automatically, again after every push.
4. Fix the comments yourself, or reply `@claude fix the review comments`.
5. A teammate approves, then squash-merge.

To set up the Claude review once: install the [Claude GitHub App](https://github.com/apps/claude) on the repository and save a token from `claude setup-token` as the repository secret `CLAUDE_CODE_OAUTH_TOKEN`. Until the secret exists, the Claude workflows skip themselves and only CI runs.
