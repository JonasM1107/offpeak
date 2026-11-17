"""The homeowner consumption forecast: how much power a house will use, hour by hour, for
the next 1 to 7 days.

It is built like the price model (offpeak/forecast/model.py), so the team explains one idea
twice:
- It learns how an hour differs from the average of the last known week, not the kW
  themselves. "The evening uses 0.3 kW more than this week's average" holds in summer and in
  winter, while the level itself moves with the season.
- Facts per hour: hour of day, weekday, month, how far ahead, the same hour yesterday and a
  week before, the week's daily shape, and the temperature, which is the same weather for
  every profile (heating, cooling, lights in the dark season). A household's measurements
  are its own: the model is trained per site and per profile and never on a business's data
  (offpeak/db.read_measurements needs the profile).
- scikit-learn's HistGradientBoostingRegressor with the absolute-error loss, so a few unusual
  hours (a party, a sauna evening) do not pull the forecast up.
- backtest() walks forward over the last weeks: every day pretends to be today and forecasts
  the 7 days after it, using only what was known then. The model has to beat two simple
  rules: the same hour last week, and the same hour averaged over the last 7 days.

Training on three years of 15-minute data takes a few seconds.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from offpeak.forecast.model import daily_matrix

TZ = "Europe/Berlin"
LEADS = range(1, 8)  # days after the last known day: tomorrow .. a week ahead
MIN_DAYS = 28
COLUMNS = ["lead", "hour", "weekday", "month", "level", "last_day", "last_week", "profile"]
TEMP_COLUMNS = ["temp", "temp_change"]


def hourly_load(slots: pd.DataFrame) -> pd.Series:
    """Hourly mean load (kW) from 15-minute measurements (offpeak/load), indexed by UTC hour."""
    return slots.set_index("ts")["load_kw"].resample("1h").mean().dropna()


def _features(m, d0, lead, day, temps=None) -> pd.DataFrame:
    """24 rows: the facts for each hour of day d0 + lead, standing at the end of day d0."""
    week = m[d0 - 6 : d0 + 1]
    level = float(week.mean())
    out = {
        "lead": lead,
        "hour": np.arange(24),
        "weekday": day.weekday(),
        "month": day.month,
        "level": level,
        "last_day": m[d0] - level,
        "last_week": m[d0 + lead - 7] - level,
        "profile": week.mean(axis=0) - level,
    }
    if temps is not None:
        target = temps[d0 + lead]
        out["temp"] = target
        out["temp_change"] = _mean(target) - _mean(temps[d0 - 6 : d0 + 1])
    return pd.DataFrame(out)


def _mean(a: np.ndarray) -> float:
    """Mean of what is known; NaN when nothing is (the model copes with gaps)."""
    return float(np.nanmean(a)) if np.isfinite(a).any() else np.nan


def _days(index, extra: int = 0) -> list:
    last = index[-1]
    return list(index) + [last + pd.Timedelta(days=i) for i in range(1, extra + 1)]


def _temp_matrix(temp: pd.Series | None, days) -> np.ndarray | None:
    if temp is None or temp.empty:
        return None
    return daily_matrix(temp).reindex(days).to_numpy()


class LoadModel:
    """Learns one site's consumption. `temp`: hourly air temperature (°C, UTC index), the
    measured past for training and the forecast for the coming days; optional."""

    key = "ml"
    label = "ML model"

    def __init__(self, loss: str = "squared_error") -> None:
        self.loss = loss
        self.model: HistGradientBoostingRegressor | None = None
        self.columns = COLUMNS

    def fit(self, history: pd.Series, temp: pd.Series | None = None) -> "LoadModel":
        table = daily_matrix(history)
        if len(table) < MIN_DAYS:
            raise ValueError(f"Needs at least {MIN_DAYS} days of measurements")
        m = table.to_numpy()
        temps = _temp_matrix(temp, list(table.index))
        self.columns = COLUMNS + (TEMP_COLUMNS if temps is not None else [])
        xs, ys = [], []
        for d0 in range(6, len(m) - 1):
            level = m[d0 - 6 : d0 + 1].mean()
            for lead in LEADS:
                if d0 + lead >= len(m):
                    break
                xs.append(_features(m, d0, lead, table.index[d0 + lead], temps))
                ys.append(m[d0 + lead] - level)
        x = pd.concat(xs, ignore_index=True)[self.columns]
        self.model = HistGradientBoostingRegressor(
            loss=self.loss, max_iter=300, learning_rate=0.05, random_state=0
        ).fit(x, np.concatenate(ys))
        return self

    def predict(self, history: pd.Series, temp: pd.Series | None = None) -> pd.DataFrame:
        """kW for every hour of the 7 days after the last measured day: day, lead, hour, kw."""
        if self.model is None:
            raise ValueError("Fit the model first")
        table = daily_matrix(history)
        m = table.to_numpy()
        d0 = len(m) - 1
        days = _days(table.index, extra=7)
        temps = _temp_matrix(temp, days) if "temp" in self.columns else None
        level = m[d0 - 6 : d0 + 1].mean()
        parts = []
        for lead in LEADS:
            x = _features(np.vstack([m, np.zeros((7, 24))]), d0, lead, days[d0 + lead], temps)
            kw = np.clip(level + self.model.predict(x[self.columns]), 0, None)
            parts.append(
                pd.DataFrame({"day": days[d0 + lead], "lead": lead, "hour": range(24), "kw": kw})
            )
        return pd.concat(parts, ignore_index=True)


@dataclass
class LoadBacktest:
    mae_kw: dict[str, float]  # hourly mean absolute error, kW, per forecaster
    daily_mae_kwh: dict[str, float]  # error of each day's total, kWh
    by_lead: pd.DataFrame  # forecaster x lead: hourly MAE, kW
    days: int


def backtest(
    history: pd.Series,
    temp: pd.Series | None = None,
    days: int = 56,
    retrain: int = 14,
    loss: str = "squared_error",
) -> LoadBacktest:
    """Walk forward over the last `days` days. Each day d0 pretends to be today: the model,
    trained only on days up to d0 (again every `retrain` days), forecasts d0+1 .. d0+7."""
    table = daily_matrix(history)
    m = table.to_numpy()
    n = len(m)
    if n < MIN_DAYS + days:
        raise ValueError("Not enough measurements for this backtest")
    temps_all = _temp_matrix(temp, list(table.index))
    rows, model, trained_at = [], None, -retrain
    for d0 in range(n - days - 7, n - 7):
        if d0 - trained_at >= retrain:
            past = history[
                history.index < pd.Timestamp(table.index[d0 + 1], tz=TZ).tz_convert("UTC")
            ]
            model = LoadModel(loss).fit(past, temp)
            trained_at = d0
        level = m[d0 - 6 : d0 + 1].mean()
        for lead in LEADS:
            truth = m[d0 + lead]
            x = _features(m, d0, lead, table.index[d0 + lead], temps_all)
            guesses = {
                "ML model": np.clip(level + model.model.predict(x[model.columns]), 0, None),
                "Same hour last week": m[d0 + lead - 7],
                "Average of the last 7 days": m[d0 - 6 : d0 + 1].mean(axis=0),
            }
            for name, guess in guesses.items():
                rows.append(
                    {
                        "forecaster": name,
                        "lead": lead,
                        "abs_kw": np.abs(guess - truth).mean(),
                        "day_kwh": abs(guess.sum() - truth.sum()),
                    }
                )
    err = pd.DataFrame(rows)
    return LoadBacktest(
        mae_kw=err.groupby("forecaster")["abs_kw"].mean().round(3).to_dict(),
        daily_mae_kwh=err.groupby("forecaster")["day_kwh"].mean().round(2).to_dict(),
        by_lead=err.pivot_table(index="forecaster", columns="lead", values="abs_kw").round(3),
        days=days,
    )
