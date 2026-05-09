---
name: analyzing-serp-competition
description: Fetches the live SERP for each target query via SERPER.dev (free tier, 2500 queries/month), captures the top 10 organic results plus SERP features (PAA, AI Overview, Knowledge Panel, video pack, image pack), then crawls each top-10 URL with firecrawl to extract on-page signals (title, meta, H1-H3 hierarchy, word count, schema markup, internal-link count). Computes intent classification (informational / commercial / transactional / navigational) and dominant content type per query. The output is a per-query competitive map that drives intent-gap analysis. Triggers on words like "SERP", "top 10", "competitor pages", "intent gap", "PAA", "Serper".
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
- `country`: ISO code or `all`. Per-country SERPs differ, score the SERP in the user's country.
- `language`: `en` or `fr`. Forces Google's `hl` and `gl` parameters.

---

## Step A: Fetch the SERP via SERPER.dev (API-first)

SERPER.dev is the free-tier SERP API that exposes AI Overview data in its response, critical for the GEO/AEO audit downstream. Free tier: 2500 queries/month.

```bash
curl -X POST "https://google.serper.dev/search" \
  -H "X-API-KEY: $SERPER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "<target_query>",
    "gl": "<country>",
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

### Fallback: scrape the SERP page

If SERPER is unavailable or the user has not configured an API key:

```bash
firecrawl scrape "https://www.google.com/search?q=<url-encoded-query>&hl=<language>&gl=<country>" \
  --format markdown --only-main-content > /tmp/serp-<n>.md
```

Note: AI Overview text is intermittently captured by firecrawl due to rendering. SERPER is preferred precisely because of its `aiOverview` field. Document the fallback in the report.

---

## Step B: Crawl each top-10 URL

For each top-10 organic result:

```bash
firecrawl scrape "<url>" --format markdown --only-main-content > /tmp/page-<n>.md
```

From each page, extract:

| Signal | What to capture |
|--------|-----------------|
| Title tag | Verbatim string |
| Meta description | Verbatim string + length in chars |
| H1 | Verbatim |
| H2 / H3 outline | Full hierarchy (proxy for content depth) |
| Word count | Body content only |
| Schema markup | JSON-LD types present (Article, FAQPage, HowTo, Product, BreadcrumbList, Organization) |
| Author signal | Visible byline + linked author page (E-E-A-T proxy) |
| Date signals | Published date, last-updated date |
| Image count | Number of inline images (informational depth proxy) |
| Internal links | Approx count of links to same domain |

Capture per-URL into a structured object. The script `serp_analyzer.py` automates this loop and outputs `/tmp/serp-analysis.json`.

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
| AI Overview | Cuts top-organic CTR by ~58%. Brand must be cited in the Overview, not just rank top-3 (see `auditing-geo-aeo/SKILL.md`). |
| Featured snippet | Position-zero snippet absorbs CTR. Target it explicitly with answer-block formatting. |
| PAA box | Each PAA question is a sub-query the page can address with H2/H3 + answer block. |
| Knowledge Panel | Brand-entity is established. New brands cannot dislodge but can adjacent-rank. |
| Video pack | Video content required to capture full SERP real estate. Out of scope for content-only audit; flag for the founder. |
| Image pack | Images optimized with descriptive alt + filename + schema (ImageObject) help. |
| Local pack | Local SEO signal (Google Business Profile) outweighs content. Flag for the founder. |

---

## Output

The skill outputs a per-query JSON record:

```yaml
serp_analysis:
  query: "best invoicing for freelancers"
  country: US
  language: en
  fetched_at: 2026-04-29T...
  intent: commercial
  dominant_format: listicle (7/10)
  ai_overview:
    present: true
    text: "..."
    cited_sources: ["url1", "url2", "url3"]
  features:
    paa: ["how do freelancers invoice", "what software ...", ...]
    featured_snippet: { url: "...", text: "..." }
    knowledge_panel: false
    video_pack: false
  top_10:
    - position: 1
      url: ...
      title: ...
      meta: ...
      meta_length: 152
      h1: ...
      h2_outline: [...]
      word_count: 2400
      schema_types: [Article, FAQPage, BreadcrumbList]
      author_signal: present
      date_published: 2025-...
      date_updated: 2026-...
  user_page:
    url: "<user's ranking page or null>"
    current_position: 14
    gaps_vs_top_3:
      - "missing FAQPage schema"
      - "no comparison table"
      - "word count 800 vs top-3 avg 2300"
```

This JSON is appended to the audit's main JSON sidecar (one entry per query) so downstream skills can consume it.

---

## Failure modes

- **SERPER.dev rate-limited / quota exceeded** → fall back to firecrawl SERP scrape. Note the AI-Overview field will be missing or unreliable.
- **firecrawl blocked on Google SERP** → infer SERP intent from crawling each top-10 URL individually (read each ranking page, classify content type per page). Less reliable but acceptable for top-3 queries.
- **Top 10 is mostly forum threads (Reddit, Quora)** → brand pages will struggle. Recommend the founder consider Reddit-AMA or paid forum strategies as adjacent acquisition, not content-rank-alone.
- **AI Overview cites only news sites** → SERP is news-driven; long-tail content cannot dislodge. Pivot the query to a less news-driven adjacent.
- **No user_page exists yet** (greenfield query) → skip the gap analysis, output only the SERP map. Recommend creating the page based on the dominant format.

---

## Anti-patterns to refuse

- **Comparing user's page to position 1 only.** Position 1 is often an outlier. Compare to the median of top 3 or top 5.
- **Reading the SERP without country filter.** A `gl=US` SERP differs from `gl=FR` for the same query. The country must match the user's audience.
- **Ignoring SERP features.** A query with AI Overview + PAA + featured snippet has only 35-40% of its real estate available to organic top-10. The audit must reflect that.
- **Treating word count as the goal.** Word count is a **proxy** for depth, not a target. A 1000-word page that nails the intent beats a 3000-word page that pads it.

---

## Source

Adapted from the serp-analysis methodology in agent-seo-content-pipeline, with explicit SERPER.dev integration and AI-Overview field handling per 2026 SERP composition.
