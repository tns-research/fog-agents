---
name: managing-topic-registry
description: Keeps the topic registry of the site (<project>/seo-audit/topics.json), one line per subject the site covers or plans, and gates every new subject through it. scripts/topics.py builds the registry from the crawl (query from the H1, title, H2 and H3 of each content page) and the briefs of state.json, answers check "<subject>" with new, refresh (the URL and the section to enrich) or duplicate (the URL or brief that already treats it), records briefs, drafts and proposals with add, and proposes new topics from free sources (Search Console queries without a page, Google autocomplete, People also ask, competitor sitemaps), each one checked, for the founder to pick. Use at Steps 6 and 9 of seo-audit, in topics mode, and before any brief or article. Triggers on "topic ideas", "what should we write", "already covered", "duplicate article", "cannibalization", "content gap", "topic registry".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# managing-topic-registry

A site loses more to the article written twice than to the article never written: two pages split the impressions of one query, and the second costs as much as the first. The registry is the memory that prevents it. Search Console only sees a duplicate once both pages get impressions; the registry sees it before the brief, including when the subject lives in an H2 of another article that has no impression on it yet.

The script compares, counts and records. The model reads the verdicts, explains them to the founder and writes. The founder chooses the subjects.

## The registry

`<project>/seo-audit/topics.json`, one line per subject:

| Field | Holds |
|-------|-------|
| `id` | `t-<slug>`, stable across runs |
| `query` | main query, normalized (lowercase, accents kept, punctuation removed) |
| `aliases` | variants: the title when it differs from the H1, the top Search Console query of the page, queries added later |
| `url` | the page; `null` for a proposal and for the brief of a new article |
| `status` | `live`, `brief`, `draft`, `proposed`, `dropped` |
| `source` | `crawl`, `brief`, `write`, `propose` |
| `title`, `h2`, `h3` | H1 (or title) and outline of the page or the draft |
| `brief_id` | the open brief of `state.json` on that line |

One `live` line per URL. A refresh never adds a line: its brief or draft is recorded on the live line (`brief_id`, `notes`).

## When to build it

- Every audit run, right after the crawl (Step 1) and before the topic map (Step 6):

  ```bash
  python3 scripts/topics.py build --registry <project>/seo-audit/topics.json --crawl R/crawl.jsonl \
    --state <project>/seo-audit/state.json --bands R/bands.json --today <YYYY-MM-DD>
  ```

  `--bands` is optional (it adds the top Search Console query of each page as an alias). The build is idempotent: the same crawl gives the same file. A page that now redirects, answers an error or turned noindex becomes `dropped`; a page missing from the crawl (page cap) is left as it was.
- In `topics` mode or `write` mode when the registry is older than the latest crawl: build again on the latest run first.
- The crawl must hold `h2` and `h3` (crawl.py writes them). An older crawl without them still builds, with empty outlines: crawl again before trusting a `new` verdict.

Pages left out on purpose: home and language roots, section indexes (`/blog/`), tag, category, author and pagination pages, legal, privacy and contact pages, noindex pages, pages whose canonical points elsewhere, redirects, headings repeated on most pages (footer, newsletter box) and generic headings (FAQ, Sources, Conclusion). Thresholds and lists: `assets/topics-rules.json`, overridden by a `topics` object in the project config.

## Every subject goes through check

Before any brief, outline or article, and for every idea shown to the founder:

```bash
python3 scripts/topics.py check --registry <project>/seo-audit/topics.json "<subject>" --json
```

Several at once (the H2 plan of a draft, a list of ideas): `--subjects-file F --json`, one subject per line.

| Verdict | Means | Do |
|---------|-------|----|
| `duplicate` | the subject is the main subject of a live page, a brief or a draft (`url` or `topic_id`) | no new page. Open or extend a refresh brief on that URL, or continue that brief or draft |
| `refresh` with `section` | the subject is treated in that H2 or H3 of the page at `url` | enrich that section (expand action), or give it its own section there; a new page would compete with it |
| `refresh` without `section` | close to the main subject of the page at `url`, not the same | expand or retarget that page; a new page only if the SERP shows a different intent, and the founder agrees, written in the brief |
| `new` | no line is close enough | brief or write it; `already_proposed` names the proposal line to move forward |

A `new` verdict with a `broad` list means several pages touch the subject and none owns it: offer a pillar page that links to them, or a refresh of the closest one, and let the founder choose. The score is lexical: synonyms (`installer` and `ajouter`, `prix` and `pricing`) and two languages stay apart, so read the `nearest` lines of every `new` before calling it a gap.

Read `score`, `reason` and `nearest` before saying anything: a `new` at 0.52 next to a refresh threshold of 0.55 is worth one sentence to the founder ("close to `<url>`, kept apart because ..."). Never override a verdict silently; when the model disagrees (a different intent the score cannot see), say why in the brief and in the report.

Then record the decision, so the next check sees it:

```bash
python3 scripts/topics.py add --registry <project>/seo-audit/topics.json --query "<subject>" --status brief --brief-id <id>
python3 scripts/topics.py add --registry <project>/seo-audit/topics.json --query "<subject>" --status draft --source write \
  --url <planned URL> --h2-file <draft>.md --title "<H1>"
```

`--h2-file` reads the `##` and `###` lines of a Markdown draft (or a JSON list, or one heading per line). A new line that `check` calls a duplicate is refused (exit 1); `--force` exists for a decision the founder took, written in the notes.

## Proposing topics

`topics` mode, or the article briefs of Step 9 when the founder has no subject in mind:

```bash
python3 scripts/topics.py propose --registry <project>/seo-audit/topics.json --out-dir R \
  --bands R/bands.json --serp R/serp-analysis.json --config <project>/seo-audit/config.json --today <YYYY-MM-DD>
```

Sources, each optional, all free:

- **Search Console**: queries of `bands.json` or of exports (`--gsc`, API JSON or UI CSV) with enough impressions; brand queries are set aside.
- **Autocomplete**: Google's public suggest endpoint from `--seed` (repeatable, default `target_queries`), `--expand` adds the letters a to z. Network: `--offline` turns it off, `--suggest-file` reads saved answers.
- **People also ask**: read from the `serp-analysis.json` of the run, no new SERP call.
- **Competitor sitemaps**: `--competitor` (default `competitors` of the config, then the domains of `geo.competitors`) or `--competitor-sitemap`; article URLs become subjects from their slug, or from the page H1 with `--fetch-titles` (plain HTTP, capped). News and press slugs are dropped.

Each idea is checked; similar ideas are grouped (variants listed); duplicates are set aside with the URL that covers them; `new` and `refresh` are ranked by a priority written out per line (sources that converge, Search Console impressions, competitors). Output: `R/propose-<YYYYMMDD>.json` and `.md`. Without `--add` the registry is not touched.

## Presenting the proposals to the founder

The founder picks; the agent never starts a brief or an article from a proposal on its own.

1. Show the table of `propose-<YYYYMMDD>.md` as is (topic, verdict, where, sources, priority, why), 10 lines at most, `new` and `refresh` together: a refresh is often the cheaper win.
2. For each line, one sentence at most from the evidence: the Search Console numbers, the seeds or the competitor URL. No invented volume, no difficulty score the run did not measure.
3. Say what was set aside (duplicates with their URL, brand queries) in one line, so the founder sees the gate worked.
4. Ask which ones to keep. Record the picks with `add --status proposed` (or run `propose --add` when the founder keeps the whole list), the refused ones with `add --status dropped --notes "<reason>"` so they are not proposed again as new.
5. A picked `refresh` becomes a refresh brief on its URL (Step 9, five actions); a picked `new` becomes an article brief. Check it again just before the brief: the registry may have moved since.

## Failure modes

- **`check` exits 2** → the registry does not exist yet: run `build` on the latest crawl.
- **Everything is `new` on a site with a blog** → the crawl has no `h2`/`h3` (old crawl) or the articles are JavaScript shells (`thin-raw-html` in the crawl): crawl again, or add the outlines by hand with `add --h2-file`.
- **A live page reads as `dropped`** → its URL redirected, broke or turned noindex in this crawl: report it as a technical blocker, the line comes back to `live` when the page does.
- **Autocomplete returns nothing** → the endpoint blocked the box or the run is offline: the source is marked `skipped` or empty in the output, the other sources still count.
- **A competitor has no sitemap** → its line says so; ask the founder for its sitemap URL or skip it.
