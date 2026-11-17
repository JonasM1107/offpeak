"""Train and backtest one home's consumption forecast (offpeak/forecast/load_model.py).

    uv run python -m offpeak.jobs.train_load_model --site 2 --profile home
    uv run python -m offpeak.jobs.train_load_model --csv data/fronius/fronius_5min.csv

From the database it reads only the given site and profile (offpeak/db.read_measurements),
so a household's measurements never train a business model. A local CSV is read with
offpeak/load/fronius.py and stays on that computer. Temperature: Open-Meteo's measured
history for the site, the same weather data every profile may use.
"""

import argparse
from datetime import UTC, datetime, timedelta

import pandas as pd

from offpeak import db
from offpeak.forecast import load_model
from offpeak.load import fronius
from offpeak.sites import SITES


def temperature(site, start, end) -> pd.Series | None:
    from offpeak.weather.open_meteo import fetch_archive

    try:
        w = fetch_archive(site, start, end)
    except Exception as err:  # the forecast still works without temperature
        print(f"no temperature, training without it: {err}")
        return None
    return w.set_index("ts")["temp_c"].resample("1h").mean().dropna()


def main(argv=None) -> load_model.LoadBacktest:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv")
    parser.add_argument("--site", type=int)
    parser.add_argument("--profile", default="home", choices=("home",))
    parser.add_argument("--days", type=int, default=56)
    args = parser.parse_args(argv)
    if args.csv:
        slots = fronius.read_csv(args.csv)
    else:
        url = db.database_url()
        if not url or args.site is None:
            raise SystemExit("Give --csv, or --site with DATABASE_URL set")
        end = datetime.now(UTC)
        slots = db.read_measurements(
            db.get_engine(url), args.site, args.profile, end - timedelta(days=4 * 365), end
        )
    history = load_model.hourly_load(slots)
    site = SITES[args.profile]
    temp = temperature(site, history.index.min().date(), history.index.max().date())
    result = load_model.backtest(history, temp, days=args.days)
    print(f"backtest over {result.days} days, hourly MAE kW: {result.mae_kw}")
    print(f"error of the day's total, kWh: {result.daily_mae_kwh}")
    return result


if __name__ == "__main__":
    main()
