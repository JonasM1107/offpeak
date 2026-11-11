import numpy as np
import pandas as pd
import pytest

from offpeak.forecast.baselines import LastDay, LastWeek
from offpeak.forecast.model import PriceModel
from offpeak.forecast.outlook import backtest, day_summaries, local_day_hours, outlook

TZ = "Europe/Berlin"


def weekly_history(weeks: int = 12, noise: float = 0.0) -> pd.Series:
    """Hourly prices that repeat every week: cheap at night and at weekends."""
    idx = pd.date_range("2026-08-03", periods=weeks * 7 * 24, freq="h", tz="UTC")
    hour, weekday = idx.hour, idx.day_of_week
    price = 20 + 10 * np.sin((hour - 6) / 24 * 2 * np.pi) - 6 * (weekday >= 5)
    rng = np.random.default_rng(1)
    return pd.Series(price + rng.normal(0, noise, len(idx)), index=idx)


def test_last_week_repeats_the_week_and_steps_back_further_if_needed():
    h = weekly_history()
    targets = pd.date_range(h.index[-1] + pd.Timedelta(hours=1), periods=24 * 10, freq="h")
    guess = LastWeek().predict(h, targets)
    assert guess.notna().all()  # 10 days ahead: steps back two weeks where needed
    assert (guess.values == h.reindex(targets - pd.Timedelta(days=7 * 2)).values).sum() > 0


def test_last_day_repeats_the_last_known_day():
    h = weekly_history()
    targets = pd.date_range(h.index[-1] + pd.Timedelta(hours=1), periods=48, freq="h")
    guess = LastDay().predict(h, targets)
    assert list(guess.iloc[24:]) == list(guess.iloc[:24])


def test_backtest_finds_the_weekly_pattern():
    test = backtest(weekly_history(), TZ, days=21)
    scores = test.scores.set_index("forecaster")
    assert scores.loc["last_week", "mae"] == pytest.approx(0, abs=1e-9)
    assert scores.loc["last_week", "decision"] == 1.0
    assert scores.loc["last_day", "mae"] > 0
    assert set(test.errors["lead"]) == set(range(1, 7))


def test_outlook_covers_six_days_with_a_band():
    h = weekly_history(noise=1.5)
    test = backtest(h, TZ, days=21)
    out, used = outlook(h, TZ, test)
    assert set(used.values()) == {"last_week"}  # a weekly pattern: last week wins at every lead
    assert out["lead"].nunique() == 6
    assert (out["p10"] <= out["p50"] + 1e-9).all() and (out["p50"] <= out["p90"] + 1e-9).all()
    assert out["ts"].min() > h.index.max()


def test_local_day_hours_on_clock_change():
    assert len(local_day_hours(pd.Timestamp("2026-10-25").date(), TZ)) == 25
    assert len(local_day_hours(pd.Timestamp("2026-03-29").date(), TZ)) == 23


def test_ml_slot_is_honest_until_trained():
    with pytest.raises(NotImplementedError):
        PriceModel().predict(weekly_history(), pd.DatetimeIndex([]))


def test_day_summaries_find_the_cheapest_window():
    h = weekly_history(noise=1.5)
    out, _ = outlook(h, TZ, backtest(h, TZ, days=21))
    days = day_summaries(out, TZ)
    assert len(days) == 6
    # the weekly pattern is cheapest around 00:00 (sin minimum near 00 UTC = 01-02 local)
    assert days["window_start"].between(0, 3).all()
    assert (days["window_ct"] <= days["p50"]).all()


def test_view_payload():
    from offpeak.forecast.outlook import view_payload

    h = weekly_history(noise=1.5)
    p = view_payload(h, backtest(h, TZ, days=21), TZ)
    assert len(p["forecast"]["t"]) == len(p["forecast"]["p50"]) >= 6 * 23
    assert len(p["days"]) == 6 and p["days"][0]["end"] > p["days"][0]["start"]
    assert {m["key"] for m in p["models"]} == {"last_week", "last_day", "blend"}
    assert sorted(sum((m["used_for"] for m in p["models"]), [])) == [2, 3, 4, 5, 6, 7]


def test_backtest_says_so_when_history_is_too_short():
    with pytest.raises(ValueError, match="Not enough price history"):
        backtest(weekly_history().iloc[: 3 * 24], TZ)  # three days
