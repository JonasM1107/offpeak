// Fetch a Fronius system's 5-minute history from Solar.web and download it as one CSV.
//
// Run it in the browser console on a solarweb.com page, signed in as the system's owner,
// after replacing PV_SYSTEM_ID (from the page URL: ...?pvSystemId=<id>) and FIRST_DAY.
// It reads the same JSON the Solar.web charts load (GetChartNew, interval=day), for the
// "production" and "consumption" views, day by day, with four requests in parallel and a
// short pause after each. Read only: nothing in the account changes.
//
// This is not an official Fronius API (that is the paid Solar.web Query API). Use it only
// for your own system, once, and keep the file out of the repository (data/ is ignored).

const PV_SYSTEM_ID = 'REPLACE-WITH-YOUR-PV-SYSTEM-ID';
const FIRST_DAY = new Date(2023, 8, 16);  // the system's first day (months count from 0)
const LAST_DAY = new Date(new Date().setDate(new Date().getDate() - 1));  // yesterday
const WORKERS = 4, PAUSE_MS = 500;

(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const days = [];
  for (let d = new Date(FIRST_DAY); d <= LAST_DAY; d.setDate(d.getDate() + 1)) {
    days.push([d.getFullYear(), d.getMonth() + 1, d.getDate()]);
  }
  const rows = {}, cols = new Set(), failed = [];
  let next = 0;
  async function getDay([y, m, d]) {
    for (const view of ['production', 'consumption']) {
      let ok = false;
      for (let attempt = 0; attempt < 3 && !ok; attempt++) {
        try {
          const r = await fetch(`/Chart/GetChartNew?pvSystemId=${PV_SYSTEM_ID}&year=${y}&month=${m}&day=${d}&interval=day&view=${view}`);
          if (!r.ok) throw new Error(r.status);
          for (const s of (await r.json()).settings.series) {
            if (!Array.isArray(s.data) || s.data.length < 2) continue;  // skip status series
            cols.add(s.id);
            for (const [ts, v] of s.data) (rows[ts] ||= {})[s.id] = v;  // ts: UTC milliseconds
          }
          ok = true;
        } catch (e) { await sleep(2000); }
      }
      if (!ok) failed.push(`${y}-${m}-${d} ${view}`);
    }
  }
  async function worker() {
    while (next < days.length) { await getDay(days[next++]); await sleep(PAUSE_MS); }
  }
  await Promise.all(Array.from({ length: WORKERS }, worker));

  const header = [...cols];
  const lines = ['ts_utc,' + header.join(',')];
  for (const ts of Object.keys(rows).map(Number).sort((a, b) => a - b)) {
    lines.push(new Date(ts).toISOString() + ',' + header.map(c => rows[ts][c] ?? '').join(','));
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
  a.download = 'fronius_5min.csv';
  document.body.appendChild(a);
  a.click();
  console.log(`${days.length} days, ${lines.length - 1} rows, failed: ${failed.length}`, failed);
})();
