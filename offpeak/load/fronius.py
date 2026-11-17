"""Read a Fronius Solar.web history (5-minute CSV) into 15-minute slots.

The CSV comes from scripts/experiments/fronius/fetch_solarweb.js on the branch
experiment/fronius-data: one row per 5 minutes, ts_utc, then watts per flow (Solar.web's own
series ids) and the battery's charge in %. Real files stay out of the repository (data/ is
git-ignored); the tests use a small made-up file in tests/fixtures/.

Our columns (kW, mean over the 15 minutes; soc in %):
    pv_kw          FromGen                own solar production
    load_kw        ToConsumer             what the house used
    grid_in_kw     FromGridToConsumer     bought from the grid
    grid_out_kw    FromGenToGrid          sold to the grid
    battery_in_kw  FromGenToBatt          solar into the battery
    battery_out_kw FromBattToConsumer     battery into the house
    soc_pct        StateOfChargeAggregated
"""

from pathlib import Path

import pandas as pd

COLUMNS = {
    "FromGen": "pv_kw",
    "ToConsumer": "load_kw",
    "FromGridToConsumer": "grid_in_kw",
    "FromGenToGrid": "grid_out_kw",
    "FromGenToBatt": "battery_in_kw",
    "FromBattToConsumer": "battery_out_kw",
}
REQUIRED = ("ts_utc", "FromGen", "ToConsumer")
MAX_KW = 100.0  # a household or small business inverter; anything above is a unit mistake


class FroniusFileError(ValueError):
    """The file is not a Fronius history we can read; the message says why."""


def read_csv(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """15-minute slots: ts (UTC slot start) and the columns above. Slots without any value
    are dropped, never filled in. Raises FroniusFileError for a file that is not usable."""
    raw = source if isinstance(source, pd.DataFrame) else pd.read_csv(source)
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise FroniusFileError(f"missing columns: {', '.join(missing)}")
    ts = pd.to_datetime(raw["ts_utc"], utc=True, errors="coerce", format="ISO8601")
    if ts.isna().any():
        raise FroniusFileError(f"{int(ts.isna().sum())} rows have no valid time")
    watts = raw[[c for c in COLUMNS if c in raw.columns]].apply(pd.to_numeric, errors="coerce")
    if (watts < 0).any().any():
        raise FroniusFileError("negative power: these columns are flows and never negative")
    kw = watts.rename(columns=COLUMNS) / 1000
    if (kw > MAX_KW).any().any():
        raise FroniusFileError(f"power above {MAX_KW:.0f} kW: is the file in W?")
    frame = kw.set_index(ts)
    if "StateOfChargeAggregated" in raw.columns:
        soc = pd.to_numeric(raw["StateOfChargeAggregated"], errors="coerce").set_axis(ts)
        if ((soc < 0) | (soc > 100)).any():
            raise FroniusFileError("battery charge outside 0-100 %")
        frame["soc_pct"] = soc
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    # Solar.web leaves a flow empty when it is zero (no export at night, for example), but a
    # row without production or consumption is a gap
    known = frame[["pv_kw", "load_kw"]].notna().any(axis=1)
    frame = frame[known].fillna({c: 0.0 for c in COLUMNS.values() if c in frame})
    slots = frame.resample("15min").mean().dropna(how="all")
    return slots.rename_axis("ts").reset_index()


def coverage(slots: pd.DataFrame) -> dict:
    """What a file covers: first and last slot, days with data, missing slots in between."""
    if slots.empty:
        return {"first": None, "last": None, "days": 0, "missing_slots": 0}
    expected = pd.date_range(slots["ts"].min(), slots["ts"].max(), freq="15min")
    return {
        "first": slots["ts"].min(),
        "last": slots["ts"].max(),
        "days": int(slots["ts"].dt.tz_convert("Europe/Berlin").dt.date.nunique()),
        "missing_slots": int(len(expected) - len(slots)),
    }


# The browser-console script on the "My data" page (the page puts `const FIRST = new Date(...)`
# in front, the day after the newest stored one). It is fetch_solarweb.js from the Fronius
# experiment, shortened: the system id comes from the page address, four requests at a time.
SYNC_SCRIPT = """const ID = new URLSearchParams(location.search).get('pvSystemId');
const LAST = new Date(); LAST.setDate(LAST.getDate() - 1);  // up to yesterday
(async () => {
  if (!ID) return alert('Open your system\\'s chart page on solarweb.com first.');
  const sleep = ms => new Promise(r => setTimeout(r, ms)), days = [], rows = {}, cols = new Set();
  for (let d = new Date(FIRST); d <= LAST; d.setDate(d.getDate() + 1))
    days.push([d.getFullYear(), d.getMonth() + 1, d.getDate()]);
  let next = 0, failed = 0;
  async function day([y, m, d]) {
    for (const view of ['production', 'consumption']) {
      const q = `pvSystemId=${ID}&year=${y}&month=${m}&day=${d}&interval=day&view=${view}`;
      const r = await fetch(`/Chart/GetChartNew?${q}`);
      if (!r.ok) { failed++; continue; }
      for (const s of (await r.json()).settings.series) {
        if (!Array.isArray(s.data) || s.data.length < 2) continue;
        cols.add(s.id);
        for (const [ts, v] of s.data) (rows[ts] ||= {})[s.id] = v;
      }
    }
  }
  async function worker() {
    while (next < days.length) { await day(days[next++]); await sleep(500); }
  }
  await Promise.all([worker(), worker(), worker(), worker()]);
  const head = [...cols], lines = ['ts_utc,' + head.join(',')];
  for (const ts of Object.keys(rows).map(Number).sort((a, b) => a - b))
    lines.push(new Date(ts).toISOString() + ',' + head.map(c => rows[ts][c] ?? '').join(','));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lines.join('\\n')], { type: 'text/csv' }));
  a.download = 'fronius_5min.csv'; document.body.appendChild(a); a.click();
  console.log(`${days.length} days, ${lines.length - 1} rows, ${failed} failed requests`);
})();"""
