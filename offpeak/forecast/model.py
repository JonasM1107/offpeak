"""The machine-learning price model (docs/PLAN.md section 9.4), step 1: prices only.

What it learns: how the price of one hour, 2 to 7 days ahead, differs from the average of the
last known week, given simple facts about that hour (hour of day, weekday, how far ahead) and
about the last known days (what the same hour cost yesterday and last week, how the week
went). It is one more forecaster next to the baselines in offpeak/forecast/baselines.py: the
backtest compares them all and the outlook uses whichever was best at each lead.

Why the difference to the weekly average and not the price itself: prices move between
levels (a 6 ct summer, a 12 ct winter). A tree model cannot predict a level it never saw, but
"3 ct above this week's average at 19:00 on a Thursday" holds across seasons.

The model: scikit-learn's HistGradientBoostingRegressor, many small decision trees where each
corrects the previous ones. Loss "absolute_error" aims at the median, so a few extreme
price spikes do not pull the whole forecast up.

Training uses only the history it is given, so the backtest can never peek into the future:
every training example is "standing at the end of day d, guess day d + lead", built from days
up to the end of that history. Retraining takes about a second; the backtest walks forward
through 8 weeks, so the model is reused for up to RETRAIN_DAYS and then trained again
(never on data after the day it is used for).

Step 2 (not built yet): add the weather forecast (wind in northern Germany, sun in the south)
as features, trained on historical forecasts, never on measured weather.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

TZ = "Europe/Berlin"
LEADS = range(1, 7)  # days after the last known day (D+2 .. D+7 when tomorrow is published)
MIN_DAYS = 21  # less history than this: no forecast (the baselines still work)
RETRAIN_DAYS = 14  # as accurate as weekly in the backtest, and half the training time
FEATURES = [
    "lead",  # days ahead of the last known day
    "hour",  # local hour of day
    "weekday",  # 0 = Monday
    "last_day",  # same hour on the last known day, minus the week's average
    "last_week",  # same hour and weekday one week before the target, minus the average
    "profile",  # same hour, averaged over the last 7 days, minus the average
    "spread",  # how much prices moved within the last 7 days (standard deviation)
    "trend",  # last known day's average minus the week's average
]


def daily_matrix(history: pd.Series, tz: str = TZ) -> pd.DataFrame:
    """Prices as a table: one row per local day, one column per local hour 0..23.
    Clock-change days: the doubled hour is averaged, the missing hour copied from the one
    before, so every day has 24 values."""
    local = history.index.tz_convert(tz)
    table = history.groupby([local.date, local.hour]).mean().unstack()
    table = table.reindex(columns=range(24))
    return table.ffill(axis=1).bfill(axis=1)


def features(matrix: np.ndarray, d0: int, lead: int, weekday: int) -> pd.DataFrame:
    """The 24 rows (one per hour) for guessing day d0 + lead, standing at the end of day d0.
    `weekday` is the target day's weekday."""
    week = matrix[d0 - 6 : d0 + 1]
    level = week.mean()
    return pd.DataFrame(
        {
            "lead": lead,
            "hour": np.arange(24),
            "weekday": weekday,
            "last_day": matrix[d0] - level,
            "last_week": matrix[d0 + lead - 7] - level,
            "profile": week.mean(axis=0) - level,
            "spread": week.std(),
            "trend": matrix[d0].mean() - level,
        }
    )


def training_set(table: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Every (end of day d0, lead) pair inside the history: features and the true difference
    from the week's average."""
    m = table.to_numpy()
    weekdays = [pd.Timestamp(d).day_of_week for d in table.index]
    xs, ys = [], []
    for d0 in range(6, len(m) - 1):
        level = m[d0 - 6 : d0 + 1].mean()
        for lead in LEADS:
            if d0 + lead >= len(m):
                break
            xs.append(features(m, d0, lead, weekdays[d0 + lead]))
            ys.append(m[d0 + lead] - level)
    return pd.concat(xs, ignore_index=True), np.concatenate(ys)


class PriceModel:
    key = "ml"
    label = "Machine learning model"

    def __init__(self) -> None:
        # (trained model, last hour of its training history), kept as one pair: the app
        # shares this object between visitors, so each forecast takes its own copy of both
        self.trained: tuple[HistGradientBoostingRegressor, pd.Timestamp] | None = None

    def fit(self, history: pd.Series) -> HistGradientBoostingRegressor:
        x, y = training_set(daily_matrix(history))
        model = HistGradientBoostingRegressor(
            loss="absolute_error", max_iter=200, learning_rate=0.05, random_state=0
        ).fit(x[FEATURES], y)
        self.trained = (model, history.index.max())
        return model

    def _model_for(self, history: pd.Series) -> HistGradientBoostingRegressor:
        """The trained model if it saw nothing after this history ends and is recent enough,
        else a new one trained on this history."""
        trained, end = self.trained, history.index.max()
        if trained is not None:
            model, until = trained
            if until <= end and end - until < pd.Timedelta(days=RETRAIN_DAYS):
                return model
        return self.fit(history)

    def predict(self, history: pd.Series, targets: pd.DatetimeIndex) -> pd.Series:
        table = daily_matrix(history)
        if len(table) < MIN_DAYS:
            return pd.Series(np.nan, index=targets, dtype=float)
        model = self._model_for(history)
        m = table.to_numpy()
        d0, last_day = len(m) - 1, table.index[-1]
        level = m[d0 - 6 : d0 + 1].mean()
        local = targets.tz_convert(TZ)
        out = pd.Series(np.nan, index=targets, dtype=float)
        for day in sorted(set(local.date)):
            lead = (day - last_day).days
            if lead not in LEADS:
                continue
            x = features(m, d0, lead, pd.Timestamp(day).day_of_week)
            by_hour = level + model.predict(x[FEATURES])
            here = local.date == day
            out[here] = by_hour[local.hour[here]]
        return out
