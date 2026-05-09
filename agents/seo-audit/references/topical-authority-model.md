# Topical authority model

Reference for the pillar-and-cluster framework used by `mapping-content-clusters/SKILL.md`. Explains why isolated pages underperform clusters in 2026, what topical authority looks like to Google's quality systems, and how AI engines extend the same logic to citation behavior.

---

## What topical authority is

A site has topical authority on a topic when **its body of work demonstrates depth and breadth that other sources lack**. Google's systems and AI engines both reward this:

- Google's classic ranking: clustered, internally-linked, in-depth content ranks higher than equivalent isolated pages.
- AI engines (Perplexity, ChatGPT, Google AI Overview): cite sources that have multiple relevant pages on a topic more often than sources with a single page on it.

The pattern is not "rank a single keyword". The pattern is "be the place" for a topic.

---

## The pillar-and-cluster topology

```
                 [Pillar: Freelance Invoicing]
              (broad, comprehensive, evergreen)
                /         |          \
        [Cluster A]   [Cluster B]   [Cluster C]
        Multi-currency  Templates    Tax handling
```

- **Pillar** covers the topic broadly. 2500-4000 words. Targets a head term ("freelance invoicing").
- **Clusters** cover specific subtopics deeply. 800-1800 words each. Target long-tails or specific intents.
- **Internal links** flow both ways: pillar links to all clusters; each cluster links back to the pillar with descriptive anchor text.

The topology is what signals "this is a topical hub" to ranking and citation systems.

---

## Why isolated pages underperform

A single page targeting "freelance invoicing":

- Has no internal-link reinforcement from sibling content.
- Cannot signal depth, readers can't drill down into subtopics.
- Is harder to cite by AI engines because there's nothing to cluster it with.
- Loses to competitors who have 5+ related pages even if the single page is excellent.

The single-page strategy works only for: brand-new sites with one priority piece, or topics so narrow that they have no clusters (rare for founder-stage SaaS).

---

## What "comprehensive" means for the pillar

A pillar is comprehensive when it answers, in one place:

- What is X?
- Who needs X?
- How does X work?
- What are the main approaches to X?
- Common mistakes / failure modes.
- When to choose approach 1 vs approach 2.
- Glossary of terms in the topic.
- Internal links to deep-dive cluster pages for each sub-question.

A reader landing on the pillar should not need to leave the site to understand the topic at the level of an informed beginner.

---

## What "specific" means for clusters

A cluster page is specific when it:

- Targets a long-tail or sub-intent (e.g. "how to invoice across EUR and USD as a freelance designer").
- Goes deeper than the pillar's mention of the topic.
- Addresses a single user task or question.
- Is self-contained (a reader can land here directly and get value).
- Links up to the pillar at least once with a descriptive anchor.
- Links sideways to 1-2 sibling cluster pages where relevant.

A cluster is not a thinner version of the pillar. A cluster is a deep-dive on one slice.

---

## How AI engines weight topical authority

AI engines (Perplexity, ChatGPT browse, Google AI Overview) cite sources by:

1. **Topical relevance**: does the source's body of work cover this topic?
2. **Depth signal**: does it have enough content to be worth citing as the canonical source?
3. **Authority**: backlinks, age, branded entity, E-E-A-T (`assets/eeat-audit-checklist.md`).
4. **Citability**: structured patterns from `assets/aeo-winning-patterns.md` (answer blocks, schema, expert quotes, statistics).

A site with 1 great page on Topic X is rarely cited. A site with 6 connected pages on Topic X is cited frequently. The cluster is the unit of authority for AI engines, not the page.

---

## When to build a pillar vs add a cluster

Decision tree:

| Situation | Action |
|-----------|--------|
| Cluster has 5+ existing pages, no pillar | **Build the pillar.** Highest-leverage move. |
| Pillar exists, only 1-2 cluster pages | **Add 3-5 more cluster pages** before touching pillar. |
| Pillar exists, 5+ cluster pages, but pillar is thin | **Beef up the pillar** (word count, depth, expert quotes). |
| Cluster has 5+ pages but they cannibalize each other | **Consolidate** before adding more (per `mapping-content-clusters/SKILL.md` Step D). |
| Greenfield topic (no pages yet) | **Pillar first**, then clusters in next sprint. Pillar establishes the topical anchor. |

---

## How clusters interact across topics

Clusters from different topics can link to each other when there's a real connection ("multi-currency invoicing" cluster from invoicing topic links to "international tax handling" cluster from tax topic).

Cross-topic links should be:

- Sparingly used (3-5 across-topic links per cluster, not 30).
- Anchor-text-descriptive, not "click here".
- Reciprocal where the connection is real.

Excessive cross-topic linking dilutes topical authority, both topics look generic.

---

## The 90-day topical-authority sprint

A typical sprint that emerges from the audit:

| Weeks | Action | Why |
|-------|--------|-----|
| 1-2 | Fix cannibalization in priority cluster | Highest-ROI, lowest-effort. 301s + canonical fixes. |
| 3-4 | Build the missing pillar in the priority cluster | Compounds cluster signal, lifts every existing cluster page. |
| 5-8 | Add 3-5 cluster pages where SERP is reachable | Build topical depth in the prioritized cluster. |
| 9-12 | Expand to second priority cluster (pillar or fixes) | Second-cluster build starts compounding. |

By month 6, the site has 2-3 strong clusters with pillars and 5+ deep cluster pages each. That's the foundation of topical authority.

---

## Anti-patterns

- **Building 50 cluster pages before any pillar.** Inverted topology fails to consolidate signal.
- **Building 5 pillars in different topics simultaneously.** Spreads effort thin; no topic ever reaches authority threshold.
- **Treating the pillar as a permanent freeze.** Pillars need refresh every 6-12 months as the topic evolves and as the cluster pages reveal new angles to add.
- **Putting product/marketing content in the pillar.** A pillar that pushes a product loses topical authority signal. Keep pillars editorial; product pages link in from clusters where appropriate.
- **Skipping internal links.** A pillar that doesn't link to its clusters, or clusters that don't link back to the pillar, fail to signal topology.

---

## Source

Pillar-and-cluster framework popularized by HubSpot circa 2017; topical-authority model refined through 2020-2026 with growing emphasis on AI-engine citation logic. Calibrated for founder-stage SaaS sites where a 90-day sprint is the operating cadence.
