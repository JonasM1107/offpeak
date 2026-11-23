"""Read a consumption export (smart meter app, metering operator, ERP such as SAP) into
15-minute slots.

Such exports differ in detail but share a shape: one row per interval, a time and the energy
(kWh) or power (kW) of that interval. We accept that shape, whatever the interval (5 minutes to
1 hour), with comma or semicolon separators and German decimal commas, because that is what
Excel in Germany writes.

    time column    named timestamp, time, ts, datetime, date, zeit, zeitstempel or datum
                   (any case); with a UTC offset, or without one = German local time
    value column   the first column whose name contains "kwh" (energy per interval) or
                   else "kw" (mean power), e.g. "consumption_kWh" or "Verbrauch (kWh)"

The result is like offpeak/load/fronius.py's: ts (UTC slot start) and load_kw, the mean power
over the 15 minutes. Hourly values are spread evenly over their four quarter-hours, because a
meter that reports hourly says nothing finer. Nothing is guessed: rows without a value are
dropped, never filled in.
"""

from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/Berlin"
TIME_NAMES = ("timestamp", "time", "ts", "datetime", "date", "zeit", "zeitstempel", "datum")
MAX_KW = 10_000.0  # 10 MW: a large SME; anything above is a unit mistake (W instead of kW)
MIN_ROWS = 4  # less than an hour of data says nothing about a consumption profile


class MeterFileError(ValueError):
    """The file is not a consumption export we can read; the message says why."""


def _find_columns(columns) -> tuple[str, str, str]:
    """The time column, the value column and its unit ('kwh' or 'kw')."""
    lower = {str(c).strip().lower(): c for c in columns}
    time = next((lower[n] for n in TIME_NAMES if n in lower), None)
    if time is None:
        raise MeterFileError("no time column (name it e.g. 'timestamp')")
    for unit in ("kwh", "kw"):  # "kwh" first: "kw" is part of "kwh"
        value = next((c for n, c in lower.items() if unit in n and c != time), None)
        if value is not None:
            return time, value, unit
    raise MeterFileError("no column in kWh or kW (name it e.g. 'consumption_kwh')")


def _to_utc(raw: pd.Series) -> pd.Series:
    """Times to UTC: with an offset as given, without one as German local time."""
    text = raw.astype(str).str.strip()
    has_offset = text.str.contains(r"(?:[+-]\d{2}:?\d{2}|Z)$", regex=True)
    if has_offset.all():
        ts = pd.to_datetime(text, utc=True, errors="coerce", format="ISO8601")
    else:
        local = pd.to_datetime(text, errors="coerce", dayfirst=True, format="mixed")
        if local.isna().any():
            raise MeterFileError(f"{int(local.isna().sum())} rows have no valid time")
        # The hour that exists twice in late October: a file listing it twice in order is read
        # as summer time, then winter time ("infer"); a file listing it once takes summer time.
        # The hour that does not exist in late March is moved forward.
        try:
            ts = local.dt.tz_localize(TZ, ambiguous="infer", nonexistent="shift_forward")
        except Exception:  # pytz/pandas cannot infer: one copy of the hour only
            ts = local.dt.tz_localize(TZ, ambiguous=True, nonexistent="shift_forward")
        ts = ts.dt.tz_convert("UTC")
    if ts.isna().any():
        raise MeterFileError(f"{int(ts.isna().sum())} rows have no valid time")
    return ts


def read_csv(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """15-minute slots: ts (UTC slot start) and load_kw. Raises MeterFileError for a file that
    cannot be used, with the reason in words."""
    if isinstance(source, pd.DataFrame):
        raw = source
    else:
        try:  # sep=None: let pandas find out whether "," or ";" separates the columns
            raw = pd.read_csv(source, sep=None, engine="python", dtype=str)
        except (pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as err:
            raise MeterFileError(f"not a readable CSV file ({err.__class__.__name__})") from err
    time, value, unit = _find_columns(raw.columns)
    ts = _to_utc(raw[time])
    # "1.234,5" (German) and "1234.5" both become 1234.5
    text = raw[value].astype(str).str.strip()
    german = text.str.contains(",", regex=False)
    text = text.where(~german, text.str.replace(".", "", regex=False).str.replace(",", "."))
    values = pd.to_numeric(text, errors="coerce").set_axis(ts)
    values = values[~values.index.duplicated(keep="first")].sort_index()
    # the interval the meter reports in: the most common step between two rows, taken before
    # empty rows are dropped, so a gap does not look like a longer interval
    steps = values.index.to_series().diff().dropna()
    values = values.dropna()
    if len(values) < MIN_ROWS:
        raise MeterFileError("fewer than four values: too little to show a profile")
    if (values < 0).any():
        raise MeterFileError("negative consumption: is this a feed-in column?")
    step = steps.mode().min()  # with a tie, the shorter step
    if not pd.Timedelta(minutes=1) <= step <= pd.Timedelta(hours=1):
        raise MeterFileError("one value per 1 to 60 minutes expected")
    kw = values / (step / pd.Timedelta(hours=1)) if unit == "kwh" else values
    if (kw > MAX_KW).any():
        raise MeterFileError(f"more than {MAX_KW:,.0f} kW: is the file in W or Wh?")
    # a value longer than a quarter-hour holds for each quarter-hour of its interval: an hourly
    # value at 10:00 becomes four equal ones at 10:00, 10:15, 10:30 and 10:45
    parts = max(1, int(step // pd.Timedelta(minutes=15)))
    if parts > 1:
        offsets = pd.to_timedelta(np.tile(np.arange(parts) * 15, len(kw)), unit="min")
        kw = pd.Series(kw.to_numpy().repeat(parts), index=kw.index.repeat(parts) + offsets)
    slots = kw.resample("15min").mean().dropna()
    return slots.rename("load_kw").rename_axis("ts").reset_index()


def summary(slots: pd.DataFrame) -> dict:
    """What a file shows: days, energy in total and per day, the peak, and the average power
    per hour of the (local) day."""
    if slots.empty:
        return {"days": 0, "kwh": 0.0, "kwh_per_day": 0.0, "peak_kw": 0.0, "by_hour": []}
    local = slots["ts"].dt.tz_convert(TZ)
    days = int(local.dt.date.nunique())
    kwh = float(slots["load_kw"].sum() * 0.25)  # kW over a quarter-hour = kWh / 4
    by_hour = slots.groupby(local.dt.hour)["load_kw"].mean().reindex(range(24))
    return {
        "days": days,
        "first": slots["ts"].min(),
        "last": slots["ts"].max(),
        "kwh": kwh,
        "kwh_per_day": kwh / days,
        "peak_kw": float(slots["load_kw"].max()),
        "by_hour": [None if pd.isna(v) else round(float(v), 3) for v in by_hour],
    }
