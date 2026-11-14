# examples/

Reproducible runs of `cold-outreach-builder`, inputs only: every output rebuilds in one command and goes to `/tmp`.

| Example | What it shows | Command |
|---------|---------------|---------|
| [`swanbase-preseed-founders-20261012/`](swanbase-preseed-founders-20261012/) | Three fictional prospects for the stack's example brand: cached pages, verified dossiers, tiers A, B and C, a tier A sequence written for the person, a tier B template with its hook, the lint at 0 BLOCK. Rendered messages in `preview.md` | see the example's README, or `python3 tests/run_tests.py` |

Regression fixtures that must fail (the April 2026 run, duplicates, broken dossiers, replies, DNS answers) live in [`../tests/fixtures/`](../tests/fixtures/).

## Adding an example

A folder `<brand>-<audience>-<YYYYMMDD>/` with `leads.csv`, `cache/` (text pages stored with `scripts/cache_page.py --from-file`), `dossiers/<id>/prospect.json`, `cold-outreach-output.json`, `messages.json`, a `README.md` with the commands, and `preview.md`. English, fictional people on `.example` domains (or public figures with a public source), signature `{{sender_first_name}}`, no invented figure.
