# Offpeak

Offpeak tells a small business every afternoon **when to use electricity tomorrow and how much that saves**. It combines tomorrow's spot prices, a forecast of the site's own solar generation, and the site's consumption.

Germany is the first market. The design lets us switch on Portugal and other EU price zones by configuration.

## Status

Early build. Live day-ahead prices (Energy-Charts) and the weather forecast (Open-Meteo) are connected, and a first Streamlit dashboard shows them. The build plan is in `docs/PLAN.md`; the live data setup is in `docs/LIVE_DATA.md`.

## Run it

```bash
uv sync
```

```bash
uv run streamlit run app/main.py
```

```bash
uv run pytest
```

## Team

Jonas, Mika and Noa — final project for Introduction to Programming, Nova SBE.

## Stack

Python, Streamlit, Supabase Postgres, GitHub Actions. Details and the reasons are in the plan.
