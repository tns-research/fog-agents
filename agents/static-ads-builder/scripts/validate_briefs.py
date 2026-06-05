#!/usr/bin/env python3
"""validate_briefs.py - Guard the briefs JSON before any fal spend.

The render input is `static-ads-briefs-YYYYMMDD.json`: a top-level array of brief
payloads. The renderer trusts this file, so it must be valid before Gate 2. This
checker catches the cheap-to-fix mistakes that would otherwise waste a render:

  - invalid JSON / not an array
  - missing required fields (image_prompt, headline, subheadline, typography)
  - conditional language in image_prompt ("if available", "optional", "can be generic")
  - reference_assets malformed (not a list of {role, instruction}, bad role, or
    empty instruction)
  - reference_assets present but image_prompt does not reference the attached
    image(s) (or vice versa)
  - a logo asset is attached but nothing guards against redrawing it
  - duplicate named angle across briefs (_concept reuse), if _concept is present
  - empty image_prompt or one too short to carry the 7-element formula

It does NOT judge taste (is the headline good); that is the agent's job. It only
blocks structural errors that make a render pointless.

Usage:
    python validate_briefs.py briefs.json

Exit codes:
    0  valid (warnings allowed, printed to stderr)
    3  invalid (errors printed); fix before rendering
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED = ("image_prompt", "headline", "subheadline", "typography")
TYPO_REQUIRED = ("font_style", "color", "headline_placement", "subheadline_placement")
CONDITIONAL_PATTERNS = [
    r"\bif (?:reference|available|provided|a product)\b",
    r"\boptional\b",
    r"\bcan be (?:generic|branded|either)\b",
    r"\bgeneric or\b",
    r"\bn/a\b",
]
VALID_ROLES = ("product", "screenshot", "logo", "hero")
ATTACHED_REF_HINT = "attached"  # the prompt must name the attached image(s)
LOGO_GUARD_PATTERNS = [r"do not redraw", r"exactly as provided", r"do not recolor",
                       r"do not restyle", r"reproduce the attached"]
MIN_PROMPT_WORDS = 25  # a 7-element prompt is never a one-liner


def _check_brief(i: int, brief: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    tag = f"brief #{i}"

    if not isinstance(brief, dict):
        return [f"{tag}: not a JSON object"], warnings

    for field in REQUIRED:
        if field not in brief:
            errors.append(f"{tag}: missing required field '{field}'")

    prompt = brief.get("image_prompt", "")
    if isinstance(prompt, str):
        if not prompt.strip():
            errors.append(f"{tag}: empty image_prompt")
        elif len(prompt.split()) < MIN_PROMPT_WORDS:
            warnings.append(f"{tag}: image_prompt looks short "
                            f"({len(prompt.split())} words); check the 7-element formula")
        low = prompt.lower()
        for pat in CONDITIONAL_PATTERNS:
            if re.search(pat, low):
                errors.append(f"{tag}: conditional language in image_prompt "
                              f"(matched /{pat}/)")
                break

    typo = brief.get("typography")
    if isinstance(typo, dict):
        for sub in TYPO_REQUIRED:
            if sub not in typo:
                errors.append(f"{tag}: typography missing '{sub}'")
    elif "typography" in brief:
        errors.append(f"{tag}: typography must be an object")

    sub = brief.get("subheadline")
    typo_sp = typo.get("subheadline_placement", "") if isinstance(typo, dict) else ""
    if isinstance(sub, str) and not sub.strip() and typo_sp.strip():
        warnings.append(f"{tag}: subheadline is empty but subheadline_placement is set")

    ra = brief.get("reference_assets")
    if ra is not None:
        if not isinstance(ra, list) or not ra:
            errors.append(f"{tag}: reference_assets must be a non-empty array "
                          f"(omit the key entirely when no asset is shown)")
        else:
            roles_seen: list[str] = []
            for j, a in enumerate(ra, start=1):
                if not isinstance(a, dict):
                    errors.append(f"{tag}: reference_assets[{j}] must be an object "
                                  f"with 'role' and 'instruction'")
                    continue
                role = a.get("role")
                roles_seen.append(role)
                if role not in VALID_ROLES:
                    errors.append(f"{tag}: reference_assets[{j}] role '{role}' invalid "
                                  f"(one of {', '.join(VALID_ROLES)})")
                instr = a.get("instruction")
                if not (isinstance(instr, str) and instr.strip()):
                    errors.append(f"{tag}: reference_assets[{j}] missing a non-empty 'instruction'")
            if isinstance(prompt, str) and ATTACHED_REF_HINT not in prompt.lower():
                errors.append(f"{tag}: reference_assets present but image_prompt does not "
                              f"reference the attached image(s)")
            if "logo" in roles_seen:
                guard_text = (prompt + " " + " ".join(
                    str(a.get("instruction", "")) for a in ra if isinstance(a, dict)
                )).lower()
                if not any(re.search(p, guard_text) for p in LOGO_GUARD_PATTERNS):
                    warnings.append(f"{tag}: logo asset attached but nothing tells the model "
                                    f"not to redraw it (add 'use exactly as provided, do not redraw')")
    else:
        if isinstance(prompt, str) and re.search(
            r"attached (?:product|logo|reference|ui|screenshot|hero|image|brand)", prompt.lower()
        ):
            warnings.append(f"{tag}: image_prompt references an attached image "
                            f"but there is no reference_assets array")

    return errors, warnings


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: validate_briefs.py <briefs.json>\n")
        return 3
    try:
        data = json.loads(Path(sys.argv[1]).read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"validate_briefs: cannot read JSON: {e}\n")
        return 3
    if not isinstance(data, list):
        sys.stderr.write("validate_briefs: top-level JSON must be an array of briefs\n")
        return 3
    if not data:
        sys.stderr.write("validate_briefs: array is empty\n")
        return 3

    all_errors: list[str] = []
    all_warnings: list[str] = []
    seen_concepts: dict[str, int] = {}

    for i, brief in enumerate(data, start=1):
        errs, warns = _check_brief(i, brief)
        all_errors.extend(errs)
        all_warnings.extend(warns)
        if isinstance(brief, dict):
            concept = (brief.get("_concept") or "").strip().lower()
            if concept:
                if concept in seen_concepts:
                    all_errors.append(
                        f"brief #{i}: duplicate concept/angle '{brief.get('_concept')}' "
                        f"(also brief #{seen_concepts[concept]})")
                else:
                    seen_concepts[concept] = i

    for w in all_warnings:
        sys.stderr.write(f"WARN  {w}\n")
    for e in all_errors:
        sys.stderr.write(f"ERROR {e}\n")

    if all_errors:
        sys.stderr.write(f"validate_briefs: {len(all_errors)} error(s); fix before rendering.\n")
        return 3
    sys.stderr.write(f"validate_briefs: {len(data)} brief(s) OK"
                     f" ({len(all_warnings)} warning(s)).\n")
    print(json.dumps({"briefs": len(data), "errors": 0,
                      "warnings": len(all_warnings)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
