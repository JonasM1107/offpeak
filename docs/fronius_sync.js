// Fetches a Fronius system's 5-minute history from solarweb.com as fronius_5min.csv, which
// the Connect card (Settings or My data, Homeowner) reads. For the team, not for customers:
// open the system's chart page on solarweb.com while signed in, open the browser console,
// set FIRST to the day after the newest day offpeak has (My data: "Newest day"), paste, Enter.
// It only reads what the Solar.web charts show and changes nothing.
const FIRST = new Date(2023, 8, 16);  // first day to fetch; months count from 0 (8 = September)
const ID = new URLSearchParams(location.search).get('pvSystemId');
const LAST = new Date(); LAST.setDate(LAST.getDate() - 1);  // up to yesterday
(async () => {
  if (!ID) return alert('Open your system\'s chart page on solarweb.com first.');
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
  a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
  a.download = 'fronius_5min.csv'; document.body.appendChild(a); a.click();
  console.log(`${days.length} days, ${lines.length - 1} rows, ${failed} failed requests`);
})();
