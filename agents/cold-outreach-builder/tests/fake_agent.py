#!/usr/bin/env python3
"""Stand-in for a model CLI in the run_dossiers.py test: reads a research
brief on stdin and writes the smallest valid prospect.json (no fact), so the
orchestration (waves, file check, resume) is tested offline. Prospect ids
listed in FAKE_AGENT_FAIL write nothing, to test the failure path."""

import json
import os
import re
import sys

brief = sys.stdin.read()
pid = re.search(r"^# Research brief: (\S+)", brief, re.M).group(1)
out = re.search(r"^Write `([^`]+prospect\.json)`", brief, re.M).group(1)
if pid in os.environ.get("FAKE_AGENT_FAIL", "").split(","):
    print(f"{pid}: simulated failure")
    sys.exit(0)
first = re.search(r"^- first_name: (.+)$", brief, re.M).group(1)
data = {"schema_version": "1.0", "prospect_id": pid, "first_name": first, "researched_at": "2026-10-12",
        "language": "en", "relationship": "none", "facts": [], "pages_read": [], "notes": "fake agent"}
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
print(f"{pid}: written")
