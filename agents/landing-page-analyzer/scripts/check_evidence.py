#!/usr/bin/env python3
"""check_evidence.py: every recommendation of the audit points at a measure or a capture
that exists.

  python3 scripts/check_evidence.py <landing-audit-YYYYMMDD.json> --root <run folder> [--repo <site source>]

Reads the sidecar JSON and checks that each finding scored Partial or Missing (and
any other finding that lists evidence), each
entry of top_fixes and each copy rewrite carries a non-empty "evidence" list, and that
every reference resolves under --root (the folder holding probe.json, journey/,
fixes/ and the screenshots):

  probe:<viewport>.<metric>     a key of probe.json summary (for example probe:mobile.overflow_x_px),
                                or a dotted path under viewports.<viewport>.measures
  journey:<viewport>/<file>.png a capture written by journey.py
  journey:step:<n>              a step of journey-log.json that ran ok on at least one viewport
  fix:<id>                      fixes/<id>/fix.json exists and its status is pass
  shot:<relative path>          any capture under --root (capture-page.py slices, a founder screenshot)
  psi:<key>                     a key of psi-summary.json
  url:<https://...>             an external source, accepted as written
  page:"<quoted text>"          a verbatim quote from the page; must appear in page.md or page.html when present
  patch:<id>                    repo-patches/repo-patches.json records fix <id> ready and its patch file exists

Also checks that "criteria" IDs on fixes exist in assets/lever-grid.md or the visual
and mobile checklists. When the sidecar has "repo_patches" (repo mode, written from
repo-patches/repo-patches.json of scripts/repo_patch.py), each entry
{"fix", "status", "patch", "locations"} must match what repo_patch.py recorded; an entry
announced "ready" or "ready-needs-import" must name a patch that exists under --root and
passes git apply --check on a temporary copy of the repo (--repo, else the sidecar
"repo", relative to the sidecar, else the path repo_patch.py recorded); a "manual" entry
must carry its reason; each "path:line" location must exist in the repo or be created
by the patch. Prints one line per problem.

Exit 0 when every recommendation has evidence, every reference resolves and every
announced repo patch holds, 1 when not, 2 when the sidecar cannot be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repo_patch import READY, apply_check, patch_paths  # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
ID_SOURCES = ["assets/lever-grid.md", "assets/visual-criteria-checklist.md", "assets/mobile-ux-checklist.md"]


def known_ids() -> set:
    ids = set()
    for rel in ID_SOURCES:
        p = AGENT / rel
        if p.exists():
            ids |= set(re.findall(r"\b([CTUKM]\d{3}|V\d{1,2}|TM\d|PM\d|LM\d|FM\d)\b", p.read_text(encoding="utf-8")))
    return ids


def dig(obj: Any, path: str):
    for part in path.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return None, False
    return obj, True


class Resolver:
    def __init__(self, root: Path):
        self.root = root
        self._probe = self._load("probe.json")
        self._journey = self._load("journey/journey-log.json")
        self._psi = self._load("psi-summary.json")
        page = ""
        for name in ("page.md", "page.html"):
            if (root / name).exists():
                page += (root / name).read_text(encoding="utf-8", errors="ignore")
        self._page = re.sub(r"\s+", " ", page)

    def _load(self, rel: str):
        p = self.root / rel
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def check(self, ref: str) -> str:
        """Return '' when the reference resolves, else the reason."""
        if not isinstance(ref, str) or ":" not in ref:
            return "not a reference (kind:value)"
        kind, value = ref.split(":", 1)
        if kind == "probe":
            if not self._probe:
                return "probe.json missing under --root"
            if "." not in value:
                return "write probe:<viewport>.<metric>"
            vp, path = value.split(".", 1)
            if path in (self._probe.get("summary", {}).get(vp) or {}):
                return ""
            _, ok = dig(self._probe.get("viewports", {}).get(vp, {}).get("measures", {}), path)
            return "" if ok else f"no {path} for viewport {vp} in probe.json"
        if kind == "journey":
            if value.startswith("step:"):
                if not self._journey:
                    return "journey/journey-log.json missing under --root"
                try:
                    n = int(value[5:])
                except ValueError:
                    return "journey:step:<n> needs a number"
                for vp in self._journey.get("viewports", []):
                    for st in vp.get("steps", []):
                        if st.get("n") == n and st.get("status") == "ok":
                            return ""
                return f"step {n} did not run ok"
            return "" if (self.root / "journey" / value).exists() else f"no journey/{value}"
        if kind == "fix":
            p = self.root / "fixes" / value / "fix.json"
            if not p.exists():
                return f"no fixes/{value}/fix.json"
            st = json.loads(p.read_text(encoding="utf-8")).get("status")
            return "" if st == "pass" else f"fix {value} status {st}"
        if kind == "shot":
            return "" if (self.root / value).exists() else f"no file {value}"
        if kind == "psi":
            if not self._psi:
                return "psi-summary.json missing under --root"
            _, ok = dig(self._psi, value)
            return "" if ok else f"no {value} in psi-summary.json"
        if kind == "url":
            return "" if value.startswith(("http://", "https://")) else "url: needs http(s)"
        if kind == "patch":
            rec = self._load("repo-patches/repo-patches.json")
            if not rec:
                return "repo-patches/repo-patches.json missing under --root"
            hit = next((f for f in rec.get("fixes", []) if f.get("id") == value), None)
            if not hit:
                return f"fix {value} not in repo-patches.json"
            if hit.get("status") not in READY or not hit.get("patch"):
                return f"fix {value} is {hit.get('status')}, no patch"
            return "" if (self.root / hit["patch"]).exists() else f"no file {hit['patch']}"
        if kind == "page":
            quote = value.strip().strip('"')
            if not self._page:
                return ""
            return "" if re.sub(r"\s+", " ", quote) in self._page else "quote not found in page.md or page.html"
        return f"unknown kind {kind}"


def check_repo_patches(side: Dict[str, Any], root: Path, base: Path, repo_arg: Optional[str]) -> Tuple[int, List[str]]:
    entries = side.get("repo_patches") or []
    if not entries:
        return 0, []
    try:
        rec = json.loads((root / "repo-patches" / "repo-patches.json").read_text(encoding="utf-8"))
    except Exception:
        return len(entries), ["repo_patches: repo-patches/repo-patches.json missing or unreadable under --root (run repo_patch.py)"]
    problems: List[str] = []
    repo_s = repo_arg or side.get("repo") or rec.get("repo")
    repo = Path(repo_s) if repo_s else None
    if repo is not None and not repo.is_absolute():
        repo = base / repo
    if repo is None or not repo.is_dir():
        problems.append(f"repo_patches: repo {repo_s} not found, patches cannot be checked (pass --repo)")
        repo = None
    recorded = {f.get("id"): f for f in rec.get("fixes", [])}
    if rec.get("all", {}).get("patch"):
        recorded["all"] = dict(rec["all"], id="all", status="ready")
    for e in entries:
        fid = e.get("fix")
        label = f"repo_patch {fid}"
        r = recorded.get(fid)
        if not r:
            problems.append(f"{label}: not in repo-patches.json")
            continue
        st = e.get("status")
        if st != r.get("status"):
            problems.append(f"{label}: announced {st!r}, repo_patch.py recorded {r.get('status')!r}")
        created = set()
        if st in READY:
            patch = e.get("patch") or r.get("patch")
            if not patch:
                problems.append(f"{label}: announced {st} without a patch")
                continue
            if patch != r.get("patch"):
                problems.append(f"{label}: patch {patch} is not the one repo_patch.py wrote ({r.get('patch')})")
            p = root / patch
            if not p.exists():
                problems.append(f"{label}: no file {patch}")
                continue
            created = {rel for rel, new in patch_paths(p.read_text(encoding="utf-8")) if new}
            if repo is not None:
                why = apply_check(repo, p)
                if why:
                    problems.append(f"{label}: {patch} does not pass git apply --check: {why}")
        elif st == "manual":
            if not (e.get("reason") or r.get("reason")):
                problems.append(f"{label}: manual without a reason")
            if e.get("patch"):
                problems.append(f"{label}: manual but names a patch")
        for loc in e.get("locations") or []:
            path, _, line = str(loc).rpartition(":")
            if not path or not line.isdigit():
                problems.append(f"{label}: location {loc!r} is not path:line")
            elif path in created or repo is None:
                continue
            elif not (repo / path).is_file():
                problems.append(f"{label}: location {loc}: no file {path} in the repo")
            elif int(line) > len((repo / path).read_text(encoding="utf-8", errors="ignore").splitlines()):
                problems.append(f"{label}: location {loc}: {path} has fewer lines")
    return len(entries), problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sidecar")
    ap.add_argument("--root", required=True, help="run folder holding probe.json, journey/, fixes/, repo-patches/, screenshots")
    ap.add_argument("--repo", help="site source the repo patches apply to (default: the sidecar repo, else the one repo_patch.py recorded)")
    args = ap.parse_args()
    try:
        side = json.loads(Path(args.sidecar).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"error: cannot read {args.sidecar}: {e}", file=sys.stderr)
        return 2
    res = Resolver(Path(args.root))
    ids = known_ids()
    problems: List[str] = []
    items: List[tuple] = []
    for f in side.get("findings", []):
        if f.get("status") in ("Partial", "Missing") or f.get("evidence"):
            items.append((f"finding {f.get('id')}", f))
    for f in side.get("top_fixes", []):
        items.append((f"top_fix {f.get('rank')}", f))
        for c in f.get("criteria", []) or []:
            if c not in ids:
                problems.append(f"top_fix {f.get('rank')}: unknown criterion {c}")
    for f in side.get("rewrites", []):
        items.append((f"rewrite {f.get('location')}", f))
    refs = 0
    for label, item in items:
        ev = item.get("evidence")
        if not ev:
            problems.append(f"{label}: no evidence")
            continue
        for ref in ev:
            refs += 1
            why = res.check(ref)
            if why:
                problems.append(f"{label}: {ref}: {why}")
    n_patches, patch_problems = check_repo_patches(side, Path(args.root), Path(args.sidecar).resolve().parent, args.repo)
    problems += patch_problems
    for p in problems:
        print(p)
    print(f"check_evidence: {len(items)} recommendations, {refs} references, {n_patches} repo patches, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
