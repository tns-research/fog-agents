---
name: package-output
description: Closes a static-ads-builder run. Writes the Meta package with scripts/package_meta.py (import CSV with every ad PAUSED, exports per ad set, primary text, headline, description, CTA, UTM links, naming by stage, angle, style and ratio, creative ledger for the next performance read), then the run report from assets/output-template.md, the fresh-eyes review and the run log. Ends on the human stop - the founder approves and imports, the agent never publishes. Use at Step 7. Triggers on "package the ads", "import file", "Ads Manager CSV", "write the report".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# package-output

The founder should not retype anything in Ads Manager, and next month's export should map back to what was tried. Both come from the names and the package written here.

## 1. Meta package

Only renders with `qa.json` at 0 error and a `TEXT_OK` proofread are packaged.

```bash
python3 scripts/package_meta.py <run>/ads.json --renders <run>/renders \
  --ledger <project>/static-ads-builder/creative-ledger.json
```

Writes `<run>/meta/`:

| File | Content |
|------|---------|
| `ads-import-YYYYMMDD.csv` | one row per ad and format: Campaign Name, Ad Set Name, Ad Name, Ad Status (`PAUSED`), Title, Body, Link Description, Call to Action, Link, URL Tags, Image File Name, Placements. Headers follow the Ads Manager bulk-import sheet; before the first import, export a blank template from the founder's Ads Manager and align the headers (Meta renames columns over time) |
| `exports/<ad_set>/<ad name>.jpg` | the upload files, one folder per ad set |
| `ad-copy.md` | every text to paste, with lengths, the stop date of dated offers, the winner each ad extends |
| `utm.csv` | ad name to the full tracked URL (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` = ad name, `utm_term` = ad set) |

and appends to the creative ledger one line per ad name (stage, angle, style, ratio, ad set, destination, extends), so `perf.py` joins next month's export back to the concepts. Warnings: primary text outside 50 to 150 characters, headline over 27 (Meta's feed guide, [`../../references/README.md`](../../references/README.md)).

Placements: 1:1 and 4:5 files are feed creatives, 9:16 files are Stories and Reels creatives. One row per format keeps the import simple; the founder may merge the formats of one concept into a single ad with placement customisation in Ads Manager, keeping the 4:5 name.

## 2. Preflight before the founder imports

List in the report, per destination URL: the promise of each ad against what the page says today (price, offer, dates, delivery or response time). A contradiction is fixed before import, in the ad or on the page. With a `scrape` provider, read the page; otherwise ask the founder to confirm each line. For a deeper audit, point to `landing-page-analyzer`.

## 3. Report

`<run>/static-ads-YYYYMMDD.md` from [`../../assets/output-template.md`](../../assets/output-template.md): performance read, batch table, QA and review rounds, proofread verdicts, spend (0 unless plates; estimated and actual when plates ran), Meta package, preflight, claims ledger, methodology (provider per capability, reviewer used), limitations. Paths relative to the run folder.

## 4. Gates, then the human stop

Fresh-eyes review ([`../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)) on the report, the contact sheet and `ad-copy.md`; one revision. Run log line and proposed decisions ([`../../../../shared/skills/keeping-project-memory/SKILL.md`](../../../../shared/skills/keeping-project-memory/SKILL.md)) with `checks.qa`, `checks.proofread`, `render_review_rounds`.

Then show the founder `renders/contact-sheet.jpg`, the batch table and the import file path. The founder approves, imports and switches ads on. The agent never publishes and never changes a live campaign.

## Rules

- Never package a render that failed QA or the proofread; list it under "Not delivered" with the reason.
- Never invent a CTA type, a URL or an ad set: they come from `ads.json`.
- Spend is reported exactly, plates included, re-renders separately.
