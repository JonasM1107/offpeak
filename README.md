# Offpeak

Offpeak tells a small business every afternoon **when to use electricity tomorrow and how much that saves**. It combines tomorrow's spot prices, a forecast of the site's own solar generation, and the site's consumption.

Germany is the first market. The design lets us switch on Portugal and other EU price zones by configuration.

Final project for Introduction to Programming, Nova SBE, by Jonas, Mika and Noa. The build plan is in `docs/PLAN.md`.

## Get started

You need [uv](https://docs.astral.sh/uv/). macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.

```bash
git clone https://github.com/JonasM1107/offpeak.git
cd offpeak
uv sync
cp .env.example .env      # then fill in the values from the team password manager
uv run pytest
uv run streamlit run app/main.py
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
app/          Streamlit dashboard (pages only, no calculations)
offpeak/      all logic: prices, tariffs, weather, solar, load, optimiser, jobs
tests/        tests, mirroring offpeak/
docs/         the plan and decisions
.github/      CI and the Claude review workflows
AGENTS.md     rules for Claude and Codex
```
