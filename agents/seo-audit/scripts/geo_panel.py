#!/usr/bin/env python3
"""
geo_panel.py

Measures how answer engines talk about the brand on a panel of real questions,
with several draws per question because generated answers vary from one draw
to the next. The model writes the panel (geo/panel.json); this script runs or
collects the answers (capability ai_answers), then computes mention rate,
citation rate, share of voice and the spread between draws. It also reads
robots.txt for the AI crawlers. Standard library only.

Commands:
  check     --panel P
  links     --panel P --out links.md
            One prefilled link per question and surface (ChatGPT, Perplexity,
            Claude, Google) for the manual tier.
  template  --panel P --surface S [--draws N] --out capture.md
            Blocks the founder fills by pasting each answer and its sources.
  import    --capture capture.md --out answers.jsonl [--date D]
  run       --panel P --surface S --provider command|perplexity --out answers.jsonl
            [--cmd "<cli reading the question on stdin>"] [--draws N] [--confirm-spend]
            Appends one line per question and draw, skips what answers.jsonl
            already holds (resumable). Every provider may cost money or quota:
            without --confirm-spend (or FOG_ALLOW_SPEND=1 in the environment
            for scripted runs) the script prints the planned number of
            calls and exits 1 (spend gate).
            command: any CLI the founder already uses (a model CLI with web
            search, an internal tool). It gets the question on stdin and the
            environment variables GEO_PROMPT_ID, GEO_SURFACE, GEO_DRAW; it
            prints either plain text (URLs in it count as citations) or JSON
            {"answer": "...", "citations": ["https://..."]}. --cmd is split
            with shlex and run without a shell: put pipes or redirections in
            a script and pass that script.
            perplexity: the Perplexity API (PERPLEXITY_API_KEY, model sonar by
            default, --model to change), citations from the response.
  score     --panel P --answers A [A ...] --out-dir D [--previous geo-score.json]
            Writes geo-score.json and geo-score.md.
  robots    (--robots-file F | --site URL [--fetch-base URL]) --out-dir D [--crawl crawl.jsonl] [--paths /,/blog/]
            AI crawler access table from assets/ai-crawlers.json, Content-Signal
            lines, and (with --crawl) the pages that show almost no text
            without JavaScript. Writes ai-access.json and ai-access.md.

Metrics (per surface, per topic, per question):
  mention rate     draws where the brand (name, alias or domain) appears / draws
  citation rate    draws citing a URL of the brand's domains / draws, only on
                   surfaces that returned citations (else n/a)
  share of voice   brand mention draws / mention draws of brand + competitors
  citation share   citations to the brand / citations to brand + competitors
  spread           max minus min mention rate across draw indexes (draw 1,
                   draw 2, ...): how much one capture would have misled
A surface of the panel with no answer is Unverified, never 0 %.

Exit codes: 0 done, 1 spend gate closed, `check` found errors, or every call
of `run` failed, 2 usage error, invalid panel or unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, Origin, Robots, ai_crawler_table, fetch, load_assets_json, load_json,  # noqa: E402
                     normalize_url, parse_day, read_jsonl, write_json, write_text)

URL_RE = re.compile(r"https?://[^\s<>\"'\])}]+")
LINKS = {
    "chatgpt": "https://chatgpt.com/?q={q}",
    "perplexity": "https://www.perplexity.ai/search/new?q={q}",
    "claude": "https://claude.ai/new?q={q}",
    "google": "https://www.google.com/search?q={q}",
}


# --------------------------------------------------------------------------
# panel

def load_panel(path: str) -> Dict[str, Any]:
    p = load_json(path)
    errors = validate_panel(p)
    if errors:
        raise InputError("invalid panel: " + "; ".join(errors))
    return p


def validate_panel(p: Any) -> List[str]:
    e = []
    if not isinstance(p, dict):
        return ["panel must be a JSON object"]
    b = p.get("brand") or {}
    if not b.get("name"):
        e.append("brand.name is required")
    if not b.get("domains"):
        e.append("brand.domains needs at least one domain")
    topics = p.get("topics") or []
    if not topics:
        e.append("topics needs at least one topic")
    ids = set()
    for t in topics:
        if not t.get("id") or not t.get("questions"):
            e.append(f"topic {t.get('id')!r} needs an id and questions")
            continue
        for q in t["questions"]:
            pid = f"{t['id']}.{q.get('id')}"
            if not q.get("id") or not q.get("text"):
                e.append(f"question in {t['id']} needs id and text")
            if pid in ids:
                e.append(f"duplicate question id {pid}")
            ids.add(pid)
            if not q.get("source"):
                e.append(f"{pid} needs a source (where the question comes from: icp, People also ask, autocomplete, market-signal quote id, founder)")
    d = p.get("draws", 3)
    if not isinstance(d, int) or d < 1:
        e.append("draws must be an integer >= 1")
    for c in p.get("competitors", []):
        if not c.get("name"):
            e.append("every competitor needs a name")
    return e


def prompts(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for t in p["topics"]:
        for q in t["questions"]:
            out.append({"id": f"{t['id']}.{q['id']}", "topic": t["id"], "text": q["text"]})
    return out


# --------------------------------------------------------------------------
# collect

def existing_keys(path: str) -> set:
    if not os.path.exists(path):
        return set()
    return {(r.get("prompt_id"), r.get("surface"), r.get("draw")) for _, r in read_jsonl(path)}


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def parse_output(text: str) -> Tuple[str, List[str]]:
    t = text.strip()
    if t.startswith("{"):
        try:
            d = json.loads(t)
            ans = str(d.get("answer") or d.get("text") or "")
            cites = [str(c.get("url") if isinstance(c, dict) else c) for c in d.get("citations") or []]
            return ans, [c for c in cites if c]
        except json.JSONDecodeError:
            pass
    return t, []


def call_command(argv: List[str], prompt: Dict[str, Any], surface: str, draw: int, timeout: int) -> Tuple[str, List[str]]:
    """Run the operator's CLI without a shell: argv comes from shlex.split(--cmd)."""
    env = dict(os.environ, GEO_PROMPT_ID=prompt["id"], GEO_SURFACE=surface, GEO_DRAW=str(draw))
    r = subprocess.run(argv, input=prompt["text"], capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"command exited {r.returncode}: {r.stderr.strip()[:200]}")
    return parse_output(r.stdout)


def call_perplexity(model: str, prompt: Dict[str, Any], timeout: int) -> Tuple[str, List[str]]:
    key = os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        raise RuntimeError("PERPLEXITY_API_KEY is not set")
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt["text"]}]}).encode()
    req = urllib.request.Request("https://api.perplexity.ai/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # never echo the key: the message holds no header
        raise RuntimeError(f"Perplexity call failed: {type(e).__name__}")
    ans = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    cites = d.get("citations") or [r.get("url") for r in d.get("search_results") or [] if r.get("url")]
    return ans, [c for c in cites if c]


def cmd_run(a) -> int:
    panel = load_panel(a.panel)
    draws = a.draws or panel.get("draws", 3)
    have = existing_keys(a.out)
    todo = [(p, d) for p in prompts(panel) for d in range(1, draws + 1) if (p["id"], a.surface, d) not in have]
    if not todo:
        print(f"run: nothing to do, {a.out} already holds every draw for {a.surface}")
        return 0
    if not (a.confirm_spend or os.environ.get("FOG_ALLOW_SPEND", "").strip() == "1"):
        print(f"spend gate: {len(todo)} call(s) to provider {a.provider} for surface {a.surface}. "
              "Re-run with --confirm-spend once the founder agreed (quota or money).")
        return 1
    argv: List[str] = []
    if a.provider == "command":
        if not a.shell_cmd:
            raise InputError("--provider command needs --cmd")
        try:
            argv = shlex.split(a.shell_cmd)
        except ValueError as e:
            raise InputError(f"--cmd cannot be parsed: {e}")
        if not argv:
            raise InputError("--provider command needs --cmd")
    ok = failed = 0
    day = parse_day(a.date).isoformat()
    for p, d in todo:
        try:
            if a.provider == "command":
                ans, cites = call_command(argv, p, a.surface, d, a.timeout)
            else:
                ans, cites = call_perplexity(a.model, p, a.timeout)
        except Exception as e:
            failed += 1
            print(f"  {p['id']} draw {d}: {e}", file=sys.stderr)
            continue
        append_jsonl(a.out, {"prompt_id": p["id"], "surface": a.surface, "draw": d, "provider": a.provider,
                             "captured_on": day, "answer": ans, "citations": cites})
        ok += 1
    print(f"run: {ok} answer(s) written to {a.out}, {failed} failed")
    return 1 if failed and not ok else 0


def cmd_links(a) -> int:
    panel = load_panel(a.panel)
    L = [f"# Prefilled links: {panel['brand']['name']} GEO panel", "",
         "Open each link signed out or in a private window, read the answer, and paste it with its sources into the capture file "
         "(`geo_panel.py template`). Run every draw in a new conversation.", ""]
    for p in prompts(panel):
        q = urllib.parse.quote(p["text"])
        L.append(f"## {p['id']}")
        L.append("")
        L.append(f"> {p['text']}")
        L.append("")
        for s, tpl in LINKS.items():
            L.append(f"- {s}: {tpl.format(q=q)}")
        L.append("")
    write_text(a.out, "\n".join(L))
    print(f"links: {len(prompts(panel))} question(s) -> {a.out}")
    return 0


def cmd_template(a) -> int:
    panel = load_panel(a.panel)
    draws = a.draws or panel.get("draws", 3)
    tpl = LINKS.get(a.surface)
    L = [f"# GEO capture: surface {a.surface}", "",
         "Paste each answer under Answer and the URLs it cites one per line under Citations. Use a new conversation for every draw. "
         "Leave a block empty when you skipped it: empty blocks are not counted.", ""]
    for p in prompts(panel):
        for d in range(1, draws + 1):
            L.append(f"## {p['id']} | {a.surface} | draw {d}")
            L.append(f"Question: {p['text']}")
            if tpl:
                L.append(f"Link: {tpl.format(q=urllib.parse.quote(p['text']))}")
            L += ["", "Answer:", "", "Citations:", ""]
    write_text(a.out, "\n".join(L))
    print(f"template: {len(prompts(panel)) * draws} block(s) -> {a.out}")
    return 0


def cmd_import(a) -> int:
    try:
        text = open(a.capture, encoding="utf-8").read()
    except OSError as e:
        raise InputError(str(e))
    have = existing_keys(a.out)
    day = parse_day(a.date).isoformat()
    n = 0
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"\s*(\S+)\s*\|\s*(\S+)\s*\|\s*draw\s*(\d+)", head)
        if not m:
            continue
        pid, surface, draw = m.group(1), m.group(2), int(m.group(3))
        ans_m = re.search(r"^Answer:\s*\n(.*?)(?=^Citations:)", body, re.S | re.M)
        cit_m = re.search(r"^Citations:\s*\n(.*)", body, re.S | re.M)
        answer = (ans_m.group(1) if ans_m else "").strip()
        if not answer or (pid, surface, draw) in have:
            continue
        cites = URL_RE.findall(cit_m.group(1)) if cit_m else []
        append_jsonl(a.out, {"prompt_id": pid, "surface": surface, "draw": draw, "provider": "manual",
                             "captured_on": day, "answer": answer, "citations": cites})
        n += 1
    print(f"import: {n} answer(s) -> {a.out}")
    return 0


# --------------------------------------------------------------------------
# score

def mention_re(names: List[str]) -> Optional["re.Pattern[str]"]:
    names = [n for n in names if n]
    if not names:
        return None
    return re.compile(r"(?<![\w.])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![\w])", re.I)


def host_matches(url: str, domains: List[str]) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return any(host == d or host.endswith("." + d) for d in domains)


class Entity:
    def __init__(self, spec: Dict[str, Any]) -> None:
        self.name = spec["name"]
        self.domains = [d.lower().lstrip(".").replace("www.", "", 1) for d in spec.get("domains", [])]
        self.rx = mention_re([spec["name"]] + spec.get("aliases", []) + self.domains)

    def mentioned(self, text: str) -> bool:
        return bool(self.rx and self.rx.search(text or ""))

    def cited(self, urls: List[str]) -> int:
        return sum(1 for u in urls if host_matches(u, self.domains))


def rate(k: int, n: int) -> Optional[float]:
    return round(k / n, 3) if n else None


def score(panel: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    brand = Entity(panel["brand"])
    comps = [Entity(c) for c in panel.get("competitors", [])]
    plist = {p["id"]: p for p in prompts(panel)}
    draws_expected = panel.get("draws", 3)
    surfaces = list(dict.fromkeys((panel.get("surfaces") or []) + sorted({r["surface"] for r in rows})))
    rows = [r for r in rows if r.get("prompt_id") in plist and (r.get("answer") or "").strip()]
    enriched = []
    domain_counts: Dict[str, int] = {}
    for r in rows:
        urls = list(dict.fromkeys((r.get("citations") or []) + URL_RE.findall(r.get("answer") or "")))
        for u in urls:
            h = (urllib.parse.urlsplit(u).hostname or "").lower()
            h = h[4:] if h.startswith("www.") else h
            if h:
                domain_counts[h] = domain_counts.get(h, 0) + 1
        enriched.append({
            "prompt_id": r["prompt_id"], "topic": plist[r["prompt_id"]]["topic"], "surface": r["surface"], "draw": r.get("draw", 1),
            "has_citations": bool(urls),
            "brand_mentioned": brand.mentioned(r["answer"]), "brand_cited": brand.cited(urls),
            "comp_mentioned": {c.name: c.mentioned(r["answer"]) for c in comps},
            "comp_cited": {c.name: c.cited(urls) for c in comps},
        })

    def agg(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(items)
        with_c = [i for i in items if i["has_citations"]]
        bm = sum(i["brand_mentioned"] for i in items)
        bc_draws = sum(1 for i in with_c if i["brand_cited"])
        cm = {c.name: sum(i["comp_mentioned"][c.name] for i in items) for c in comps}
        b_cites = sum(i["brand_cited"] for i in items)
        c_cites = {c.name: sum(i["comp_cited"][c.name] for i in items) for c in comps}
        sov_den = bm + sum(cm.values())
        cs_den = b_cites + sum(c_cites.values())
        by_draw: Dict[int, List[bool]] = {}
        for i in items:
            by_draw.setdefault(i["draw"], []).append(i["brand_mentioned"])
        per_draw = {d: rate(sum(v), len(v)) for d, v in sorted(by_draw.items())}
        vals = [v for v in per_draw.values() if v is not None]
        return {
            "answers": n,
            "mention_rate": rate(bm, n),
            "citation_rate": rate(bc_draws, len(with_c)) if with_c else None,
            "answers_with_citations": len(with_c),
            "share_of_voice": rate(bm, sov_den) if sov_den else None,
            "citation_share": rate(b_cites, cs_den) if cs_den else None,
            "competitors": {c.name: {"mention_rate": rate(cm[c.name], n), "citations": c_cites[c.name]} for c in comps},
            "mention_rate_by_draw": per_draw,
            "spread": round(max(vals) - min(vals), 3) if len(vals) > 1 else None,
        }

    res: Dict[str, Any] = {"surfaces": {}, "topics": {}, "prompts": [], "unverified_surfaces": [], "incomplete": []}
    for s in surfaces:
        items = [i for i in enriched if i["surface"] == s]
        if not items:
            res["unverified_surfaces"].append(s)
            continue
        res["surfaces"][s] = agg(items)
        for t in sorted({i["topic"] for i in items}):
            res["topics"].setdefault(t, {})[s] = agg([i for i in items if i["topic"] == t])
    for pid in plist:
        for s in res["surfaces"]:
            items = [i for i in enriched if i["prompt_id"] == pid and i["surface"] == s]
            if len(items) < draws_expected:
                res["incomplete"].append({"prompt_id": pid, "surface": s, "draws": len(items), "expected": draws_expected})
            if not items:
                continue
            res["prompts"].append({"prompt_id": pid, "surface": s, "draws": len(items),
                                   "brand_mentioned": f"{sum(i['brand_mentioned'] for i in items)}/{len(items)}",
                                   "brand_cited": f"{sum(1 for i in items if i['brand_cited'])}/{len(items)}",
                                   "stable": len({i['brand_mentioned'] for i in items}) == 1})
    if enriched:
        res["overall"] = agg(enriched)
    res["top_cited_domains"] = [{"domain": d, "citations": c} for d, c in sorted(domain_counts.items(), key=lambda x: (-x[1], x[0]))[:15]]
    return res


def pp(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{round(v * 100)} %"


def render_score(panel: Dict[str, Any], res: Dict[str, Any], delta: Optional[Dict[str, Any]]) -> str:
    comps = [c["name"] for c in panel.get("competitors", [])]
    L = [f"# GEO panel: {panel['brand']['name']}", "",
         f"{len(prompts(panel))} questions in {len(panel['topics'])} topics, {panel.get('draws', 3)} draws per question and surface. "
         "Rates are over draws; a surface without citations has no citation rate.", ""]
    L += ["| Surface | Answers | Mention rate | Citation rate | Share of voice | Citation share | Spread between draws |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for s, a in res["surfaces"].items():
        L.append(f"| {s} | {a['answers']} | {pp(a['mention_rate'])} | {pp(a['citation_rate'])} | {pp(a['share_of_voice'])} | "
                 f"{pp(a['citation_share'])} | {pp(a['spread'])} |")
    for s in res["unverified_surfaces"]:
        L.append(f"| {s} | 0 | Unverified | Unverified | Unverified | Unverified | n/a |")
    L.append("")
    if comps:
        L += ["## Competitors (mention rate per surface)", "", "| Competitor | " + " | ".join(res["surfaces"]) + " |",
              "|---|" + "---:|" * len(res["surfaces"])]
        for c in comps:
            L.append(f"| {c} | " + " | ".join(pp(a["competitors"][c]["mention_rate"]) for a in res["surfaces"].values()) + " |")
        L.append("")
    L += ["## Per topic", "", "| Topic | Surface | Mention rate | Citation rate | Share of voice |", "|---|---|---:|---:|---:|"]
    for t, per in res["topics"].items():
        for s, a in per.items():
            L.append(f"| {t} | {s} | {pp(a['mention_rate'])} | {pp(a['citation_rate'])} | {pp(a['share_of_voice'])} |")
    L += ["", "## Per question", "", "| Question | Surface | Mentioned | Cited | Same result every draw |", "|---|---|---|---|---|"]
    for p in res["prompts"]:
        L.append(f"| `{p['prompt_id']}` | {p['surface']} | {p['brand_mentioned']} | {p['brand_cited']} | {'yes' if p['stable'] else 'no'} |")
    L += ["", "## Most cited domains", ""]
    for d in res["top_cited_domains"]:
        L.append(f"- {d['domain']}: {d['citations']}")
    if res["incomplete"]:
        L += ["", "## Incomplete", ""]
        for i in res["incomplete"]:
            L.append(f"- `{i['prompt_id']}` on {i['surface']}: {i['draws']} of {i['expected']} draws")
    if delta:
        L += ["", "## Since the previous panel", "", "| Surface | Mention rate | Citation rate | Share of voice |", "|---|---|---|---|"]
        for s, d in delta.items():
            L.append(f"| {s} | {d['mention_rate']} | {d['citation_rate']} | {d['share_of_voice']} |")
    L.append("")
    return "\n".join(L)


def diff_scores(prev: Dict[str, Any], cur: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for s, a in cur["surfaces"].items():
        b = prev.get("surfaces", {}).get(s)
        if not b:
            out[s] = {k: f"{pp(a[k])} (new surface)" for k in ("mention_rate", "citation_rate", "share_of_voice")}
            continue
        row = {}
        for k in ("mention_rate", "citation_rate", "share_of_voice"):
            if a[k] is None or b[k] is None:
                row[k] = f"{pp(b[k])} -> {pp(a[k])}"
            else:
                row[k] = f"{pp(b[k])} -> {pp(a[k])} ({round((a[k] - b[k]) * 100):+d} pts)"
        out[s] = row
    return out


def cmd_score(a) -> int:
    panel = load_panel(a.panel)
    rows: List[Dict[str, Any]] = []
    for p in a.answers:
        rows.extend(r for _, r in read_jsonl(p))
    res = score(panel, rows)
    res.update(schema_version="1.0", generated_by="geo_panel.py", generated_on=parse_day(a.date).isoformat(),
               brand=panel["brand"]["name"], answers_files=[os.path.basename(x) for x in a.answers])
    delta = None
    if a.previous:
        delta = diff_scores(load_json(a.previous), res)
        res["since_previous"] = delta
    write_json(os.path.join(a.out_dir, "geo-score.json"), res)
    write_text(os.path.join(a.out_dir, "geo-score.md"), render_score(panel, res, delta))
    o = res.get("overall") or {}
    print(f"score: {o.get('answers', 0)} answers, mention rate {pp(o.get('mention_rate'))}, share of voice {pp(o.get('share_of_voice'))}, "
          f"unverified surfaces: {', '.join(res['unverified_surfaces']) or 'none'} -> {os.path.join(a.out_dir, 'geo-score.json')}")
    return 0


# --------------------------------------------------------------------------
# robots

def cmd_robots(a) -> int:
    crawlers = load_assets_json("ai-crawlers.json")
    if a.robots_file:
        try:
            text = open(a.robots_file, encoding="utf-8").read()
        except OSError as e:
            raise InputError(str(e))
        source = os.path.basename(a.robots_file)
    elif a.site:
        origin = Origin(a.fetch_base or a.site, a.site if a.fetch_base else None)
        r = fetch(origin.to_fetch(origin.home + "robots.txt"))
        ok = r["status"] == 200 and "html" not in (r["content_type"] or "").lower()
        text = r["text"] if ok else ""
        source = f"{origin.home}robots.txt ({r['status'] or r['error']})"
    else:
        raise InputError("give --robots-file or --site")
    robots = Robots(text)
    paths = [p.strip() for p in a.paths.split(",") if p.strip()]
    table = ai_crawler_table(robots, crawlers["crawlers"], paths)
    thin = []
    if a.crawl:
        for n, rec in read_jsonl(a.crawl):
            if "thin-raw-html" in rec.get("issues", []):
                thin.append({"url": rec["url"], "words": rec.get("word_count"), "line": n})
    blocked_search = [r["token"] for r in table if r["purpose"] in ("search", "user") and not r["allowed"].get("/", True)]
    blocked_training = [r["token"] for r in table if r["purpose"] in ("training", "control") and not r["allowed"].get("/", True)]
    res = {"schema_version": "1.0", "generated_by": "geo_panel.py robots", "source": source, "paths": paths,
           "crawlers": table, "content_signals": robots.content_signals, "sitemaps": robots.sitemaps,
           "blocked_search_or_user_agents": blocked_search, "blocked_training_agents": blocked_training,
           "thin_raw_html_pages": thin, "robots_found": bool(text.strip())}
    write_json(os.path.join(a.out_dir, "ai-access.json"), res)
    L = ["# AI crawler access", "", f"Source: {source}. Operators' documentation in `assets/ai-crawlers.json`.", ""]
    if not text.strip():
        L += ["No robots.txt: every crawler is allowed by default.", ""]
    L += ["| User agent | Operator | Purpose | Group applied | " + " | ".join(paths) + " |", "|---|---|---|---|" + "---|" * len(paths)]
    for r in table:
        L.append(f"| `{r['token']}` | {r['operator']} | {r['purpose']} | `{r['group']}` | "
                 + " | ".join("allowed" if r["allowed"][p] else "**blocked**" for p in paths) + " |")
    L.append("")
    if robots.content_signals:
        L += ["Content-Signal lines (a stated preference, not an access rule; see " + crawlers["content_signals_doc"] + "):", ""]
        L += [f"- `{c}`" for c in robots.content_signals]
        L.append("")
    if blocked_search:
        L.append(f"Search or user agents blocked on `/`: {', '.join(blocked_search)}. Their answer engine cannot fetch these pages to cite them.")
    if blocked_training:
        L.append(f"Training or control agents blocked on `/`: {', '.join(blocked_training)} (no effect on citation by search agents).")
    if thin:
        L += ["", f"{len(thin)} page(s) show fewer words than the crawl threshold without JavaScript; crawlers that do not run JavaScript see them almost empty:", ""]
        L += [f"- {t['url']} ({t['words']} words, crawl.jsonl:{t['line']})" for t in thin]
    L.append("")
    write_text(os.path.join(a.out_dir, "ai-access.md"), "\n".join(L))
    print(f"robots: {len(blocked_search)} search/user agent(s) blocked, {len(blocked_training)} training/control agent(s) blocked, "
          f"{len(thin)} thin raw-HTML page(s) -> {os.path.join(a.out_dir, 'ai-access.json')}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="GEO panel: answers per question and draw, mention and citation rates, AI crawler access.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("--panel", required=True)
    p = sub.add_parser("links")
    p.add_argument("--panel", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("template")
    p.add_argument("--panel", required=True)
    p.add_argument("--surface", required=True)
    p.add_argument("--draws", type=int)
    p.add_argument("--out", required=True)
    p = sub.add_parser("import")
    p.add_argument("--capture", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--date")
    p = sub.add_parser("run")
    p.add_argument("--panel", required=True)
    p.add_argument("--surface", required=True)
    p.add_argument("--provider", choices=["command", "perplexity"], required=True)
    p.add_argument("--cmd", dest="shell_cmd", help="CLI reading the question on stdin, split with shlex, run without a shell")
    p.add_argument("--model", default="sonar")
    p.add_argument("--draws", type=int)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--date")
    p.add_argument("--confirm-spend", action="store_true")
    p = sub.add_parser("score")
    p.add_argument("--panel", required=True)
    p.add_argument("--answers", nargs="+", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--previous")
    p.add_argument("--date")
    p = sub.add_parser("robots")
    p.add_argument("--robots-file")
    p.add_argument("--site")
    p.add_argument("--fetch-base")
    p.add_argument("--crawl")
    p.add_argument("--paths", default="/")
    p.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "check":
            errors = validate_panel(load_json(a.panel))
            for e in errors:
                print(f"error: {e}")
            if not errors:
                print(f"panel ok: {len(prompts(load_json(a.panel)))} question(s)")
            return 1 if errors else 0
        return {"links": cmd_links, "template": cmd_template, "import": cmd_import, "run": cmd_run,
                "score": cmd_score, "robots": cmd_robots}[a.cmd](a)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
