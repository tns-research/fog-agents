---
name: analyzing-serp-competition
description: Fetches the live SERP for each target query through the resolved serp provider (Serper by default, SerpApi as an alternative, a Firecrawl scrape of the Google page as a last API resort, result URLs from the host agent's built-in web search in degraded mode), captures the top 10 organic results plus AI Overview, People also ask and featured snippet when the provider returns them, then fetches each top-10 URL through the resolved scrape provider (Firecrawl, keyless Jina Reader, plain HTTP) to extract on-page signals (title, meta, H1, H2 and H3 outline, word count, schema types, authors, dates, outbound links). The model then classifies the intent (informational / commercial / transactional / navigational) and the dominant content type per query. The output is a per-query competitive map that drives intent-gap analysis. Features the provider did not return are marked Unverified, never guessed. Triggers on words like "SERP", "top 10", "competitor pages", "intent gap", "PAA", "Serper".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# analyzing-serp-competition

The competitive-mapping layer. Once `analyzing-gsc-data` has identified priority queries (low-hanging, decay, lost), this skill maps the live SERP for each so the agent can answer: *what does Google currently consider the right answer for this query, and where is the user's page positioned within that consensus?*

The script that pairs with this skill is `scripts/serp_analyzer.py`.

---

## When to invoke

- Step 5 of the agent workflow: after GSC priorities are known, fetch each top-10 SERP.
- Per-query refresh: when a single high-stakes query needs deeper SERP analysis without re-running the whole audit.
- Before writing title/meta rewrites: the SERP is the source of "what wording Google currently rewards".

---

## Inputs

- `target_queries`: list from agent input PLUS top-N priorities from GSC analysis (typically 5 to 15 queries total).
- `serp_country`: two-letter ISO code, lowercase (`us`, `fr`). Never `all`: a SERP is always fetched for one country. Resolved by the agent Step 0: `serp_country` from config, else `country` when it is a real code, else `geography.country` from `project-context`, else `us`. Per-country SERPs differ, score the SERP in the user's country.
- `language`: Google's `hl` parameter (`--language`, e.g. `en`, `fr`); `gl` comes from `serp_country` (`--country`).

---

## Providers

Two capabilities, resolved at the agent's Step 0 ([`../../../../shared/tools.md`](../../../../shared/tools.md)):

| Capability | Tier | Provider | SERP features returned |
|------------|------|----------|------------------------|
| `serp` | API | Serper (default, `SERPER_API_KEY`) | organic, AI Overview, PAA, featured snippet |
| `serp` | API | SerpApi (`SERPAPI_API_KEY`) | organic, AI Overview, PAA, featured snippet |
| `serp` | API | Firecrawl scrape of the Google page (`FIRECRAWL_API_KEY`, last resort) | raw page only: organic order not parsed |
| `serp` | Built-in | host web search, or the ordered URLs of any other SERP tool (DataForSEO has no adapter in the script), through `--organic-file` | organic order only: AI Overview, PAA, featured snippet Unverified |
| `serp` | Manual | founder pastes the first page of results or a screenshot | what the paste shows |
| `scrape` | API | Firecrawl (`FIRECRAWL_API_KEY`) | n/a |
| `scrape` | API | Jina Reader, keyless (`JINA_API_KEY` raises the rate) | n/a |
| `scrape` | Local | plain HTTP with a browser user agent (inside the script) | n/a, no JavaScript rendering |

`scripts/serp_analyzer.py` implements both chains (`--serp-provider`, `--scrape-provider`, both `auto` by default) and records the provider used per query and per page, for the report's Methodology. Serper, SerpApi and Firecrawl bill per call: when the chain holds one of them, the script sends nothing without `--confirm-spend` (exit 1, planned calls printed). Pass the flag only after the founder's yes at the Step 0 spend gate; otherwise use `--serp-provider file --organic-file <urls.json> --scrape-provider jina`.

---

## Step A: Fetch the SERP (`serp`)

Default provider shown: Serper, whose response exposes AI Overview data, useful for the GEO/AEO audit downstream. Free tier: 2500 queries/month. SerpApi (`GET https://serpapi.com/search.json?engine=google&q=...&gl=...&hl=...`) returns the same fields under `organic_results`, `ai_overview`, `related_questions`, `answer_box`.

```bash
curl -X POST "https://google.serper.dev/search" \
  -H "X-API-KEY: $SERPER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "<target_query>",
    "gl": "<serp_country>",
    "hl": "<language>",
    "num": 10
  }' > /tmp/serper-<n>.json
```

The response contains:
- `organic`: top organic results (URL, title, snippet, position).
- `answerBox`: featured snippet if present.
- `peopleAlsoAsk`: PAA questions.
- `aiOverview` (when present): AI Overview text + cited sources.
- `relatedSearches`: bottom-of-page suggestions.
- `knowledgeGraph`: entity panel if present.

### Without a SERP API: built-in search or pasted results

1. Run the host agent's web search for each query (set to the `serp_country` locale when the tool allows it) and keep the ordered result URLs. Or use the first page of results the founder pasted in answer to the agent's Step 0 message.
2. Write them to `/tmp/organic.json` as `{"<query>": ["url1", "url2", ...]}` and run `serp_analyzer.py --serp-provider file --organic-file /tmp/organic.json --scrape-provider jina` so the page signals of Step B are still extracted at no cost (`--scrape-provider auto --confirm-spend` instead when the founder agreed to Firecrawl scrapes).
3. Mark AI Overview, PAA and featured snippet **Unverified** for these queries (the script sets `status: unverified`). Built-in search results are not a Google SERP in the target country: say so in Limitations.

A Firecrawl scrape of the Google results page (`--serp-provider firecrawl`) is a last API resort: organic order is not parsed and AI Overview text is captured intermittently. Document it in the report when used.

---

## Step B: Crawl each top-10 URL (`scrape`)

The site's own page is never scraped here: its signals come from `crawl.jsonl` of the run (cite the line). Competitor pages are read by `serp_analyzer.py`, which parses their HTML with the same parser as `crawl.py`, so word counts and schema types compare.

For each top-10 organic result, fetch the page with the resolved `scrape` provider. Examples:

```bash
firecrawl scrape "<url>" --format markdown --only-main-content > /tmp/page-<n>.md   # Firecrawl (default when the key is set)
curl -s -H "X-Return-Format: html" "https://r.jina.ai/<url>" > /tmp/page-<n>.html   # Jina Reader, keyless
curl -sL -A "Mozilla/5.0" "<url>" > /tmp/page-<n>.html                              # plain HTTP
```

Title, meta and schema live in the HTML head: prefer an HTML format. A page no provider can fetch keeps its SERP title and snippet, with its on-page signals marked Unverified.

From each page, extract:

| Signal | What to capture |
|--------|-----------------|
| Title tag | Verbatim string |
| Meta description | Verbatim string + length in chars |
| H1 | Verbatim |
| H2 / H3 outline | Full hierarchy (proxy for content depth) |
| Word count | Body content only |
| Schema markup | JSON-LD types present (Article, FAQPage, HowTo, Product, BreadcrumbList, Organization) |
| Author signal | JSON-LD author names, or a `rel=author` link (E-E-A-T proxy) |
| Date signals | JSON-LD `datePublished` and `dateModified` |
| Image count | Number of inline images (informational depth proxy) |
| Outbound links | Sources the page cites on other sites |

The script `serp_analyzer.py` automates this loop and writes the file given to `--out` (`R/serp-analysis.json` in an audit run).

---

## Step C: Classify intent

For each query, classify the dominant intent based on what the top 10 actually serves:

| Intent | Cues |
|--------|------|
| Informational | "what is", "how to", guides, definitions; top 10 is articles/Wikipedia/educational |
| Commercial | "best", "vs", "review"; top 10 is comparison articles, listicles, review sites |
| Transactional | "buy", "pricing", "signup"; top 10 is product pages, pricing pages |
| Navigational | brand or product name; top 10 is the brand's own properties |

A query can be mixed-intent (e.g. "best CRM" is commercial-leaning informational). Note the mix; do not force a single tag.

---

## Step D: Identify dominant content type

Across the top 10, what content **shape** is winning?

| Pattern | What it tells you |
|---------|-------------------|
| 7+ articles, ≥1500 words | Long-form content depth required |
| 5+ listicles ("Top 10 X") | List format expected |
| Top 3 are video carousel | Video required, written content alone is fighting against UX |
| Top 3 are forum threads (Reddit, Quora) | Authentic peer voice required, brand pages will struggle |
| AI Overview cites 3-5 sources | Brand needs to be one of the cited sources, not just rank #1-10 |
| FAQPage schema dominates | Structured Q&A format expected |

The dominant type is what the user's page should also be (or differentiate from intentionally with a unique angle).

---

## Step E: Identify SERP features and surface coverage

| Feature present | Implication |
|-----------------|-------------|
| AI Overview | Takes clicks from the organic results below it. Brand must be cited in the Overview, not just rank top-3 (see `auditing-geo-aeo/SKILL.md`). |
| Featured snippet | Position-zero snippet absorbs CTR. Target it explicitly with answer-block formatting. |
| PAA box | Each PAA question is a sub-query the page can address with H2/H3 + answer block. |
| Knowledge Panel | Brand-entity is established. New brands cannot dislodge but can adjacent-rank. |
| Video pack | Video content required to capture full SERP real estate. Out of scope for content-only audit; flag for the founder. |
| Image pack | Images optimized with descriptive alt + filename + schema (ImageObject) help. |
| Local pack | Local SEO signal (Google Business Profile) outweighs content. Flag for the founder. |

---

## Output

`serp_analyzer.py` writes one JSON file: `version`, `country_requested`, `serp_country`, `providers` (the `serp` and `scrape` chains used), `queries_analyzed`, and `data`, one record per query:

```yaml
query: "best invoicing for freelancers"
country: us
language: en
fetched_at: 2026-04-29T...
serp_provider: serper      # serper | serpapi | file (built-in search or pasted) | firecrawl | null
ai_overview:
  present: true            # null when status is unverified
  status: captured         # captured | unverified (provider returned no AI Overview field)
  text: "..."
  cited_sources: ["url1", "url2", "url3"]
features:
  paa: ["how do freelancers invoice", "what software ...", ...]
  paa_status: captured     # captured | unverified
  featured_snippet: { url: "...", text: "..." }
  featured_snippet_status: captured
top_10:
  - position: 1
    url: ...
    serp_title: ...
    serp_snippet: ...
    scrape_provider: http  # firecrawl | jina | http | null
    title: ...
    meta: ...
    meta_length: 152
    h1: ...
    outline: [{h2: ..., h3: [...]}]
    h2_outline: [...]
    h3_outline: [...]
    word_count: 2400
    word_count_basis: html-main-content
    schema_types: [Article, FAQPage, BreadcrumbList]
    author_signal: true
    authors: [...]
    date_published: 2025-...
    date_modified: 2026-...
    images: 6
    outbound_links: [...]
_warnings: [...]
```

The model adds, per query, what the script does not compute, in the report and its JSON sidecar: the intent (Step C), the dominant format (Step D), the features the provider showed beyond AI Overview, People also ask and featured snippet (Knowledge Panel, video, image or local pack, Step E), and the site's own page with its crawl line and its gaps against the top 3:

```yaml
intent: commercial
dominant_format: listicle (7/10)
user_page:                 # from crawl.jsonl, with its line
  url: "<user's ranking page or null>"
  crawl_ref: "crawl.jsonl:<n>"
  current_position: 14
  gaps_vs_top_3:
    - "missing FAQPage schema"
    - "no comparison table"
    - "word count 800 vs top-3 avg 2300"
```

---

## Failure modes

- **SERP API rate-limited / quota exceeded / no key** → drop to the next `serp` tier (another SERP API, then built-in search via `--organic-file`, then pasted results). Mark the AI Overview, PAA and featured snippet fields Unverified.
- **A top-10 page blocks every `scrape` provider** → infer SERP intent from the other pages (read each ranking page, classify content type per page). Less reliable but acceptable for top-3 queries.
- **Top 10 is mostly forum threads (Reddit, Quora)** → brand pages will struggle. Recommend the founder consider Reddit-AMA or paid forum strategies as adjacent acquisition, not content-rank-alone.
- **AI Overview cites only news sites** → SERP is news-driven; long-tail content cannot dislodge. Pivot the query to a less news-driven adjacent.
- **No user_page exists yet** (greenfield query) → skip the gap analysis, output only the SERP map. Recommend creating the page based on the dominant format.

---

## Anti-patterns to refuse

- **Comparing user's page to position 1 only.** Position 1 is often an outlier. Compare to the median of top 3 or top 5.
- **Reading the SERP without country filter.** A `gl=US` SERP differs from `gl=FR` for the same query. The country must match the user's audience.
- **Ignoring SERP features.** A query with AI Overview + PAA + featured snippet leaves the organic top-10 a smaller share of the screen and of the clicks. The audit must reflect that: report the features present per query and compare the query's CTR with the site's own CTR at that position.
- **Treating word count as the goal.** Word count is a **proxy** for depth, not a target. A 1000-word page that nails the intent beats a 3000-word page that pads it.

---

## Source

Built on a SERP analysis methodology, with provider-independent SERP handling (Serper by default) and AI-Overview field handling per 2026 SERP composition.
