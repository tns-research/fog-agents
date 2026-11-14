# seo-audit

> The SEO and GEO loop of a founder's site: crawl what is really served, read Search Console with one definition of decline, read the SERP, measure the answer engines on a panel of real questions, write refresh briefs a writer can execute, verify the published page, follow it at 14, 28 and 56 days. Every run starts with what changed since the last one. No paid API required.

**Run when:** once a month, when you run it or schedule it ([`shared/scheduling.md`](../../shared/scheduling.md)), when traffic dips, after a refresh goes live, or to find out whether ChatGPT, Perplexity and Google's AI cite you and who they cite instead.

## How it works

- **Crawl first.** `crawl.py` reads robots.txt, the sitemaps and the served HTML before anything else. The report never quotes a current title or description without its line in `crawl.jsonl`, and `check_report.py` blocks a guessed value. Canonicals to the home page, sitemaps on another host, noindex pages in the sitemap, slash duplicates, invalid JSON-LD and JavaScript shells are found by rule, not by chance.
- **One definition of the bands.** `gsc_bands.py` and `assets/gsc-bands.json` decide declines (with their cause), quick wins (positions 4 to 20), CTR gaps against the site's own curve, lost queries, cannibalization and measurement artifacts, on the API JSON or the UI CSV export in any interface language.
- **A loop, not a snapshot.** `state.json` keeps the runs, the briefs, the ship dates, the verifications and the 14/28/56-day checkpoints; each run writes `since-last-run.md`. Briefs carry the five refresh actions (update, refine, expand, retarget, merge) and always rewrite the existing URL. `verify_served.py` checks the published page (title, canonical, og:url, hreflang, sitemap, JSON-LD, jargon).
- **GEO measured as a panel.** AI crawler access in robots.txt (GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended...), then several draws per question and surface through the `ai_answers` capability, and `geo_panel.py` computes mention rate, citation rate, share of voice and the spread between draws.
- **E-E-A-T measured, not judged.** `eeat.py` reads the crawl: byline, author in the JSON-LD, author page linked, publication and update dates, days since the update, outbound sources, citations, About, Contact, legal and privacy pages, Organization schema, reviews marked up. Each signal carries its evidence; the score comes from the fixed weights of `assets/eeat-weights.json`, so the same crawl gives the same score, and `seo_state.py` lists the signals each page gained or lost since the last run. The model comments, `check_report.py --eeat` blocks a hand rating.
- **Repo mode.** Give the path of the site's source repository and `repo_fix.py` traces each fixable defect (title, description, H1, alt, canonical, JSON-LD author or dateModified, broken internal link) to its file and line, frontmatter included, and writes one patch per file checked by `git apply --check`. Text it cannot know stays a `TODO(seo-audit)` placeholder the model fills in a checked step; a defect without a single source is listed with its candidates. Your repository is never modified.
- **Internal linking.** `links.py` counts the links inside the text of each page apart from the menu, footer and repeated template links, flags orphans, pages reached only from the menu, quick wins with fewer than 3 body links, deep pages, generic or repeated anchors and links through a redirect, then proposes the links to add on words your pages already wrote, matched to the target's Search Console queries, H1, slug and title. For a new article, it lists the existing pages that should link to it. With your repository, each link becomes a line of a patch checked by `git apply --check`.
- **Topic registry.** `topics.py` keeps every live page, brief and draft with its H2 and H3 in `topics.json`. `check` answers new, refresh (with the URL and section to enrich) or duplicate before any brief or article, and `propose` turns Search Console queries without a page, Google autocomplete, People also ask and competitor sitemaps into checked subjects you pick from. No paid call.
- **Write mode.** On the subject you chose, `write_article.py` plans from the H2 and H3 of the top 10, the model drafts in your voice and cuts 15 to 25 % of the words, a gate checks links, coverage, FAQ and banned words, then the article is assembled with its frontmatter and JSON-LD and delivered as a file, or as a patch on your site repository checked by `git apply --check`. `article_visuals.py` renders the cover and three to five body visuals (comparison, steps, checklist, stat, timeline, decision) in HTML, CSS and SVG with your `brand.json` colors, fonts and logo, as PNG on a local Chromium. The article enters the registry as a draft.
- **No interactive stops** except the spend gate (paid SERP or answer-engine calls) and publication, which stays the founder's act.

## What you get

```
<your-projects-root>/<project>/seo-audit/
  runs/<YYYYMMDD>/seo-audit-<YYYYMMDD>.md     the report (template: assets/output-template.md)
  runs/<YYYYMMDD>/crawl.jsonl, eeat.md, bands.md, geo/geo-score.md, since-last-run.md
  runs/<YYYYMMDD>/links/links.md, links/repo/patches/          internal linking (patches in repo mode)
  runs/<YYYYMMDD>/repo-fix/patches/<file>.patch, repo-fix.md   repo mode only
  briefs/index-<YYYYMMDD>.md, briefs/<id>/brief.md + expect.json
  topics.json, runs/<YYYYMMDD>/propose-<YYYYMMDD>.md           topic registry, proposed subjects
  articles/<slug>/article.md, jsonld.json, visuals/*.png, patch/  write mode
  state.json, facts-ledger.md
```

Preview of a run on a fictional site: [`examples/swanbase-example-20261012/`](examples/swanbase-example-20261012/).

## Quick start

Nothing to install (Python 3.9+). To see it work on the fictional test site:

```bash
python3 agents/seo-audit/tests/fixture_server.py --port 8765 &
python3 agents/seo-audit/scripts/crawl.py http://127.0.0.1:8765/ --as-origin https://swanbase.example --out-dir /tmp/seo-run --delay 0
python3 agents/seo-audit/scripts/gsc_bands.py --current agents/seo-audit/tests/fixtures/gsc/api-current.json \
  --prior agents/seo-audit/tests/fixtures/gsc/api-prior.json --site https://swanbase.example --out-dir /tmp/seo-run
cat /tmp/seo-run/bands.md
python3 agents/seo-audit/scripts/eeat.py --crawl /tmp/seo-run/crawl.jsonl --out-dir /tmp/seo-run --today 2026-10-12
cat /tmp/seo-run/eeat.md
```

Repo mode on the fictional larkspur.example site and its mini source repository: run the tests with `--keep /tmp/seo-tests --only repo` and open `/tmp/seo-tests/repo-fix/`.

Then, from your coding agent:

> Run the seo-audit agent at `agents/seo-audit/` for project acme. Domain: https://acme.example/.

Optional, only for the providers you pick:

- **Search Console:** the CSV compare export (Performance > Date > Compare > Export) dropped in `<project>/seo-audit/data/`, no setup; or the API through the `gsc` CLI (https://github.com/the20100/cli-skills), set up once in your own terminal.
- **SERP:** `SERPER_API_KEY` or `SERPAPI_API_KEY`; without one, your coding agent's built-in search (order only).
- **Answer engines:** `PERPLEXITY_API_KEY`, any answer-engine CLI you already use, or paste answers from the prefilled links the agent gives you.

## Inputs

If you ran [`project-context`](../project-context/) first, `domain`, `language`, competitors and the GEO question sources are prefilled.

| Input | Required | Default |
|-------|----------|---------|
| `domain` | yes | project-context `url` |
| `target_queries` | no | 3 to 5 proposed from project-context |
| `period_days` | no | `28` (last 28 days vs the 28 before) |
| `country` | no | `all` (Search Console filter) |
| `serp_country` | no | `country` if a real code, else project-context `geography.country`, else `us` |
| `language` | no | `en` |
| `repo_path` | no | none: fixes are described on the served HTML; with it, patches per source file (repo mode) |
| `crawl`, `geo`, `briefs`, `gsc_bands`, `crawl_rules`, `eeat`, `links`, `topics`, `write` | no | see [`config.example.json`](config.example.json) |

## Tools

Every capability is optional; providers in [`../../shared/tools.md`](../../shared/tools.md). The site itself is always read locally by `crawl.py`.

| Capability | Used for | Without it |
|------------|----------|------------|
| `search_console` | bands, checkpoints, URL inspection | no-traffic mode; checkpoints not measured |
| `serp` | top 10, AI Overview, People also ask, drift checks | built-in search: order only, features Unverified |
| `scrape` | competitor pages | plain HTTP |
| `ai_answers` | GEO panel answers and citations (API, a CLI, or manual capture) | that surface Unverified; crawler access still checked |
| `image_gen` (Local tier) | write mode: article visuals rendered to PNG by a local Chromium through Playwright | HTML pages written, the article ships without body visuals |

## Tests

```bash
python3 agents/seo-audit/tests/run_tests.py
```

Offline (a local test server on 127.0.0.1, fictional data, a fake answer engine, a mini source repository that is never modified; git is used for `git apply --check`). Details: [`scripts/README.md`](scripts/README.md#tests-offline).

## Read more

- Full agent spec: [`AGENT_SEO_AUDIT.md`](./AGENT_SEO_AUDIT.md)
- Scripts, outputs and exit codes: [`scripts/README.md`](./scripts/README.md)
- References and the Google documentation behind the checks: [`references/README.md`](./references/README.md)

## License

Apache 2.0.
