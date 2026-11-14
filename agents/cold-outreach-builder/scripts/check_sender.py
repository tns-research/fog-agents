#!/usr/bin/env python3
"""
check_sender.py

Deliverability preflight of the sending domain, by DNS queries only:
SPF, DKIM (for the selectors you give), DMARC and MX. Standard library only,
Python 3.9+.

    python3 check_sender.py --domain outreach.example.com --dkim-selector s1 \
        [--dkim-selector s2] [--inbox-age-days 45 --list-size 120] \
        [--resolver auto|dig|doh] [--records records.json] [--json] [--out sender-check.json]

Resolvers, first that works:
  dig    the dig command, when installed
  doh    DNS over HTTPS, JSON API of a public resolver (Cloudflare, then
         Google), no key, no account
  --records FILE  answers given as JSON ({"TXT": {"name": ["..."]},
         "MX": {"name": ["10 mx.example.com."]}}): offline tests, or the
         manual tier when the founder pastes what their DNS panel shows
When nothing resolves, the script prints the dig commands to run by hand
and exits 2.

No SMTP probe, ever: this script opens no connection to port 25 and sends
no RCPT. Probing mail servers from the machine that runs the agent gets its
IP listed on blocklists, after which every check reads as a failure.
Address verification is a third-party service or nothing (capability
email_verify in shared/tools.md when it exists).

Checks:
  spf    exactly one v=spf1 TXT on the domain; ends with -all or ~all (?all
         and +all fail); at most 10 DNS-querying terms (include, a, mx, ptr,
         exists, redirect) counted at the top level
  dkim   <selector>._domainkey.<domain> holds a v=DKIM1 or p= record with a
         non-empty key; without a selector: "not checked" (read the s= tag
         of the DKIM-Signature header of a message you sent)
  dmarc  v=DMARC1 at _dmarc.<domain>, or at the parent domain for a
         subdomain (then sp= applies); p=none passes with a warning,
         quarantine or reject pass; rua= absent is a warning
  mx     the domain has MX records (replies and bounces need them); a null
         MX (".") fails
  plan   with --inbox-age-days and --list-size: daily cap from the stack
         default table of assets/deliverability-checklist.md section D (the
         low end of each range) and the days needed to send step 1 to the
         whole list

The JSON written with --out is what the sidecar's "deliverability" block
copies: what was seen, by which resolver, when.

Exit codes: 0 no blocker (warnings allowed), 1 at least one check fails,
2 DNS could not be read or usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DOH = ["https://cloudflare-dns.com/dns-query", "https://dns.google/resolve"]
TYPES = {"TXT": 16, "MX": 15}
# Stack defaults, assets/deliverability-checklist.md section D (not provider rules).
CAPS = [(14, 0), (30, 5), (60, 20), (10 ** 6, 30)]


class DnsError(Exception):
    pass


class Resolver:
    def __init__(self, mode: str, records: Optional[Dict[str, Any]], timeout: int = 8) -> None:
        self.mode = mode
        self.records = records
        self.timeout = timeout
        self.used = "records" if records is not None else None

    def query(self, name: str, rtype: str) -> List[str]:
        name = name.rstrip(".").lower()
        if self.records is not None:
            return list((self.records.get(rtype) or {}).get(name, []))
        modes = ["dig", "doh"] if self.mode == "auto" else [self.mode]
        last = None
        for m in modes:
            try:
                out = self._dig(name, rtype) if m == "dig" else self._doh(name, rtype)
                self.used = self.used or m
                return out
            except DnsError as e:
                last = e
        raise DnsError(str(last) if last else "no resolver")

    def _dig(self, name: str, rtype: str) -> List[str]:
        exe = shutil.which("dig")
        if not exe:
            raise DnsError("dig not installed")
        try:
            p = subprocess.run([exe, "+short", "+time=5", "+tries=2", rtype, name],
                               capture_output=True, text=True, timeout=self.timeout * 2)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DnsError(f"dig failed: {e}")
        if p.returncode != 0:
            raise DnsError(f"dig exit {p.returncode}: {p.stderr.strip()}")
        lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip() and not ln.startswith(";")]
        if rtype == "TXT":
            return [join_txt(ln) for ln in lines]
        return lines

    def _doh(self, name: str, rtype: str) -> List[str]:
        last = None
        for base in DOH:
            url = f"{base}?{urllib.parse.urlencode({'name': name, 'type': rtype})}"
            req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
            except (OSError, ValueError) as e:
                last = e
                continue
            if data.get("Status") not in (0, 3):
                last = DnsError(f"DoH status {data.get('Status')}")
                continue
            return [join_txt(a["data"]) if rtype == "TXT" else a["data"]
                    for a in data.get("Answer", []) or [] if a.get("type") == TYPES[rtype]]
        raise DnsError(f"DNS over HTTPS failed: {last}")


def join_txt(s: str) -> str:
    """'"v=spf1 include:a" " -all"' -> 'v=spf1 include:a -all'."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', s)
    return "".join(parts) if parts else s.strip()


def tags(record: str) -> Dict[str, str]:
    out = {}
    for part in record.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


def check_spf(res: Resolver, domain: str) -> Dict[str, Any]:
    txt = [t for t in res.query(domain, "TXT") if t.lower().startswith("v=spf1")]
    r: Dict[str, Any] = {"check": "spf", "name": domain, "seen": txt, "status": "pass", "notes": []}
    if not txt:
        r.update(status="fail", notes=["no v=spf1 record: receivers cannot tell which servers may send for this domain"])
        return r
    if len(txt) > 1:
        r["status"] = "fail"
        r["notes"].append(f"{len(txt)} SPF records: there must be exactly one (permerror otherwise)")
    rec = txt[0]
    terms = rec.split()[1:]
    lookups = sum(1 for t in terms if re.match(r"^[+~?-]?(include:|a\b|a:|a/|mx\b|mx:|mx/|ptr|exists:|redirect=)", t, re.I))
    r["lookups_top_level"] = lookups
    if lookups > 10:
        r["status"] = "fail"
        r["notes"].append(f"{lookups} DNS-querying terms at the top level, limit 10 (RFC 7208 section 4.6.4)")
    allm = [t for t in terms if re.match(r"^[+~?-]?all$", t, re.I)]
    if not allm and not any(t.lower().startswith("redirect=") for t in terms):
        r["status"] = "fail" if r["status"] == "fail" else "warn"
        r["notes"].append("no 'all' term at the end: end with ~all or -all")
    elif allm and allm[-1].lstrip("+").lower() in ("all", "?all"):
        r["status"] = "fail"
        r["notes"].append(f"'{allm[-1]}' lets anyone send as this domain: use ~all or -all")
    return r


def check_dkim(res: Resolver, domain: str, selectors: List[str]) -> List[Dict[str, Any]]:
    if not selectors:
        return [{"check": "dkim", "name": f"<selector>._domainkey.{domain}", "seen": [], "status": "not_checked",
                 "notes": ["give --dkim-selector: the s= tag of the DKIM-Signature header of a message sent from this domain"]}]
    out = []
    for sel in selectors:
        name = f"{sel}._domainkey.{domain}"
        txt = res.query(name, "TXT")
        rec = next((t for t in txt if "p=" in t.replace(" ", "") or t.lower().startswith("v=dkim1")), "")
        r: Dict[str, Any] = {"check": "dkim", "name": name, "selector": sel, "seen": txt, "status": "pass", "notes": []}
        if not rec:
            r.update(status="fail", notes=["no DKIM key at this selector: check the selector or publish the key"])
        elif not tags(rec).get("p"):
            r.update(status="fail", notes=["empty p= tag: the key is revoked"])
        out.append(r)
    return out


def parent_domain(domain: str) -> Optional[str]:
    parts = domain.split(".")
    return ".".join(parts[1:]) if len(parts) > 2 else None


def check_dmarc(res: Resolver, domain: str) -> Dict[str, Any]:
    name = f"_dmarc.{domain}"
    txt = [t for t in res.query(name, "TXT") if t.lower().startswith("v=dmarc1")]
    inherited = False
    if not txt and parent_domain(domain):
        pname = f"_dmarc.{parent_domain(domain)}"
        txt = [t for t in res.query(pname, "TXT") if t.lower().startswith("v=dmarc1")]
        if txt:
            name, inherited = pname, True
    r: Dict[str, Any] = {"check": "dmarc", "name": name, "seen": txt, "status": "pass", "notes": [], "inherited": inherited}
    if not txt:
        r.update(status="fail", notes=["no v=DMARC1 record at the domain or its parent: Gmail requires one for bulk senders (Google email sender guidelines)"])
        return r
    t = tags(txt[0])
    policy = (t.get("sp") if inherited and t.get("sp") else t.get("p", "")).lower()
    r["policy"] = policy
    if policy not in ("none", "quarantine", "reject"):
        r.update(status="fail")
        r["notes"].append(f"invalid or missing policy '{policy}'")
    elif policy == "none":
        r["status"] = "warn"
        r["notes"].append("p=none monitors only: move to quarantine once SPF and DKIM align")
    if not t.get("rua"):
        r["status"] = "warn" if r["status"] == "pass" else r["status"]
        r["notes"].append("no rua= address: you will not see aggregate reports")
    return r


def check_mx(res: Resolver, domain: str) -> Dict[str, Any]:
    mx = res.query(domain, "MX")
    r: Dict[str, Any] = {"check": "mx", "name": domain, "seen": mx, "status": "pass", "notes": []}
    if not mx:
        r.update(status="fail", notes=["no MX: replies and bounces to this domain have nowhere to go"])
    elif all(re.match(r"^\d+\s+\.$", m.strip()) for m in mx):
        r.update(status="fail", notes=["null MX: the domain declares it receives no mail"])
    return r


def plan(inbox_age: Optional[int], list_size: Optional[int]) -> Optional[Dict[str, Any]]:
    if inbox_age is None:
        return None
    cap = next(c for limit, c in CAPS if inbox_age < limit)
    out: Dict[str, Any] = {"inbox_age_days": inbox_age, "daily_cap_step_1": cap,
                           "source": "stack default, assets/deliverability-checklist.md section D"}
    if cap == 0:
        out["note"] = "inbox under 14 days: warm-up only, no cold send"
    if list_size is not None and cap:
        out["list_size"] = list_size
        out["days_to_send_step_1"] = -(-list_size // cap)
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", required=True, help="Sending domain (the part after @ in the From address)")
    ap.add_argument("--dkim-selector", action="append", default=[], help="DKIM selector, repeatable")
    ap.add_argument("--resolver", default="auto", choices=["auto", "dig", "doh"])
    ap.add_argument("--records", help="JSON file of DNS answers (offline tests or the manual tier)")
    ap.add_argument("--inbox-age-days", type=int)
    ap.add_argument("--list-size", type=int)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="Write the JSON result to this path")
    a = ap.parse_args(argv)
    domain = a.domain.strip().lower().rstrip(".")
    if "@" in domain:
        domain = domain.split("@", 1)[1]

    records = None
    if a.records:
        try:
            with open(a.records, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {a.records}: {e}", file=sys.stderr)
            return 2
    res = Resolver(a.resolver, records)
    try:
        checks = [check_spf(res, domain)] + check_dkim(res, domain, a.dkim_selector) + [check_dmarc(res, domain), check_mx(res, domain)]
    except DnsError as e:
        print(f"error: DNS could not be read ({e}). Run these and paste the answers into a --records file:", file=sys.stderr)
        sel = a.dkim_selector[0] if a.dkim_selector else "<selector>"
        for cmd in (f"dig +short TXT {domain}", f"dig +short TXT {sel}._domainkey.{domain}",
                    f"dig +short TXT _dmarc.{domain}", f"dig +short MX {domain}"):
            print(f"  {cmd}", file=sys.stderr)
        return 2

    status = "fail" if any(c["status"] == "fail" for c in checks) else \
        "warn" if any(c["status"] in ("warn", "not_checked") for c in checks) else "pass"
    result = {"domain": domain, "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "resolver": res.used or a.resolver, "smtp_probe": False, "status": status, "checks": checks,
              "sending_plan": plan(a.inbox_age_days, a.list_size)}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{domain} (resolver: {result['resolver']}, no SMTP probe)")
        for c in checks:
            print(f"  {c['check']:<6} {c['status'].upper():<11} {c['name']}")
            for s in c["seen"]:
                print(f"         seen: {s}")
            for n in c["notes"]:
                print(f"         note: {n}")
        p = result["sending_plan"]
        if p:
            line = f"  plan   cap {p['daily_cap_step_1']}/day for step 1"
            if "days_to_send_step_1" in p:
                line += f", {p['days_to_send_step_1']} day(s) for {p['list_size']} prospects"
            print(line + f" ({p['source']})" + (f"; {p['note']}" if p.get("note") else ""))
        print(f"\nSender check: {status.upper()}")
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
