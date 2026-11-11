# Offpeak

Offpeak tells a small business every afternoon **when to use electricity tomorrow and how much that saves**. It combines tomorrow's spot prices, a forecast of the site's own solar generation, and the site's consumption.

Germany is the first market. The design lets us switch on Portugal and other EU price zones by configuration.

**Live app: https://offpeak.streamlit.app**

Team project for Introduction to Programming, Nova SBE, 2026.

| Name | Student number |
|---|---|
| Jonas (TODO: full name) | TODO |
| Mika (TODO: full name) | TODO |
| Noa (TODO: full name) | TODO |

What the project must fulfil, including the grading criteria and where we stand, is in `docs/PROJECT_STANDARDS.md`. The original build plan is in `docs/PLAN.md`; how the live data works is in `docs/LIVE_DATA.md`.

## What it does

- **Dashboard:** tomorrow's prices and this week's plan, i.e. when each machine should run and what that saves.
- **Analytics:** day-ahead power prices, weather and solar, a 7-day price outlook from a machine learning model (with an honest backtest), and a simulation cockpit to plan machines.
- **Results:** savings replayed on past days, and a tariff calculator.
- **Setup:** the site's components (solar, wind, battery, machines), shown in a 3D site view.

## Get started

You need [uv](https://docs.astral.sh/uv/). macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.

```bash
git clone https://github.com/JonasM1107/offpeak.git
cd offpeak
uv sync
```

Run the app (it works without a database, calling the public APIs directly):

```bash
uv run streamlit run app/main.py
```

With the shared database: `cp .env.example .env` and fill in `DATABASE_URL` from the team password manager.

Run the tests (they never call the real APIs; they use saved responses in `tests/fixtures/`):

```bash
uv run pytest
```

The database tests need a local Postgres and are skipped without one. To include them, point `TEST_DATABASE_URL` at an empty local database (CI does this with a throwaway Postgres):

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest
```

## How we work

1. `git switch main && git pull`, then `git switch -c feat/<area>-<topic>`.
2. Build it with tests. Before opening a pull request, run the review loop in `AGENTS.md`: format, lint, test, self-review, fix, repeat.
3. Open a pull request. CI runs the tests, and Claude reviews it automatically, again after every push.
4. Fix the comments yourself, or reply `@claude fix the review comments`.
5. A teammate approves, then squash-merge.

## Setting up the Claude review (once, by the repo owner)

1. Install the Claude GitHub App on this repo: https://github.com/apps/claude
2. Create a token with your Claude subscription: run `claude setup-token` in a terminal.
3. Save it as a repository secret named `CLAUDE_CODE_OAUTH_TOKEN`: run `gh secret set CLAUDE_CODE_OAUTH_TOKEN` and paste it. (An Anthropic API key saved as `ANTHROPIC_API_KEY` works instead, but is billed per use.)

Until the secret exists, the Claude workflows skip themselves and only CI runs.

## What is where

```
app/          Streamlit dashboard: views/ (one file per page), data.py (cached loading), ui/
offpeak/      all logic: markets, tariffs, weather, forecast (ML), cockpit, savings, db.py, jobs
db/           database migrations (run once in Supabase)
tests/        tests, mirroring offpeak/, with saved API responses in tests/fixtures/
docs/         project standards, the plan, live data, tariffs
.github/      CI, scheduled data jobs and the Claude review workflows
AGENTS.md     rules for Claude and Codex
```
