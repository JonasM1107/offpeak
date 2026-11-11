"""The machine-learning price models (docs/PLAN.md section 9.4).

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

Two versions, so the page can show what the weather adds:
- PriceModel learns from prices and the calendar only.
- WeatherPriceModel also gets the weather forecast for the target day (wind in the north, sun
  in the south, temperature; offpeak/weather/price_drivers.py), as it was forecast at the
  time: for a target `lead` days after the last known day, the forecast made the day before
  that last known day (lead + 1 days ahead), which is when tomorrow's prices come out. It also
  gets the week before as a reference: a windy week makes cheap prices, and a calm target day
  after it will be dearer than that week's average.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

TZ = "Europe/Berlin"
LEADS = range(1, 7)  # days after the last known day (D+2 .. D+7 when tomorrow is published)
MIN_DAYS = 21  # less history than this: no forecast (the baselines still work)
RETRAIN_DAYS = 14  # as accurate as weekly in the backtest, and half the training time
PRICE_FEATURES = [
    "lead",  # days ahead of the last known day
    "hour",  # local hour of day
    "weekday",  # 0 = Monday
    "last_day",  # same hour on the last known day, minus the week's average
    "last_week",  # same hour and weekday one week before the target, minus the average
    "profile",  # same hour, averaged over the last 7 days, minus the average
    "spread",  # how much prices moved within the last 7 days (standard deviation)
    "trend",  # last known day's average minus the week's average
]
FEATURES = PRICE_FEATURES  # kept for the tests and the page
WEATHER_FEATURES = [
    "wind",  # turbine share 0..1 in the north, this hour, as forecast
    "sun",  # solar radiation in the south, W/m², this hour, as forecast
    "wind_day",  # the target day's average wind share
    "sun_day",  # the target day's average sun
    "temp_day",  # the target day's average temperature, °C
    "wind_change",  # target day's wind minus the last known week's
    "sun_change",  # target day's sun minus the last known week's
]


def daily_matrix(history: pd.Series, tz: str = TZ) -> pd.DataFrame:
    """Prices as a table: one row per local day, one column per local hour 0..23.
    Clock-change days: the doubled hour is averaged, the missing hour copied from the one
    before, so every day has 24 values."""
    local = history.index.tz_convert(tz)
    table = history.groupby([local.date, local.hour]).mean().unstack()
    table = table.reindex(columns=range(24))
    return table.ffill(axis=1).bfill(axis=1)


def driver_tables(drivers: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Each driver column (wind_1 .. temp_7) as a day x hour table, built once per model."""
    return {
        col: daily_matrix(drivers[col].dropna())
        for col in drivers.columns
        if drivers[col].notna().any()
    }


def weather_days(tables: dict[str, pd.DataFrame], days) -> dict[str, np.ndarray]:
    """The driver tables as arrays with one row per entry of `days` (NaN where the forecast is
    missing; the model copes with gaps)."""
    empty = np.full((len(days), 24), np.nan)
    names = [f"{v}_{k}" for v in ("wind", "sun", "temp") for k in range(1, 8)]
    return {n: tables[n].reindex(list(days)).to_numpy() if n in tables else empty for n in names}


def _mean(a: np.ndarray) -> float:
    return float(np.nanmean(a)) if np.isfinite(a).any() else np.nan


def weather_features(w: dict[str, np.ndarray], d0: int, lead: int) -> dict:
    """The forecast for day d0 + lead as it was known when day d0 + 1 was published."""
    k = min(lead + 1, 7)
    t = d0 + lead
    wind, sun, temp = w[f"wind_{k}"][t], w[f"sun_{k}"][t], w[f"temp_{k}"][t]
    # the week up to d0, from the forecasts made one day before each day (the best we knew)
    wind_week, sun_week = _mean(w["wind_1"][d0 - 6 : d0 + 1]), _mean(w["sun_1"][d0 - 6 : d0 + 1])
    return {
        "wind": wind,
        "sun": sun,
        "wind_day": _mean(wind),
        "sun_day": _mean(sun),
        "temp_day": _mean(temp),
        "wind_change": _mean(wind) - wind_week,
        "sun_change": _mean(sun) - sun_week,
    }


def features(
    matrix: np.ndarray, d0: int, lead: int, weekday: int, weather: dict | None = None
) -> pd.DataFrame:
    """The 24 rows (one per hour) for guessing day d0 + lead, standing at the end of day d0.
    `weekday` is the target day's weekday; `weather` (from weather_days) adds the forecast."""
    week = matrix[d0 - 6 : d0 + 1]
    level = week.mean()
    extra = weather_features(weather, d0, lead) if weather is not None else {}
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
            **extra,
        }
    )


def training_set(
    table: pd.DataFrame, tables: dict[str, pd.DataFrame] | None = None
) -> tuple[pd.DataFrame, np.ndarray]:
    """Every (end of day d0, lead) pair inside the history: features and the true difference
    from the week's average."""
    m = table.to_numpy()
    weather = weather_days(tables, table.index) if tables is not None else None
    weekdays = [pd.Timestamp(d).day_of_week for d in table.index]
    xs, ys = [], []
    for d0 in range(6, len(m) - 1):
        level = m[d0 - 6 : d0 + 1].mean()
        for lead in LEADS:
            if d0 + lead >= len(m):
                break
            xs.append(features(m, d0, lead, weekdays[d0 + lead], weather))
            ys.append(m[d0 + lead] - level)
    return pd.concat(xs, ignore_index=True), np.concatenate(ys)


class PriceModel:
    """Learns from prices and the calendar."""

    key = "ml"
    label = "ML model: prices"
    tables: dict[str, pd.DataFrame] | None = None  # weather, set by WeatherPriceModel

    def __init__(self) -> None:
        # (trained model, last hour of its training history), kept as one pair: the app
        # shares this object between visitors, so each forecast takes its own copy of both
        self.trained: tuple[HistGradientBoostingRegressor, pd.Timestamp] | None = None

    @property
    def columns(self) -> list[str]:
        return PRICE_FEATURES + (WEATHER_FEATURES if self.tables is not None else [])

    def fit(self, history: pd.Series) -> HistGradientBoostingRegressor:
        x, y = training_set(daily_matrix(history), self.tables)
        model = HistGradientBoostingRegressor(
            loss="absolute_error", max_iter=200, learning_rate=0.05, random_state=0
        ).fit(x[self.columns], y)
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
        days = list(table.index) + [last_day + pd.Timedelta(days=i) for i in range(1, 8)]
        weather = weather_days(self.tables, days) if self.tables is not None else None
        level = m[d0 - 6 : d0 + 1].mean()
        local = targets.tz_convert(TZ)
        out = pd.Series(np.nan, index=targets, dtype=float)
        for day in sorted(set(local.date)):
            lead = (day - last_day).days
            if lead not in LEADS:
                continue
            x = features(m, d0, lead, pd.Timestamp(day).day_of_week, weather)
            by_hour = level + model.predict(x[self.columns])
            here = local.date == day
            out[here] = by_hour[local.hour[here]]
        return out


class WeatherPriceModel(PriceModel):
    """Also gets the weather forecast: `drivers` from offpeak.weather.price_drivers."""

    key = "ml_weather"
    label = "ML model: prices + weather"

    def __init__(self, drivers: pd.DataFrame) -> None:
        super().__init__()
        self.tables = driver_tables(drivers)
