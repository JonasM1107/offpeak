"""Store a site's measured history in the database, for its own models only.

    uv run python -m offpeak.jobs.import_measurements data/fronius/fronius_5min.csv \
        --site 2 --profile home

Reads a Fronius Solar.web CSV (offpeak/load/fronius.py), checks it, and upserts its 15-minute
slots into site_measurements with the given profile. Needs DATABASE_URL. The file itself
stays on the computer that runs this (data/ is git-ignored).
"""

import argparse

from offpeak import db
from offpeak.load import fronius


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv")
    parser.add_argument("--site", type=int, required=True)
    parser.add_argument("--profile", required=True, choices=("home", "business"))
    args = parser.parse_args(argv)
    slots = fronius.read_csv(args.csv)
    info = fronius.coverage(slots)
    url = db.database_url()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    n = db.save_measurements(db.get_engine(url), args.site, args.profile, slots, "fronius")
    print(f"stored {n} slots, {info['days']} days, {info['first']} to {info['last']}")
    return n


if __name__ == "__main__":
    main()
