"""The slot for the machine-learning price model (docs/PLAN.md section 9.4). Not trained yet.

Plan: LightGBM, trained three times for the 10 %, 50 % and 90 % quantiles, hourly, for
D+2 to D+7. Features: hour, weekday, holiday; recent prices and the same hour last week; the
wind forecast at 100 m across northern Germany and solar radiation in the south; temperature.
Train on historical *forecasts* (Open-Meteo previous runs), never on measured weather, and
validate walking forward in time.

To plug it in: implement `predict()` (same contract as offpeak/forecast/base.py), add the
instance to FORECASTERS in offpeak/forecast/outlook.py. The page then compares it with the
baselines and uses it as soon as its backtest error is lower.
"""

import pandas as pd


class PriceModel:
    key = "ml"
    label = "Machine learning model"

    def predict(self, history: pd.Series, targets: pd.DatetimeIndex) -> pd.Series:
        raise NotImplementedError("The ML price model is not trained yet.")
