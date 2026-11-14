---
name: crawling-own-site
description: Crawls the audited site locally before anything else (robots.txt obeyed, declared and standard sitemaps, breadth-first from the home page up to a page cap) with scripts/crawl.py, and turns the served HTML into crawl.jsonl (one line per URL with status, redirect chain, title, meta description, H1, canonical, robots, hreflang, og:url, words of the raw HTML, internal links, parsed JSON-LD, E-E-A-T evidence) plus crawl-summary.json (issues with severity, sitemaps, AI crawler access, host and slash variants), then scores E-E-A-T on it with scripts/eeat.py. Every later statement about a page's current state cites its crawl line. Use at Step 1 of every seo-audit run and whenever a page's current title, description, canonical or schema is needed. Triggers on "crawl", "current title", "canonical", "sitemap", "noindex", "duplicate", "technical SEO".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# crawling-own-site

A title rewrite proposed for a page that was never fetched rests on a guess ("Current title (likely)"). The defects that cost founders the most (a canonical pointing at the home page, a sitemap declared on another domain, a noindex page in the sitemap, a slash duplicate, a JavaScript shell that crawlers see empty) only show in the served HTML. This skill reads it first, with a script, and every later step quotes it.

## When to invoke

- Step 1 of every run, before Search Console and the SERP.
- Before writing any current title, description, H1, canonical or schema type in a report or a brief.
- On a local build or staging copy before deployment (`--as-origin`).

## Step A: run the crawl

```bash
python3 scripts/crawl.py https://acme.example/ --out-dir <project>/seo-audit/runs/<YYYYMMDD>/
```

- Start URL: the home page of `domain` (config `crawl.start_url` overrides it).
- `--max-pages` (config `crawl.max_pages`, default 200). URLs left over are listed in `crawl-summary.json` (`not_crawled_due_to_cap`): say so in Limitations.
- robots.txt is obeyed for the crawler's own token; a larger `Crawl-delay` wins over `--delay` (capped at 5 s). `--ignore-robots` exists only for the founder's own staging copy.
- `--as-origin https://acme.example` with a local start URL (`http://127.0.0.1:4321/`) audits a build before it ships, with production URLs in every output.
- Exit 1 means the start URL did not answer 200 HTML: stop the technical part, report the status and the redirect chain from `crawl.jsonl` line 1, continue with Search Console and the SERP.

Then measure E-E-A-T on the same crawl (no fetch, the evidence is in the `eeat_raw` field of each line):

```bash
python3 scripts/eeat.py --crawl <run>/crawl.jsonl --out-dir <run> --today <YYYY-MM-DD>
```

`--today` is the run date: the days since the last update depend on it, and the same crawl with the same date gives the same `eeat.json`. The score is the fixed formula of `assets/eeat-weights.json`; the model comments it (`assets/eeat-audit-checklist.md`) and never rates a page.

Done when `crawl.jsonl`, `crawl-summary.json` and `eeat.json` exist and the crawl exited 0 (or 1 is reported as the first blocker).

## Step B: read the issues

`crawl-summary.json` → `issues` lists every code with its severity, count and up to 20 example URLs; codes and severities live in `assets/crawl-rules.json`. Read errors first:

| Code | What it means for the founder |
|------|-------------------------------|
| `canonical-home`, `canonical-other-host`, `canonical-multiple` | Google is told this page is a copy of another URL: it will not rank it |
| `sitemap-other-host`, `sitemap-noindex`, `sitemap-non-200`, `sitemap-redirect` | the sitemap contradicts the pages it lists |
| `slash-duplicate`, `host-variant-not-redirected` | two URLs serve the same page: signals split between them |
| `status-4xx` with `broken-internal-link` on the source page | the site links to dead pages (`broken_links` names source and target) |
| `jsonld-invalid` | a JSON-LD block does not parse: every type in it is lost |
| `thin-raw-html` | almost no text without JavaScript: crawlers that do not run it (several AI crawlers among them) see an empty page |
| `noindex`, `blocked-by-robots` | deliberate or not: check with the founder's intent in the report |
| `og-url-mismatch`, `hreflang-*` | tags built from an environment variable often point at the wrong host |

Length codes (`title-long`, `description-length`) are info only: display truncation depends on pixel width, not on a character count.

Done when every error and warning code is either in the technical blockers table of the report or explained as deliberate.

## Step C: quote the crawl, never memory

Every current value quoted in a report or a brief carries the crawl line it comes from, in this form:

```
**Current title:** `Pricing | Acme` (crawl.jsonl:12)
```

Get the line with:

```bash
python3 scripts/crawl.py --lookup <run>/crawl.jsonl https://acme.example/pricing/
```

A URL that is not in the crawl is crawled (a second run with `--max-pages` raised, or the URL as start URL in another folder) or left out. `scripts/check_report.py` blocks any current title, description or H1 without its line, with a guessed value, or that differs from the line.

## Step D (optional): from the served defect to the source file

With `repo_path` in the config (repo mode), run `scripts/repo_fix.py` after `scripts/eeat.py`:

```bash
python3 scripts/repo_fix.py plan --crawl <run>/crawl.jsonl --repo <repo_path> --out-dir <run>/repo-fix
```

It traces each fixable defect (title missing or too long, description missing, H1 missing or multiple, img without alt, canonical missing, JSON-LD dateModified or author missing, broken internal link) to its source line: the file whose path maps to the URL or whose frontmatter slug or permalink does, then its layout and imported components, then the whole repository. One location gives a patch per file, checked by `git apply --check` on a temporary copy; zero or several give a "to locate by hand" item with the candidates. The repository is read, never written.

The script invents no text. Fill `<run>/repo-fix/fills.json` (title within the budget the layout leaves, description within the bounds of `assets/crawl-rules.json`, alt text describing the image, a URL that answers 200 in the crawl, a JSON-LD value taken from the project, never an invented author or date; `null` drops the fix), through the claims gate, then:

```bash
python3 scripts/repo_fix.py fill --out-dir <run>/repo-fix --fills <run>/repo-fix/fills.json
python3 scripts/repo_fix.py check --out-dir <run>/repo-fix
```

`check` exits 0 before the patches go into the report. Defects the script does not handle (a layout that forces `canonical: '/'`, a `SITE_URL` that falls back to another domain, a robots.txt left on an example domain, a sanitizer that strips JSON-LD) are located by reading the code and proposed as a diff in the report, never applied. Without `repo_path`, the fix is described on the served HTML.

## Anti-patterns to refuse

- Writing a current title from the SERP snippet or from memory: Google rewrites snippets, memory is not a source.
- Auditing the source code instead of the served HTML: a correct template with a wrong environment variable serves wrong tags.
- Recommending `priority` or `changefreq` changes in the sitemap: Google ignores them (`assets/sitemap-probe-checklist.md`).
- Treating every `noindex` as a bug: apply, legal or thank-you pages are often noindex on purpose. A noindex page listed in the sitemap is the bug.
