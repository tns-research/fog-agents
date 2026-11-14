---
name: writing-seo-briefs
description: Turns the audit into work a writer can execute without the conversation. scripts/write_briefs.py reads bands.json and crawl.jsonl and writes one refresh brief per page (brief.md with the current state quoted from the crawl, the Search Console numbers, a suggested action among update, refine, expand, retarget and merge, the rules of a refresh, and expect.json for the served-HTML check), plus a queue sorted by priority. The model then runs the SERP drift check that confirms or changes the action, lists the exact changes and what not to touch, and keeps a facts ledger as the only source of new facts. New pages get an article brief. A refresh always rewrites the existing URL and file, never a new one. Use at the brief step of seo-audit. Triggers on "brief", "refresh", "rewrite", "update an article", "content plan", "merge pages".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# writing-seo-briefs

The audit is worth what gets shipped from it. This skill writes the hand-off: any writer, human or agent, internal or not, can take a brief, change the page, and hand it back for verification. The method comes from the refresh pipeline used on real sites: three lanes of candidates (close to page 1, dropping, decayed), a SERP drift check, five actions, surgical briefs that keep the URL.

## When to invoke

- After the bands and the crawl of a run exist (`audit` mode, Step 9) or alone (`brief` mode, on the latest run).
- When the founder asks for a refresh of a given page: run the script, then keep only that page's brief.

## Step A: generate the briefs

```bash
python3 scripts/write_briefs.py --bands <run>/bands.json --crawl <run>/crawl.jsonl \
  --out-dir <project>/seo-audit/briefs --date <YYYY-MM-DD> --state <project>/seo-audit/state.json --top 8
```

The script, deterministic:

- picks candidates: merge groups from `cannibalization` (a page is merged only when the shared query is its own main query; a page that only overlaps keeps its intent and links to the survivor; trailing-slash pairs become a technical merge), then every page with a primary band;
- suggests an action and says which rule chose it;
- scores `impressions x (position - 3)`, x1.3 when clicks were lost, and sorts by score divided by effort;
- writes `briefs/<id>/brief.md` from `assets/refresh-brief-template.md`, `briefs/<id>/expect.json`, and `briefs/index-<YYYYMMDD>.md`;
- lists as **blocked** every page that is missing from the crawl or not 200 and indexable there: fix the page first;
- registers each brief as `open` in `state.json` (a second open brief on the same URL is refused).

Done when the index exists and `python3 scripts/check_report.py briefs/*/brief.md --crawl <run>/crawl.jsonl` exits 0.

## Step B: the five actions

| Action | When | What changes | Effort |
|--------|------|--------------|-------:|
| update | intent stable, facts or dates stale | numbers, dates, screenshots, prices; no structural change | 1 |
| refine | positions 4 to 10, weak CTR or thin on-page signals | title, description, internal links in and out, schema, a missing definition; no new section | 1 |
| expand | thinner than what ranks, missing subtopics | sections that fill real gaps of the top 3 with new information (no padding) | 2 |
| retarget | the SERP format or intent shifted, or a better query fits | restructure to the dominant format or re-angle; **same URL** | 2 |
| merge | two URLs of the site compete for one intent | unique content moved to the survivor, 301 from every merged URL, internal links updated | 3 |

## Step C: SERP drift check (the model's part)

For each brief, read the SERP of its target query (`serp-analysis.json` of the run, or `scripts/serp_analyzer.py` for that query alone) and fill the drift table of the brief:

| Dimension | Read from the page (crawl line) | Read from the current SERP | Verdict |
|-----------|---------------------------------|----------------------------|---------|
| Format | listicle, how-to, definition, comparison | dominant format of the top 10 | stable or shifted |
| Depth | words of the raw HTML | median of the top 3 | on par or thin |
| Coverage | H2 list | common H2 of the top 3, People also ask | covered or gaps |
| Schema | JSON-LD types | types in the top 3 served HTML | match or missing |
| Facts | dates, numbers, prices in the body | n/a | current or stale |

Then confirm the suggested action or change it with the reason from the table, and write:

- **Changes (only these):** each change located by its heading, each new fact with its ledger ID.
- **Do NOT touch:** the URL, the slug, the sections that rank (from the top queries of the page), anything not listed.
- For refine: the proposed title and description, through the claims gate ([`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)) and the writing gate. Put the final title in `expect.json` once it is chosen.

Without a SERP provider the drift table says "SERP not read (no provider)" and the action stays the suggested one, labelled unconfirmed.

Done when every brief kept has its drift verdict, its final action, at least one located change and its Do NOT touch list.

## Step D: facts ledger

`<project>/seo-audit/facts-ledger.md` from `assets/facts-ledger-template.md`: every new number, name, date or claim a brief asks for, with its URL and access date. A writer uses nothing else. The published page is the source of truth for its own worked examples: a refresh changes one only with a newer ledger row, and any tool or schema tied to an article is checked against the article's numbers, not against a plan.

## Step E: new pages

When a query has no page of the site in `bands.json` nor in `crawl.jsonl`, write an article brief from `assets/article-brief-template.md`: query, cluster and pillar, what Google shows (date, provider), questions, angle with ledger IDs, what to avoid, the served-page expectations. Never a new page for a query a site URL already receives impressions for: that is a refresh.

## Rules a brief always carries

- Rewrite at the existing URL and in the existing source file; never a new URL, a dated copy or an alternative slug.
- `dateModified` and the visible "updated" date move only for update, expand and retarget.
- No production jargon in the page (`assets/pipeline-jargon.json`): no "target keyword", no "SERP", no brief comment left in the HTML.
- The brief closes only after `verify_served.py` passes on the published URL (skill `verifying-and-tracking`).

## Hand-off

The brief folder is the contract: any writer can execute it (another agent, a freelancer, the founder). Nobody publishes from this skill: publication is the founder's act.
