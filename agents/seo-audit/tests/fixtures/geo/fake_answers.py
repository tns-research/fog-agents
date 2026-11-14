#!/usr/bin/env python3
"""Stands in for an answer engine CLI in the tests: reads the question on
stdin, answers from a fixed table keyed by GEO_PROMPT_ID and GEO_DRAW, prints
JSON {answer, citations}. Fictional answers, fictional .example domains."""
import json
import os
import sys

sys.stdin.read()
ANSWERS = {
    ("paris-accelerators.q1", "1"): ("Options include swanbase and Northpier, both open to first-time founders.",
                                     ["https://swanbase.example/program/", "https://northpier.example/apply"]),
    ("paris-accelerators.q1", "2"): ("Northpier and Launchyard run pre-seed programs in Paris.",
                                     ["https://northpier.example/", "https://news.example.org/paris-accelerators"]),
    ("paris-accelerators.q1", "3"): ("swanbase is a pre-seed accelerator in Paris; Northpier is another option.",
                                     ["https://northpier.example/"]),
    ("paris-accelerators.q2", "1"): ("Yes: swanbase is free and on application.", ["https://swanbase.example/"]),
    ("paris-accelerators.q2", "2"): ("swanbase (free, on application) and Launch Yard (paid).",
                                     ["https://swanbase.example/apply/", "https://launchyard.example/pricing"]),
    ("paris-accelerators.q2", "3"): ("Some programs are free, such as swanbase.", []),
    ("first-pitch.q1", "1"): ("Start with the problem, keep the ask concrete.", ["https://news.example.org/first-pitch"]),
    ("first-pitch.q1", "2"): ("Practice in front of peers before investors.", ["https://news.example.org/first-pitch"]),
    ("first-pitch.q1", "3"): ("Open with the problem; see https://blog.example.net/pitch for a checklist.", []),
}
key = (os.environ.get("GEO_PROMPT_ID"), os.environ.get("GEO_DRAW"))
if key not in ANSWERS:
    print("unknown prompt", file=sys.stderr)
    sys.exit(3)
answer, cites = ANSWERS[key]
print(json.dumps({"answer": answer, "citations": cites}))
