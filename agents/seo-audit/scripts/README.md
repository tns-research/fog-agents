# scripts/

The model reads, decides and writes; these scripts crawl, count, compare, verify and remember. Every script runs alone (`--help`), uses the Python 3.9+ standard library only (`requests` is used when installed, never required; `article_visuals.py` renders with Playwright and Chromium when installed: `pip install playwright pillow && python3 -m playwright install chromium`), makes no paid call unless a spend flag says so, and is deterministic: the same files give the same output. Commands below run from `agents/seo-audit/`.

## The scripts, in workflow order

| Script | Step | Does | Writes |
|--------|------|------|--------|
| `crawl.py` | 1 | robots.txt (obeyed), declared and standard sitemaps, breadth-first crawl up to `--max-pages`; per URL: status, redirect chain, X-Robots-Tag, title, meta description, H1, canonical and its status (self, home, other, other host), meta robots, hreflang, og:url, lang, words of the raw HTML, internal links, JSON-LD parsed; issue codes of `assets/crawl-rules.json`; host and trailing-slash variants; AI crawler access. `--as-origin` audits a local build with production URLs. `--lookup FILE URL` prints a line with its `crawl.jsonl:N` reference. | `crawl.jsonl`, `crawl-summary.json` |
| `eeat.py` | 1 | E-E-A-T signals measured on `crawl.jsonl`, each with its evidence: byline, author in the JSON-LD, author page answering 200, publication and update dates (JSON-LD, meta, `<time>`, visible text), days since the update (`--today`), outbound sources (social networks and own hosts excluded), citations; site: About, Contact, legal, privacy pages, Organization and `sameAs`, reviews marked up, author pages, testimonial blocks. Page score (articles) and site score by the fixed formula of `assets/eeat-weights.json`; same input, same output | `eeat.json`, `eeat.md` |
| `seo_state.py` | 2, 4, verify, track | State between runs: `init`, `record-run` (diff with the previous run, E-E-A-T signals gained and lost per page), `open-brief`, `ship`, `verified`, `drop`, `due`, `track` (14/28/56-day checkpoints from daily rows or two UI exports), `summary`, `show` | `state.json`, `<run>/since-last-run.json` and `.md` |
| `gsc_bands.py` | 3 | The single definition of decline, quick win, CTR gap, lost query, artifact suspect and cannibalization (`assets/gsc-bands.json`), on API JSON or UI CSV exports (English, French, German, Spanish, Italian headers; compare exports) | `bands.json`, `bands.md` |
| `serp_analyzer.py` | 5 | SERP per query (Serper, SerpApi, Firecrawl, or URLs from built-in search) and on-page signals of each result (headings as an outline, each H2 with its H3s, chrome left out; outbound links), parsed with the same parser as the crawl | `serp-analysis.json` |
| `geo_panel.py` | 7 | GEO: `robots` (AI crawler access, Content-Signal, JavaScript-shell pages), `check` the panel, `links` and `template` for manual capture, `run` (Perplexity API or any CLI, behind a spend gate), `import`, `score` (mention rate, citation rate, share of voice, spread between draws, trend) | `ai-access.*`, `answers-<date>.jsonl`, `geo-score.*` |
| `write_briefs.py` | 9 | Refresh briefs from `bands.json` and `crawl.jsonl`: merge groups, suggested action among update, refine, expand, retarget, merge, priority = score / effort, blocked pages listed; registers each brief in the state | `briefs/<id>/brief.md`, `briefs/<id>/expect.json`, `briefs/index-<date>.md` |
| `topics.py` | 1, 6, 9, topics | Topic registry: `build` from `crawl.jsonl` (query from the H1, title, H2, H3 of each content page; home, indexes, legal, contact, tag, pagination, noindex and template headings left out) and the briefs of `state.json`, idempotent; `check "<subject>"` gives new, refresh (URL and H2/H3 section) or duplicate with score and reason (normalized tokens, FR and EN stop words, light stemming, split spellings joined, words weighted by their rarity in the registry from 30 lines on, Jaccard plus substring overlap, link-card headings ignored, a subject several pages touch without owning it flagged broad, thresholds in `assets/topics-rules.json`); `add` records a brief, draft or proposal (a duplicate is refused without `--force`, a draft never overwrites its live line); `propose` turns Search Console queries, Google autocomplete (free endpoint, `--offline`, `--suggest-file`), People also ask of `serp-analysis.json` and competitor sitemaps into checked, grouped and ranked ideas, `--add` records them as proposed; `list` prints the registry | `topics.json`, `propose-<YYYYMMDD>.json` and `.md` |
| `write_article.py` | write | `plan`: registry check (topics.py, else built-in), outline of the top 10 (H2 groups with H3, frequency, sources, must), People also ask, median length, terms, outbound and internal candidates, writing spec; `check`: concision band, outbound and internal links, must H2, FAQ, placeholders, jargon, banned words, long dashes, title and description bounds; `assemble`: mapped frontmatter (default, astro, hugo, eleventy, next presets), visuals after their H2, validated JSON-LD (Article, FAQPage, BreadcrumbList); `patch`: article and images in one patch checked by `git apply --check`, repository never written; `register`: draft line in `topics.json`. Never writes prose | `articles/<slug>/outline.json`, `spec.md`, `check.json`, `article.md`, `jsonld.json`, `patch/article.patch` |
| `article_visuals.py` | write | Cover (1200x630) and body visuals (comparison, steps, checklist, stat, timeline, decision; 1200 wide) from the model's `visuals-spec.json` (`assets/visuals-spec.schema.json`) and `brand.json`: HTML, CSS and inline SVG templates of `assets/visuals/`, colour roles with the fallbacks of `shared/schemas/README.md`, local font files (a Google Fonts family without files is downloaded into `_src/fonts-cache/` through `shared/scripts/fetch_fonts.py`, `--no-font-fetch` to stay offline), logo variant by `mode`. PNG through local Chromium, optional standalone SVG for cover, stat, steps, checklist and comparison. Checks: spec rules, WCAG contrast of the brand roles (BLOCK under 3:1), DOM overflow and minimum text size after the fit, brand font loaded, cover size, PNG weight, flat bands. `qa` re-checks a folder. Never writes text | `visuals/*.png`, `visuals/*.svg`, `visuals/visuals.json`, `visuals/visuals-qa.json`, `visuals/_src/` |
| `check_report.py` | 10 | Gate: every current title, description or H1 in the report or a brief cites its `crawl.jsonl:N` line and matches it; guessed values block; with `--eeat`, the E-E-A-T site score and page scores equal `eeat.json` and a hand rating ("Expertise 2/4") blocks | stdout, `--json` |
| `repo_fix.py` | 8.R (repo mode) | `plan`: each fixable defect of the crawl and of the E-E-A-T rules (title missing or long, description missing, H1 missing or multiple, img without alt, canonical missing, JSON-LD dateModified or author missing, broken internal link) traced to its source file and line (route of the file, frontmatter, layout, imports; page scope first, then the repository), one unified patch per file checked by `git apply --check` on a temporary copy, placeholders `TODO(seo-audit) pNN` for text it cannot know, ambiguous or unfound defects listed by hand with candidates; `fill` rebuilds the patches with the values of `fills.json` (`null` drops a fix); `check` blocks a placeholder left, a value out of bounds, a URL that is not a 200 page of the crawl, a patch that no longer applies. Never writes the repository | `repo-fix/patches/*.patch`, `repo-fix.json`, `repo-fix.md`, `fills.json` |
| `links.py` | 6.L, write W4.L, 8.R | `audit`: link graph of the crawl, body links apart from nav, header, footer, aside and template links (same anchor on 30 % of the pages of a language); orphans, menu-only pages, quick wins and new pages under 3 body inlinks, deep pages, generic and repeated anchors, links through a redirect or to an error page, dead ends; links to add on phrases the source page already wrote (target's Search Console queries, H1, slug, title; keyword and H1 of a `--new-page`), same language, outside existing links and punctuation, capped per source, paragraph and target; `patch`: each kept link wrapped on its single source line (Markdown link in .md and .mdx, `<a href>` elsewhere), redirect hrefs replaced by the final URL, one patch per file checked by `git apply --check`, the rest listed by hand. Never writes prose nor the repository | `links/links.json`, `links.md`, `repo/patches/*.patch`, `links-patch.json`, `links-patch.md` |
| `verify_served.py` | verify | The published page against its `expect.json`: status 200 at the URL, indexable, robots.txt, title, canonical, og:url, hreflang, sitemap of the same host, JSON-LD valid with the expected types, no production jargon (`assets/pipeline-jargon.json`), merged URLs 301 to it, optional internal links | stdout, `--out verify.json` |
| `seo_lib.py` | | Shared helpers: fetch with the redirect chain, HTML parser, robots.txt (most specific group, longest match), sitemaps, Search Console loaders. Not a command. | |

## serp_analyzer.py providers

Every provider is optional; keys are read from the environment and never printed.

| Capability | Provider (in `auto` order) | Key | Without it |
|------------|---------------------------|-----|------------|
| `serp` | Serper | `SERPER_API_KEY` | next provider |
| `serp` | SerpApi | `SERPAPI_API_KEY` | next provider |
| `serp` | URLs from built-in web search or the founder (`--organic-file`, `{"query": ["url", ...]}`) | none | AI Overview, People also ask and featured snippet Unverified |
| `serp` | Firecrawl scrape of the Google page | `FIRECRAWL_API_KEY` | organic order not parsed |
| `scrape` | Firecrawl, then Jina Reader (keyless), then plain HTTP | optional | a page no provider fetches keeps its SERP title, signals Unverified |

Spend gate in code: when the resolved chains hold Serper, SerpApi or Firecrawl, `serp_analyzer.py` sends nothing without `--confirm-spend` (or `FOG_ALLOW_SPEND=1` for a scripted run). It prints the planned calls (up to one SERP call per query, up to 10 Firecrawl scrapes per query) and exits 1, like `geo_panel.py run`. The agent adds the flag only after the founder's yes at Step 0. Without the flag, Jina Reader runs keyless. Only `http` and `https` URLs are fetched, redirects included.

`--country` is Google's `gl`, a country: `all`-like values fall back to `--fallback-country` (default `us`), and a language code passed as a country (`en`) is mapped to a country (`us`) with a warning, because `gl=en` is rejected. Queries run one after the other (parallel calls returned off-topic results from a provider cache): read the titles of each SERP before analysing it. Each paid SERP call counts against the spend announced at Step 0.

## Single sources

| File | Read by | Holds |
|------|---------|-------|
| `assets/gsc-bands.json` | `gsc_bands.py`, `write_briefs.py`, `seo_state.py` | band thresholds, priority order, tracking checkpoints and outcome thresholds |
| `assets/crawl-rules.json` | `crawl.py`, `repo_fix.py` | issue codes, severities, length conventions (also the bounds of the filled titles and descriptions) |
| `assets/eeat-weights.json` | `eeat.py`, `repo_fix.py` | E-E-A-T signals, weights, caps, freshness bands, page and site formula, article detection, site page names, social domains |
| `assets/ai-crawlers.json` | `crawl.py`, `geo_panel.py` | AI user agents with operator, purpose and documentation URL |
| `assets/pipeline-jargon.json` | `verify_served.py` | words and tokens that must never reach a published page |
| `assets/refresh-brief-template.md` | `write_briefs.py` | the brief format |
| `assets/link-rules.json` | `links.py` | phrase lengths, Search Console minimums, quick-win positions, caps per source, paragraph and target, template-link share, anchor diversity, weights, generic anchors in English and French, skipped paths |
| `assets/topics-rules.json` | `topics.py` | similarity thresholds (duplicate, refresh, section, cluster), stop words, stemming suffixes, ignored headings, excluded paths, propose caps and priority weights |
| `assets/write-rules.json` | `write_article.py` | concision band, link counts, outline grouping and must threshold, FAQ patterns, placeholders, assemble defaults, frontmatter presets |
| `assets/visuals-spec.schema.json`, `assets/visuals-manifest.schema.json`, `assets/visuals/` | `article_visuals.py`, `write_article.py` | visuals spec and `visuals.json` contracts, templates per kind |

A project overrides thresholds with `gsc_bands`, `crawl_rules`, `eeat`, `links`, `topics` and `write` objects in its `config.json` (`--config`).

## Example run

```bash
RUN=<project>/seo-audit/runs/20261012
python3 scripts/crawl.py https://acme.example/ --out-dir $RUN
python3 scripts/eeat.py --crawl $RUN/crawl.jsonl --out-dir $RUN --today 2026-10-12
python3 scripts/seo_state.py init --state <project>/seo-audit/state.json --project acme --domain https://acme.example/
python3 scripts/seo_state.py record-run --state <project>/seo-audit/state.json --run-dir $RUN
python3 scripts/gsc_bands.py --current <project>/seo-audit/data/gsc-current.json --prior <project>/seo-audit/data/gsc-prior.json --site https://acme.example --out-dir $RUN
python3 scripts/geo_panel.py robots --site https://acme.example --crawl $RUN/crawl.jsonl --out-dir $RUN/geo
python3 scripts/write_briefs.py --bands $RUN/bands.json --crawl $RUN/crawl.jsonl --out-dir <project>/seo-audit/briefs --state <project>/seo-audit/state.json
python3 scripts/check_report.py $RUN/seo-audit-20261012.md <project>/seo-audit/briefs/*/brief.md --crawl $RUN/crawl.jsonl --eeat $RUN/eeat.json
# repo mode, only with the site's source repository
python3 scripts/repo_fix.py plan --crawl $RUN/crawl.jsonl --repo <site-repo> --out-dir $RUN/repo-fix
python3 scripts/repo_fix.py fill --out-dir $RUN/repo-fix --fills $RUN/repo-fix/fills.json
python3 scripts/repo_fix.py check --out-dir $RUN/repo-fix
# internal linking (patch only with the repository)
python3 scripts/links.py audit --crawl $RUN/crawl.jsonl --bands $RUN/bands.json --out-dir $RUN/links
python3 scripts/links.py patch --out-dir $RUN/links --repo <site-repo>
```

To try it on the fictional test site: `python3 tests/fixture_server.py --port 8765`, then crawl `http://127.0.0.1:8765/` with `--as-origin https://swanbase.example`.

## Tests (offline)

```bash
python3 agents/seo-audit/tests/run_tests.py        # from the repo root; -v lists every check, --keep DIR keeps the outputs
```

No network beyond 127.0.0.1, no API key, outputs in a temporary folder. The fictional site `swanbase.example` (`tests/fixtures/site/`, served by `tests/fixture_server.py` with exact statuses and headers) carries the defects the crawl must find; `routes-fixed.json` is the same site after a refresh shipped. It runs:

- the parser (meta attributes in any order, apostrophes, JSON-LD arrays and `@graph`, invalid blocks), robots.txt groups and longest match, sitemap indexes, Search Console CSV in English and French and compare exports;
- the crawl of the fixture: every planted defect found, lookup, determinism, exit codes;
- the bands on fictional API and CSV exports: decline with its cause, lost, quick win, CTR gap, artifact, cannibalization with slash variants, threshold override, missing prior period;
- the report gate on a report excerpt with guessed current titles (`tests/fixtures/regression-20260428/`): they block;
- briefs, expect files, the served-HTML check before (fails on og:url, sitemap host, jargon) and after the fix (passes), merge redirects, noindex, wrong title;
- state: ship, verify, due windows, tracking at 14 and 28 days from daily rows, 56 days from two UI exports, outcomes per action, diff between two runs;
- the GEO panel: spend gate, a fake answer engine (`tests/fixtures/geo/fake_answers.py`), manual capture import, rates, share of voice, spread between draws, Unverified surface, trend, links and template, AI crawler access;
- E-E-A-T on the fictional `larkspur.example` (`tests/fixtures/eeat-site/`): bylines, `@id` authors, dated phrases in two languages, a strong and a weak article, site signals, the formula, determinism, `--today`, a weight override, the report gate on scores and hand ratings, signals gained and lost on the next run (`routes-after.json`);
- repo mode on its mini source repository (`tests/fixtures/eeat-repo/`: Markdown with frontmatter, Astro layouts, a JSX and a Vue component): every defect at its file and line, a shared footer link fixed once for every page, an ambiguous image and a page without source listed by hand, no invented text, no line insertion into markup written on one line, `git apply --check`, fill and check (404 URL, bounds, quote, placeholder left), patches applied on a copy, the repository left untouched;
- the topic registry on the fictional `fernhill.example` (`tests/test_topics.py`): H2 and H3 in the crawl, build (pages left out, query from the H1, template headings dropped, briefs of the state, idempotence), check (duplicate of a live page and of a brief, refresh in an H2 and an H3, French stemming and accents, threshold override), add, propose offline (convergence ranking, duplicates and brand queries set aside, a to z expansion, no registry change without `--add`, determinism), a served competitor with `--fetch-titles`;
- the write mode on the fictional `fernhollow.example` (`tests/test_write.py`): H2 and H3 outline of a competitor page, plan (must groups, questions, median, link candidates, determinism), duplicate refused and forced, refresh of a live section, check on a passing and a blocking final, assemble (frontmatter presets, visuals, JSON-LD parsed, html), patch on a mini repository (binary images, `git apply --check`, repository untouched), register;
- article visuals on the fictional `larkspur.example` brand (`tests/test_visuals.py`): spec rules, brand roles and fallbacks, logo variant by mode, the contrast gate, HTML without remote asset, determinism, SVG parsing, `visuals.json` against its schema, `qa`; with Playwright, a real render (cover 2400x1260 at scale 2, overflow caught), otherwise those checks are counted as skipped;
- internal linking on the fictional `fernwood.example` (`tests/test_links.py`): link graph defects and links to add on a served site with its Search Console bands, patches of a mini Astro repository checked by `git apply --check`, the repository copied, never modified;
- the SERP extractor; `--help` of every script; no dash characters; the example regenerates byte for byte.

Each of `tests/test_topics.py`, `test_write.py`, `test_visuals.py` and `test_links.py` also runs alone. Expected last line: `N passed, 0 failed` (458 passed without Playwright, where the real render checks are skipped, not counted). Also run, from the repo root, `python3 scripts/validate_stack.py`.

## Exit codes

`topics.py`: 0 done (`check` always 0 on a readable registry), 1 `add` refused (duplicate without `--force`, live without URL), 2 usage or unreadable input. `write_article.py`: 0 done; 1 refused (duplicate topic, BLOCK in check, check not passed on the current final.md, invalid JSON-LD, visual without its H2, patch failing `git apply --check`, destination conflict, git missing); 2 usage or unreadable input. `article_visuals.py`: 0 written and no BLOCK, 1 at least one BLOCK or the renderer missing or failed (HTML still written), 2 usage, invalid spec or unreadable brand.json; `qa` 0 clean, 1 BLOCK, 2 unreadable `visuals.json`.

`crawl.py`: 0 written, 1 start URL not 200 HTML, 2 usage. `gsc_bands.py`, `write_briefs.py`: 0 written, 2 unreadable input. `check_report.py`: 0 clean, 1 at least one BLOCK, 2 unreadable. `verify_served.py`: 0 every check passes, 1 a check failed, 2 usage or page unreachable. `eeat.py`: 0 written, 2 unreadable input. `repo_fix.py`: `plan` and `fill` 0 written, 1 a patch failed `git apply --check` or git is missing, `check` 0 clean, 1 at least one BLOCK, 2 usage or unreadable input. `seo_state.py`: 0 done, 1 refused (unknown id, wrong status, data not covering a window, failed verification recorded), 2 usage. `geo_panel.py`: 0 done, 1 spend gate closed, `check` errors or every call failed, 2 usage or invalid panel. `serp_analyzer.py`: 0 written (read `_warnings`), 1 spend gate closed (nothing sent, nothing written), 2 bad input.

## Cross-platform notes

Forward slashes only. Works the same on macOS, Linux and Windows (use `python` instead of `python3` if that is how Python is installed).
