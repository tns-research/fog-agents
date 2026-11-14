/* fit.js: measured typography for carousel slides.
 *
 * Every text element that build.py marks with data-fit gets the largest font
 * size between data-fit-min and data-fit-max (px) such that:
 *   - it holds in data-fit-lines lines (for a list: each item does),
 *   - it does not overflow its own box horizontally (a long word),
 *   - the slide still fits: no .b block, .s-main or .s-frame overflows.
 * Elements grow in data-fit-order (title first), the others sitting at their
 * minimum, so the hierarchy decides who gets the free space. With
 * data-fit-steps the size snaps down to the direction's type scale, so a
 * series keeps a few consistent sizes instead of one size per slide.
 *
 * A text that does not hold at its minimum is NOT shrunk further: it stays at
 * the minimum, gets status "fail" and qa.py turns it into an error. The fix
 * is in deck.json (shorter copy), never in the HTML.
 *
 * Runs after document.fonts.ready and window load (images change the layout).
 * Result: window.__fit = {done, slides: [{index, id, overflow, items: [...]}]}
 * and body[data-fitted="1"].
 */
(function () {
  "use strict";
  var report = { done: false, slides: [] };
  window.__fit = report;

  function num(v, d) { var n = parseFloat(v); return isNaN(n) ? d : n; }

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

  function lines(el) {
    if (el.tagName === "UL" || el.tagName === "OL") {
      var max = 0;
      el.querySelectorAll(":scope > li .li-t").forEach(function (t) { max = Math.max(max, textLines(t)); });
      return max;
    }
    return textLines(el);
  }

  function overflowX(el) {
    if (el.scrollWidth > el.clientWidth + 1) return true;
    var bad = false;
    el.querySelectorAll(".li-t").forEach(function (t) { if (t.scrollWidth > t.clientWidth + 1) bad = true; });
    return bad;
  }

  function slideOverflow(slide) {
    var out = [];
    var frame = slide.querySelector(".s-frame");
    var main = slide.querySelector(".s-main");
    // Tolerance: display faces draw descenders and italic overhang past a
    // tight line box; that ink overflow is not a layout overflow.
    function tol(el) {
      var fs = 0;
      el.querySelectorAll("[data-fit]").forEach(function (t) { fs = Math.max(fs, num(t.style.fontSize || getComputedStyle(t).fontSize, 0)); });
      return Math.max(2, fs * 0.2);
    }
    var mt = main ? tol(main) : 2;
    if (frame && frame.scrollHeight > frame.clientHeight + mt) out.push("frame");
    if (main && main.scrollHeight > main.clientHeight + mt) out.push("main");
    // Content pushed out of the main area on either side (a flex-end column
    // overflows upwards, which scrollHeight does not see).
    if (main) {
      var mr = main.getBoundingClientRect(), mcs = getComputedStyle(main);
      var top = mr.top + num(mcs.paddingTop, 0) - 2, bottom = mr.bottom - num(mcs.paddingBottom, 0) + mt;
      var up = false;
      main.querySelectorAll(":scope > .b").forEach(function (b) {
        if (getComputedStyle(b).display === "contents") return;
        var r = b.getBoundingClientRect();
        if (r.height > 0 && (r.top < top || r.bottom > bottom)) up = true;
      });
      if (up && out.indexOf("main") < 0) out.push("main");
    }
    slide.querySelectorAll(".b").forEach(function (b) {
      var t = tol(b);
      if (getComputedStyle(b).display === "contents") return;
      if (b.scrollHeight > b.clientHeight + t || b.scrollWidth > b.clientWidth + t) out.push("b" + b.dataset.b);
    });
    return out;
  }

  function setSize(el, px) { el.style.fontSize = px + "px"; }

  function okEl(el, slide) {
    var maxLines = num(el.dataset.fitLines, 99);
    if (lines(el) > maxLines) return false;
    if (overflowX(el)) return false;
    return slideOverflow(slide).length === 0;
  }

  function snap(px, steps, min) {
    if (!steps || !steps.length) return px;
    var best = null;
    steps.forEach(function (s) { if (s <= px && s >= min && (best === null || s > best)) best = s; });
    return best === null ? px : best;
  }

  function fitSlide(slide, index) {
    var items = Array.prototype.slice.call(slide.querySelectorAll("[data-fit]"));
    items.sort(function (a, b) { return num(a.dataset.fitOrder, 9) - num(b.dataset.fitOrder, 9); });
    var res = { index: index, id: slide.id, items: [], overflow: false, overflowAt: [] };
    items.forEach(function (el) { setSize(el, num(el.dataset.fitMin, 24)); });
    items.forEach(function (el) {
      var min = num(el.dataset.fitMin, 24), max = num(el.dataset.fitMax, min);
      var steps = (el.dataset.fitSteps || "").split(",").map(Number).filter(function (x) { return x > 0; });
      var rec = { block: num(el.dataset.fitBlock, -1), kind: el.dataset.fit, min: min, max: max,
                  maxLines: num(el.dataset.fitLines, 99), size: min, lines: 0, status: "ok", reason: "" };
      setSize(el, min);
      if (!okEl(el, slide)) {
        rec.status = "fail";
        var l = lines(el);
        if (l > rec.maxLines) rec.reason = l + " lines at the " + min + " px minimum, max " + rec.maxLines;
        else if (overflowX(el)) rec.reason = "a word is wider than the box at the " + min + " px minimum";
        else rec.reason = "the slide overflows with this text at its " + min + " px minimum";
      } else {
        setSize(el, max);
        if (okEl(el, slide)) {
          rec.size = max;
        } else {
          var lo = min, hi = max;
          while (hi - lo > 1) {
            var mid = Math.floor((lo + hi) / 2);
            setSize(el, mid);
            if (okEl(el, slide)) lo = mid; else hi = mid;
          }
          rec.size = lo;
        }
        rec.size = snap(rec.size, steps, min);
        setSize(el, rec.size);
      }
      rec.lines = lines(el);
      if (rec.status === "fail") el.classList.add("fit-fail");
      res.items.push(rec);
    });
    var of = slideOverflow(slide);
    if (of.length) { res.overflow = true; res.overflowAt = of; slide.classList.add("fit-overflow"); }
    return res;
  }

  // Photo hug: a direction that sets --ph-hug: 1 on .ph-box gets the box
  // shrunk to the photo's own ratio inside the space left after the text fit,
  // so a portrait photo sits in a portrait frame instead of a wide mat.
  function hugPhotos(slide) {
    slide.querySelectorAll(".ph-box").forEach(function (box) {
      if (getComputedStyle(box).getPropertyValue("--ph-hug").trim() !== "1") return;
      var img = box.querySelector(".ph-img");
      if (!img) return;
      var w = num(img.dataset.w, 0), h = num(img.dataset.h, 0);
      if (!w || !h) return;
      // Available width = the figure's content box (the box itself may have
      // collapsed: its images are absolutely positioned).
      var fig = box.parentElement, fcs = getComputedStyle(fig);
      var bw = fig.clientWidth - num(fcs.paddingLeft, 0) - num(fcs.paddingRight, 0), bh = box.clientHeight;
      if (!bw || !bh) return;
      var r = w / h;
      if (bw / bh > r) { box.style.flex = "0 0 auto"; box.style.height = bh + "px"; box.style.width = Math.round(bh * r) + "px"; }
      else { box.style.flex = "0 0 auto"; box.style.height = Math.round(bw / r) + "px"; box.style.width = bw + "px"; }
    });
  }

  function run() {
    var slides = document.querySelectorAll("section.slide");
    slides.forEach(function (s, i) { report.slides.push(fitSlide(s, i + 1)); hugPhotos(s); });
    report.done = true;
    document.body.dataset.fitted = "1";
  }

  var loaded = new Promise(function (resolve) {
    if (document.readyState === "complete") resolve();
    else window.addEventListener("load", resolve);
  });
  Promise.all([document.fonts.ready, loaded]).then(function () {
    // One more frame so late font swaps settle before measuring.
    requestAnimationFrame(function () { requestAnimationFrame(run); });
  });
})();
