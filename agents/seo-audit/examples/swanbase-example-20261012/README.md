# Example: swanbase.example, 2026-10-12

A run of seo-audit on a **fictional** site, `swanbase.example`, served locally by [`../../tests/fixture_server.py`](../../tests/fixture_server.py) with planted defects. Search Console exports and answer-engine answers are invented test fixtures: no number here describes a real site.

| File | What it is | Produced by |
|------|------------|-------------|
| [`config.json`](config.json) | the project config of the run | the founder and Step 0 |
| [`crawl.jsonl`](crawl.jsonl) | one line per URL of the served site | `scripts/crawl.py` |
| [`bands.md`](bands.md) | Search Console bands | `scripts/gsc_bands.py` |
| [`geo-panel.json`](geo-panel.json) | the GEO panel (questions with their source, competitors, draws) | the model, checked by `geo_panel.py check` |
| [`ai-access.md`](ai-access.md), [`geo-score.md`](geo-score.md) | AI crawler access and panel scores | `scripts/geo_panel.py` |
| [`seo-audit-20261012.md`](seo-audit-20261012.md) | the report, abridged: every current title cites its crawl line | the model, gated by `scripts/check_report.py` |

Regenerate everything (briefs, state, the second run after the fix and its diff included) in one command, outputs kept in a folder:

```bash
python3 agents/seo-audit/tests/run_tests.py --keep /tmp/seo-audit-example
```

The tests check that `crawl.jsonl` here regenerates byte for byte and that the report passes the gate.
