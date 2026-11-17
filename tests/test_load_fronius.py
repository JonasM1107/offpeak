"""Reading a Fronius Solar.web history (offpeak/load/fronius.py) and storing measurements only
per profile (offpeak/db.py). The file in tests/fixtures/ is made up, not a real house."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from offpeak import db
from offpeak.load import fronius
from tests.conftest import FIXTURES

SAMPLE = FIXTURES / "fronius_sample.csv"


@pytest.fixture
def slots():
    return fronius.read_csv(SAMPLE)


def test_two_days_become_192_quarter_hours(slots):
    assert len(slots) == 192  # the duplicated row counts once
    assert str(slots["ts"].dt.tz) == "UTC"
    assert (slots["ts"].diff().dropna() == pd.Timedelta("15min")).all()


def test_watts_become_kilowatts_averaged_over_the_slot(slots):
    raw = pd.read_csv(SAMPLE).drop_duplicates("ts_utc")
    first = raw.head(3)["ToConsumer"].mean() / 1000  # the first slot's three 5-minute rows
    assert slots["load_kw"].iloc[0] == pytest.approx(first)
    assert slots["pv_kw"].max() <= 5.0


def test_an_empty_flow_counts_as_zero(slots):
    night = slots[slots["pv_kw"] == 0]
    assert (night["grid_out_kw"] == 0).all()  # no export at night, empty in the file


def test_coverage(slots):
    info = fronius.coverage(slots)
    assert info["days"] == 2 and info["missing_slots"] == 0


def test_coverage_of_nothing():
    assert fronius.coverage(pd.DataFrame({"ts": []}))["days"] == 0


def base_frame():
    return pd.read_csv(SAMPLE).head(12)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda f: f.drop(columns=["FromGen"]), "missing columns"),
        (lambda f: f.assign(ToConsumer=-5), "negative"),
        (lambda f: f.assign(FromGen=250_000), "above"),
        (lambda f: f.assign(StateOfChargeAggregated=140), "outside"),
        (lambda f: f.assign(ts_utc="yesterday"), "valid time"),
    ],
)
def test_unusable_files_are_refused_with_a_reason(change, message):
    with pytest.raises(fronius.FroniusFileError, match=message):
        fronius.read_csv(change(base_frame()))


def test_rows_without_production_or_consumption_are_gaps_not_zeros():
    frame = base_frame()
    frame.loc[0:2, ["FromGen", "ToConsumer"]] = None  # the whole first slot unknown
    slots = fronius.read_csv(frame)
    assert slots["ts"].min() > pd.Timestamp(frame["ts_utc"].iloc[0])


def test_an_unknown_profile_is_refused_before_any_database_access():
    with pytest.raises(ValueError, match="profile"):
        db.save_measurements(None, 2, "everyone", pd.DataFrame())
    with pytest.raises(ValueError, match="profile"):
        db.read_measurements(None, 2, "", datetime(2026, 1, 1, tzinfo=UTC), datetime.now(UTC))


# ── with a test database (CI) ───────────────────────────────────────────────
START, END = datetime(2026, 1, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)


def test_measurements_round_trip_for_their_profile(engine, slots):
    assert db.save_measurements(engine, 2, "home", slots, "fronius") == 192
    back = db.read_measurements(engine, 2, "home", START, END)
    assert len(back) == 192 and back["load_kw"].iloc[0] == pytest.approx(slots["load_kw"].iloc[0])
    db.save_measurements(engine, 2, "home", slots)  # again: replaced, not doubled
    assert len(db.read_measurements(engine, 2, "home", START, END)) == 192


def test_a_business_never_reads_a_homes_measurements(engine, slots):
    db.save_measurements(engine, 2, "home", slots)
    assert db.read_measurements(engine, 2, "business", START, END).empty


def test_a_site_cannot_hold_two_profiles(engine, slots):
    db.save_measurements(engine, 2, "home", slots)
    with pytest.raises(ValueError, match="another profile"):
        db.save_measurements(engine, 2, "business", slots)
