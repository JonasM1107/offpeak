"""What the price model learned: which information its forecast depends on.

The method (permutation importance): train the model on everything except the last weeks,
then forecast those weeks once normally and once with one kind of information shuffled
between the rows, so it no longer belongs to the right hour. The more the average miss grows,
the more the model relies on that information. Related columns (the three wind columns, for
example) are shuffled together, so they cannot stand in for each other.

The last weeks are never seen in training, so this measures what helps on new days.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from offpeak.forecast.model import PriceModel, daily_matrix, training_set

GROUPS = {
    "Wind forecast": ["wind", "wind_day", "wind_change"],
    "Sun forecast": ["sun", "sun_day", "sun_change"],
    "Temperature forecast": ["temp_day"],
    "Recent prices": ["last_day", "last_week", "profile", "trend", "spread"],
    "Hour of day": ["hour"],
    "Weekday": ["weekday"],
    "Days ahead": ["lead"],
}


def what_matters(
    history: pd.Series, model: PriceModel, holdout_days: int = 56, repeats: int = 3
) -> dict | None:
    """The model's average miss on the last `holdout_days` days (ct/kWh) and, per kind of
    information, how much larger it gets without it, largest first. None with too little
    history."""
    table = daily_matrix(history)
    cut = len(table) - holdout_days
    if cut < 28:
        return None
    columns = model.columns
    x_train, y_train = training_set(table.iloc[:cut], model.tables)
    # examples standing at the end of day cut - 1: every target lies in the held-out weeks
    x_test, y_test = training_set(table.iloc[cut - 7 :], model.tables)
    fitted = HistGradientBoostingRegressor(
        loss="absolute_error", max_iter=200, learning_rate=0.05, random_state=0
    ).fit(x_train[columns], y_train)
    base = float(np.mean(np.abs(fitted.predict(x_test[columns]) - y_test)))
    rng = np.random.default_rng(0)
    rows = []
    for label, cols in GROUPS.items():
        if not set(cols) <= set(columns):
            continue
        worse = []
        for _ in range(repeats):
            shuffled = x_test[columns].copy()
            order = rng.permutation(len(shuffled))
            shuffled[cols] = shuffled[cols].to_numpy()[order]  # the same shuffle for the group
            worse.append(np.mean(np.abs(fitted.predict(shuffled) - y_test)) - base)
        rows.append({"label": label, "ct": round(max(0.0, float(np.mean(worse))), 2)})
    rows.sort(key=lambda r: -r["ct"])
    return {"mae": round(base, 2), "days": holdout_days, "groups": rows}
