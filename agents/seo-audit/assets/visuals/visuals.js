/* visuals.js: measured typography and DOM checks for one article visual.
 *
 * Adapted from agents/carousel-builder/scripts/fit.js (same line counting,
 * same rule: a text that does not hold at its minimum is never shrunk
 * further, it is reported and the fix goes in the spec).
 *
 * 1. Fit: every element marked data-fit gets the largest font size between
 *    data-fit-min and data-fit-max (px) that keeps it within data-fit-lines
 *    lines, without a word wider than its box, and, on a fixed canvas (the
 *    cover), without the canvas overflowing. Elements grow in data-fit-order.
 * 2. Measure: text boxes (.tx) wider than their box, a fixed canvas that
 *    overflows, text outside the canvas, text under the minimum size
 *    (body[data-min-text], body[data-min-meta] for .meta), WCAG contrast of
 *    every text node against the first opaque background under it, and the
 *    brand families that did not load (width probe against the fallback).
 *
 * Runs after document.fonts.ready and window load. Result: window.__visual
 * = {done, width, height, fit: [...], issues: [...], fonts: {...}} and
 * body[data-fitted="1"]. article_visuals.py turns issues into BLOCK or WARN.
 */
(function () {
  "use strict";
  var R = { done: false, width: 0, height: 0, fit: [], issues: [], fonts: {} };
  window.__visual = R;

  function num(v, d) { var n = parseFloat(v); return isNaN(n) ? d : n; }
  function where(el) { var w = el.closest("[data-where]"); return w ? w.getAttribute("data-where") : el.tagName.toLowerCase(); }
  function add(code, el, message, extra) {
    var rec = { code: code, where: el ? where(el) : "canvas", message: message };
    if (extra) { for (var k in extra) rec[k] = extra[k]; }
    R.issues.push(rec);
  }

  function textLines(el) {
    var range = document.createRange();
    range.selectNodeContents(el);
    var rects = Array.prototype.slice.call(range.getClientRects()).filter(function (r) { return r.width > 1 && r.height > 1; });
    var fs = num(getComputedStyle(el).fontSize, 16);
    var tops = [];
    rects.forEach(function (r) {
      var mid = r.top + r.height / 2;
      if (!tops.some(function (t) { return Math.abs(t - mid) < fs * 0.55; })) tops.push(mid);
    });
    return tops.length;
  }

  var canvas = document.querySelector(".canvas");
  var fixed = canvas.classList.contains("fixed");

  function canvasOverflows() { return fixed && canvas.scrollHeight > canvas.clientHeight + 1; }
  function wide(el) { return el.scrollWidth > el.clientWidth + 1; }
  function holds(el) { return textLines(el) <= num(el.dataset.fitLines, 99) && !wide(el) && !canvasOverflows(); }
  function setSize(el, px) { el.style.fontSize = px + "px"; }

  function fit() {
    var items = Array.prototype.slice.call(canvas.querySelectorAll("[data-fit]"));
    items.sort(function (a, b) { return num(a.dataset.fitOrder, 9) - num(b.dataset.fitOrder, 9); });
    items.forEach(function (el) { setSize(el, num(el.dataset.fitMin, 20)); });
    items.forEach(function (el) {
      var min = num(el.dataset.fitMin, 20), max = num(el.dataset.fitMax, min);
      var rec = { where: where(el), min: min, max: max, maxLines: num(el.dataset.fitLines, 99), size: min, lines: 0, status: "ok", reason: "" };
      setSize(el, min);
      if (!holds(el)) {
        rec.status = "fail";
        var l = textLines(el);
        if (l > rec.maxLines) rec.reason = l + " lines at the " + min + " px minimum, max " + rec.maxLines;
        else if (wide(el)) rec.reason = "a word is wider than the box at the " + min + " px minimum";
        else rec.reason = "the canvas overflows with this text at its " + min + " px minimum";
      } else {
        setSize(el, max);
        if (holds(el)) {
          rec.size = max;
        } else {
          var lo = min, hi = max;
          while (hi - lo > 1) {
            var mid = Math.floor((lo + hi) / 2);
            setSize(el, mid);
            if (holds(el)) lo = mid; else hi = mid;
          }
          rec.size = lo;
        }
        setSize(el, rec.size);
      }
      rec.lines = textLines(el);
      R.fit.push(rec);
    });
  }

  function parse(c) {
    var m = (c || "").match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var v = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 };
  }
  function lum(c) {
    return [c.r, c.g, c.b].map(function (x) { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); })
      .reduce(function (s, x, i) { return s + x * [0.2126, 0.7152, 0.0722][i]; }, 0);
  }
  function ratio(a, b) { var x = lum(a), y = lum(b); if (y > x) { var t = x; x = y; y = t; } return (x + 0.05) / (y + 0.05); }
  function blend(fg, bg) { return fg.a >= 1 ? fg : { r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 }; }
  function bgOf(el) {
    for (var e = el; e; e = e.parentElement) {
      var c = parse(getComputedStyle(e).backgroundColor);
      if (c && c.a >= 0.5) return c;
      if (e === canvas) break;
    }
    return parse(getComputedStyle(canvas).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 };
  }

  function probeFonts() {
    var span = document.createElement("span");
    span.textContent = "Hamburgefontsiv 0123456789 AaBbWw";
    span.style.cssText = "position:absolute;left:-9999px;top:0;font-size:40px;white-space:nowrap;visibility:hidden";
    document.body.appendChild(span);
    ["display", "body"].forEach(function (role) {
      var fam = document.body.getAttribute("data-font-" + role);
      if (!fam) { R.fonts[role] = { family: null, loaded: false }; return; }
      var differs = ["monospace", "serif", "sans-serif"].some(function (gen) {
        span.style.fontFamily = gen; var w0 = span.getBoundingClientRect().width;
        span.style.fontFamily = '"' + fam + '", ' + gen; var w1 = span.getBoundingClientRect().width;
        return Math.abs(w1 - w0) > 0.5;
      });
      R.fonts[role] = { family: fam, loaded: differs };
    });
    span.remove();
  }

  function measure() {
    var minText = num(document.body.dataset.minText, 20), minMeta = num(document.body.dataset.minMeta, 18);
    canvas.querySelectorAll(".tx").forEach(function (t) {
      if (wide(t)) add("overflow", t, "\"" + t.textContent.trim().slice(0, 48) + "\" is wider than its box (" + t.scrollWidth + " > " + t.clientWidth + " px).");
    });
    if (canvasOverflows()) add("overflow", null, "The canvas content is " + canvas.scrollHeight + " px tall, the canvas " + canvas.clientHeight + " px.");
    var cr = canvas.getBoundingClientRect();
    var seen = new Set();
    var walker = document.createTreeWalker(canvas, NodeFilter.SHOW_TEXT);
    var n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      var el = n.parentElement;
      if (!el || seen.has(el) || el.closest("svg")) continue;
      seen.add(el);
      var cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none") continue;
      var range = document.createRange(); range.selectNodeContents(n);
      var rects = Array.prototype.slice.call(range.getClientRects()).filter(function (r) { return r.width > 0.5 && r.height > 0.5; });
      if (!rects.length) continue;
      var txt = el.textContent.trim().slice(0, 48);
      var fs = num(cs.fontSize, 16), weight = parseInt(cs.fontWeight, 10) || 400;
      var min = el.closest(".meta") ? minMeta : minText;
      if (fs < min - 0.5) add("text-too-small", el, "\"" + txt + "\" renders at " + fs.toFixed(1) + " px, min " + min + " px at 1200 wide.");
      for (var i = 0; i < rects.length; i++) {
        var r = rects[i];
        if (r.left < cr.left - 1 || r.right > cr.right + 1 || r.top < cr.top - 1 || r.bottom > cr.bottom + 1) {
          add("outside", el, "\"" + txt + "\" leaves the canvas."); break;
        }
      }
      var bg = bgOf(el), fg0 = parse(cs.color);
      if (!fg0) continue;
      var fg = blend(fg0, bg), rr = ratio(fg, bg);
      var large = fs >= 24 || (fs >= 18.66 && weight >= 700);
      var need = large ? 3 : 4.5;
      if (rr < need) add("contrast", el, "\"" + txt + "\" " + rr.toFixed(2) + ":1 on rgb(" + bg.r + "," + bg.g + "," + bg.b + "), needs " + need + ":1.", { ratio: Math.round(rr * 100) / 100, need: need });
    }
    probeFonts();
    if (!fixed) canvas.style.height = Math.ceil(canvas.getBoundingClientRect().height) + "px";
    var fr = canvas.getBoundingClientRect();
    R.width = Math.round(fr.width);
    R.height = Math.round(fr.height);
  }

  function run() {
    fit();
    measure();
    R.done = true;
    document.body.dataset.fitted = "1";
  }

  var loaded = new Promise(function (resolve) {
    if (document.readyState === "complete") resolve();
    else window.addEventListener("load", resolve);
  });
  Promise.all([document.fonts.ready, loaded]).then(function () {
    requestAnimationFrame(function () { requestAnimationFrame(run); });
  });
})();
