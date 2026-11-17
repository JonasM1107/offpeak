// The power lines: orange lines drifting slowly on a canvas, with soft current flowing along
// them. Used behind the landing page (landing.html) and behind the sign-in page
// (login_bg.html); Python puts this file into both pages (app/ui/landing.py: with_field).
//
//   const field = PowerField(canvas, options)
//
// options:
//   calm      true when the visitor asked for less motion: one still picture, no animation
//   energy    a function giving how lively the lines should be (0 = calm, 2 = racing)
//   scroll    a function giving the page's scroll position (the lines move a little with it)
//   pointer   the window whose mouse moves the lines push away from (default: this window)
//
// The returned object can be changed at any time:
//   field.pull     0..1, how far the lines are drawn into a glowing core (1 = all in it)
//   field.coreX/Y  where that core is, in pixels
//   field.kick(v)  a short burst of energy that fades by itself (a key press, a click)
function PowerField(cv, opt) {
  const ctx = cv.getContext('2d');
  const api = { pull: 0, coreX: 0, coreY: 0, boost: 0, kick(v) { api.boost = Math.min(3, api.boost + v); } };
  if (!ctx) return api;
  const calm = !!opt.calm, energyOf = opt.energy || (() => 0), scrollOf = opt.scroll || (() => 0);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  let W = 0, H = 0, lines = [], last = performance.now(), energy = 0;
  const mouse = { x: -9999, y: -9999, tx: -9999, ty: -9999 };
  // a seeded random, so the lines look the same on every visit and on both pages
  const rnd = (s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; })(7);
  const seeds = Array.from({ length: 22 }, () => Array.from({ length: 16 }, rnd));

  function build() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = cv.clientWidth || innerWidth; H = cv.clientHeight || innerHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = W < 700 ? 13 : 22;
    lines = seeds.slice(0, n).map((r, i) => ({
      base: (i + r[0] * .8) / n, amp: 16 + r[1] * 64, f: .0014 + r[2] * .0024, ph: r[3] * 6.3, ph2: r[4] * 6.3,
      sp: .00008 + r[5] * .00014, tilt: (r[6] - .5) * .45, w: .6 + r[7] * 1.1, a: .10 + r[8] * .2, depth: .04 + r[9] * .22,
      pulses: Array.from({ length: 1 + Math.floor(r[10] * 2.2) }, (_, k) => ({ s: r[11 + k], v: .00003 + r[13 + k] * .00008, size: 9 + r[15] * 14 })),
      ys: null,
    }));
  }
  const STEP = 16;
  const wrap = (v, m) => ((v % m) + m) % m;
  function shape(L, t, sy) {
    const n = Math.ceil(W / STEP) + 2;
    if (!L.ys || L.ys.length !== n) L.ys = new Float32Array(n);
    const span = H * 1.3, base = wrap(L.base * span - sy * L.depth, span) - H * .15;
    const pull = api.pull, reach = W * (.5 - .3 * pull);
    for (let k = 0; k < n; k++) {
      const x = k * STEP;
      // two waves drifting slowly in the same direction, and a slow up-and-down sway
      let y = base + L.tilt * (x - W / 2) + L.amp * Math.sin(x * L.f - t * L.sp + L.ph)
        + L.amp * .35 * Math.sin(x * L.f * 2.7 - t * L.sp * 1.7 + L.ph2) + 14 * Math.sin(t * .00025 + L.ph2);
      // the cursor pushes the lines apart, like field lines around a charge
      const dx = x - mouse.x, dy = y - mouse.y, d2 = dx * dx + dy * dy;
      if (d2 < 260000) y += (dy >= 0 ? 1 : -1) * Math.exp(-d2 / 36000) * 44;
      // drawn into the core: strongest near it, and more the further `pull` goes
      if (pull > 0) {
        const near = Math.exp(-((x - api.coreX) ** 2) / (2 * reach * reach));
        y += (api.coreY - y) * pull * (.3 + .7 * near);
      }
      L.ys[k] = y;
    }
  }
  function yAt(L, x) {
    const f = x / STEP, k = clamp(Math.floor(f), 0, L.ys.length - 2), r = f - k;
    return L.ys[k] * (1 - r) + L.ys[k + 1] * r;
  }
  function frame(now) {
    const dt = Math.min(now - last, 50); last = now;
    mouse.x += (mouse.tx - mouse.x) * .1; mouse.y += (mouse.ty - mouse.y) * .1;
    api.boost *= Math.pow(.997, dt);   // a kick fades out over about a second
    energy += (energyOf() + api.boost - energy) * .06;
    ctx.clearRect(0, 0, W, H);
    const grad = ctx.createLinearGradient(0, 0, W, 0);
    grad.addColorStop(0, 'rgba(255,95,0,0)'); grad.addColorStop(.18, 'rgba(255,95,0,1)'); grad.addColorStop(.82, 'rgba(255,110,20,1)'); grad.addColorStop(1, 'rgba(255,95,0,0)');
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    const sy = scrollOf(), fade = 1 - api.pull * .55;
    for (const L of lines) {
      shape(L, now, sy);
      ctx.strokeStyle = grad;
      ctx.beginPath();
      for (let k = 0; k < L.ys.length; k++) k ? ctx.lineTo(k * STEP, L.ys[k]) : ctx.moveTo(0, L.ys[0]);
      ctx.globalAlpha = L.a * (.22 + energy * .35) * fade; ctx.lineWidth = L.w * 6; ctx.stroke();   // soft halo
      ctx.globalAlpha = clamp(L.a * (1 + energy * 1.2), 0, 1) * fade; ctx.lineWidth = L.w; ctx.stroke(); // the line
    }
    for (const L of lines) for (const p of L.pulses) {
      // current flowing along the line: a faint, soft brighter stretch
      p.s = (p.s + p.v * dt * (1 + energy * 4)) % 1;
      const x = p.s * (W + 600) - 300, tail = p.size * (12 + energy * 8);
      const tg = ctx.createLinearGradient(x - tail, 0, x + tail * .25, 0);
      tg.addColorStop(0, 'rgba(255,95,0,0)'); tg.addColorStop(.8, 'rgba(255,120,30,1)'); tg.addColorStop(1, 'rgba(255,95,0,0)');
      ctx.beginPath();
      for (let xx = x - tail; xx <= x + tail * .25; xx += 8) xx === x - tail ? ctx.moveTo(xx, yAt(L, xx)) : ctx.lineTo(xx, yAt(L, xx));
      ctx.strokeStyle = tg;
      ctx.globalAlpha = (.07 + energy * .08) * fade; ctx.lineWidth = 6; ctx.stroke();
      ctx.globalAlpha = (.28 + energy * .25) * fade; ctx.lineWidth = 1.4; ctx.stroke();
    }
    if (api.pull > .01) {   // the glowing core the lines run into
      const r = 30 + 110 * api.pull + energy * 8;
      const g = ctx.createRadialGradient(api.coreX, api.coreY, 0, api.coreX, api.coreY, r);
      g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(.14, 'rgba(255,220,180,.95)');
      g.addColorStop(.38, 'rgba(255,128,40,.55)'); g.addColorStop(.7, 'rgba(255,95,0,.14)'); g.addColorStop(1, 'rgba(255,95,0,0)');
      ctx.globalAlpha = clamp(api.pull * 1.4, 0, 1); ctx.fillStyle = g;
      ctx.fillRect(api.coreX - r, api.coreY - r, r * 2, r * 2);
    }
    ctx.globalAlpha = 1;
    if (!calm) requestAnimationFrame(frame);
  }
  build();
  addEventListener('resize', build);
  const target = opt.pointer || window;
  try {
    target.addEventListener('pointermove', e => { mouse.tx = e.clientX; mouse.ty = e.clientY; if (mouse.x < -999) { mouse.x = mouse.tx; mouse.y = mouse.ty; } }, { passive: true });
    target.document.addEventListener('pointerleave', () => { mouse.tx = mouse.ty = -9999; });
  } catch (e) { /* that window cannot be reached: the lines simply ignore the cursor */ }
  requestAnimationFrame(frame);
  return api;
}
