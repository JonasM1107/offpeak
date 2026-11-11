// Shared helpers for the interactive views: theme following the dashboard, the frame's
// height, ECharts styling and number formats. Data always comes from Python (window.OFFPEAK).
const OP = (() => {
  const css = name => getComputedStyle(document.body).getPropertyValue(name).trim();
  const listeners = [];
  let dark = null;

  function syncTheme() {
    let d = false;
    try { d = window.parent.document.body.classList.contains('op-dark'); }
    catch (e) { d = matchMedia('(prefers-color-scheme: dark)').matches; }
    if (d === dark) return;
    dark = d;
    document.body.classList.toggle('op-dark', d);
    listeners.forEach(fn => fn());
  }

  // The frame grows with its content, so no card is ever cut off or followed by empty space.
  function fit() {
    const f = window.frameElement;
    if (!f) return;
    // measure the content, not the document: the document is never smaller than the frame
    const root = document.querySelector('.wrap') || document.body;
    const h = Math.ceil(root.getBoundingClientRect().bottom + window.scrollY + 4);
    f.style.height = h + 'px';
    f.setAttribute('height', h);
    const box = f.closest('[data-testid=stElementContainer]');
    if (box) { box.style.height = h + 'px'; box.style.minHeight = h + 'px'; }
  }

  function palette() {
    return {
      ink: css('--ink'), muted: css('--muted'), faint: css('--faint'), line: css('--line'), card: css('--card'),
      card2: css('--card2'), accent: css('--accent'), accentSoft: css('--accent-soft'), accentMid: css('--accent-mid'),
      grey: css('--grey'), sun: css('--sun'), wind: css('--wind'), dark: css('--dark'),
    };
  }

  // Common ECharts settings in the current colours.
  function base(c) {
    const axis = {
      axisLine: { lineStyle: { color: c.line } }, axisTick: { show: false },
      axisLabel: { color: c.muted, fontSize: 11, fontFamily: 'Inter, system-ui, sans-serif' },
      splitLine: { lineStyle: { color: c.line, type: [3, 4] } },
    };
    return {
      axis,
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: c.muted },
      tooltip: {
        backgroundColor: c.card, borderColor: c.line, borderWidth: 1, padding: [10, 12],
        textStyle: { color: c.ink, fontSize: 12, fontFamily: 'Inter, system-ui, sans-serif' },
        extraCssText: 'border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.18);',
        axisPointer: { lineStyle: { color: c.muted, type: [4, 4] }, crossStyle: { color: c.muted } },
      },
      animationDuration: 600, animationEasing: 'cubicOut',
    };
  }

  // A chart that redraws itself when the theme or its size changes.
  function chart(el, build) {
    let inst = null;
    const draw = () => {
      if (inst) inst.dispose();
      inst = echarts.init(el, null, { renderer: 'canvas' });
      inst.setOption(build(palette()));
      handle.inst = inst;
      handle.onDraw.forEach(fn => fn(inst));
    };
    // update(): new data in the same chart (smooth); redraw(): a fresh chart (theme change)
    const handle = { inst: null, onDraw: [], redraw: draw, update: () => inst && inst.setOption(build(palette()), { notMerge: true, lazyUpdate: true }) };
    listeners.push(draw);
    new ResizeObserver(() => inst && inst.resize()).observe(el);
    draw();
    return handle;
  }

  const nf = (v, d = 1) => (v == null || Number.isNaN(v)) ? '–' : v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
  const pad = h => String(h).padStart(2, '0');

  function start() {
    syncTheme();
    setInterval(syncTheme, 500);
    new ResizeObserver(fit).observe(document.querySelector('.wrap') || document.body);
    window.addEventListener('load', fit);
    fit();
  }

  return { start, onTheme: fn => listeners.push(fn), palette, base, chart, nf, pad, fit,
    resetIcon: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8a5.5 5.5 0 1 0 1.6-3.9"/><path d="M2.5 2.5v3h3"/></svg>' };
})();
