"""What every price forecaster provides, so the page and the backtest work with any of them.

A forecaster gets the hourly price history (ct/kWh, indexed by the UTC start of each hour,
everything up to the last published hour) and returns its best guess (the median, p50) for
the hours asked for. The ML model (offpeak/forecast/model.py) is one more forecaster.
"""

from typing import Protocol

import pandas as pd


class Forecaster(Protocol):
    key: str  # short id, e.g. "last_week"
    label: str  # shown on the page

    def predict(self, history: pd.Series, targets: pd.DatetimeIndex) -> pd.Series:
        """Median price (ct/kWh) for each target hour (UTC), indexed like `targets`."""
        ...
