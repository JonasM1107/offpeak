import pandas as pd

from offpeak.forecast.model import FEATURES, PriceModel, daily_matrix, training_set
from offpeak.forecast.outlook import local_day_hours
from tests.test_forecast import weekly_history

TZ = "Europe/Berlin"


def next_days(history: pd.Series, n: int) -> pd.DatetimeIndex:
    last = history.index.max().tz_convert(TZ).date()
    return local_day_hours(last + pd.Timedelta(days=1), TZ).append(
        [local_day_hours(last + pd.Timedelta(days=d), TZ) for d in range(2, n + 1)]
    )


def test_daily_matrix_has_24_hours_on_clock_change_days():
    idx = pd.date_range("2026-10-20", "2026-10-30", freq="h", tz="UTC", inclusive="left")
    table = daily_matrix(pd.Series(range(len(idx)), index=idx, dtype=float))
    assert list(table.columns) == list(range(24))
    assert table.notna().all().all()


def test_training_set_only_uses_the_history_given():
    h = weekly_history(weeks=4)
    x, y = training_set(daily_matrix(h))
    assert list(x[FEATURES].columns) == FEATURES
    assert len(x) == len(y) and x["lead"].between(1, 6).all()
    # the last target day is the last day of the history, never later
    days = len(daily_matrix(h))
    assert len(x) == 24 * sum(min(6, days - 1 - d0) for d0 in range(6, days - 1))


def test_learns_a_weekly_pattern():
    h = weekly_history(weeks=12)
    cut = pd.Timestamp("2026-10-12", tz=TZ)  # a local midnight, two weeks before the end
    seen = h[h.index < cut]
    targets = next_days(seen, 6)
    actual = h.reindex(targets)
    guess = PriceModel().predict(seen, targets)
    assert guess.notna().all()
    assert (guess - actual).abs().mean() < 1.0  # prices swing by about 30 ct in this pattern


def test_only_forecasts_one_to_six_days_ahead():
    h = weekly_history(weeks=6)
    guess = PriceModel().predict(h, next_days(h, 8))
    by_day = guess.groupby(guess.index.tz_convert(TZ).date).apply(lambda s: s.notna().all())
    assert by_day.tolist() == [True] * 6 + [False] * 2


def test_too_little_history_gives_no_forecast():
    h = weekly_history(weeks=2)
    assert PriceModel().predict(h, next_days(h, 2)).isna().all()


def test_never_reuses_a_model_that_saw_later_prices():
    h = weekly_history(weeks=10)
    earlier = h.iloc[:-24]
    model = PriceModel()
    model.predict(h, next_days(h, 1))
    first, until = model.trained
    assert until == h.index.max()
    model.predict(earlier, next_days(earlier, 1))  # it saw a later day: must retrain
    second, until = model.trained
    assert second is not first and until == earlier.index.max()
    model.predict(h, next_days(h, 1))  # one day later than its training: reused
    assert model.trained[0] is second
