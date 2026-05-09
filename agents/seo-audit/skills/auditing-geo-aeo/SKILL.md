---
name: auditing-geo-aeo
description: Audits whether content is cited in AI Overviews (Google), Perplexity answers, and ChatGPT responses, not just whether it ranks #1-10. AI Overviews now appear in ~55% of searches and have cut top-organic CTR by ~58%, so classic rank-only auditing misses most of the search surface. Uses an API-first protocol. SERPER.dev for AI Overview source citations, then the Perplexity CLI to programmatically run target queries and capture cited domains. Manual UI inspection is the last resort. Outputs a citation gap analysis and a fix list keyed to the AEO winning patterns. Triggers on words like "AEO", "GEO", "AI Overview", "Perplexity citation", "ChatGPT citation", "answer engine".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# auditing-geo-aeo

The 2026 audit layer. Adds citation-presence in AI answers as a first-class metric alongside classic organic rank.

The asset that pairs with this skill is `assets/aeo-winning-patterns.md` (what gets cited) and `assets/eeat-audit-checklist.md` (the foundational signal AI engines weight heavily).

---

## When to invoke

- Step 7 of the agent workflow: after classic rank analysis, run AEO citation analysis on the same query set.
- For any query where SERP analysis showed `aiOverview.present == true`. AI Overview present means classic CTR is halved; citation in the Overview is the new top-3.
- For any brand or product query where presence in Perplexity / ChatGPT directly affects discovery ("recommend a tool for X").

---

## Why this matters in 2026

- AI Overviews appear in ~55% of Google searches (Google blog, public studies 2025-2026).
- Top-organic CTR drops by ~58% when an AI Overview is present.
- ~13% of US users now treat ChatGPT/Perplexity as a primary search interface for research-stage queries.
- Brands that rank #1 organically but are not cited in the Overview lose the click anyway.

The audit's job is to surface where the user's content is and is not cited, then prescribe what to change so the cite-or-rank ratio improves.

---

## Step A: Source the AI Overview citations (Google)

Pull from SERPER.dev's `aiOverview` field per query (already captured by `analyzing-serp-competition`):

```yaml
ai_overview_citations:
  query: "best invoicing for freelancers"
  cited_domains: [stripe.com, freshbooks.com, indeed.com, reddit.com]
  cited_urls:
    - https://stripe.com/...
    - https://freshbooks.com/...
  user_domain_cited: false
  rank_in_classic_top_10: 7
```

Where SERPER does not return AI Overview (region rollout, query type, rate limit), fall back to the manual capture script (Step C).

---

## Step B: Run target queries in Perplexity (programmatic)

The `perplexity` CLI from `cli-skills` takes a query and returns answer + cited sources. Run target queries:

```bash
perplexity ask "<target_query>" --json > /tmp/pplx-<n>.json
```

Capture from the response:
- The cited URLs (Perplexity returns them as numbered citations).
- Whether the user's domain appears among them.
- The relative position of the citation (early citations carry more weight than later ones).

For each query:

```yaml
perplexity_citation:
  query: "best invoicing for freelancers"
  cited_domains: [...]
  user_domain_cited: false
  citation_position: null
  competing_cited_domains: [...]
```

---

## Step C: ChatGPT / Bing-Copilot (manual fallback)

ChatGPT does not have a public free API for cited-source capture. As a last resort, the user runs the same target queries manually in ChatGPT (with web browsing enabled) and pastes the answer + citations into a results template:

```
<project>/seo-audit/aeo-manual-capture.md
  ## Query: <q>
  ## Cited URLs:
  - ...
  ## User domain cited: yes/no
```

The agent reads this file when present and merges into the JSON sidecar. **This is a degraded UX (context-switch cost); only deploy when API-first paths fail.**

---

## Step D: Citation gap analysis

For each audited query, compute:

| Metric | Formula |
|--------|---------|
| Citation presence | (count of AI surfaces where user is cited) / (count of AI surfaces evaluated) |
| Citation rank | Average position when cited (1 = first source cited, 5 = fifth) |
| Competitor citation overlap | % of cited domains that are direct competitors per `analyzing-serp-competition` |
| Rank-vs-citation gap | Classic rank position − cited position. A user ranking #3 but cited #8 is losing clicks; a user ranking #15 but cited #2 is winning the AI surface. |

The output is a per-query gap diagnosis:

```yaml
aeo_diagnosis:
  query: "best invoicing for freelancers"
  classic_rank: 7
  ai_overview_cited: false
  perplexity_cited: false
  diagnosis: "User ranks top 10 but is invisible to AI surfaces. Likely cause: lack of answer-block format and no FAQPage schema. Fix priority: HIGH."
  fix_recommendations:
    - "Add 40-word answer block at top of section after H2 'Best invoicing for freelancers'"
    - "Add FAQPage schema with prompt-matched questions from PAA"
    - "Add inline statistic: '<source-cited number from research>'"
    - "Strengthen author E-E-A-T (see eeat-audit-checklist.md)"
```

---

## Step E: Map fixes to AEO winning patterns

Load `assets/aeo-winning-patterns.md`. For each diagnosis, pick the patterns that apply:

| Pattern | Effect |
|---------|--------|
| Question-first H2/H3 matching real prompts | Direct answer-engine matching |
| FAQPage schema with prompt-matched questions | Highest-ROI structured data for AEO |
| 40-word answer blocks at top of sections | Cited verbatim in Overviews and Perplexity |
| Expert quotes with named source | +41% citation lift (per public benchmarks) |
| Inline statistics with cited source | +30% citation lift |
| Inline citations in body | +30% citation lift |

The fix list output by `auditing-geo-aeo` is keyed to specific patterns, not vague "improve content".

---

## Step F: E-E-A-T foundation check

Citation-worthiness depends heavily on E-E-A-T signal. Load `assets/eeat-audit-checklist.md` and run for each ranking page:

- Verifiable author with credentials linked.
- Persistent author page on the domain.
- First-hand specifics (numbers, screenshots, dated events).
- Original data or interviews (not just summarized secondary sources).
- Last-updated date is truthful (not auto-bumped).

Pages that fail E-E-A-T are not cited even when content is otherwise strong. Flag the gap.

---

## Output JSON sidecar

Append to the main audit JSON:

```yaml
aeo_audit:
  surfaces_evaluated: [google_ai_overview, perplexity]
  manual_chatgpt_captured: true
  per_query:
    - query: ...
      classic_rank: ...
      ai_overview_cited: ...
      perplexity_cited: ...
      chatgpt_cited: ...
      gap_diagnosis: ...
      fix_patterns: [...]
  summary:
    queries_audited: 8
    citation_presence_rate: 0.25
    avg_citation_rank: 4.5
    rank_visible_but_uncited_count: 5    # the most important number
```

The "rank visible but uncited" count is the headline finding for most founder sites: they rank top-10 organically but are invisible to AI surfaces. That's the actionable wedge.

---

## Failure modes

- **SERPER quota exceeded** → switch to Perplexity-only audit and note the partial coverage.
- **Perplexity CLI unavailable / no API key** → flag in the report header. Run with whatever surfaces remain. Do not skip the audit entirely.
- **All AI surfaces fail to cite anyone** (AI Overview suppressed for the query) → query is uninteresting to AI engines. Classic SEO still applies; AEO not a priority for this query.
- **User domain cited everywhere** → the brand is established for this query. No fix needed; document as a strength.
- **Citation pattern shows competitors dominate** → competitive AEO problem, not a content-format problem alone. Recommend a sustained build (3-6 months) on E-E-A-T + AEO patterns rather than a 7-day sprint.

---

## Anti-patterns to refuse

- **Auditing only Google AI Overview.** ChatGPT and Perplexity are independent surfaces with different citation logics; one audit must include all three.
- **Treating "we rank #1 so we'll be cited" as automatic.** Many top-ranked pages are not cited. The two systems are correlated but separable.
- **Recommending generic "improve content".** AEO fix list must reference specific patterns from `aeo-winning-patterns.md`.
- **Counting citations without checking the citation position.** Being cited 9th out of 10 is much weaker than being cited 1st.
- **Using paid GEO/AEO SaaS (Profound, Scrunch, etc.).** Out of scope per zero-paid-SaaS rule. SERPER + Perplexity + manual fallback is sufficient.

---

## Source

Compiled from 2025-2026 public studies on AI Overview behavior (Google, Backlinko, Search Engine Land), Perplexity citation studies, and the AEO winning-patterns synthesis in `assets/aeo-winning-patterns.md`. Adapted from the geo-aeo-checklist methodology in agent-seo-content-pipeline.
