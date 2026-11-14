/* animate.js: deterministic motion timeline for the video variant (animate.py).
 *
 * Loaded after fit.js has sized every text, so the slides are exactly the
 * validated stills. It never changes a word or a size: it only stages the
 * slides on the video canvas and schedules entrances.
 *
 * window.__animSetup(cfg) builds the canvas and the timeline, returns
 *   {duration, frames, squeeze, floor,
 *    slides: [{index, id, start, contentStart, end, words, read, entrance}]}
 * Planning runs in three passes: each slide on its own clock (entrance length,
 * reading time), then an optional squeeze of the holds to fit cfg.maxDuration
 * (entrances are never shortened), then absolute frame-aligned times.
 * window.__animSeek(t) puts the page in its state at t seconds and returns
 *   {moving, sig}: moving is true when something changes between the previous
 *   frame and this one; sig changes whenever an item starts or ends. animate.py
 *   reuses the previous frame when neither changed (hold frames cost nothing).
 *
 * Every motion is a Web Animation created paused and driven by currentTime
 * (no wall clock, no requestAnimationFrame loop), plus a count-up whose value
 * is a pure function of t. Same input, same frames.
 *
 * Motion vocabulary (design-rules.md: no glow, no pulse, no parallax):
 *   rise   opacity 0 -> 1 and a 24 px lift, ease-out
 *   fade   opacity only (photos, visuals, chart frame)
 *   grow   bars scale from the zero axis
 *   draw   line charts drawn along their length, donut segments swept
 *   count  a single number counts up to its value, format preserved
 *   cross  slide to slide crossfade
 */
(function () {
  "use strict";

  var EASE = "cubic-bezier(0.22, 0.61, 0.36, 1)";
  var RISE_PX = 24;
  var items = [];   // {start, end, anim?, update?}

  function num(v, d) { var n = parseFloat(v); return isNaN(n) ? d : n; }
  function q(root, sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); }

  function snap(t, fps) { return Math.round(t * fps) / fps; }

  // Maps fn(value, axis) over a computed multi-layer background value
  // ("150px 150px, 30px 30px"); axis 0 is x, 1 is y.
  function layers(value, fn) {
    return value.split(",").map(function (layer) {
      return layer.trim().split(/\s+/).map(function (v, i) { return fn(v, i); }).join(" ");
    }).join(", ");
  }

  // Blocks are planned on a slide-relative clock into `plan`; setup() then
  // shifts each slide's plan to its absolute start and creates the animations.
  var plan = [];

  function add(el, keyframes, start, dur, easing) {
    plan.push({ el: el, keyframes: keyframes, start: start, dur: dur, easing: easing || EASE });
    return start + dur;
  }

  function materialize(p, offset) {
    p.forEach(function (it) {
      var s = it.start + offset;
      if (it.make) { items.push({ start: s, end: s + it.dur, update: it.make(s) }); return; }
      var a = it.el.animate(it.keyframes, { duration: it.dur * 1000, delay: s * 1000, fill: "both", easing: it.easing });
      a.pause();
      items.push({ start: s, end: s + it.dur, anim: a });
    });
  }

  function isInline(el) {
    if (el instanceof SVGElement) return false;
    var d = getComputedStyle(el).display;
    return d === "inline" || d === "contents";
  }

  function rise(el, start, dur) {
    if (isInline(el)) return add(el, [{ opacity: 0 }, { opacity: 1 }], start, dur || 0.5);
    return add(el, [{ opacity: 0, transform: "translateY(" + RISE_PX + "px)" }, { opacity: 1, transform: "translateY(0px)" }], start, dur || 0.55);
  }

  function fade(el, start, dur) { return add(el, [{ opacity: 0 }, { opacity: 1 }], start, dur || 0.6, "ease-out"); }

  // ---- count-up ---------------------------------------------------------

  var NUM_RE = /^(\D*?)(\d{1,3}(?:[,.   ]\d{3})+|\d+)([.,]\d+)?(\D*)$/;

  function parseCount(el) {
    if (el.children.length) return null;
    var txt = el.textContent.trim();
    var m = NUM_RE.exec(txt);
    if (!m) return null;
    var intPart = m[2], sep = "", dec = m[3] || "";
    var sm = /[,.   ]/.exec(intPart);
    if (sm) sep = sm[0];
    var target = parseFloat(intPart.replace(/[,.   ]/g, "") + (dec ? "." + dec.slice(1) : ""));
    if (!isFinite(target) || target <= 0) return null;
    // A bare four-digit number is most likely a year: counting it up reads wrong.
    if (!sep && !dec && !m[1] && !m[4] && target >= 1000) return null;
    return { prefix: m[1], suffix: m[4], sep: sep, decSep: dec ? dec[0] : "", decimals: dec ? dec.length - 1 : 0, target: target, text: txt };
  }

  function formatCount(c, v) {
    var s = v.toFixed(c.decimals);
    var parts = s.split(".");
    var ip = parts[0];
    if (c.sep) ip = ip.replace(/\B(?=(\d{3})+(?!\d))/g, c.sep);
    return c.prefix + ip + (c.decimals ? c.decSep + parts[1] : "") + c.suffix;
  }

  function count(el, start, dur) {
    var c = parseCount(el);
    fade(el, start, 0.3);
    if (!c) return start + 0.3;
    el.style.whiteSpace = "nowrap";
    plan.push({
      start: start, dur: dur,
      make: function (s0) {
        return function (t) {
          var p = Math.min(1, Math.max(0, (t - s0) / dur));
          if (p >= 1) { el.textContent = c.text; return; }
          var e = 1 - Math.pow(1 - p, 3);
          el.textContent = formatCount(c, c.target * e);
        };
      }
    });
    return start + dur;
  }

  // ---- charts -------------------------------------------------------------

  function chart(fig, start) {
    var t = start, end = start;
    var title = fig.querySelector(".c-title");
    if (title) end = Math.max(end, rise(title, t));
    var svg = fig.querySelector("svg");
    if (!svg) { end = Math.max(end, fade(fig, t)); return end; }
    t += 0.2;
    // Frame first: axis, grid, ticks, labels.
    q(svg, ".c-axis, .c-grid, .c-tick, .c-label, .c-swatch").forEach(function (el) { end = Math.max(end, fade(el, t, 0.4)); });
    t += 0.3;
    var bars = q(svg, "rect.c-bar");
    var axis = svg.querySelector(".c-axis");
    if (bars.length) {
      var horizontal = axis && Math.abs(num(axis.getAttribute("x1"), 0) - num(axis.getAttribute("x2"), 1)) < 0.5;
      var zx = axis ? num(axis.getAttribute("x1"), 0) : 0, zy = axis ? num(axis.getAttribute("y1"), 0) : 0;
      var values = q(svg, "text.c-value");
      var step = Math.min(0.09, 0.9 / bars.length), dur = 0.6;
      bars.forEach(function (b, i) {
        var s = t + i * step;
        b.style.transformOrigin = horizontal ? (zx + "px 0px") : ("0px " + zy + "px");
        var from = horizontal ? "scaleX(0)" : "scaleY(0)", to = horizontal ? "scaleX(1)" : "scaleY(1)";
        end = Math.max(end, add(b, [{ transform: from }, { transform: to }], s, dur));
        if (values[i]) end = Math.max(end, fade(values[i], s + dur * 0.7, 0.3));
      });
    }
    var lines = q(svg, "polyline.c-line");
    lines.forEach(function (l, i) {
      var s = t + i * 0.15;
      l.setAttribute("pathLength", "1");
      add(l, [{ opacity: 0 }, { opacity: 1 }], s, 0.1, "linear");
      end = Math.max(end, add(l, [{ strokeDasharray: "1 2", strokeDashoffset: 1 }, { strokeDasharray: "1 2", strokeDashoffset: 0 }], s, 1.2, "ease-in-out"));
    });
    if (lines.length) {
      var lend = end;
      q(svg, ".c-dot").forEach(function (d) { end = Math.max(end, fade(d, lend - 0.1, 0.3)); });
      if (!bars.length) q(svg, "text.c-value").forEach(function (v) { end = Math.max(end, fade(v, lend - 0.1, 0.4)); });
    }
    var segs = q(svg, "circle.c-seg");
    if (segs.length) {
      var s0 = t, total = 1.1;
      segs.forEach(function (c) {
        var parts = (c.getAttribute("stroke-dasharray") || "").split(/[ ,]+/).map(Number);
        var len = parts[0] || 0, rest = parts[1] || 100;
        var d = Math.max(0.12, total * len / 100);
        end = Math.max(end, add(c, [{ strokeDasharray: "0 100" }, { strokeDasharray: len + " " + rest }], s0, d, "ease-out"));
        s0 += d * 0.92;
      });
      q(svg, ".c-center").forEach(function (el) { end = Math.max(end, fade(el, s0 - 0.2, 0.4)); });
    }
    if (!bars.length && !lines.length && !segs.length) end = Math.max(end, fade(svg, t));
    var note = fig.querySelector(".c-note");
    if (note) end = Math.max(end, fade(note, end - 0.2, 0.4));
    return end;
  }

  // ---- blocks -----------------------------------------------------------

  // Schedules one block from `start`; returns the time its last motion ends
  // and the time the next block may start.
  function block(b, start) {
    var cls = b.classList, end = start, next = start + 0.35;
    function seq(els, gap, fn) {
      var t = start;
      els.forEach(function (el) { end = Math.max(end, (fn || rise)(el, t)); next = Math.max(next, t + 0.35); t += gap; });
    }
    if (cls.contains("b-title")) {
      seq(q(b, ".t, .sub"), 0.32);
    } else if (cls.contains("b-body")) {
      var ps = q(b, ".body > p");
      seq(ps.length ? ps : q(b, ".body"), 0.35);
    } else if (cls.contains("b-list")) {
      seq(q(b, "li"), 0.24);
    } else if (cls.contains("b-stat")) {
      var v = b.querySelector(".stat-v");
      if (v) end = Math.max(end, count(v, start, 1.2));
      var t = start + 0.45;
      q(b, ".stat-l, .stat-c").forEach(function (el) { end = Math.max(end, rise(el, t)); next = t + 0.35; t += 0.35; });
    } else if (cls.contains("b-chart")) {
      end = chart(b, start);
      next = end - 0.2;
    } else if (cls.contains("b-quote")) {
      seq(q(b, ".q-t, .q-a"), 0.5);
    } else if (cls.contains("b-logo-row")) {
      seq(q(b, ".lr-item"), 0.12, fade);
    } else if (cls.contains("b-cta")) {
      seq(q(b, ".cta-t, .cta-url, .cta-sub"), 0.3);
    } else if (cls.contains("b-screenshot")) {
      end = fade(b, start, 0.6);
      var t2 = start + 0.5;
      q(b, ".ann-box, .ann-pin").forEach(function (el) { end = Math.max(end, fade(el, t2, 0.3)); t2 += 0.15; });
      q(b, ".shot-legend > *").forEach(function (el) { end = Math.max(end, rise(el, t2)); t2 += 0.2; });
      next = start + 0.5;
    } else if (getComputedStyle(b).display === "contents") {
      seq(Array.prototype.slice.call(b.children), 0.3, fade);
    } else {
      end = fade(b, start, 0.6);
      next = start + 0.4;
    }
    return { end: end, next: next };
  }

  function words(slide) {
    var main = slide.querySelector(".s-main") || slide;
    var n = 0;
    // Prose counts word by word; chart labels and values are glanced, one each.
    var walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      var inSvg = node.parentNode && node.parentNode.closest && node.parentNode.closest("svg");
      var w = node.textContent.trim().split(/\s+/).filter(function (x) { return /[\p{L}\p{N}]/u.test(x); }).length;
      n += inSvg ? Math.min(w, 1) : w;
    }
    return n;
  }

  function setup(cfg) {
    var fps = cfg.fps;
    var css = document.createElement("style");
    css.textContent =
      "html,body{margin:0!important;padding:0!important;background:#000!important;overflow:hidden!important}" +
      ".deck{display:block!important;position:relative!important;width:" + cfg.W + "px!important;height:" + cfg.H + "px!important;padding:0!important;margin:0!important;overflow:hidden!important}" +
      ".v-scene{position:absolute;left:0;top:0;width:" + cfg.W + "px;height:" + cfg.H + "px;overflow:hidden}" +
      ".v-scene>section.slide{position:absolute!important;left:" + cfg.left + "px;top:" + cfg.top + "px;margin:0!important;" +
      "transform:scale(" + cfg.scale + ");transform-origin:0 0}";
    document.head.appendChild(css);

    var deck = document.querySelector(".deck");
    var all = q(document, "section.slide");
    var pick = cfg.slides && cfg.slides.length ? cfg.slides : all.map(function (_, i) { return i + 1; });
    var scenes = [];
    all.forEach(function (s, i) {
      var cs = getComputedStyle(s);
      var scene = document.createElement("div");
      scene.className = "v-scene";
      // The band around a scaled slide is the slide's own ground.
      scene.style.backgroundColor = cs.backgroundColor;
      if (cfg.scale !== 1 || cfg.left || cfg.top) {
        // Same texture, same scale, same origin as the slide: a grid or a
        // grain continues across the slide edge instead of changing size.
        scene.style.backgroundImage = cs.backgroundImage;
        scene.style.backgroundRepeat = cs.backgroundRepeat;
        scene.style.backgroundSize = layers(cs.backgroundSize, function (v, axis) {
          if (/px$/.test(v)) return num(v, 0) * cfg.scale + "px";
          if (/%$/.test(v)) return num(v, 0) / 100 * (axis ? s.offsetHeight : s.offsetWidth) * cfg.scale + "px";
          return v;
        });
        scene.style.backgroundPosition = layers(cs.backgroundPosition, function (v, axis) {
          var o = axis ? cfg.top : cfg.left;
          if (/px$/.test(v)) return o + num(v, 0) * cfg.scale + "px";
          if (v === "0%") return o + "px";
          return v;
        });
      }
      deck.appendChild(scene);
      scene.appendChild(s);
      if (pick.indexOf(i + 1) < 0) scene.style.display = "none";
      else scenes.push({ scene: scene, slide: s, index: i + 1 });
    });

    // Pass 1: plan each slide on its own clock, measure entrance and reading time.
    var X = cfg.transition, n = scenes.length;
    var plans = scenes.map(function (sc, k) {
      var s = sc.slide, still = k === 0 && cfg.staticFirst;
      plan = [];
      var tEnd = 0, tNext = 0;
      if (!still) {
        var blocks = q(s, ".s-main .b").filter(function (b) { return !b.parentElement.closest(".b"); });
        blocks.sort(function (a, b) { return num(a.dataset.b, 0) - num(b.dataset.b, 0); });
        blocks.forEach(function (b) {
          var r = block(b, tNext);
          tEnd = Math.max(tEnd, r.end);
          tNext = Math.max(tNext, r.next);
        });
      }
      var w = words(s);
      var maxRead = k === 0 ? Math.min(cfg.maxSlide, cfg.maxFirst) : cfg.maxSlide;
      var read = Math.min(maxRead, Math.max(cfg.minSlide, cfg.orient + w * 60 / cfg.wpm));
      var lead = k === 0 ? 0 : X * 0.6;
      var floor = Math.max(cfg.minSlide, lead + tEnd + (tEnd > 0 ? cfg.settle : 0) + (k === n - 1 ? cfg.endHold : 0));
      var full = lead + Math.max(tEnd + (tEnd > 0 ? cfg.settle : 0), read) + (k === n - 1 ? cfg.endHold : 0);
      return { sc: sc, plan: plan, words: w, read: read, entrance: tEnd, lead: lead, floor: floor, full: full };
    });
    // Pass 2: fit a total duration cap by shortening holds, never entrances.
    var total = plans.reduce(function (a, p) { return a + p.full; }, 0), squeeze = 1;
    if (cfg.maxDuration && total > cfg.maxDuration) {
      var floors = plans.reduce(function (a, p) { return a + p.floor; }, 0);
      squeeze = Math.max(0, (cfg.maxDuration - floors) / Math.max(1e-6, total - floors));
    }
    // Pass 3: absolute times, frame-aligned, then the real animations.
    var out = [], T = 0;
    plans.forEach(function (p, k) {
      var start = snap(T, fps);
      var dur = snap(p.floor + (p.full - p.floor) * squeeze, fps);
      var contentStart = snap(start + p.lead, fps);
      if (k > 0) materialize([{ el: p.sc.scene, keyframes: [{ opacity: 0 }, { opacity: 1 }], start: 0, dur: X, easing: "ease-in-out" }], start);
      materialize(p.plan, contentStart);
      out.push({ index: p.sc.index, id: p.sc.slide.id, start: start, contentStart: contentStart, end: snap(start + dur, fps),
                 words: p.words, read: Math.round(p.read * 100) / 100, entrance: Math.round(p.entrance * 100) / 100 });
      T = start + dur;
    });
    var duration = snap(T, fps);
    return { duration: duration, frames: Math.round(duration * fps), slides: out, squeeze: Math.round(squeeze * 1000) / 1000,
             floor: Math.round(plans.reduce(function (a, p) { return a + p.floor; }, 0) * 100) / 100 };
  }

  var EPS = 1e-6;

  function seek(t) {
    var moving = false, started = 0, done = 0;
    items.forEach(function (it) {
      if (it.anim) it.anim.currentTime = t * 1000;
      if (it.update) it.update(t);
      if (t > it.start + EPS) started++;
      if (t >= it.end - EPS) done++;
      if (t > it.start + EPS && t <= it.end + EPS) moving = true;
    });
    return { moving: moving, sig: started + ":" + done };
  }

  window.__animSetup = setup;
  window.__animSeek = seek;
})();
