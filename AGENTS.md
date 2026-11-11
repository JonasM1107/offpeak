# Offpeak — notes for AI agents (Claude, Codex)

Student final project for Introduction to Programming, Nova SBE. Three people: Jonas, Mika, Noa. The plan is `docs/PLAN.md`; read the relevant section before building something. The people asking are learning: explain what you changed in plain language, and they must be able to explain the code themselves.

## The standard we build to

`docs/PROJECT_STANDARDS.md` has the course rules, the grading criteria and what 100 % means for offpeak. Every change must keep the project at the top level of every criterion. In short:

- **It works:** no page may crash, including on invalid input and when a source is down. Show a clear message instead.
- **Tests** cover the accepted case, the rejected case (invalid input, missing data, a failing source) and edge cases. Never call a real API in tests, and never use the shared database.
- **External APIs:** each has a decided failure behaviour (section 4 of the standards). A new API needs one, plus a test for it.
- **Security:** secrets only from environment variables or Streamlit secrets. Check anything that changes shared data where it is saved, not only by hiding a button. Validate every input before storing it. Add a library only if it is needed; the lock file pins it.
- **Storage:** Supabase via `offpeak/db.py`. Schema changes are a new numbered file in `db/migrations/`; tell the team to run it in Supabase. Local reset: drop the tables and run the migrations in order (`tests/conftest.py` shows how).
- **Explainable:** every member must be able to explain any part, so write code and comments a teammate can follow, and say why, not only what.

## Running things

- Install or update libraries: `uv sync`. Add one: `uv add <name>`. Never use `pip` or `python -m venv`.
- Tests: `uv run pytest`
- Lint and format: `uv run ruff check --fix` and `uv run ruff format`
- App: `uv run streamlit run app/main.py`

## Where code goes

- `offpeak/`: all logic. Never imports Streamlit. One folder per area (markets, tariffs, forecast, weather, generation, load, optimizer, jobs), as in section 12.5 of the plan.
- `app/`: Streamlit pages only. They call functions in `offpeak/` and draw the result. No calculations in pages.
- `tests/`: mirrors `offpeak/`. Tests for API adapters use saved responses in `tests/fixtures/`, never the live API.
- Only `offpeak/db.py` talks to the database.

## Rules

- Timestamps are stored and passed around in UTC, one row per 15-minute slot start. Use `offpeak/timeutils.py`. Convert to local time only on screen.
- Prices: market data in €/MWh, tariffs in €/kWh, screens in ct/kWh.
- Never commit secrets, `.env`, or real business data. The repo is public. Settings come from environment variables (`.env.example` lists them).
- Never edit, skip or delete a test to make it pass. If a test looks wrong, say so and stop.
- Work on a branch per task (`feat/<area>-<topic>` or `fix/<area>-<topic>`), never on `main`.
- Keep changes small and on topic. Don't fix unrelated things you notice; mention them instead.

## The review loop: before you open a pull request

Repeat until a round finds nothing, at most three rounds:

1. `uv run ruff format`, `uv run ruff check --fix`, `uv run pytest`. Everything passes.
2. Review your own diff against `main`: in Claude Code run `/code-review`; otherwise reread the diff looking for bugs, UTC mistakes, missing tests, and logic in pages.
3. Fix what the review found, then go back to step 1.

After three rounds with findings still open, stop and list them for the person instead of looping further.

Then open the pull request. On GitHub, Claude reviews it automatically and again after every push. To let Claude fix its own review comments, reply `@claude fix the review comments`. A teammate approves before merging.
