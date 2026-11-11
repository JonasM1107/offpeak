"""Simple forecasts the ML model has to beat (docs/PLAN.md section 9.4)."""

import pandas as pd


def _step_back(history: pd.Series, targets: pd.DatetimeIndex, step: pd.Timedelta) -> pd.Series:
    """For each target hour, the price `step` earlier, or a whole multiple of `step` earlier
    if that is still in the future."""
    last = history.index.max()
    out = []
    for t in targets:
        back = t - step
        while back > last:
            back -= step
        out.append(history.get(back, float("nan")))
    return pd.Series(out, index=targets, dtype=float)


class LastWeek:
    """Same hour, same weekday, one week earlier: catches the weekly rhythm."""

    key = "last_week"
    label = "Same hour last week"

    def predict(self, history: pd.Series, targets: pd.DatetimeIndex) -> pd.Series:
        return _step_back(history, targets, pd.Timedelta(days=7))


class LastDay:
    """Same hour on the last published day: catches the current price level."""

    key = "last_day"
    label = "Same hour, last known day"

    def predict(self, history: pd.Series, targets: pd.DatetimeIndex) -> pd.Series:
        return _step_back(history, targets, pd.Timedelta(days=1))


class Blend:
    """Average of the two above: today's price level with last week's daily rhythm."""

    key = "blend"
    label = "Blend of both"

    def predict(self, history: pd.Series, targets: pd.DatetimeIndex) -> pd.Series:
        return (LastWeek().predict(history, targets) + LastDay().predict(history, targets)) / 2
