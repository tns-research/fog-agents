/* fit.js: measured typography for static ads (adapted from carousel-builder).
 *
 * Every element build.py marks with data-fit gets the largest font size
 * between data-fit-min and data-fit-max (px) such that:
 *   - it holds in data-fit-lines lines,
 *   - no word overflows its box horizontally,
 *   - no [data-box] container of the ad overflows (the safe box included).
 * Elements sharing a data-fit-group (the bullets of a list, the two columns
 * of a comparison) share one size, so a list never mixes sizes.
 * Units grow in data-fit-order (headline first) while the others sit at their
 * minimum, so the hierarchy decides who gets the free space.
 *
 * A text that does not hold at its minimum is NOT shrunk further: it stays
 * at the minimum, gets status "fail", and qa.py turns it into an error. The
 * fix is in ads.json (shorter copy) or a larger format, never in the HTML.
 *
 * After the fit: media shown whole (fit-contain) are resized to their own
 * ratio inside the space left, feature callouts get their leader lines and
 * the 9:16 panels are placed: the footer panel (.slab) under the footer, the
 * stage (.stage) from the middle of the media in the visual zone.
 *
 * Runs after document.fonts.ready and window load. Result:
 * window.__fit = {done, sections: [{name, items, overflow, overflowAt}]} and
 * body[data-fitted="1"].
 */
(function () {
  "use strict";
  var report = { done: false, sections: [] };
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

  function overflowX(el) { return el.scrollWidth > el.clientWidth + 1; }

  function sectionOverflow(sec) {
    var out = [];
    sec.querySelectorAll("[data-box]").forEach(function (b, i) {
      if (b.scrollHeight > b.clientHeight + 2 || b.scrollWidth > b.clientWidth + 2) out.push((b.className || "box").toString().split(" ")[0] + "#" + i);
    });
    return out;
  }

  function setSize(els, px) { els.forEach(function (el) { el.style.fontSize = px + "px"; }); }

  function okUnit(unit, sec) {
    for (var i = 0; i < unit.els.length; i++) {
      var el = unit.els[i];
      if (textLines(el) > unit.maxLines) return false;
      if (overflowX(el)) return false;
    }
    return sectionOverflow(sec).length === 0;
  }

  function units(sec) {
    var map = {}, list = [];
    sec.querySelectorAll("[data-fit]").forEach(function (el) {
      var g = el.dataset.fitGroup;
      var key = g ? "g:" + g : "e:" + list.length + ":" + Math.random();
      if (!map[key]) {
        map[key] = { key: key, kind: el.dataset.fit, els: [], min: num(el.dataset.fitMin, 28), max: num(el.dataset.fitMax, 28),
                     maxLines: num(el.dataset.fitLines, 99), order: num(el.dataset.fitOrder, 9), idx: list.length };
        list.push(map[key]);
      }
      map[key].els.push(el);
    });
    list.sort(function (a, b) { return a.order - b.order || a.idx - b.idx; });
    return list;
  }

  function fitSection(sec) {
    var res = { name: sec.dataset.name, items: [], overflow: false, overflowAt: [] };
    var us = units(sec);
    us.forEach(function (u) { setSize(u.els, u.min); });
    us.forEach(function (u) {
      var rec = { kind: u.kind, count: u.els.length, min: u.min, max: u.max, maxLines: u.maxLines, size: u.min, lines: 0, status: "ok", reason: "",
                  text: u.els.map(function (e) { return e.textContent.trim().slice(0, 40); }).join(" | ") };
      setSize(u.els, u.min);
      if (!okUnit(u, sec)) {
        rec.status = "fail";
        var worst = 0;
        u.els.forEach(function (e) { worst = Math.max(worst, textLines(e)); });
        if (worst > u.maxLines) rec.reason = worst + " lines at the " + u.min + " px minimum, max " + u.maxLines;
        else if (u.els.some(overflowX)) rec.reason = "a word is wider than its box at the " + u.min + " px minimum";
        else rec.reason = "the ad overflows with this text at its " + u.min + " px minimum";
      } else {
        setSize(u.els, u.max);
        if (okUnit(u, sec)) {
          rec.size = u.max;
        } else {
          var lo = u.min, hi = u.max;
          while (hi - lo > 1) {
            var mid = Math.floor((lo + hi) / 2);
            setSize(u.els, mid);
            if (okUnit(u, sec)) lo = mid; else hi = mid;
          }
          rec.size = lo;
        }
        setSize(u.els, rec.size);
      }
      u.els.forEach(function (e) { rec.lines = Math.max(rec.lines, textLines(e)); if (rec.status === "fail") e.classList.add("fit-fail"); });
      res.items.push(rec);
    });
    var of = sectionOverflow(sec);
    if (of.length) { res.overflow = true; res.overflowAt = of; sec.classList.add("fit-overflow"); }
    return res;
  }

  // Media shown whole: shrink the box to the image's own ratio inside the
  // space it was given, so a portrait photo sits in a portrait frame.
  function hugMedia(sec) {
    sec.querySelectorAll(".media.fit-contain").forEach(function (box) {
      var img = box.querySelector(".m-img");
      if (!img || box.classList.contains("full")) return;
      var w = num(img.dataset.w, 0), h = num(img.dataset.h, 0);
      if (!w || !h) return;
      var bw = box.clientWidth, bh = box.clientHeight;
      if (!bw || !bh) return;
      var r = w / h;
      if (bw / bh > r) { box.style.width = Math.round(bh * r) + "px"; box.style.height = bh + "px"; }
      else { box.style.height = Math.round(bw / r) + "px"; box.style.width = bw + "px"; }
      box.style.flex = "0 0 auto";
      box.classList.add("hugged");
    });
  }

  // Leader lines from each callout to its anchor on the media.
  function drawCallouts(sec) {
    sec.querySelectorAll(".co-stage").forEach(function (stage) {
      var svg = stage.querySelector(".co-lines"), img = stage.querySelector(".m-img");
      if (!svg || !img) return;
      var sr = stage.getBoundingClientRect(), ir = img.getBoundingClientRect();
      svg.setAttribute("viewBox", "0 0 " + sr.width + " " + sr.height);
      svg.setAttribute("width", sr.width); svg.setAttribute("height", sr.height);
      var out = "";
      stage.querySelectorAll(".co").forEach(function (co) {
        var cr = co.getBoundingClientRect();
        var ax = ir.left - sr.left + ir.width * num(co.dataset.x, 50) / 100;
        var ay = ir.top - sr.top + ir.height * num(co.dataset.y, 50) / 100;
        var left = co.parentElement.classList.contains("l");
        var sx = (left ? cr.right : cr.left) - sr.left, sy = cr.top - sr.top + cr.height / 2;
        out += '<line x1="' + sx + '" y1="' + sy + '" x2="' + ax + '" y2="' + ay + '"/><circle cx="' + ax + '" cy="' + ay + '" r="9"/>';
      });
      svg.innerHTML = out;
    });
  }

  // 9:16 footer panel: from just above the footer (or the Reels line when
  // the ad has no footer) to the bottom edge.
  function placeSlab(sec) {
    var slab = sec.querySelector(".bg > .slab");
    if (!slab) return;
    var sr = sec.getBoundingClientRect();
    var line = sr.height - num(sec.style.getPropertyValue("--sb"), 0);
    var foot = sec.querySelector(".foot.on-slab");
    var top = line + 24;
    if (foot && foot.getBoundingClientRect().height > 0) top = Math.min(foot.getBoundingClientRect().top - sr.top, line);
    slab.style.top = Math.round(top) + "px";
  }

  // 9:16 visual zone: the panel the media stand on starts at their middle.
  function placeStage(sec) {
    var stage = sec.querySelector(".bg > .stage");
    if (!stage) return;
    var sr = sec.getBoundingClientRect(), mid = null;
    sec.querySelectorAll(".ext .media").forEach(function (m) {
      var r = m.getBoundingClientRect();
      var y = r.top - sr.top + r.height * 0.5;
      mid = mid === null ? y : Math.min(mid, y);
    });
    if (mid !== null) stage.style.top = Math.round(mid) + "px";
  }

  function run() {
    document.querySelectorAll("section.ad").forEach(function (sec) {
      var r = fitSection(sec);
      hugMedia(sec);
      drawCallouts(sec);
      placeSlab(sec);
      placeStage(sec);
      report.sections.push(r);
    });
    report.done = true;
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
