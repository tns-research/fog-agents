// probe.js: DOM measures of a landing page, shared by probe.py, journey.py and fixes.py.
//
// Loaded as a Playwright init script (before any page script), so the layout-shift and
// largest-contentful-paint observers see the whole load. Exposes window.__lpa:
//   __lpa.measure(cfg)   every measure below, one JSON object
//   __lpa.forms()        form fields, labels, types, autocomplete, issues
//   __lpa.errors()       visible error messages and the field each one sits next to
//   __lpa.sel(el)        a short CSS path for an element
// Coordinates are CSS pixels in document space (scroll offsets added).
(() => {
  if (window.__lpa || window.top !== window) return;
  const state = { shifts: [], lcp: null };

  const sel = (el) => {
    if (!el || el.nodeType !== 1) return null;
    if (el.id && /^[A-Za-z][\w-]*$/.test(el.id)) return '#' + el.id;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 4) {
      if (node.id && /^[A-Za-z][\w-]*$/.test(node.id)) { parts.unshift('#' + node.id); break; }
      let part = node.tagName.toLowerCase();
      if (part === 'html' || part === 'body') { parts.unshift(part); break; }
      const cls = (typeof node.className === 'string' ? node.className : '').trim().split(/\s+/).filter(c => c && /^[A-Za-z_][\w-]*$/.test(c)).slice(0, 2);
      if (cls.length) part += '.' + cls.join('.');
      const parent = node.parentElement;
      if (parent) {
        const same = [...parent.children].filter(c => c.tagName === node.tagName);
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };

  // Real inputs, tracked here: under mobile emulation Chromium sets hadRecentInput on every
  // shift (the viewport rescale after a horizontal overflow counts as input), which would
  // drop all mobile shifts. A shift is excluded only within 500 ms after a real input.
  state.inputs = [];
  for (const type of ['pointerdown', 'keydown', 'touchstart', 'mousedown']) {
    window.addEventListener(type, () => state.inputs.push(performance.now()), { capture: true, passive: true });
  }
  const afterInput = (t) => state.inputs.some(i => t >= i && t - i < 500);
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (afterInput(e.startTime)) continue;
        state.shifts.push({ t: Math.round(e.startTime), value: e.value,
          sources: (e.sources || []).map(s => sel(s.node)).filter(Boolean).slice(0, 3) });
      }
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) { /* not supported */ }
  try {
    new PerformanceObserver((list) => {
      const all = list.getEntries();
      const last = all[all.length - 1];
      if (last) state.lcp = { t: Math.round(last.startTime), size: last.size, el: last.element || null, url: last.url || '' };
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (e) { /* not supported */ }

  const SAFE_TYPES = ['hidden'];
  const isVisible = (el) => {
    if (!el || !el.getBoundingClientRect) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    if (el.checkVisibility) return el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.05;
  };
  const docRect = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 };
  };
  const textOf = (el) => ((el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '') + '').replace(/\s+/g, ' ').trim().slice(0, 80);

  // ---- colours and WCAG contrast -------------------------------------------------
  const parse = (c) => {
    if (!c) return null;
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const v = m[1].split(/[ ,\/]+/).filter(Boolean).map(x => x.endsWith('%') ? parseFloat(x) / 100 : Number(x));
    return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 };
  };
  const lum = ({ r, g, b }) => [r, g, b].map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); })
    .reduce((s, x, i) => s + x * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const blend = (fg, bg) => fg.a >= 1 ? { ...fg, a: 1 } : { r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 };
  const hex = (c) => '#' + [c.r, c.g, c.b].map(x => Math.round(x).toString(16).padStart(2, '0')).join('');
  const MEDIA = new Set(['IMG', 'VIDEO', 'CANVAS', 'PICTURE', 'IFRAME', 'svg', 'SVG', 'OBJECT', 'EMBED']);

  // Background under a point, composited from the paint stack below `el`.
  const backgroundAt = (el, x, y) => {
    const stack = document.elementsFromPoint(x, y);
    let i = stack.findIndex(n => n === el || n.contains(el));
    if (i < 0) {
      // pointer-events: none on el: fall back to its DOM ancestors
      const chain = []; let n = el; while (n) { chain.push(n); n = n.parentElement; }
      stack.length = 0; stack.push(...chain); i = 0;
    }
    const layers = [];
    for (const n of stack.slice(i)) {
      if (MEDIA.has(n.tagName) && n !== el) return { image: true };
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        // A gradient sized smaller than its box (underline, highlight bar, stripe) is decoration, not the ground.
        const size = cs.backgroundSize || 'auto';
        const decorative = !/^(auto|cover|contain|100% 100%|100%)(, .*)?$/.test(size.trim()) && !/^auto auto$/.test(size.trim());
        if (/url\(/.test(cs.backgroundImage) && !decorative) return { image: true };
        const stops = (cs.backgroundImage.match(/rgba?\([^)]+\)/g) || []).map(parse).filter(Boolean);
        if (stops.length && !decorative) return { gradient: stops, below: layers.slice() };
      }
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
    }
    let bg = { r: 255, g: 255, b: 255, a: 1 };
    for (const c of layers.reverse()) bg = blend(c, bg);
    return { color: bg };
  };

  const textElements = (limit) => {
    const out = new Map();
    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode()) && out.size < limit) {
      if (!node.nodeValue || !node.nodeValue.trim()) continue;
      const el = node.parentElement;
      if (!el || out.has(el) || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'OPTION'].includes(el.tagName)) continue;
      if (!isVisible(el)) continue;
      out.set(el, node);
    }
    return out;
  };

  const opacityChain = (el) => { let o = 1; let n = el; while (n && n.nodeType === 1) { o *= parseFloat(getComputedStyle(n).opacity || '1'); n = n.parentElement; } return o; };

  const measureText = (elements) => {
    const sizes = {};
    const under16 = [], under12 = [];
    let chars = 0, charsUnder16 = 0;
    for (const [el, node] of elements) {
      const cs = getComputedStyle(el);
      const fs = parseFloat(cs.fontSize);
      const n = node.nodeValue.trim().length;
      chars += n;
      const key = String(Math.round(fs * 10) / 10);
      sizes[key] = (sizes[key] || 0) + n;
      if (fs < 16) {
        charsUnder16 += n;
        const item = { selector: sel(el), font_px: Math.round(fs * 10) / 10, text: node.nodeValue.trim().replace(/\s+/g, ' ').slice(0, 60), ...docRect(el) };
        under16.push(item);
        if (fs < 12) under12.push(item);
      }
    }
    const inputs = [...document.querySelectorAll('input, select, textarea')].filter(e => !SAFE_TYPES.includes(e.type) && isVisible(e))
      .map(e => ({ selector: sel(e), font_px: parseFloat(getComputedStyle(e).fontSize) })).filter(e => e.font_px < 16);
    return { chars, chars_under_16: charsUnder16, share_under_16: chars ? Math.round(1000 * charsUnder16 / chars) / 1000 : 0,
      sizes, under_16: under16.slice(0, 60), under_16_count: under16.length, under_12_count: under12.length, inputs_under_16: inputs };
  };

  const measureContrast = (elements) => {
    const fails = [], undetermined = [];
    let checked = 0;
    const H = innerHeight;
    const pending = new Map(elements);
    const maxY = Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0);
    const start = scrollY;
    for (let top = 0; top < maxY && pending.size; top += Math.max(200, H - 40)) {
      window.scrollTo(0, top);
      for (const [el, node] of [...pending]) {
        const range = document.createRange();
        range.selectNodeContents(node);
        const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
        if (!rects.length) { pending.delete(el); continue; }
        const r = rects[0];
        const cx = Math.min(Math.max(r.left + Math.min(r.width / 2, 6), 0), innerWidth - 1);
        const cy = r.top + r.height / 2;
        if (cy < 0 || cy >= H) continue;
        pending.delete(el);
        if (cx < 0 || cx >= innerWidth) continue;
        const cs = getComputedStyle(el);
        const fs = parseFloat(cs.fontSize);
        const bold = parseInt(cs.fontWeight, 10) >= 700;
        const large = fs >= 24 || (fs >= 18.66 && bold);
        const need = large ? 3 : 4.5;
        let fg = parse(cs.color);
        const label = { selector: sel(el), text: node.nodeValue.trim().replace(/\s+/g, ' ').slice(0, 60), font_px: Math.round(fs * 10) / 10, bold, required: need, x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
        const clip = cs.webkitBackgroundClip || cs.backgroundClip;
        if (!fg || fg.a === 0 || clip === 'text') { undetermined.push({ ...label, reason: 'transparent or gradient text' }); continue; }
        fg = { ...fg, a: fg.a * opacityChain(el) };
        const bg = backgroundAt(el, cx, cy);
        checked++;
        if (bg.image) { undetermined.push({ ...label, reason: 'text over an image or media' }); continue; }
        let worst, bgc;
        if (bg.gradient) {
          let base = { r: 255, g: 255, b: 255, a: 1 };
          for (const c of bg.below.reverse()) base = blend(c, base);
          for (const s of bg.gradient) { const b = blend(s, base); const v = ratio(blend(fg, b), b); if (worst === undefined || v < worst) { worst = v; bgc = b; } }
        } else { bgc = bg.color; worst = ratio(blend(fg, bgc), bgc); }
        if (worst < need) fails.push({ ...label, ratio: Math.round(worst * 100) / 100, fg: hex(blend(fg, bgc)), bg: hex(bgc) });
      }
    }
    window.scrollTo(0, start);
    fails.sort((a, b) => a.ratio - b.ratio);
    return { checked, failures: fails.slice(0, 60), failures_count: fails.length, undetermined: undetermined.slice(0, 30), undetermined_count: undetermined.length };
  };

  // ---- horizontal overflow ----------------------------------------------------------
  const clipsX = (el) => { const v = getComputedStyle(el).overflowX; return v === 'hidden' || v === 'clip' || v === 'auto' || v === 'scroll'; };
  const measureOverflow = () => {
    const W = document.documentElement.clientWidth || innerWidth;
    const sw = Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0);
    const offenders = [];
    const all = document.body ? document.body.querySelectorAll('*') : [];
    const isOff = (el) => {
      if (!isVisible(el)) return false;
      const r = el.getBoundingClientRect();
      if (!(r.right > W + 0.5 || r.left < -0.5)) return false;
      if (getComputedStyle(el).position === 'fixed' && r.left >= W) return false;
      let p = el.parentElement;
      while (p && p !== document.body && p !== document.documentElement) { if (clipsX(p)) return false; p = p.parentElement; }
      return true;
    };
    const flagged = new Set();
    for (const el of all) if (isOff(el)) flagged.add(el);
    for (const el of flagged) {
      if (el.parentElement && flagged.has(el.parentElement)) continue;
      const r = el.getBoundingClientRect();
      offenders.push({ selector: sel(el), text: textOf(el).slice(0, 50), right_px: Math.round(r.right), overflow_px: Math.round(Math.max(r.right - W, -r.left)), ...docRect(el) });
    }
    offenders.sort((a, b) => b.overflow_px - a.overflow_px);
    const htmlX = getComputedStyle(document.documentElement).overflowX, bodyX = document.body ? getComputedStyle(document.body).overflowX : 'visible';
    return { viewport_width: W, scroll_width: sw, overflow_x_px: Math.max(0, sw - W), offenders: offenders.slice(0, 15), offenders_count: offenders.length,
      root_clips_x: [htmlX, bodyX].some(v => v === 'hidden' || v === 'clip') };
  };

  // ---- touch targets (WCAG 2.2 2.5.8 and 44 px) ------------------------------------
  const TARGETS = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=checkbox], [role=radio], [role=tab], [role=menuitem], [role=switch], [onclick]';
  const measureTargets = () => {
    const els = [...document.querySelectorAll(TARGETS)].filter(e => isVisible(e) && !e.disabled);
    // keep the outermost target when targets nest (a button inside a link counts once)
    const uniq = els.filter(e => !els.some(o => o !== e && o.contains(e)));
    const items = uniq.map(e => {
      const r = e.getBoundingClientRect();
      const cs = getComputedStyle(e);
      let exempt = null;
      if (e.tagName === 'A' && cs.display === 'inline') {
        const block = e.parentElement && e.parentElement.closest('p, li, td, dd, blockquote, figcaption, span, label') ;
        const host = block || e.parentElement;
        if (host && (host.innerText || '').trim().length > (e.innerText || '').trim().length + 15) exempt = 'inline-in-text';
      }
      if (!exempt && e.tagName === 'INPUT' && ['checkbox', 'radio'].includes(e.type) && cs.appearance !== 'none' && cs.webkitAppearance !== 'none') exempt = 'user-agent-control';
      return { el: e, r, exempt, cx: r.left + r.width / 2, cy: r.top + r.height / 2 };
    });
    const under = (t, n) => t.r.width < n || t.r.height < n;
    const circleHitsRect = (cx, cy, rad, r) => { const dx = Math.max(r.left - cx, 0, cx - r.right); const dy = Math.max(r.top - cy, 0, cy - r.bottom); return dx * dx + dy * dy < rad * rad; };
    const fail24 = [], raw24 = [], u44 = [];
    for (const t of items) {
      const base = { selector: sel(t.el), text: textOf(t.el).slice(0, 40), w: Math.round(t.r.width * 10) / 10, h: Math.round(t.r.height * 10) / 10, x: Math.round(t.r.left + scrollX), y: Math.round(t.r.top + scrollY) };
      if (!t.exempt && under(t, 44)) u44.push(base);
      if (!under(t, 24)) continue;
      raw24.push(base);
      if (t.exempt) continue;
      // spacing exception: a 24 px circle centred on the target touches no other target and no other undersized circle
      const crowded = items.some(o => o !== t && (circleHitsRect(t.cx, t.cy, 12, o.r) || (under(o, 24) && Math.hypot(o.cx - t.cx, o.cy - t.cy) < 24)));
      if (crowded) fail24.push(base);
    }
    return { targets: items.length, under_24: fail24.slice(0, 80), under_24_count: fail24.length, under_24_raw_count: raw24.length,
      under_44: u44.slice(0, 80), under_44_count: u44.length, exempt_inline: items.filter(t => t.exempt === 'inline-in-text').length };
  };

  // ---- CTAs and the fold ------------------------------------------------------------
  const buttonLike = (e) => {
    if (e.tagName === 'BUTTON' || e.getAttribute('role') === 'button' || (e.tagName === 'INPUT' && ['submit', 'button'].includes(e.type))) return true;
    const cs = getComputedStyle(e);
    const bg = parse(cs.backgroundColor);
    const border = parseFloat(cs.borderTopWidth) >= 1 && cs.borderTopStyle !== 'none';
    const pad = parseFloat(cs.paddingLeft) >= 8 && parseFloat(cs.paddingTop) >= 4;
    return ((bg && bg.a > 0.5) || border) && pad;
  };
  const destination = (e) => {
    const href = e.getAttribute('href');
    if (!href) return { kind: e.closest('form') ? 'form-submit' : 'script' };
    if (href.startsWith('#')) return { kind: 'anchor', href };
    if (/^(mailto|tel):/i.test(href)) return { kind: href.split(':')[0].toLowerCase(), href };
    if (/^javascript:/i.test(href)) return { kind: 'script', href };
    try { const u = new URL(href, location.href); return { kind: u.host === location.host ? (u.pathname === location.pathname ? 'same-page' : 'internal') : 'external', href: u.href }; }
    catch (err) { return { kind: 'unknown', href }; }
  };
  const measureCtas = (cfg) => {
    const H = innerHeight, screenH = (cfg && cfg.screen_height) || screen.height || H;
    const els = [...document.querySelectorAll('a[href], button, input[type=submit], input[type=button], [role=button]')].filter(e => isVisible(e));
    const ctas = els.filter(buttonLike).map(e => {
      const r = docRect(e);
      return { selector: sel(e), text: textOf(e), ...destination(e), x: r.x, y: r.y, w: r.w, h: r.h, bottom: Math.round(r.y + r.h),
        above_fold: r.y + r.h <= H, above_screen: r.y + r.h <= screenH, area: Math.round(r.w * r.h) };
    });
    let primary = null;
    const want = cfg && cfg.primary ? cfg.primary.toLowerCase() : null;
    if (want) {
      const match = els.map(e => ({ e, t: textOf(e).toLowerCase() })).find(o => o.t === want) || els.map(e => ({ e, t: textOf(e).toLowerCase() })).find(o => o.t.includes(want));
      if (match) { const r = docRect(match.e); primary = { selector: sel(match.e), text: textOf(match.e), ...destination(match.e), y: r.y, bottom: Math.round(r.y + r.h), source: 'given' }; }
    }
    if (!primary) {
      const hero = ctas.filter(c => c.y < 1.5 * H).sort((a, b) => b.area - a.area)[0];
      if (hero) primary = { selector: hero.selector, text: hero.text, kind: hero.kind, href: hero.href, y: hero.y, bottom: hero.bottom, source: 'largest button-like element in the first 1.5 screens' };
    }
    if (primary) { primary.fold_px = H; primary.screen_px = screenH; primary.above_fold = primary.bottom <= H; primary.above_screen = primary.bottom <= screenH; }
    const labels = {};
    for (const c of ctas) { const k = c.text.toLowerCase(); if (!k) continue; (labels[k] = labels[k] || new Set()).add(c.href || c.kind); }
    const map = Object.entries(labels).map(([text, dests]) => ({ text, destinations: [...dests] }));
    return { fold_px: H, screen_px: screenH, primary, ctas: ctas.slice(0, 40), ctas_count: ctas.length, cta_map: map.slice(0, 30) };
  };

  const measureSticky = () => {
    const H = innerHeight, W = innerWidth;
    const out = [];
    for (const el of document.querySelectorAll('body *')) {
      const cs = getComputedStyle(el);
      if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
      if (!isVisible(el)) continue;
      const r = el.getBoundingClientRect();
      const vis = Math.max(0, Math.min(r.bottom, H) - Math.max(r.top, 0)) * Math.max(0, Math.min(r.right, W) - Math.max(r.left, 0));
      if (vis > 0) out.push({ el, selector: sel(el), position: cs.position, h: Math.round(r.height), cover_pct: Math.round(1000 * vis / (W * H)) / 10 });
    }
    const top = out.filter(o => !out.some(p => p !== o && p.el.contains(o.el))).map(({ el, ...rest }) => rest);
    return { elements: top.slice(0, 10), cover_pct: Math.round(top.reduce((s, o) => s + o.cover_pct, 0) * 10) / 10 };
  };

  const measureImages = () => {
    const H = innerHeight;
    const imgs = [...document.images];
    const noDims = [], lazyAbove = [], broken = [], noAlt = [];
    for (const img of imgs) {
      const cs = getComputedStyle(img);
      const vis = isVisible(img);
      const r = docRect(img);
      const base = { selector: sel(img), src: (img.currentSrc || img.src || '').split('/').pop().slice(0, 60), ...r };
      if (vis && !(img.hasAttribute('width') && img.hasAttribute('height')) && (!cs.aspectRatio || cs.aspectRatio === 'auto')) noDims.push(base);
      if (img.loading === 'lazy' && vis && r.y < H) lazyAbove.push(base);
      if (img.complete && img.naturalWidth === 0 && (img.currentSrc || img.src)) broken.push(base);
      if (!img.hasAttribute('alt') && vis) noAlt.push(base);
    }
    let lcp = null;
    if (state.lcp) {
      const el = state.lcp.el;
      lcp = { t_ms: state.lcp.t, size: state.lcp.size, selector: el ? sel(el) : null, url: (state.lcp.url || '').split('/').pop().slice(0, 60),
        lazy: !!(el && el.tagName === 'IMG' && el.loading === 'lazy'), tag: el ? el.tagName.toLowerCase() : null };
    }
    return { images: imgs.length, without_dimensions: noDims.slice(0, 30), without_dimensions_count: noDims.length,
      lazy_above_fold: lazyAbove, lazy_above_fold_count: lazyAbove.length, broken, broken_count: broken.length,
      missing_alt: noAlt.slice(0, 30), missing_alt_count: noAlt.length, lcp };
  };

  // CLS as web.dev defines it: largest session window (1 s gap, 5 s cap), shifts right after a real input excluded.
  const measureCls = () => {
    let best = 0, cur = 0, start = 0, last = -1e9; let bestShifts = [], curShifts = [];
    for (const s of state.shifts) {
      if (s.t - last > 1000 || s.t - start > 5000) { cur = 0; start = s.t; curShifts = []; }
      cur += s.value; last = s.t; curShifts.push(s);
      if (cur > best) { best = cur; bestShifts = curShifts.slice(); }
    }
    const total = state.shifts.reduce((a, s) => a + s.value, 0);
    return { cls: Math.round(best * 1000) / 1000, total: Math.round(total * 1000) / 1000, shifts: state.shifts.length,
      worst: bestShifts.sort((a, b) => b.value - a.value).slice(0, 5).map(s => ({ t_ms: s.t, value: Math.round(s.value * 1000) / 1000, sources: s.sources })) };
  };

  // ---- forms --------------------------------------------------------------------------
  const accName = (f) => {
    if (f.getAttribute('aria-labelledby')) {
      const t = f.getAttribute('aria-labelledby').split(/\s+/).map(id => document.getElementById(id)).filter(Boolean).map(n => n.innerText).join(' ').trim();
      if (t) return { label: t, source: 'aria-labelledby' };
    }
    if (f.labels && f.labels.length) { const t = [...f.labels].map(l => l.innerText).join(' ').trim(); if (t) return { label: t, source: 'label', visible: [...f.labels].some(isVisible) }; }
    if (f.getAttribute('aria-label')) return { label: f.getAttribute('aria-label'), source: 'aria-label' };
    if (f.getAttribute('placeholder')) return { label: f.getAttribute('placeholder'), source: 'placeholder-only' };
    if (f.getAttribute('title')) return { label: f.getAttribute('title'), source: 'title' };
    return { label: '', source: 'none' };
  };
  const PURPOSE = [
    [/e-?mail|courriel/i, 'email', 'email'],
    [/phone|tel|mobile|portable/i, 'tel', 'tel'],
    [/first.?name|given|pr[ée]nom/i, null, 'given-name'],
    [/last.?name|family|surname|nom de famille/i, null, 'family-name'],
    [/full.?name|^name$|your name|^nom$/i, null, 'name'],
    [/company|organi[sz]ation|startup|soci[ée]t[ée]|entreprise/i, null, 'organization'],
    [/postal|zip|code postal/i, null, 'postal-code'],
    [/address|adresse/i, null, 'street-address'],
    [/city|ville/i, null, 'address-level2'],
    [/country|pays/i, null, 'country-name'],
    [/website|url|site/i, 'url', 'url'],
  ];
  const forms = () => {
    const fields = [...document.querySelectorAll('input, select, textarea')].filter(f => !['hidden', 'submit', 'button', 'reset', 'image'].includes(f.type) && isVisible(f));
    const groups = new Map();
    for (const f of fields) { const k = f.form || null; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(f); }
    const out = [];
    let issues = 0;
    for (const [form, fs] of groups) {
      const items = fs.map(f => {
        const n = accName(f);
        const hint = [f.name, f.id, n.label, f.getAttribute('autocomplete') || ''].join(' ');
        const purpose = PURPOSE.find(([re]) => re.test(hint));
        const problems = [];
        if (n.source === 'placeholder-only') problems.push('placeholder-only label');
        if (n.source === 'none') problems.push('no accessible label');
        if (n.source === 'label' && n.visible === false) problems.push('label not visible');
        if (purpose && purpose[1] && f.tagName === 'INPUT' && f.type !== purpose[1]) problems.push('type=' + f.type + ', expected type=' + purpose[1]);
        if (purpose && purpose[2] && f.tagName !== 'SELECT' && !(f.getAttribute('autocomplete') || '').trim()) problems.push('no autocomplete, expected autocomplete=' + purpose[2]);
        issues += problems.length;
        const r = docRect(f);
        return { selector: sel(f), tag: f.tagName.toLowerCase(), type: f.type || null, name: f.name || null, label: n.label.slice(0, 60), label_source: n.source,
          autocomplete: f.getAttribute('autocomplete'), inputmode: f.getAttribute('inputmode'), required: f.required, font_px: parseFloat(getComputedStyle(f).fontSize), problems, ...r };
      });
      const rows = new Set(items.map(i => Math.round(i.y / 6)));
      const submit = form ? [...form.querySelectorAll('button, input[type=submit]')].filter(isVisible).map(textOf)[0] || null : null;
      out.push({ form: form ? sel(form) : '(no form element)', method: form ? (form.getAttribute('method') || 'get').toLowerCase() : null,
        action: form ? form.getAttribute('action') : null, fields: items, field_count: items.length, required_count: items.filter(i => i.required).length,
        single_column: rows.size === items.length, submit_text: submit });
    }
    return { forms: out, forms_count: out.length, fields_count: fields.length, issues_count: issues };
  };

  const errors = () => {
    const nodes = new Set([...document.querySelectorAll('[role=alert], [aria-live=assertive], [aria-live=polite], .error, .errors, .invalid-feedback, .field-error, [class*="error-message"], [class*="error_message"], [class*="form-error"]')]);
    const fields = [...document.querySelectorAll('input, select, textarea')].filter(isVisible);
    const out = [];
    for (const n of nodes) {
      if (!isVisible(n)) continue;
      const text = (n.innerText || '').replace(/\s+/g, ' ').trim();
      if (!text) continue;
      const r = n.getBoundingClientRect();
      let near = null, dist = Infinity;
      for (const f of fields) {
        const q = f.getBoundingClientRect();
        const dx = Math.max(q.left - r.right, 0, r.left - q.right), dy = Math.max(q.top - r.bottom, 0, r.top - q.bottom);
        const d = Math.hypot(dx, dy);
        if (d < dist) { dist = d; near = f; }
      }
      out.push({ selector: sel(n), text: text.slice(0, 120), nearest_field: near ? sel(near) : null, distance_px: near ? Math.round(dist) : null });
    }
    const invalid = fields.filter(f => f.getAttribute('aria-invalid') === 'true').map(sel);
    return { messages: out.slice(0, 20), aria_invalid: invalid };
  };

  const meta = () => {
    const vp = document.querySelector('meta[name=viewport]');
    const content = vp ? vp.getAttribute('content') || '' : '';
    const h1 = [...document.querySelectorAll('h1')].filter(isVisible).map(h => h.innerText.replace(/\s+/g, ' ').trim().slice(0, 120));
    const unnamed = [...document.querySelectorAll('a[href], button')].filter(e => isVisible(e) && !textOf(e) && !e.querySelector('img[alt]:not([alt=""]), svg title')).map(sel);
    return { url: location.href, title: document.title, lang: document.documentElement.getAttribute('lang'), viewport_meta: content || null,
      zoom_disabled: /user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b/i.test(content), inner_width: innerWidth, inner_height: innerHeight,
      screen_height: screen.height, dpr: devicePixelRatio, scroll_height: document.documentElement.scrollHeight, h1, h1_count: h1.length,
      unnamed_controls: unnamed.slice(0, 20), unnamed_controls_count: unnamed.length };
  };

  const measure = (cfg) => {
    cfg = cfg || {};
    window.scrollTo(0, 0);
    const out = { meta: meta(), overflow: measureOverflow(), targets: measureTargets(), ctas: measureCtas(cfg), sticky: measureSticky(), images: measureImages(), forms: forms() };
    const els = textElements(cfg.max_text || 2500);
    out.text = measureText(els);
    out.contrast = cfg.contrast === false ? null : measureContrast(els);
    out.cls = measureCls();
    window.scrollTo(0, 0);
    return out;
  };

  window.__lpa = { measure, forms, errors, sel, state, isVisible };
})();
