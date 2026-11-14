#!/usr/bin/env python3
"""selftest.py: offline regression test of content-publisher.

  python3 scripts/selftest.py [--keep DIR]

No network, no key, no real provider: the run sets CONTENT_PUBLISHER_OFFLINE=1
and removes every provider key from the environment of the commands it runs.
The approval key is a throwaway file in the temporary folder
(FOG_APPROVAL_KEY_FILE); approvals are typed at a pseudo-terminal (pty), as a
person would at their own terminal. POSIX only (the pty module).

1. Counting: X weighted length (URL 23, emoji and flags 2, CJK 2), graphemes.
2. Stress spec (examples/stress/posts.json): every failure it was built to
   trigger shows with the expected code on the expected post and network.
3. Reference spec (examples/swanbase-week-20261019/posts.json): passes, and
   the carousel importer rebuilds the carousel post from captions.md.
4. Queue lifecycle on a copy of the reference example: init, add (all
   to_review), idempotent re-add, slot windows, review packet.
5. Approval gate: approve without a terminal, a code passed as an argument,
   reserved names, a wrong code typed at the terminal, schedule of an
   unapproved item, a hand-edited "approved" status, an approval forged in
   queue.json with the right content hash and history event, an approval
   copied from another item, an edit after approval and a media swap after
   approval are all refused; no command but approve prints a review code;
   the approval sentinel and the review code each have one call site.
6. Adapters: real adapters refuse without --live, without a key, offline and
   over plain http; a redirect to another host drops the Authorization
   header; the command adapter runs a local fake; dry-run writes the outbox
   with the link in the LinkedIn first comment and the X reply, never in a body.
7. sync, mark, validate, schema; --help of every script.
8. Media paths: a spec or a hand-edited queue pointing outside the project
   folder is refused by add, schedule and validate.

Exit 0 when all hold, 1 otherwise. Work happens in a temporary folder (or
--keep DIR), the repo is never written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
import variants  # noqa: E402
from adapters import base as adapter_base  # noqa: E402
from adapters.zernio import ZernioAdapter  # noqa: E402

EXAMPLE = AGENT / "examples" / "swanbase-week-20261019"
STRESS = AGENT / "examples" / "stress" / "posts.json"
NOW = "2026-10-19T08:00"

# (where, code) the stress spec must produce.
EXPECTED_STRESS = [
    ("stress-x.x", "x-thread"),
    ("stress-x.x", "over-limit"),
    ("stress-links.linkedin", "link-in-body"),
    ("stress-links.instagram", "wrong-link-pointer"),
    ("stress-links.instagram", "missing-bio-pointer"),
    ("stress-links.instagram", "too-many-hashtags"),
    ("stress-media.media[5]", "missing-media-file"),
    ("stress-media.instagram", "media-required"),
    ("stress-media.instagram", "document-not-supported"),
    ("stress-media.x", "too-many-images"),
    ("stress-media.threads", "missing-variant"),
    ("stress-gate.linkedin.text", "writing-gate:not-x-its-y"),
    ("stress-gate.linkedin.text", "writing-gate:buzzword"),
    ("stress-gate.linkedin.text", "writing-gate:em-dash"),
]

PROVIDER_ENV = ("ZERNIO_API_KEY", "ZERNIO_BASE_URL", "CONTENT_PUBLISHER_COMMAND", "CONTENT_PUBLISHER_WEBHOOK_URL",
                "CONTENT_PUBLISHER_WEBHOOK_TOKEN")
PROMPT = "Type the review code"

FAILS: List[str] = []


def check(cond: bool, label: str) -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {label}")
    if not cond:
        FAILS.append(label)


def env(**extra: str) -> Dict[str, str]:
    e = {k: v for k, v in os.environ.items() if k not in PROVIDER_ENV}
    e["CONTENT_PUBLISHER_OFFLINE"] = "1"
    e.update(extra)
    return e


def run(script: str, *args: str, cwd: Path, extra_env: Dict[str, str] = None, stdin: str = "") -> Tuple[int, str]:
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=str(cwd), capture_output=True, text=True,
                       env=env(**(extra_env or {})), input=stdin)
    out = r.stdout + r.stderr
    if "Traceback" in out:
        print(out[-3000:])
        FAILS.append(f"{script} {' '.join(args[:2])}: crashed")
    return r.returncode, out


def q(cwd: Path, *args: str, **kw: Any) -> Tuple[int, str]:
    return run("pubqueue.py", *args, "--queue", "queue.json", cwd=cwd, **kw)


def run_tty(cwd: Path, answer: Callable[[str], str], *args: str, timeout: float = 120.0) -> Tuple[int, str]:
    """pubqueue.py under a pseudo-terminal, as a person runs it in their own
    terminal: at each review-code prompt, answer(output so far) is typed."""
    import pty
    import select
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, str(SCRIPTS / "pubqueue.py"), *args, "--queue", "queue.json"], cwd=str(cwd),
                            stdin=slave, stdout=slave, stderr=slave, env=env(), close_fds=True)
    os.close(slave)
    buf, answered, deadline = b"", 0, time.time() + timeout
    try:
        while time.time() < deadline:
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:  # EIO: the child closed the terminal
                    break
                if not chunk:
                    break
                buf += chunk
                text = buf.decode("utf-8", "replace")
                if text.count(PROMPT) > answered:
                    answered += 1
                    os.write(master, (answer(text) + "\n").encode("utf-8"))
            elif proc.poll() is not None:
                break
        else:
            proc.kill()
    finally:
        os.close(master)
    rc = proc.wait(timeout=10)
    out = buf.decode("utf-8", "replace")
    if "Traceback" in out:
        print(out[-3000:])
        FAILS.append(f"pubqueue.py {' '.join(args[:2])} (tty): crashed")
    return rc, out


def shown_code(text: str) -> str:
    """The person reads the code approve printed just above its prompt."""
    found = re.findall(r"Review code: ([0-9a-f]{6})", text)
    return found[-1] if found else ""


def load(cwd: Path) -> Dict[str, Any]:
    return json.loads((cwd / "queue.json").read_text(encoding="utf-8"))


def item(cwd: Path, item_id: str) -> Dict[str, Any]:
    return next(i for i in load(cwd)["items"] if i["id"] == item_id)


def code_of(cwd: Path, item_id: str) -> str:
    """The review code approve would print (same throwaway key as the commands)."""
    return common.review_code(item(cwd, item_id))


# ------------------------------------------------------------------ parts

def part_counting() -> None:
    print("1. counting")
    check(variants.x_length("hello") == 5, "x: plain ASCII counts 1 per character")
    check(variants.x_length("see https://example.com/" + "a" * 200) == 4 + 23, "x: any URL counts 23")
    check(variants.x_length("\U0001F680") == 2, "x: an emoji counts 2")
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467\u200d\U0001F466"
    check(variants.x_length(family) == 2, "x: a ZWJ family sequence counts 2")
    check(variants.x_length("\U0001F1EB\U0001F1F7") == 2, "x: a flag counts 2")
    check(variants.x_length("\u65e5\u672c") == 4, "x: CJK counts 2 per character")
    check(variants.x_length("caf\u00e9") == 4, "x: accented Latin counts 1")
    check(variants.graphemes("cafe\u0301") == 4, "bluesky: a combining accent is not a character")
    check(variants.graphemes(family) == 1, "bluesky: a ZWJ family is one grapheme")


def part_stress(tmp: Path) -> None:
    print("2. stress spec")
    code, out = run("variants.py", "lint", str(STRESS), "--json", cwd=tmp)
    check(code == 1, f"lint exits 1 on the stress spec (got {code})")
    try:
        rep = json.loads(out[out.index("{"):])
    except ValueError:
        check(False, "lint --json prints JSON")
        return
    got = {(f["where"], f["code"]) for f in rep["findings"] if f["level"] == "error"}
    for where, c in EXPECTED_STRESS:
        check((where, c) in got, f"{c} on {where}")


def part_reference(tmp: Path) -> None:
    print("3. reference spec and carousel import")
    code, out = run("variants.py", "lint", str(EXAMPLE / "posts.json"), "--json", cwd=tmp)
    rep = json.loads(out[out.index("{"):]) if "{" in out else {"findings": [{"level": "error"}]}
    check(code == 0 and not [f for f in rep["findings"] if f["level"] == "error"], "reference spec passes lint and writing gate")
    check(rep.get("gate", {}).get("ran") is True, "the shared writing gate ran")
    out_spec = tmp / "imported" / "posts.json"
    run_dir = EXAMPLE / "carousel-builder" / "pitch-deck-order-20261019"
    code, out = run("import_carousel.py", str(run_dir), "--ref", "pitch-deck-order", "--out", str(out_spec), cwd=tmp)
    check(code == 0 and out_spec.exists(), "import_carousel.py writes a spec")
    if not out_spec.exists():
        return
    spec = json.loads(out_spec.read_text(encoding="utf-8"))
    post = spec["posts"][0]
    check(post["link"] == "https://swanbase.co/en/blog/startup-pitch-deck-guide-2026/", "link taken from the first comment")
    check(post["variants"]["linkedin"]["first_comment"].endswith(post["link"]), "LinkedIn first comment imported")
    check([m["type"] for m in post["media"]] == ["document", "image", "image", "image"], "PDF and three slides imported")
    check(post["media"][1]["alt"].startswith("Cover."), "alt text read from the captions table")
    check("x" not in post["variants"], "no X text in captions.md: left for the model to write")
    code, out = run("variants.py", "lint", str(out_spec), "--json", cwd=tmp)
    rep = json.loads(out[out.index("{"):])
    errs = {(f["where"], f["code"]) for f in rep["findings"] if f["level"] == "error"}
    check(errs == {("pitch-deck-order.x", "missing-variant")}, f"imported draft only misses its X text (got {sorted(errs)})")


def part_lifecycle(tmp: Path) -> Path:
    print("4. queue lifecycle")
    proj = tmp / "project"
    shutil.copytree(EXAMPLE, proj)
    code, _ = run("pubqueue.py", "init", "--queue", "queue.json", "--config", str(AGENT / "config.example.json"),
                  "--project-name", "swanbase", cwd=proj)
    check(code == 0, "init from config.example.json")
    code, out = q(proj, "add", "posts.json", "--now", NOW)
    check(code == 0, "add the reference spec")
    data = load(proj)
    check(len(data["items"]) == 9, f"one item per post and network (got {len(data['items'])})")
    check(all(i["status"] == "to_review" for i in data["items"]), "every new item is to_review")
    check(all(i["approval"] is None for i in data["items"]), "no new item carries an approval")
    check(all(i.get("slot") for i in data["items"]), "every item has a slot")
    check(not common.window_conflicts(data["items"], data["settings"]["window_minutes"]), "no two posts of a network in one window")
    check(not common.schema_errors(data, common.QUEUE_SCHEMA), "queue.json matches assets/queue.schema.json")
    before = (proj / "queue.json").read_text(encoding="utf-8")
    code, out = q(proj, "add", "posts.json", "--now", NOW)
    check(code == 0 and "9 unchanged" in out, "re-adding the same spec changes nothing")
    # A second LinkedIn post aimed at the same slot is planned outside the window.
    extra = {"schema_version": "1.0", "posts": [{"ref": "extra-linkedin", "kind": "text", "language": "en", "link": None,
                                                 "networks": ["linkedin"], "target_slot": "2026-10-20T09:00",
                                                 "variants": {"linkedin": {"text": "Write the purpose of your company in one sentence before you write a single slide."}}}]}
    (proj / "extra.json").write_text(json.dumps(extra), encoding="utf-8")
    code, _ = q(proj, "add", "extra.json", "--now", NOW)
    data = load(proj)
    ex = item(proj, "extra-linkedin.linkedin")
    check(code == 0 and ex["slot"] and ex["slot"] != "2026-10-20T09:00", f"same-slot LinkedIn post moved (to {ex['slot']})")
    check(item(proj, "pitch-deck-order.linkedin")["slot"] == "2026-10-20T09:00", "the post planned first keeps its slot")
    check(item(proj, "apply-checklist.linkedin")["slot"] == "2026-10-22T09:00", "a new post never pushes a planned one")
    check(not common.window_conflicts(data["items"], data["settings"]["window_minutes"]), "still no window conflict")
    code, _ = q(proj, "review", "--out", "review.md", "--now", NOW)
    rv = (proj / "review.md").read_text(encoding="utf-8") if (proj / "review.md").exists() else ""
    check(code == 0 and all(i["id"] in rv for i in data["items"]), "review packet lists every item")
    check(not any(common.review_code(i) in rv for i in data["items"]) and "--code" not in rv,
          "the review packet carries no review code")
    code, out = q(proj, "list")
    check(code == 0 and not any(common.review_code(i) in out for i in data["items"]), "list prints no review code")
    check("https://" not in "".join(re.findall(r"Body:\n\n```text\n(.*?)```", rv, re.S)), "no URL in any body of the packet")
    return proj


def part_gate(proj: Path) -> None:
    print("5. approval gate")
    li = "pitch-deck-order.linkedin"
    code, out = q(proj, "approve", li, "--by", "alice", "--now", NOW)
    check(code == 3 and "interactive terminal" in out and item(proj, li)["status"] == "to_review",
          "approve without a terminal: exit 3")
    code, out = q(proj, "approve", li, "--by", "alice", "--code", code_of(proj, li), "--now", NOW)
    check(code == 3 and "not accepted as arguments" in out and item(proj, li)["status"] == "to_review",
          "approve --code with the right code: refused, codes are never arguments")
    for name in ("agent", "Claude", "content-publisher", "<your-name>"):
        code, out = q(proj, "approve", li, "--by", name, "--now", NOW)
        check(code == 3 and "--by must be" in out, f"approve --by {name!r} refused")
    code, out = run_tty(proj, lambda t: "000000" if shown_code(t) != "000000" else "111111", "approve", li, "--by", "alice", "--now", NOW)
    check(code == 3 and "wrong review code" in out and item(proj, li)["status"] == "to_review",
          "wrong review code typed at the terminal refused")
    code, out = q(proj, "show", li)
    check(code == 0 and code_of(proj, li) not in out, "show prints no review code")
    code, _ = q(proj, "schedule", "--id", li, "--now", NOW)
    check(code == 3, "schedule of a to_review item: exit 3")
    code, out = q(proj, "schedule", "--now", NOW)
    check(all(i["status"] != "scheduled" for i in load(proj)["items"]), "schedule with nothing approved schedules nothing")

    # Hand-edited queue: "approved" without any approval.
    data = load(proj)
    forged = next(i for i in data["items"] if i["id"] == "first-customer-calls.x")
    forged["status"] = "approved"
    (proj / "queue.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    code, _ = q(proj, "validate")
    check(code == 1, "validate flags an approved item without approval")
    code, out = q(proj, "schedule", "--now", NOW)
    check(item(proj, "first-customer-calls.x")["status"] == "to_review", "schedule sends a forged status back to to_review")

    # Hand-edited queue: a complete approval copied from the content hash, with its history event.
    th = "first-customer-calls.threads"
    data = load(proj)
    forged = next(i for i in data["items"] if i["id"] == th)
    forged["status"] = "approved"
    forged["approval"] = {"by": "alice", "at": NOW, "content_hash": forged["content_hash"], "mac": "0" * 64}
    forged["history"].append({"at": NOW, "action": "approved", "by": "alice", "note": "", "from": "to_review", "to": "approved"})
    (proj / "queue.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    code, out = q(proj, "validate")
    check(code == 1 and "not recorded by" in out, "validate flags an approval typed into queue.json")
    code, out = q(proj, "schedule", "--now", NOW)
    it = item(proj, th)
    check(it["status"] == "to_review" and it["approval"] is None and "not recorded by" in out,
          "schedule sends an approval forged with the right content hash back to to_review, saying why")
    check(not (proj / "outbox" / f"{th}.json").exists(), "the forged item never reaches the outbox")

    # Approval by a person at a terminal.
    code, out = run_tty(proj, shown_code, "approve", li, "--by", "alice", "--now", NOW)
    it = item(proj, li)
    check(code == 0 and it["status"] == "approved" and len((it["approval"] or {}).get("mac", "")) == 64,
          "approve at a terminal with the code it shows")
    check(code_of(proj, li) not in json.dumps(it), "the review code is written nowhere in queue.json")

    # The approval of one item copied onto another.
    px = "pitch-deck-order.x"
    data = load(proj)
    src = next(i for i in data["items"] if i["id"] == li)
    dst = next(i for i in data["items"] if i["id"] == px)
    dst["status"] = "approved"
    dst["approval"] = dict(src["approval"], content_hash=dst["content_hash"])
    dst["history"].append({"at": NOW, "action": "approved", "by": "alice", "note": "", "from": "to_review", "to": "approved"})
    (proj / "queue.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    code, out = q(proj, "schedule", "--id", px, "--now", NOW)
    check(item(proj, px)["status"] == "to_review", "an approval copied from another item is refused")

    # Approval, then an edit: back to to_review, approval cleared.
    code, out = q(proj, "edit", li, "--text", item(proj, li)["text"] + "\n\nSave it for your next deck.", "--by", "alice", "--now", NOW)
    it = item(proj, li)
    check(code == 0 and it["status"] == "to_review" and it["approval"] is None, "an edit after approval clears it")
    check(code_of(proj, li) not in out, "edit prints no review code")
    code, _ = q(proj, "schedule", "--id", li, "--now", NOW)
    check(code == 3, "the edited item cannot be scheduled")

    # Approval, then a media swap on disk.
    ig = "apply-checklist.instagram"
    code, _ = run_tty(proj, shown_code, "approve", ig, "--by", "alice", "--now", NOW)
    check(code == 0 and item(proj, ig)["status"] == "approved", "approve the Instagram image post")
    media = proj / item(proj, ig)["media"][0]["path"]
    original = media.read_bytes()
    media.write_bytes(original + b"\0")
    code, out = q(proj, "schedule", "--id", ig, "--now", NOW)
    check(item(proj, ig)["status"] == "to_review", "a media swap after approval sends the item back to review")
    media.write_bytes(original)

    # Past slot.
    code, _ = run_tty(proj, shown_code, "approve", "first-customer-calls.bluesky", "--by", "alice", "--now", "2026-12-01T08:00")
    check(code == 1, "approve refuses an item whose slot has passed")

    # Static: one call site of the approval sentinel and of the review code, no direct status write to approved.
    sources = {p.name: p.read_text(encoding="utf-8") for p in list(SCRIPTS.glob("*.py")) + list((SCRIPTS / "adapters").glob("*.py"))
               if p.name != "selftest.py"}
    approve_src = sources["pubqueue.py"].split("def cmd_approve", 1)[1].split("\ndef ", 1)[0]
    for token in ("common.HUMAN_APPROVAL", "common.review_code("):
        uses = {n: s.count(token) for n, s in sources.items()}
        check(sum(uses.values()) == 1 and uses.get("pubqueue.py") == 1 and token in approve_src,
              f"{token} used once, inside cmd_approve ({uses})")
    direct = [n for n, s in sources.items() if re.search(r"""\[["']status["']\]\s*=\s*["']approved""", s)]
    check(not direct, f"no script writes status approved directly ({direct})")


def approve_all(proj: Path) -> None:
    q(proj, "review", "--out", "review.md", "--now", NOW)  # refreshes the hashes of items whose media changed
    ids = [it["id"] for it in load(proj)["items"] if it["status"] == "to_review"]
    if ids:
        run_tty(proj, shown_code, "approve", *ids, "--by", "alice", "--now", NOW)


def part_adapters(proj: Path, tmp: Path) -> None:
    print("6. adapters")
    approve_all(proj)
    approved = [i["id"] for i in load(proj)["items"] if i["status"] == "approved"]
    check(len(approved) >= 9, f"items approved by a person for the adapter tests ({len(approved)})")
    code, _ = q(proj, "schedule", "--adapter", "zernio", "--now", NOW)
    check(code == 2, "zernio without --live: exit 2")
    code, _ = q(proj, "schedule", "--adapter", "zernio", "--live", "--now", NOW)
    check(code == 4, "zernio without ZERNIO_API_KEY: exit 4")
    code, _ = q(proj, "schedule", "--adapter", "zernio", "--live", "--now", NOW, extra_env={"ZERNIO_API_KEY": "test-key"})
    check(code == 4, "zernio offline: exit 4, no request")
    code, _ = q(proj, "schedule", "--adapter", "webhook", "--live", "--now", NOW,
                extra_env={"CONTENT_PUBLISHER_WEBHOOK_URL": "https://hooks.example.invalid/x"})
    check(code == 4, "webhook offline: exit 4, no request")
    code, out = q(proj, "schedule", "--adapter", "webhook", "--live", "--now", NOW,
                  extra_env={"CONTENT_PUBLISHER_WEBHOOK_URL": "http://hooks.example.invalid/x",
                             "CONTENT_PUBLISHER_WEBHOOK_TOKEN": "test-token"})
    check(code == 4 and "use https" in out, "webhook over plain http refused before any request")
    code, out = q(proj, "schedule", "--adapter", "zernio", "--live", "--now", NOW,
                  extra_env={"ZERNIO_API_KEY": "test-key", "ZERNIO_BASE_URL": "http://zernio.example.invalid/api/v1"})
    check(code == 4 and "use https" in out, "ZERNIO_BASE_URL over plain http refused before any request")
    check(adapter_base.url_problem("http://127.0.0.1:8787/hook") is None and adapter_base.url_problem("http://localhost/x") is None,
          "plain http allowed to localhost only")
    check(bool(adapter_base.url_problem("file:///etc/passwd")) and adapter_base.url_problem("https://zernio.com/api/v1") is None,
          "file:// refused, https allowed")
    try:
        adapter_base.http("GET", "http://example.invalid/x", headers={"Authorization": "Bearer k"})
        check(False, "http() refuses a plain http URL")
    except adapter_base.ProviderUnavailable as e:
        check("use https" in str(e), "http() refuses a plain http URL")
    req = urllib.request.Request("https://api.example.invalid/v1/posts", headers={"Authorization": "Bearer k"})
    hop = adapter_base.SafeRedirect()
    other = hop.redirect_request(req, None, 302, "Found", {}, "https://elsewhere.example.invalid/x")
    same = hop.redirect_request(req, None, 302, "Found", {}, "https://api.example.invalid/v2/posts")
    down = hop.redirect_request(req, None, 302, "Found", {}, "http://api.example.invalid/v2/posts")
    check(not other.has_header("Authorization") and not down.has_header("Authorization") and same.has_header("Authorization"),
          "a redirect to another host or to plain http drops the Authorization header")
    check(sorted(i["id"] for i in load(proj)["items"] if i["status"] == "approved") == sorted(approved),
          "refused providers leave items approved")

    fake = tmp / "fake_publisher.py"
    received = tmp / "received.jsonl"
    fake.write_text(
        "import json, sys\n"
        "doc = json.load(sys.stdin)\n"
        f"open({str(received)!r}, 'a').write(json.dumps(doc) + '\\n')\n"
        "print(json.dumps({'post_id': 'cmd-' + doc.get('id', ''), 'status': 'published' if doc.get('action') == 'status' else 'scheduled'}))\n",
        encoding="utf-8")
    cmd_env = {"CONTENT_PUBLISHER_COMMAND": f"{sys.executable} {fake}"}
    code, _ = q(proj, "schedule", "--adapter", "command", "--live", "--id", "first-customer-calls.threads", "--now", NOW, extra_env=cmd_env)
    th = item(proj, "first-customer-calls.threads")
    sent = [json.loads(l) for l in received.read_text().splitlines()] if received.exists() else []
    check(code == 0 and th["status"] == "scheduled" and th["provider"]["name"] == "command", "command adapter schedules through a local program")
    check(bool(sent) and sent[0]["network"] == "threads" and sent[0]["reply"].endswith("https://swanbase.co/en/")
          and "https://" not in sent[0]["text"], "command adapter receives the body and the link reply")

    code, out = q(proj, "schedule", "--now", NOW)
    data = load(proj)
    check(code == 0 and all(i["status"] == "scheduled" for i in data["items"] if i["id"] in approved),
          "dry-run schedules every approved item")
    outbox = proj / "outbox"
    for it in data["items"]:
        if it["status"] != "scheduled" or it["provider"]["name"] != "dry-run":
            continue
        doc = json.loads((outbox / f"{it['id']}.json").read_text(encoding="utf-8"))
        ws, zv = doc["would_send"], doc["zernio_view"]
        lim = common.limits()[it["network"]]
        if variants.links_in(ws["text"]):
            check(False, f"{it['id']}: URL in the body")
        if variants.length(ws["text"], it["network"], common.limits()) > lim["text_max"]:
            check(False, f"{it['id']}: body over the limit")
        if it["link"] and it["network"] == "linkedin":
            check(it["link"] in zv["platforms"][0]["platformSpecificData"]["firstComment"], f"{it['id']}: link in the first comment")
        if it["link"] and it["network"] == "x":
            ti = zv["platforms"][0]["platformSpecificData"]["threadItems"]
            check(len(ti) == 2 and it["link"] in ti[1]["content"] and it["link"] not in ti[0]["content"],
                  f"{it['id']}: one tweet, link in the first reply")
            check(all(variants.x_length(t["content"]) <= 280 for t in ti), f"{it['id']}: tweet and reply within 280")
        if it["network"] == "instagram":
            check(not zv["platforms"][0].get("platformSpecificData"), f"{it['id']}: Instagram caption only")
    li_item = {"id": "deck.linkedin", "network": "linkedin", "text": "Body", "first_comment": "Guide: https://example.com/g",
               "media": [{"path": "deck.pdf", "type": "document", "title": "Deck"}], "slot": "2026-10-20T09:00", "content_hash": "0" * 64}
    zv = ZernioAdapter().build_payload(li_item, {"settings": {"timezone": "Europe/Paris"}})
    psd = zv["platforms"][0]["platformSpecificData"]
    check(psd.get("firstComment", "").endswith("https://example.com/g") and psd.get("documentTitle") == "Deck",
          "zernio payload: LinkedIn first comment and document title")


def part_sync(proj: Path, tmp: Path) -> None:
    print("7. sync, mark, validate")
    code, _ = q(proj, "sync", "--now", "2026-10-20T09:30")
    data = load(proj)
    st = {i["id"]: i["status"] for i in data["items"]}
    check(st["pitch-deck-order.x"] == "published", "sync: a dry-run item whose slot passed is published (simulated)")
    check(st["apply-checklist.instagram"] == "scheduled", "sync: a future slot stays scheduled")
    code, _ = q(proj, "mark", "apply-checklist.linkedin", "--failed", "--by", "alice", "--note", "account disconnected")
    check(code == 0 and item(proj, "apply-checklist.linkedin")["status"] == "failed", "mark --failed")
    code, _ = q(proj, "reopen", "apply-checklist.linkedin", "--by", "alice", "--now", NOW)
    it = item(proj, "apply-checklist.linkedin")
    check(code == 0 and it["status"] == "to_review" and it["approval"] is None, "reopen a failed item: back to review, approval cleared")
    code, out = q(proj, "validate")
    check(code == 0, "validate passes at the end" + ("" if code == 0 else f": {out[-600:]}"))
    data = load(proj)
    check(not common.schema_errors(data, common.QUEUE_SCHEMA), "final queue matches the schema")
    for script in ("pubqueue.py", "variants.py", "import_carousel.py", "selftest.py"):
        r = subprocess.run([sys.executable, str(SCRIPTS / script), "--help"], capture_output=True, text=True)
        check(r.returncode == 0, f"{script} --help")


def part_paths(tmp: Path) -> None:
    print("8. media paths")
    proj = tmp / "paths"
    (proj / "media").mkdir(parents=True)
    png = EXAMPLE / "media" / "checklist-4x5.png"
    shutil.copyfile(png, proj / "media" / "c.png")
    outside = tmp / "outside.png"
    shutil.copyfile(png, outside)
    run("pubqueue.py", "init", "--queue", "queue.json", "--config", str(AGENT / "config.example.json"), "--project-name", "paths", cwd=proj)
    ref = json.loads((EXAMPLE / "posts.json").read_text(encoding="utf-8"))
    text = next(p for p in ref["posts"] if p["ref"] == "apply-checklist")["variants"]["linkedin"]["text"]

    def spec(name: str, path: str) -> Path:
        doc = {"schema_version": "1.0", "posts": [{"ref": name, "kind": "image", "language": "en", "link": None,
                                                   "media": [{"path": path, "type": "image", "alt": "Checklist"}],
                                                   "networks": ["linkedin"], "target_slot": "2026-10-20T09:00",
                                                   "variants": {"linkedin": {"text": text}}}]}
        f = proj / f"{name}.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        return f

    code, out = q(proj, "add", spec("outside", "../outside.png").name, "--now", NOW)
    check(code == 1 and "outside the project folder" in out and not load(proj)["items"], "add refuses a media path outside the project")
    code, out = q(proj, "add", spec("inside", "media/c.png").name, "--now", NOW)
    check(code == 0, "add accepts a media file inside the project")
    run_tty(proj, shown_code, "approve", "inside.linkedin", "--by", "alice", "--now", NOW)
    check(item(proj, "inside.linkedin")["status"] == "approved", "approved by a person")
    data = load(proj)
    data["items"][0]["media"][0]["path"] = str(outside)  # hand edit: same file content, absolute path
    (proj / "queue.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    code, out = q(proj, "schedule", "--now", NOW)
    it = item(proj, "inside.linkedin")
    check(code == 1 and it["status"] == "failed" and "outside the project folder" in out,
          "schedule refuses an approved item whose media path was edited to a file outside the project")
    check(not (proj / "outbox" / "inside.linkedin.json").exists(), "nothing written to the outbox for it")
    code, out = q(proj, "validate")
    check(code == 1 and "outside the project folder" in out, "validate flags the media path outside the project")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", help="work in this folder and keep it")
    a = ap.parse_args(argv)
    tmp = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="content-publisher-selftest-"))
    if a.keep:
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
    os.environ[common.APPROVAL_KEY_ENV] = str(tmp / "keys" / "approval.key")  # throwaway key, outside every project
    try:
        part_counting()
        part_stress(tmp)
        part_reference(tmp)
        proj = part_lifecycle(tmp)
        part_gate(proj)
        part_adapters(proj, tmp)
        part_sync(proj, tmp)
        part_paths(tmp)
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nselftest: {'PASS' if not FAILS else 'FAIL'} ({len(FAILS)} failure(s))")
    for f in FAILS:
        print(f"  - {f}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
