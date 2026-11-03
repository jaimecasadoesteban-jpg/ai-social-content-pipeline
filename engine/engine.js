// Reel animation engine. A page declares scenes (.scene > .cam) and elements with data-in / data-out / data-anim.
// Times are seconds ("4.2") or a phrase from the script: "@the usual" (its start), "@the usual$" (its end), "@the usual-0.3".
// window.seek(t) renders one exact frame; window.audit() and window.meta() feed the automated QA judge.
(function () {
  const W = window.WORDS || [];
  const norm = s => s.toLowerCase().replace(/[¿?¡!.,:;«»"()]/g, '').trim();
  const toks = W.map(w => norm(w.w));
  function find(ph) {
    const p = norm(ph).split(/\s+/);
    for (let i = 0; i <= toks.length - p.length; i++) if (p.every((x, j) => toks[i + j] === x)) return [i, p.length];
    throw new Error('Phrase not found in script: ' + ph);
  }
  function T(spec) {
    if (spec == null || spec === '') return null;
    if (typeof spec === 'number') return spec;
    spec = String(spec).trim();
    if (spec === 'fin') return R.DUR;
    if (spec[0] !== '@') return parseFloat(spec);
    const m = spec.slice(1).match(/^(.*?)(\$)?\s*([+-]\s*\d*\.?\d+)?$/);
    const [i, n] = find(m[1]);
    const base = m[2] ? W[i + n - 1].end : W[i].start;
    return base + (m[3] ? parseFloat(m[3].replace(/\s/g, '')) : 0);
  }
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const eo = p => 1 - Math.pow(1 - p, 3);
  const eio = p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const back = p => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
  const R = (window.R = { W, T, clamp, eo, eio, back, HOLD: 0.9, hooks: [], extraEvents: [] });
  R.on = fn => R.hooks.push(fn);
  R.prog = (t, a, d = 0.4) => clamp((t - T(a)) / d);

  R.init = function (opts = {}) {
    if (opts.hold != null) R.HOLD = opts.hold;
    R.DUR = opts.dur != null ? opts.dur : W.length ? W[W.length - 1].end + R.HOLD : 10;
    R.scenes = [...document.querySelectorAll('.scene')].map(el => ({
      el, cam: el.querySelector('.cam') || el, type: el.dataset.type,
      start: T(el.dataset.start) || 0, freeze: T(el.dataset.freeze),
    }));
    R.scenes.forEach((s, i) => (s.end = i + 1 < R.scenes.length ? R.scenes[i + 1].start : R.DUR));
    R.anims = [...document.querySelectorAll('[data-in],[data-out]')].map(el => ({
      el, tin: T(el.dataset.in), tout: T(el.dataset.out), anim: el.dataset.anim || 'up', dur: parseFloat(el.dataset.dur || '0.4'),
    }));
    // "Typing..." bubble: placed exactly where the next bubble will appear, without taking up space
    document.querySelectorAll('.bub.typing').forEach(el => {
      const nx = el.nextElementSibling;
      Object.assign(el.style, { position: 'absolute', left: '26px', top: (nx ? nx.offsetTop : 0) + 'px' });
    });
    document.querySelectorAll('.txt').forEach((el, i) => (el.dataset.k = i));
    R.SFX = (window.SFX || []).map(s => ({ t: +T(s.t).toFixed(3), s: s.s }));
    R.bg = [...document.querySelectorAll('#bg .blob')];
    window.DUR = R.DUR;
    window.seek(0);
  };

  window.seek = function (t) {
    R.t = t;
    if (R.bg.length) {
      R.bg[0].style.translate = `${Math.sin(t * 0.55) * 260}px ${Math.cos(t * 0.4) * 300}px`;
      R.bg[1].style.translate = `${Math.cos(t * 0.47) * 280}px ${Math.sin(t * 0.36) * 320}px`;
    }
    R.scenes.forEach((s, i) => {
      const last = i === R.scenes.length - 1;
      const vis = t >= s.start && t < s.end + (last ? 1 : 0.14);
      if (!vis) { s.el.style.visibility = 'hidden'; return; }
      s.el.style.visibility = 'visible';
      s.el.style.zIndex = i + 1;
      const pin = i === 0 ? 1 : eo(clamp((t - s.start) / 0.2));
      const pout = !last && t >= s.end ? 1 - clamp((t - s.end) / 0.14) : 1;
      s.el.style.opacity = pin * pout;
      const d = s.end - s.start, p = clamp((t - s.start) / d);
      let sc, ty;
      if (s.freeze != null) {
        const pf = clamp((t - s.start) / (s.freeze - s.start));
        sc = t >= s.freeze ? 1 : 1 + 0.06 * Math.sin(Math.PI * pf);
        ty = t >= s.freeze ? 0 : -16 * Math.sin(Math.PI * pf);
      } else {
        sc = 1 + 0.06 * Math.sin(Math.PI * p) + 0.012 * Math.sin((2 * Math.PI * (t - s.start)) / 2.4);
        ty = -16 * Math.sin(Math.PI * p);
      }
      sc *= 1 + 0.05 * (1 - pin);
      s.cam.style.transform = `translateY(${ty.toFixed(2)}px) scale(${sc.toFixed(4)})`;
    });
    R.anims.forEach(a => {
      let o = 1, tx = 0, ty = 0, s = 1, r = 0, sx = null;
      if (a.tin != null) {
        const p = clamp((t - a.tin) / a.dur), e = eo(p);
        switch (a.anim) {
          case 'up': o = e; ty = 60 * (1 - e); break;
          case 'down': o = e; ty = -60 * (1 - e); break;
          case 'left': o = e; tx = -110 * (1 - e); break;
          case 'right': o = e; tx = 110 * (1 - e); break;
          case 'pop': o = clamp(p * 2.5); s = 0.55 + 0.45 * back(p); break;
          case 'stamp': o = clamp(p * 4); s = 1.4 - 0.4 * e; break;
          case 'drop': o = clamp(p * 3); ty = -220 * (1 - back(p)); break;
          case 'grow': o = p > 0 ? 1 : 0; sx = `${e} 1`; break;
          case 'rise': o = p > 0 ? 1 : 0; sx = `1 ${e}`; break;
          case 'fade': o = e; break;
        }
      }
      if (a.tout != null) { const q = clamp((t - a.tout) / 0.25); o *= 1 - q; ty -= 24 * q; }
      a.el.style.opacity = o;
      a.el.style.translate = `${tx}px ${ty}px`;
      a.el.style.scale = sx != null ? sx : `${s}`;
    });
    R.hooks.forEach(f => f(t));
  };

  window.audit = function () {
    const out = [];
    document.querySelectorAll('.txt').forEach(el => {
      let o = 1, n = el, hidden = false;
      while (n && n !== document.documentElement) {
        const cs = getComputedStyle(n);
        if (cs.visibility === 'hidden' || cs.display === 'none') { hidden = true; break; }
        o *= parseFloat(cs.opacity);
        n = n.parentElement;
      }
      if (hidden || o < 0.05) return;
      const r = el.getBoundingClientRect();
      out.push({ k: +el.dataset.k, o: +o.toFixed(2), x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width),
        h: Math.round(r.height), txt: el.textContent.trim().replace(/\s+/g, ' ') });
    });
    return out;
  };

  window.meta = () => ({
    DUR: R.DUR, SFX: R.SFX,
    scenes: R.scenes.map(s => ({ type: s.type, start: +s.start.toFixed(2), end: +s.end.toFixed(2), freeze: s.freeze })),
    events: [...new Set([...R.scenes.map(s => s.start), ...R.anims.map(a => a.tin).filter(x => x != null),
      ...R.extraEvents.map(T)].map(x => +x.toFixed(2)))].sort((a, b) => a - b),
  });
})();
