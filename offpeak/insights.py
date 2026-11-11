"""Plain-language insights for the dashboard: what to do tomorrow, what shifting is worth,
and a rough look at the days after tomorrow. Everything here is arithmetic on real prices
and the real wind forecast; the pages only draw the results.
"""

from dataclasses import dataclass

import pandas as pd

from offpeak.analysis import Window, best_window

# Typical flexible loads, for "what is moving it worth?" (power in kW, run time in hours)
LOAD_EXAMPLES = [
    ("Induction furnace batch", 500.0, 1),
    ("EV fleet charging", 60.0, 4),
    ("Compressed air", 30.0, 2),
    ("Cold store pre-cooling", 15.0, 3),
]


@dataclass
class Shift:
    name: str
    kw: float
    hours: int
    cheap: Window  # cheapest block of that length
    peak: Window  # most expensive block of that length
    saving_eur: float  # cost at peak - cost in the cheap block, energy part only


def shift_savings(prices: pd.DataFrame, loads=LOAD_EXAMPLES) -> list[Shift]:
    """For each example load: run it in the cheapest block instead of the most expensive one.

    Saving = kWh × (peak price − cheap price). Prices are €/MWh, so divide by 1000 for €/kWh.
    Only the market price counts here; grid fees and taxes are the same in every hour.
    """
    out = []
    for name, kw, hours in loads:
        cheap, peak = best_window(prices, hours), best_window(prices, hours, cheapest=False)
        if cheap is None or peak is None:
            continue
        kwh = kw * hours
        saving = kwh * (peak.avg_eur_mwh - cheap.avg_eur_mwh) / 1000
        out.append(Shift(name, kw, hours, cheap, peak, saving))
    return out


def change_pct(before: float, after: float) -> float | None:
    """Change from `before` to `after` in percent, or None if `before` is zero."""
    if before == 0:
        return None
    return (after - before) / abs(before) * 100


@dataclass
class WindFit:
    """A straight line through the last weeks: price = intercept + slope × wind."""

    intercept: float  # ct/kWh when there is no wind
    slope: float  # ct/kWh per extra m/s (negative: wind makes power cheaper)
    mae: float  # typical error of the line, in ct/kWh, on the hours it was fitted on
    hours: int


def fit_wind_line(joined: pd.DataFrame) -> WindFit | None:
    """Least-squares line through hourly (wind, price) pairs.

    slope = covariance(wind, price) / variance(wind)
    intercept = mean price − slope × mean wind
    Needs columns wind_north_ms and ct_kwh, and at least a week of hours.
    """
    if len(joined) < 24 * 7 or joined["wind_north_ms"].var() == 0:
        return None
    wind, price = joined["wind_north_ms"], joined["ct_kwh"]
    slope = wind.cov(price) / wind.var()
    intercept = price.mean() - slope * wind.mean()
    mae = (price - (intercept + slope * wind)).abs().mean()
    return WindFit(float(intercept), float(slope), float(mae), len(joined))


def outlook(fit: WindFit, daily_wind: pd.DataFrame, typical_ct: float) -> pd.DataFrame:
    """Estimated average price per day from that day's average wind.

    Columns: day, wind_north_ms, est_ct, label ("likely cheaper", "about usual",
    "likely pricier" compared with `typical_ct`, the average of the last weeks).
    """
    est = fit.intercept + fit.slope * daily_wind["wind_north_ms"]
    label = pd.Series("about usual", index=daily_wind.index)
    label[est < typical_ct - fit.mae / 2] = "likely cheaper"
    label[est > typical_ct + fit.mae / 2] = "likely pricier"
    return daily_wind.assign(est_ct=est, label=label)


def _clock(ts: pd.Timestamp, tz: str, is_end: bool = False) -> str:
    """Local clock time; a block ending at midnight reads 24:00."""
    t = pd.Timestamp(ts).tz_convert(tz)
    return "24:00" if is_end and t.hour == 0 and t.minute == 0 else t.strftime("%H:%M")


def headline(today: pd.DataFrame, tomorrow: pd.DataFrame, tz: str) -> str | None:
    """One sentence a business owner can act on, or None before tomorrow's prices are out."""
    cheap, peak = best_window(tomorrow, 3), best_window(tomorrow, 3, cheapest=False)
    if cheap is None or peak is None:
        return None
    parts = []
    if not today.empty:
        pct = change_pct(today["eur_mwh"].mean(), tomorrow["eur_mwh"].mean())
        if pct is not None and abs(pct) >= 5:
            parts.append(
                f"Tomorrow is {abs(pct):.0f} % {'cheaper' if pct < 0 else 'dearer'} than today."
            )
        else:
            parts.append("Tomorrow costs about the same as today.")
    parts.append(
        f"Run flexible loads {_clock(cheap.start, tz)}–{_clock(cheap.end, tz, True)} "
        f"({cheap.avg_eur_mwh / 10:.1f} ct/kWh) and avoid "
        f"{_clock(peak.start, tz)}–{_clock(peak.end, tz, True)} "
        f"({peak.avg_eur_mwh / 10:.1f} ct/kWh)."
    )
    return " ".join(parts)
