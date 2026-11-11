"""Backtest the forecasters and build the price outlook for the coming days.

Timing, as in real use: once tomorrow's prices are published (around 13:00), we know prices
up to the end of D+1 and forecast D+2 to D+7, so the lead is 1 to 6 days beyond the last
known price.
"""

from dataclasses import dataclass

import pandas as pd

from offpeak.forecast.baselines import Blend, LastDay, LastWeek

FORECASTERS = [LastWeek(), LastDay(), Blend()]  # the ML model joins here once it is trained
LEAD_DAYS = range(1, 7)  # days after the last published day (D+2 .. D+7)


def local_day_hours(day, tz: str) -> pd.DatetimeIndex:
    """UTC start of every hour of one local day (23, 24 or 25 hours)."""
    start = pd.Timestamp(day, tz=tz)
    # the next local midnight, not start + 24 h: clock-change days are 23 or 25 hours long
    end = pd.Timestamp(start.date() + pd.Timedelta(days=1), tz=tz)
    return pd.date_range(start, end, freq="h", inclusive="left").tz_convert("UTC")


def cheapest_hours(values: pd.Series, n: int) -> set:
    return set(values.nsmallest(n).index)


@dataclass
class Backtest:
    errors: pd.DataFrame  # forecaster, lead, ts, forecast, actual
    scores: pd.DataFrame  # forecaster, mae, decision (share 0..1), by lead as columns mae_1..


def backtest(history: pd.Series, tz: str, days: int = 56, forecasters=None) -> Backtest:
    """Walk forward over the last `days` days: each day pretends to be 'today', with prices
    known up to the end of the next day, and forecasts the 6 days after that."""
    forecasters = forecasters or FORECASTERS
    hours_per_day = pd.Series(1, index=history.index.tz_convert(tz).date).groupby(level=0).sum()
    local_days = sorted(hours_per_day.index)
    last_full = hours_per_day[hours_per_day >= 23].index.max()  # skip a day still incomplete
    rows = []
    for origin in local_days[-(days + 7) : -7]:
        known_until = local_day_hours(origin, tz)[-1] + pd.Timedelta(days=1)  # end of D+1
        seen = history[history.index <= known_until]
        for lead in LEAD_DAYS:
            target_day = origin + pd.Timedelta(days=1 + lead)
            if target_day > last_full:
                continue
            targets = local_day_hours(target_day, tz)
            actual = history.reindex(targets)
            for f in forecasters:
                guess = f.predict(seen, targets)
                rows.append(
                    pd.DataFrame(
                        {
                            "forecaster": f.key,
                            "lead": lead,
                            "day": target_day,
                            "ts": targets,
                            "forecast": guess.values,
                            "actual": actual.values,
                        }
                    )
                )
    if not rows:
        raise ValueError("Not enough price history for a backtest (needs about 3 weeks).")
    errors = pd.concat(rows, ignore_index=True).dropna(subset=["forecast", "actual"])
    errors["error"] = errors["forecast"] - errors["actual"]
    return Backtest(errors=errors, scores=_scores(errors))


def _decision(group: pd.DataFrame) -> float:
    """Share of the forecast's 4 cheapest hours that are among the day's 6 truly cheapest."""
    picked = cheapest_hours(group.set_index("ts")["forecast"], 4)
    true = cheapest_hours(group.set_index("ts")["actual"], 6)
    return len(picked & true) / 4


def _scores(errors: pd.DataFrame) -> pd.DataFrame:
    out = []
    for key, g in errors.groupby("forecaster", sort=False):
        row = {"forecaster": key, "mae": g["error"].abs().mean()}
        decisions = g.groupby(["lead", "day"]).apply(_decision, include_groups=False)
        row["decision"] = decisions.mean()
        for lead, gl in g.groupby("lead"):
            row[f"mae_{lead}"] = gl["error"].abs().mean()
        out.append(row)
    return pd.DataFrame(out)


def best_by_lead(test: Backtest) -> dict[int, str]:
    """For each lead day, the forecaster with the smallest backtest error there."""
    scores = test.scores.set_index("forecaster")
    return {lead: scores[f"mae_{lead}"].idxmin() for lead in LEAD_DAYS if f"mae_{lead}" in scores}


def outlook(
    history: pd.Series, tz: str, test: Backtest, forecasters=None
) -> tuple[pd.DataFrame, dict[int, str]]:
    """Forecast the 6 days after the last published day. Each lead day uses the forecaster
    that did best at that lead in the backtest. Band: the 10th and 90th percentile of that
    forecaster's past errors at the same lead.
    Returns (ts, day, lead, forecaster, p10, p50, p90) and the forecaster used per lead."""
    forecasters = {f.key: f for f in (forecasters or FORECASTERS)}
    used = best_by_lead(test)
    last_day = history.index.max().tz_convert(tz).date()
    parts = []
    for lead, key in used.items():
        day = last_day + pd.Timedelta(days=lead)
        targets = local_day_hours(day, tz)
        p50 = forecasters[key].predict(history, targets)
        err = test.errors[(test.errors["forecaster"] == key) & (test.errors["lead"] == lead)]
        # error = forecast - actual, so actual = forecast - error
        lo, hi = err["error"].quantile(0.9), err["error"].quantile(0.1)
        parts.append(
            pd.DataFrame(
                {
                    "ts": targets,
                    "day": day,
                    "lead": lead,
                    "forecaster": key,
                    "p50": p50.values,
                    "p10": p50.values - lo,
                    "p90": p50.values - hi,
                }
            )
        )
    return pd.concat(parts, ignore_index=True), used


def day_summaries(out: pd.DataFrame, tz: str, window: int = 3) -> pd.DataFrame:
    """Per forecast day: average p10/p50/p90 and the cheapest `window` hours in a row."""
    rows = []
    for day, g in out.groupby("day"):
        g = g.sort_values("ts").reset_index(drop=True)
        roll = g["p50"].rolling(window).mean()
        end = int(roll.idxmin())
        start_local = g.loc[end - window + 1, "ts"].tz_convert(tz)
        rows.append(
            {
                "day": day,
                "lead": int(g["lead"].iloc[0]),
                "forecaster": g["forecaster"].iloc[0],
                "p10": g["p10"].mean(),
                "p50": g["p50"].mean(),
                "p90": g["p90"].mean(),
                "window_start": start_local.hour,
                "window_ct": float(roll.min()),
            }
        )
    return pd.DataFrame(rows)


def _unix(ts) -> list[int]:
    return (
        (pd.Series(ts) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
    ).tolist()


def view_payload(history: pd.Series, test: Backtest, tz: str, forecasters=None) -> dict:
    """Everything the Price outlook view draws: the last two weeks of published prices, the
    forecast with its band, a summary per forecast day and the backtest scores."""
    forecasters = forecasters or FORECASTERS
    labels = {f.key: f.label for f in forecasters}
    out, used = outlook(history, tz, test, forecasters)
    days = day_summaries(out, tz)
    recent = history[history.index > history.index.max() - pd.Timedelta(days=14)]
    scores = test.scores.set_index("forecaster")
    return {
        "published": {"t": _unix(recent.index), "ct": recent.round(2).tolist()},
        "forecast": {
            "t": _unix(out["ts"]),
            "p10": out["p10"].round(2).tolist(),
            "p50": out["p50"].round(2).tolist(),
            "p90": out["p90"].round(2).tolist(),
        },
        "days": [
            {
                "name": f"{pd.Timestamp(d['day']):%a %-d %b}",
                "lead": int(d["lead"]),
                "start": int(pd.Timestamp(d["day"], tz=tz).timestamp()),
                "end": int(local_day_hours(d["day"], tz)[-1].timestamp()) + 3600,
                "p10": round(d["p10"], 1),
                "p50": round(d["p50"], 1),
                "p90": round(d["p90"], 1),
                "window": f"{d['window_start']:02d}–{(d['window_start'] + 3) % 24:02d}",
                "window_ct": round(d["window_ct"], 1),
                "model": labels[d["forecaster"]],
            }
            for _, d in days.iterrows()
        ],
        "models": [
            {
                "key": key,
                "label": labels[key],
                "mae": round(float(row["mae"]), 2),
                "decision": round(float(row["decision"]) * 100),
                "by_lead": [round(float(row[f"mae_{lead}"]), 2) for lead in LEAD_DAYS],
                "used_for": [lead + 1 for lead, k in used.items() if k == key],
            }
            for key, row in scores.iterrows()
        ],
        "backtest_days": int(test.errors["day"].nunique()),
        "last_published": f"{history.index.max().tz_convert(tz):%a %-d %b}",
    }
