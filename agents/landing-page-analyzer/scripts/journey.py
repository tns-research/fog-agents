#!/usr/bin/env python3
"""journey.py: follow the conversion path the model wrote in journey.json, capture every
step on desktop and mobile, and block the final send by network interception.

  python3 scripts/journey.py <journey.json> --out <dir> [--url BASE_URL] [--viewports desktop,mobile]
  python3 scripts/journey.py <journey.json> --lint          # check the spec, run nothing

The spec (contract in assets/journey-playbook.md, schema in assets/journey.schema.json):

  {"url": "https://acme.example/", "goal": "demo",
   "test_data": {"email": "lpa-test@example.com"},      # optional overrides of the defaults
   "allow_write": ["/cart/add.js"],                    # optional: writes allowed BEFORE the final step
   "block": ["/api/track"],                            # optional: extra URLs blocked whatever the method
   "steps": [
     {"do": "goto", "url": "{{url}}", "name": "landing"},
     {"do": "click", "text": "Book a demo", "name": "open-form"},
     {"do": "submit", "text": "Send", "name": "empty-submit"},
     {"do": "fill", "field": "Work email", "value": "{{email}}"},
     {"do": "submit", "text": "Send", "name": "final-submit"}]}

Step verbs: goto, click, submit (a click marked final), fill, select, check, press,
tab (keyboard focus check), wait, scroll, reload, back, observe, check_links.
Locators: "text" (button or link name, then any text), "selector" (CSS), "role" +
"name", "field" (label, then placeholder, then CSS) for form verbs; "frame" (CSS of
an iframe) acts inside an embedded form; "nth" picks a match. Options per step:
"name", "only" (desktop or mobile), "optional", "final", "shot" (viewport, full,
false), "watch" (selectors whose text or attribute is recorded before and after),
"expect" ({"text": ...} or {"selector": ...}, recorded and failing the step when absent).

Safety, applied to every request of the browser context (all frames, iframes included;
service workers blocked; WebSockets never connected):
  - every write (POST, PUT, PATCH, DELETE) is aborted, except a URL listed in
    allow_write before the final step, and even then not when its URL or body
    (request.post_data) carries a test value;
  - allow_write patterns must name a path: "/", "*", a pattern under 4 characters
    or a bare host are refused by the lint;
  - during a final step (submit, or "final": true) every write is aborted, allow_write
    or not;
  - once a fill (or select) has run, every GET whose URL carries a value it typed is
    aborted, whatever the resource type (document, fetch, XHR, image, script, beacon)
    and whatever the step, and during a final step so is every GET carrying any test
    value: a GET form, a pixel or a JSONP call that holds the test e-mail never leaves;
  - writes to payment hosts (Stripe, PayPal, Adyen, Braintree, Checkout.com, Mollie,
    Paddle, Square, GoCardless, Lemon Squeezy, Shopify Pay) are always aborted;
  - newsletter endpoints (Mailchimp list-manage, /subscribe/post) and the spec's
    "block" list are aborted whatever the method.
Each abort is logged with its step, method, URL, resource type and reason, then
confirmed by the browser's requestfailed event (net::ERR_BLOCKED_BY_CLIENT). A write
that reaches the network during a final step is a safety violation (exit 3).
Test data must use reserved values: e-mails on example.com, example.org, example.net
or a .test, .invalid, .example domain, otherwise the spec is refused.

Per step and viewport it records: URL, HTTP status and redirect chain of the page,
HTTPS and certificate (issuer, validity), visible error messages and the field each
sits next to, fields whose filled value was lost, the clicked element's state just
after the click (label, disabled, aria-busy), watched values, focus indicator on tab
steps, anchor landing under a sticky header, iframe hosts, payment hosts seen, link
statuses on check_links steps, and a PNG (<out>/journey/<viewport>/NN-<name>.png).
Writes <out>/journey/journey-log.json and <out>/journey/journey-board.jpg (one row
per step, desktop and mobile side by side).

Exit 0: every required step passed on every viewport and the safety proof holds.
Exit 1: a required step or an expect failed (later steps not run, outputs written).
Exit 2: fatal (bad spec, unsafe test data, Playwright missing or older than 1.48,
the first version able to intercept WebSockets).
Exit 3: safety violation (a write left the browser during a final step).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpa_common as C  # noqa: E402

VERBS = {"goto", "click", "submit", "fill", "select", "check", "press", "tab", "wait", "scroll",
         "reload", "back", "observe", "check_links"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PAYMENT_HOSTS = ["api.stripe.com", "m.stripe.com", "r.stripe.com", "*.paypal.com", "paypal.com",
                 "*.adyen.com", "*.adyenpayments.com", "*.braintreegateway.com", "api.checkout.com",
                 "*.mollie.com", "*.paddle.com", "connect.squareup.com", "pci-connect.squareup.com",
                 "*.gocardless.com", "api.lemonsqueezy.com", "pay.shopify.com", "shop.app"]
DEFAULT_BLOCK = ["*list-manage.com/subscribe*", "*/subscribe/post*", "*/subscribe/post-json*"]
MIN_TEST_VALUE_LEN = 4  # shorter test values ("75" ...) would match unrelated URLs
MIN_ALLOW_WRITE_LEN = 4
# check_links never follows a link whose path holds one of these (after dropping - and _).
LINK_SKIP_WORDS = ("logout", "signout", "unsubscribe", "delete")
TOKEN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


# ---- policy (pure, unit-tested by selftest.py) --------------------------------------------
def _match(pattern: str, url: str) -> bool:
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(url, pattern) or fnmatch.fnmatch(url, "*" + pattern.lstrip("*"))
    return pattern in url


def _host_match(host: str, pattern: str) -> bool:
    return fnmatch.fnmatch(host, pattern)


def carries_test_value(text: Optional[str], test_values: List[str]) -> bool:
    """True when a test value appears in text (URL or request body), raw, URL-decoded once or
    twice, case-insensitive, as a whole token (not inside a longer word)."""
    if not text:
        return False
    raw = text.lower()
    once = unquote(raw.replace("+", " "))
    forms = {raw, once, unquote(once)}
    for v in test_values:
        v = str(v).strip().lower()
        if len(v) < MIN_TEST_VALUE_LEN:
            continue
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(v) + r"(?![a-z0-9])")
        if any(pat.search(f) for f in forms):
            return True
    return False


def classify(method: str, url: str, resource_type: str, final: bool, allow_write: List[str],
             block: List[str], test_values: List[str], typed_values: Optional[List[str]] = None,
             body: Optional[str] = None) -> Tuple[str, str]:
    """Return ("continue" | "abort", reason) for one request.

    test_values: every reserved test value of the run (writes and final steps are checked
    against them). typed_values: the values fill and select steps have typed so far in this
    context; once there is one, every GET carrying one is aborted, any resource type, any
    step. body: the request body of a write (request.post_data)."""
    typed = list(typed_values or [])
    method = method.upper()
    host = (urlparse(url).hostname or "").lower()
    write = method not in SAFE_METHODS
    if write and any(_host_match(host, p) for p in PAYMENT_HOSTS):
        return "abort", "payment-write"
    if any(_match(p, url) for p in block):
        return "abort", "spec-block"
    if any(_match(p, url) for p in DEFAULT_BLOCK):
        return "abort", "subscribe-endpoint"
    if write:
        if final:
            return "abort", "final-step-write"
        if any(_match(p, url) for p in allow_write):
            if carries_test_value(url, test_values) or carries_test_value(body, test_values):
                return "abort", "allowed-write-with-test-data"
            return "continue", "allowed-write"
        return "abort", "write"
    if final and carries_test_value(url, list(test_values) + typed):
        return "abort", "final-step-get-with-test-data"
    if typed and carries_test_value(url, typed):
        return "abort", "get-with-test-data"
    return "continue", "read"


def allow_write_error(pattern: Any) -> Optional[str]:
    """Why an allow_write pattern is too broad, or None. A pattern must name a path."""
    if not isinstance(pattern, str):
        return f"allow_write: {pattern!r} must be a string"
    pat = pattern.strip()
    if pat in ("/", "*") or len(pat) < MIN_ALLOW_WRITE_LEN:
        return f"allow_write: {pattern!r} is too broad (\"/\", \"*\" and patterns under {MIN_ALLOW_WRITE_LEN} characters match every write)"
    rest = pat.split("://", 1)[1] if "://" in pat else pat
    core = rest.lstrip("*?")  # "*/api/lead" names a path, "*.acme.example" a host
    path = core[core.find("/"):] if "/" in core else ""
    if not path.strip("*?/"):
        return (f"allow_write: {pattern!r} is too broad (a bare host or wildcard path); name the endpoint path, "
                "for example /cart/add.js")
    return None


def is_test_email(value: str) -> bool:
    if "@" not in value:
        return True
    domain = value.rsplit("@", 1)[1].lower().strip()
    return domain in C.TEST_EMAIL_DOMAINS or domain.endswith(C.TEST_EMAIL_TLDS)


# ---- spec ---------------------------------------------------------------------------------
def load_spec(path: Path) -> Dict[str, Any]:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        C.die(f"cannot read {path}: {e}")
    return spec


def lint(spec: Dict[str, Any], data: Dict[str, str]) -> List[str]:
    errs = []
    if not isinstance(spec.get("steps"), list) or not spec["steps"]:
        errs.append("steps: a non-empty list is required")
        return errs
    for k in ("allow_write", "block"):
        if not isinstance(spec.get(k, []), list):
            errs.append(f"{k}: must be a list of URL patterns")
    for pat in spec.get("allow_write", []) if isinstance(spec.get("allow_write", []), list) else []:
        if isinstance(pat, str) and any(h.strip("*.") in pat for h in PAYMENT_HOSTS):
            errs.append(f"allow_write: {pat!r} targets a payment host; payment writes are never allowed")
        broad = allow_write_error(pat)
        if broad:
            errs.append(broad)
    for key, value in data.items():
        if ("email" in key or "@" in str(value)) and not is_test_email(str(value)):
            errs.append(f"test_data.{key}: {value!r} is not a reserved test address (use example.com, example.org, example.net or a .test domain)")
    finals = 0
    for i, st in enumerate(spec["steps"], 1):
        where = f"steps[{i}]"
        if not isinstance(st, dict):
            errs.append(f"{where}: must be an object")
            continue
        verb = st.get("do")
        if verb not in VERBS:
            errs.append(f"{where}: unknown verb {verb!r} (known: {', '.join(sorted(VERBS))})")
            continue
        if st.get("only") not in (None, *C.PROFILES.keys()):
            errs.append(f"{where}: only must be a viewport name")
        if verb in ("click", "submit") and not any(k in st for k in ("text", "selector", "role")):
            errs.append(f"{where}: {verb} needs text, selector or role")
        if verb in ("fill", "select", "check") and not any(k in st for k in ("field", "selector")):
            errs.append(f"{where}: {verb} needs field or selector")
        if verb in ("fill", "select") and "value" not in st:
            errs.append(f"{where}: {verb} needs value")
        if verb == "goto" and not st.get("url"):
            errs.append(f"{where}: goto needs url")
        if verb == "press" and not st.get("key"):
            errs.append(f"{where}: press needs key")
        if verb == "fill":
            v = expand(str(st.get("value", "")), data, "")
            if "@" in v and not is_test_email(v):
                errs.append(f"{where}: value {v!r} is not a reserved test address")
            for tok in TOKEN.findall(str(st.get("value", ""))):
                if tok not in data and tok != "url":
                    errs.append(f"{where}: unknown token {{{{{tok}}}}} (known: {', '.join(sorted(data))})")
        if verb == "submit" or st.get("final"):
            finals += 1
    if finals == 0:
        errs.append("no final step: mark the click that sends the form or pays with do=submit or final=true")
    return errs


def link_has_side_effect(href: str) -> bool:
    """A link whose path names logout, signout, unsubscribe or delete (log-out, sign_out too)."""
    path = unquote(urlparse(href).path).lower().replace("-", "").replace("_", "")
    return any(w in path for w in LINK_SKIP_WORDS)


def expand(value: str, data: Dict[str, str], base: str) -> str:
    return TOKEN.sub(lambda m: base if m.group(1) == "url" else str(data.get(m.group(1), m.group(0))), value)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "step"


# ---- page helpers -------------------------------------------------------------------------
def scope(page, st):
    return page.frame_locator(st["frame"]) if st.get("frame") else page


def visible_first(loc, nth: int = 0):
    try:
        loc = loc.filter(visible=True)
    except TypeError:
        pass
    return loc.nth(nth)


def locate(page, st) -> Tuple[Any, str]:
    sc = scope(page, st)
    nth = int(st.get("nth", 0))
    if st.get("selector"):
        return visible_first(sc.locator(st["selector"]), nth), "selector"
    if st.get("role"):
        return visible_first(sc.get_by_role(st["role"], name=st.get("name_text") or st.get("text")), nth), "role"
    if st.get("field"):
        field = st["field"]
        for how, loc in (("label", sc.get_by_label(field)), ("placeholder", sc.get_by_placeholder(field))):
            if loc.count():
                return visible_first(loc, nth), how
        return visible_first(sc.locator(field), nth), "selector"
    text = st["text"]
    exact = bool(st.get("exact"))
    for how, loc in (("button", sc.get_by_role("button", name=text, exact=exact)),
                     ("link", sc.get_by_role("link", name=text, exact=exact)),
                     ("text", sc.get_by_text(text, exact=exact))):
        try:
            n = loc.filter(visible=True).count()
        except TypeError:
            n = loc.count()
        if n:
            return visible_first(loc, nth), how
    return visible_first(sc.get_by_text(text, exact=exact), nth), "text"


WATCH_JS = """(items) => items.map(w => {
  const el = document.querySelector(w.selector);
  if (!el) return {selector: w.selector, value: null};
  const v = w.attr ? el.getAttribute(w.attr) : (el.innerText || el.value || '').replace(/\\s+/g, ' ').trim().slice(0, 200);
  return {selector: w.selector, attr: w.attr || null, value: v};
})"""

# Records the clicked element's state at click time and on every change for 3 s, so a
# loading state that lasts a few milliseconds is still caught.
WATCH_CLICK_JS = """(el) => {
  const st = () => ({text: (el.innerText || el.value || '').replace(/\\s+/g, ' ').trim().slice(0, 80), disabled: !!el.disabled,
    aria_busy: el.getAttribute('aria-busy'), aria_disabled: el.getAttribute('aria-disabled'), class: (typeof el.className === 'string' ? el.className : '').slice(0, 120)});
  window.__lpaClickStates = [st()];
  const mo = new MutationObserver(() => { const s = st(); const last = window.__lpaClickStates[window.__lpaClickStates.length - 1];
    if (JSON.stringify(s) !== JSON.stringify(last)) window.__lpaClickStates.push(s); });
  mo.observe(el, {attributes: true, childList: true, subtree: true, characterData: true});
  setTimeout(() => mo.disconnect(), 3000);
}"""

FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const pick = (cs) => [cs.outlineStyle, cs.outlineWidth, cs.outlineColor, cs.boxShadow, cs.borderColor, cs.backgroundColor, cs.textDecorationLine, cs.color].join('|');
  const focused = pick(getComputedStyle(el));
  const r = el.getBoundingClientRect();
  el.blur();
  const rest = pick(getComputedStyle(el));
  return {selector: window.__lpa.sel(el), text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 60),
    indicator: focused !== rest, x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height)};
}"""

ANCHOR_JS = """(hash) => {
  const id = decodeURIComponent(hash.slice(1));
  const target = document.getElementById(id) || document.querySelector('[name="' + id + '"]');
  if (!target) return {hash, found: false};
  const top = target.getBoundingClientRect().top;
  let cover = 0;
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    const r = el.getBoundingClientRect();
    if (r.top <= 1 && r.height > 0 && r.height < innerHeight / 2) cover = Math.max(cover, r.bottom);
  }
  return {hash, found: true, target_top_px: Math.round(top), sticky_bottom_px: Math.round(cover), hidden_under_sticky: top < cover - 1};
}"""

FIELDS_JS = """(names) => names.map(n => { const el = document.querySelector(n.selector); return {selector: n.selector, filled: n.value, now: el ? el.value : null}; })"""


class Run:
    def __init__(self, spec, data, base, out: Path, viewport: str):
        self.spec, self.data, self.base, self.out, self.vp = spec, data, base, out, viewport
        self.step_no = 0
        self.final = False
        self.network: List[Dict[str, Any]] = []
        self.by_request: Dict[Any, Dict[str, Any]] = {}
        self.writes_sent: List[Dict[str, Any]] = []
        self.violations: List[Dict[str, Any]] = []
        self.websockets: List[str] = []
        self.payment_hosts: set = set()
        self.filled: List[Dict[str, str]] = []
        self.typed: List[str] = []  # values typed by fill and select: a GET carrying one is aborted
        self.test_values = [v for v in data.values() if isinstance(v, str)]
        self.docs: List[Dict[str, Any]] = []

    # network
    def typed_value(self, raw: str, value: str) -> None:
        """Record a typed value and the test values its tokens expanded to, before typing it."""
        for v in [value] + [str(self.data[t]) for t in TOKEN.findall(raw) if t in self.data]:
            if v and v not in self.typed:
                self.typed.append(v)

    @staticmethod
    def _body(request) -> str:
        try:
            buf = request.post_data_buffer
        except Exception:
            return ""
        return buf.decode("utf-8", errors="replace") if buf else ""

    def route(self, route, request):
        write = request.method.upper() not in SAFE_METHODS
        body = self._body(request) if write else ""
        action, reason = classify(request.method, request.url, request.resource_type, self.final,
                                  self.spec.get("allow_write", []), self.spec.get("block", []), self.test_values,
                                  typed_values=self.typed, body=body)
        host = (urlparse(request.url).hostname or "").lower()
        if any(_host_match(host, p) for p in PAYMENT_HOSTS):
            self.payment_hosts.add(host)
        if action == "abort" or write:
            post = body
            entry = {"step": self.step_no, "final": self.final, "action": action, "reason": reason,
                     "method": request.method, "url": request.url[:300], "type": request.resource_type,
                     "body_bytes": len(post.encode("utf-8")) if post else 0, "confirmed": False}
            self.network.append(entry)
            self.by_request[request] = entry
        if action == "abort":
            route.abort("blockedbyclient")
        else:
            route.continue_()

    def on_failed(self, request):
        e = self.by_request.get(request)
        if e and e["action"] == "abort":
            e["confirmed"] = True
            e["browser_error"] = request.failure

    def on_finished(self, request):
        if request.method.upper() in SAFE_METHODS:
            return
        e = self.by_request.get(request, {"step": self.step_no, "final": self.final, "url": request.url[:300], "method": request.method})
        rec = {"step": e["step"], "method": request.method, "url": request.url[:300], "final": e.get("final")}
        self.writes_sent.append(rec)
        if e.get("final"):
            self.violations.append(rec)

    def on_ws(self, ws):
        self.websockets.append(ws.url[:200])
        self.network.append({"step": self.step_no, "final": self.final, "action": "abort", "reason": "websocket",
                             "method": "WS", "url": ws.url[:300], "type": "websocket", "confirmed": True})

    def on_response(self, resp):
        try:
            if resp.request.resource_type == "document" and resp.frame == resp.frame.page.main_frame:
                chain, r = [], resp.request.redirected_from
                while r:
                    chain.insert(0, r.url)
                    r = r.redirected_from
                sec = None
                try:
                    sec = resp.security_details()
                except Exception:
                    pass
                self.docs.append({"step": self.step_no, "url": resp.url, "status": resp.status, "redirects": chain,
                                  "https": resp.url.startswith("https://"),
                                  "tls": {k: sec.get(k) for k in ("protocol", "issuer", "validFrom", "validTo")} if sec else None})
        except Exception:
            pass


def do_step(page, ctx, run: Run, st: Dict[str, Any], obs: Dict[str, Any]) -> None:
    verb = st["do"]
    timeout = int(st.get("timeout", 8000))
    if verb == "goto":
        url = urljoin(run.base, expand(st["url"], run.data, run.base))
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        C.settle(page, int(st.get("settle_ms", 800)))
    elif verb in ("click", "submit"):
        loc, how = locate(page, st)
        loc.wait_for(state="visible", timeout=timeout)
        obs["matched_by"] = how
        info = loc.evaluate("(el) => ({href: el.getAttribute('href'), target: el.getAttribute('target'), tag: el.tagName.toLowerCase()})")
        obs["element"] = info
        if info.get("target") == "_blank":
            loc.evaluate("(el) => el.removeAttribute('target')")
            obs["note"] = "target=_blank removed so the destination opens in the same tab"
        loc.scroll_into_view_if_needed(timeout=timeout)
        handle = loc.element_handle(timeout=timeout)
        before = obs.pop("_before_path", None)
        if before:
            before.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(before))
            obs["shot_before"] = before.parent.name + "/" + before.name
        url_before = page.url
        if handle:
            handle.evaluate(WATCH_CLICK_JS)
        loc.click(timeout=timeout)
        page.wait_for_timeout(150)
        try:
            states = page.evaluate("() => window.__lpaClickStates || null")
            if states:
                obs["click_states"] = states[:6]
                obs["after_click"] = states[1] if len(states) > 1 else dict(states[0], changed=False)
            else:
                obs["after_click"] = "element gone (navigation or re-render)"
        except Exception:
            obs["after_click"] = "element gone (navigation or re-render)"
        page.wait_for_timeout(int(st.get("settle_ms", 700)))
        C.settle(page, 300)
        href = info.get("href") or ""
        if href.startswith("#") and len(href) > 1:
            obs["anchor"] = page.evaluate(ANCHOR_JS, href)
        obs["navigated"] = page.url != url_before
    elif verb == "fill":
        loc, how = locate(page, st)
        loc.wait_for(state="visible", timeout=timeout)
        value = expand(str(st["value"]), run.data, run.base)
        run.typed_value(str(st["value"]), value)  # before typing: an autocomplete call may carry it
        loc.fill(value, timeout=timeout)
        obs["matched_by"] = how
        if how == "placeholder":
            obs["label_issue"] = "field found by its placeholder only (no label)"
        try:
            sel = loc.evaluate("(el) => window.__lpa ? window.__lpa.sel(el) : null")
            if sel and not st.get("frame"):
                page_url = page.url.split("#")[0]
                run.filled = [f for f in run.filled if f["page"] == page_url and f["selector"] != sel] + [{"selector": sel, "value": value, "page": page_url}]
        except Exception:
            pass
        if st.get("blur", True):
            loc.press("Tab")
            page.wait_for_timeout(250)
    elif verb == "select":
        loc, how = locate(page, st)
        value = expand(str(st["value"]), run.data, run.base)
        run.typed_value(str(st["value"]), value)
        try:
            loc.select_option(label=value, timeout=timeout)
        except Exception:
            loc.select_option(value=value, timeout=timeout)
        obs["matched_by"] = how
        page.wait_for_timeout(int(st.get("settle_ms", 500)))
    elif verb == "check":
        loc, how = locate(page, st)
        loc.check(timeout=timeout)
        obs["matched_by"] = how
    elif verb == "press":
        if st.get("field") or st.get("selector"):
            loc, _ = locate(page, st)
            loc.press(st["key"], timeout=timeout)
        else:
            page.keyboard.press(st["key"])
        page.wait_for_timeout(400)
    elif verb == "tab":
        focus = []
        for _ in range(int(st.get("count", 5))):
            page.keyboard.press("Tab")
            page.wait_for_timeout(120)
            f = page.evaluate(FOCUS_JS)
            if f:
                focus.append(f)
        obs["focus"] = focus
        obs["focus_without_indicator"] = [f["selector"] for f in focus if not f["indicator"]]
    elif verb == "wait":
        if "ms" in st:
            page.wait_for_timeout(int(st["ms"]))
        if st.get("selector"):
            page.locator(st["selector"]).first.wait_for(state="visible", timeout=timeout)
        if st.get("text"):
            page.get_by_text(st["text"]).first.wait_for(state="visible", timeout=timeout)
        if st.get("url_contains"):
            page.wait_for_url(re.compile(re.escape(st["url_contains"])), timeout=timeout)
    elif verb == "scroll":
        to = st.get("to", "bottom")
        if to == "bottom":
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        elif isinstance(to, (int, float)):
            page.evaluate(f"window.scrollTo(0, {int(to)})")
        else:
            page.locator(to).first.scroll_into_view_if_needed(timeout=timeout)
        page.wait_for_timeout(500)
    elif verb == "reload":
        page.reload(wait_until="domcontentloaded")
        C.settle(page, 800)
    elif verb == "back":
        page.go_back(wait_until="domcontentloaded")
        C.settle(page, 600)
    elif verb == "check_links":
        scope_sel = st.get("selector", "header a[href], nav a[href], footer a[href]")
        hrefs = page.evaluate("(s) => [...new Set([...document.querySelectorAll(s)].map(a => a.href).filter(h => /^https?:/.test(h)))]", scope_sel)
        results = []
        for href in hrefs[: int(st.get("max", 40))]:
            if any(_match(p, href) for p in DEFAULT_BLOCK + run.spec.get("block", [])):
                results.append({"url": href, "status": None, "skipped": "blocked pattern"})
                continue
            if link_has_side_effect(href):
                results.append({"url": href, "status": None, "skipped": "side-effect link (logout, signout, unsubscribe, delete)"})
                continue
            try:
                r = ctx.request.get(href.split("#")[0], timeout=12000, max_redirects=5)
                results.append({"url": href, "status": r.status, "final_url": r.url})
            except Exception as e:
                results.append({"url": href, "status": None, "error": str(e).splitlines()[0][:120]})
        obs["links"] = results
        obs["dead_links"] = [r["url"] for r in results if not r.get("skipped") and (r.get("status") is None or r["status"] >= 400)]
    # observe: nothing to do beyond the shared observations


def observe(page, run: Run, st: Dict[str, Any], obs: Dict[str, Any]) -> None:
    obs["url"] = page.url
    obs["title"] = page.title()
    try:
        obs["errors"] = page.evaluate("() => window.__lpa ? window.__lpa.errors() : null")
    except Exception:
        obs["errors"] = None
    here = [f for f in run.filled if f["page"] == page.url.split("#")[0]]
    if here:
        try:
            vals = page.evaluate(FIELDS_JS, here)
            obs["fields_lost"] = [v["selector"] for v in vals if v["now"] is not None and v["now"] != v["filled"]]
        except Exception:
            pass
    try:
        obs["iframes"] = page.evaluate("() => [...document.querySelectorAll('iframe')].filter(f => f.getBoundingClientRect().height > 20).map(f => { try { return new URL(f.src, location.href).host } catch (e) { return f.src } }).filter(Boolean)")
    except Exception:
        pass


def shoot(page, path: Path, mode) -> Optional[str]:
    if mode is False or mode == "false":
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "full":
        vp = page.viewport_size or {"width": 1280, "height": 900}
        total = page.evaluate("document.documentElement.scrollHeight")
        page.screenshot(path=str(path), full_page=True, clip={"x": 0, "y": 0, "width": vp["width"], "height": min(total, vp["height"] * 6)})
    else:
        page.screenshot(path=str(path))
    return path.as_posix()


def run_viewport(p, browser, spec, data, base, out: Path, vp: str, args) -> Dict[str, Any]:
    run = Run(spec, data, base, out, vp)
    ctx = C.new_context(browser, vp, args.locale, args.timezone)
    ctx.route("**/*", run.route)
    if not hasattr(ctx, "route_web_socket"):  # main() refuses such a Playwright before any run
        raise RuntimeError("this Playwright version cannot intercept WebSockets: upgrade to 1.48 or later")
    ctx.route_web_socket(re.compile(".*"), lambda ws: run.on_ws(ws))
    ws_note = "WebSockets intercepted and never connected"
    page = ctx.new_page()
    page.on("requestfailed", run.on_failed)
    page.on("requestfinished", run.on_finished)
    page.on("response", run.on_response)
    console_errors: List[str] = []
    page.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
    steps_out = []
    stopped = False
    status = "pass"
    if spec["steps"][0].get("do") != "goto":
        page.goto(base, wait_until="domcontentloaded", timeout=45000)
        C.settle(page, 800)
    for i, st in enumerate(spec["steps"], 1):
        name = slug(st.get("name") or f"{st['do']}-{st.get('text') or st.get('field') or ''}")
        rec: Dict[str, Any] = {"n": i, "do": st["do"], "name": name, "final": bool(st["do"] == "submit" or st.get("final"))}
        if st.get("only") and st["only"] != vp:
            rec["status"] = "skipped (only " + st["only"] + ")"
            steps_out.append(rec)
            continue
        if stopped:
            rec["status"] = "not-run"
            steps_out.append(rec)
            continue
        run.step_no = i
        run.final = rec["final"]
        obs: Dict[str, Any] = {}
        t0 = time.time()
        try:
            if rec["final"] and st.get("shot", "viewport") not in (False, "false"):
                obs["_before_path"] = out / "journey" / vp / f"{i:02d}-{name}-before.png"
            if st.get("watch"):
                obs["watch_before"] = page.evaluate(WATCH_JS, [w if isinstance(w, dict) else {"selector": w} for w in st["watch"]])
            do_step(page, ctx, run, st, obs)
            if run.final:
                page.wait_for_timeout(int(st.get("final_wait_ms", 1500)))
            if st.get("watch"):
                obs["watch_after"] = page.evaluate(WATCH_JS, [w if isinstance(w, dict) else {"selector": w} for w in st["watch"]])
            observe(page, run, st, obs)
            exp = st.get("expect")
            if exp:
                ok = True
                if exp.get("text"):
                    ok = ok and page.get_by_text(exp["text"]).first.is_visible()
                if exp.get("selector"):
                    ok = ok and page.locator(exp["selector"]).first.is_visible()
                obs["expect"] = {"want": exp, "met": bool(ok)}
                if not ok:
                    raise RuntimeError(f"expect not met: {exp}")
            rec["status"] = "ok"
        except Exception as e:
            rec["status"] = "failed (optional)" if st.get("optional") else "failed"
            rec["error"] = str(e).splitlines()[0][:300]
            try:
                observe(page, run, st, obs)
            except Exception:
                pass
            if not st.get("optional"):
                stopped = True
                status = "fail"
        finally:
            run.final = False
        rec["seconds"] = round(time.time() - t0, 2)
        shot_mode = st.get("shot", "viewport")
        fname = f"{i:02d}-{name}{'-failed' if rec['status'].startswith('failed') else ''}.png"
        try:
            rec["shot"] = shoot(page, out / "journey" / vp / fname, shot_mode)
            if rec["shot"]:
                rec["shot"] = f"{vp}/{fname}"
        except Exception as e:
            rec["shot_error"] = str(e).splitlines()[0][:200]
        if rec["final"]:
            blocked = [n for n in run.network if n["step"] == i and n["action"] == "abort"]
            rec["blocked"] = blocked
            if obs.get("url", "").startswith("chrome-error://"):
                obs["page_after_block"] = "the browser shows its error page after the blocked navigation: read the -before capture for the filled form"
            rec["final_note"] = ("final send blocked: " + ", ".join(f"{b['method']} {urlparse(b['url']).path}" for b in blocked)) if blocked else \
                "no request left the page at this step (client-side validation or no handler): read the capture"
        obs.pop("_before_path", None)
        rec["observations"] = obs
        steps_out.append(rec)
    page.wait_for_timeout(300)
    ctx.close()
    unconfirmed = [n for n in run.network if n["action"] == "abort" and not n["confirmed"] and n["reason"] != "websocket"]
    return {
        "viewport": vp, "status": status, "steps": steps_out,
        "documents": run.docs,
        "safety": {
            "policy": "writes aborted except allow_write before the final step and never with test data in the URL or body; every write, payment write and GET carrying test data aborted during final steps; after a fill, every GET carrying a typed value aborted (any resource type, any step); WebSockets not connected; service workers blocked",
            "websockets": ws_note,
            "requests_logged": len(run.network),
            "aborted": sum(1 for n in run.network if n["action"] == "abort"),
            "aborted_confirmed_by_browser": sum(1 for n in run.network if n["action"] == "abort" and n["confirmed"]),
            "aborted_unconfirmed": unconfirmed[:10],
            "writes_sent": run.writes_sent,
            "writes_sent_during_final_steps": run.violations,
            "payment_hosts_seen": sorted(run.payment_hosts),
        },
        "network": run.network,
        "console_errors": console_errors[:20],
    }


def board(log: Dict[str, Any], out: Path) -> Optional[Path]:
    """One row per step: label, desktop capture, mobile capture."""
    from PIL import Image, ImageDraw
    vps = [v["viewport"] for v in log["viewports"]]
    rows = []
    n_steps = max(len(v["steps"]) for v in log["viewports"]) if log["viewports"] else 0
    widths = {"desktop": 560, "desktop-hd": 560, "mobile": 210}
    for i in range(n_steps):
        cells, label = [], None
        for v in log["viewports"]:
            st = v["steps"][i]
            label = label or f"{st['n']:02d} {st['do']} {st['name']}"
            shot = st.get("shot")
            obs = st.get("observations") or {}
            if obs.get("page_after_block") and obs.get("shot_before"):
                shot = obs["shot_before"]
            path = out / "journey" / shot if shot else None
            cells.append((v["viewport"], st, path if path and path.exists() else None))
        rows.append((label, cells))
    if not rows:
        return None
    f, fs = C.font(18), C.font(14)
    W = 260 + sum(widths.get(v, 400) + 20 for v in vps)
    tiles = []
    for label, cells in rows:
        ims = []
        for vp, st, path in cells:
            w = widths.get(vp, 400)
            if path:
                im = Image.open(path).convert("RGB")
                im = im.resize((w, max(1, int(im.height * w / im.width))))
            else:
                im = Image.new("RGB", (w, 60), (235, 235, 235))
            ims.append((vp, st, im))
        h = max(im.height for _, _, im in ims) + 20
        row = Image.new("RGB", (W, h), (255, 255, 255))
        d = ImageDraw.Draw(row)
        d.text((12, 12), label, fill=(17, 17, 17), font=f)
        y = 40
        for vp, st, _ in ims:
            color = (20, 110, 50) if st.get("status") == "ok" else (170, 30, 30)
            d.text((12, y), f"{vp}: {st.get('status')}", fill=color, font=fs)
            y += 20
            for b in st.get("blocked", [])[:3]:
                d.text((12, y), f"blocked {b['method']} {urlparse(b['url']).path[:24]}", fill=(150, 30, 30), font=fs)
                y += 18
        x = 260
        for vp, st, im in ims:
            row.paste(im, (x, 10))
            x += widths.get(vp, 400) + 20
        tiles.append(row)
    total_h = sum(t.height for t in tiles) + 4 * len(tiles)
    img = Image.new("RGB", (W, total_h), (210, 210, 210))
    y = 0
    for t in tiles:
        img.paste(t, (0, y))
        y += t.height + 4
    path = out / "journey" / "journey-board.jpg"
    img.save(path, "JPEG", quality=78, optimize=True)
    return path


def websockets_interceptable() -> bool:
    try:
        from playwright.sync_api import BrowserContext
    except Exception:
        return False
    return hasattr(BrowserContext, "route_web_socket")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="journey.json")
    ap.add_argument("--out", help="output folder (journey/ is created inside)")
    ap.add_argument("--url", help="base URL, overrides the spec url (relative goto URLs resolve against it)")
    ap.add_argument("--viewports", help="comma list, overrides the spec (default desktop,mobile)")
    ap.add_argument("--locale", default="en-US")
    ap.add_argument("--timezone", default="UTC")
    ap.add_argument("--lint", action="store_true", help="check the spec and exit")
    args = ap.parse_args()
    spec = load_spec(Path(args.spec))
    data = dict(C.TEST_DATA_DEFAULTS)
    data.update({k: str(v) for k, v in (spec.get("test_data") or {}).items()})
    errs = lint(spec, data)
    if errs:
        for e in errs:
            print(f"spec error: {e}", file=sys.stderr)
        return 2
    if args.lint:
        print(f"spec ok: {len(spec['steps'])} steps")
        return 0
    if not args.out:
        C.die("--out is required unless --lint")
    base = args.url or spec.get("url")
    if not base:
        C.die("no base URL: set url in the spec or pass --url")
    vps = C.parse_viewports(args.viewports or ",".join(spec.get("viewports", ["desktop", "mobile"])))
    out = Path(args.out)
    (out / "journey").mkdir(parents=True, exist_ok=True)
    sync_playwright = C.need_playwright()
    if not websockets_interceptable():
        print("journey.py: this Playwright cannot intercept WebSockets (route_web_socket, added in 1.48), so a form "
              "sent over a WebSocket would really be sent. Nothing was run. Upgrade: "
              "pip install -U 'playwright>=1.48' && playwright install chromium", file=sys.stderr)
        return 2
    log: Dict[str, Any] = {"tool": "journey.py", "spec": Path(args.spec).name, "url": base, "goal": spec.get("goal"),
                           "started_at": C.now_iso(), "test_data": data, "viewports": []}
    with sync_playwright() as p:
        browser = C.launch(p)
        for vp in vps:
            try:
                res = run_viewport(p, browser, spec, data, base, out, vp, args)
            except Exception as e:
                res = {"viewport": vp, "status": "fail", "steps": [], "error": str(e).splitlines()[0][:300],
                       "safety": {"writes_sent_during_final_steps": []}, "network": []}
            res["context"] = C.context_record(browser, vp, args.locale, args.timezone)
            log["viewports"].append(res)
        browser.close()
    violations = [v for r in log["viewports"] for v in r["safety"].get("writes_sent_during_final_steps", [])]
    finals = [s for r in log["viewports"] for s in r["steps"] if s.get("final") and s.get("status") == "ok"]
    log["proof"] = {
        "final_steps_run": len(finals),
        "final_steps_with_blocked_send": sum(1 for s in finals if s.get("blocked")),
        "requests_aborted": sum(r["safety"].get("aborted", 0) for r in log["viewports"]),
        "writes_that_reached_the_network_during_final_steps": len(violations),
        "statement": ("no write request left the browser during a final step" if not violations
                      else "SAFETY VIOLATION: a write left the browser during a final step, see viewports[].safety"),
    }
    log["finished_at"] = C.now_iso()
    C.write_json(out / "journey" / "journey-log.json", log)
    try:
        b = board(log, out)
        if b:
            log["board"] = b.name
            C.write_json(out / "journey" / "journey-log.json", log)
    except Exception as e:
        print(f"warning: board not written ({e})", file=sys.stderr)
    for r in log["viewports"]:
        ok = sum(1 for s in r["steps"] if s.get("status") == "ok")
        print(f"{r['viewport']}: {r['status']}, {ok}/{len(r['steps'])} steps ok, {r['safety'].get('aborted', 0)} requests aborted"
              + (f", error: {r['error']}" if r.get("error") else ""))
        for s in r["steps"]:
            if s.get("final"):
                print(f"  step {s['n']:02d} {s['name']}: {s.get('final_note', s.get('status'))}")
            if str(s.get("status", "")).startswith("failed"):
                print(f"  step {s['n']:02d} {s['name']}: {s['status']}: {s.get('error')}")
    print(log["proof"]["statement"])
    print(f"wrote {out / 'journey' / 'journey-log.json'}")
    if violations:
        return 3
    return 0 if all(r["status"] == "pass" for r in log["viewports"]) else 1


if __name__ == "__main__":
    sys.exit(main())
