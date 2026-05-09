---
name: mapping-content-clusters
description: Organizes the audited domain into pillar pages and cluster topics so the fix list is structured around topical authority, not isolated query fixes. Identifies which pillar each ranking page belongs to, where pillar pages are missing entirely, where cluster pages compete with each other (cannibalization), and which clusters are under-built relative to SERP-implied volume. Produces a topic map plus a consolidation/expansion plan. Triggers on words like "pillar", "cluster", "topical authority", "cannibalization", "topic map".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# mapping-content-clusters

The strategic-structure layer. Without it, the audit returns a flat list of fixes that the founder applies one by one. With it, the fixes are organized into a coherent topical-authority plan that compounds over the next 6 months.

The reference that pairs with this skill is `references/topical-authority-model.md` (the framework). The asset that pairs is `assets/aeo-winning-patterns.md` (because clusters now must be designed for AI Overview citation, not just classic rank).

---

## When to invoke

- Step 6 of the agent workflow: after GSC data and SERP analysis are in, before the fix list is written.
- Whenever the audit reveals 5+ pages targeting overlapping queries (likely cannibalization).
- Whenever the founder is planning a content sprint and needs to know which pillar to invest in.

---

## The pillar-and-cluster model

```
Pillar page (broad, evergreen, comprehensive)
├── Cluster page 1 (specific subtopic, deep)
├── Cluster page 2 (specific subtopic, deep)
├── Cluster page 3 (specific subtopic, deep)
└── ...
```

Each cluster page links up to the pillar. The pillar links down to all clusters. This internal-link topology signals topical authority to Google's quality systems and to LLM crawlers (cited sources cluster topically; isolated pages get cited less).

**Pillar criteria:**
- Targets a broad, high-volume head term ("freelance invoicing" rather than "send invoice in 3 currencies").
- 2500+ words of comprehensive coverage.
- Links to 5+ cluster pages.
- Stable URL, rarely retired.

**Cluster criteria:**
- Targets a specific long-tail or sub-intent ("how to invoice in EUR and USD as a freelancer").
- 800-1800 words deep on one question.
- Links up to the pillar with descriptive anchor text.
- Can be retired or merged when SERP shifts.

---

## Step A: Inventory existing pages

From the GSC JSON sidecar, list every URL that has clicks or impressions in the period. Group by URL prefix (`/blog/*`, `/guides/*`, `/`, etc.).

For each URL, capture: top 3 ranking queries, total impressions, top intent (from `analyzing-serp-competition`).

---

## Step B: Cluster the queries by topic

Group queries into topics. Two heuristics:

1. **Lexical overlap**: queries sharing 2+ noun phrases ("invoicing freelancer", "freelance invoice software", "invoice tool freelancers" all share the {invoicing, freelancer} pair).
2. **SERP overlap**: queries where ≥3 of the top-10 URLs are the same. Google considers these the same topic.

Output: 3 to 8 topic clusters per audit. Name each cluster.

---

## Step C: Map pages to clusters

For each cluster, list:
- The pillar page (if one exists).
- Cluster pages contributing to this topic.
- Pages with mixed intent that "live in two clusters" (a problem; flag for split or specialization).

Common patterns:

| Pattern | Diagnosis |
|---------|-----------|
| Cluster has 5+ pages but no pillar | **Pillar gap**, create a comprehensive pillar that the clusters can link to. |
| Pillar exists but is thinner than 2 of its clusters | **Inverted authority**, clusters are stealing the pillar's signal. Beef up the pillar or merge a cluster into it. |
| 2+ pages target the same intent | **Cannibalization**, consolidate to one canonical page; 301 the others. |
| Cluster has pillar + only 1-2 clusters | **Under-built**, create 3-5 more cluster pages or de-prioritize the cluster. |
| Cluster has 0 ranking pages | **Greenfield opportunity**, if SERP shows reachable competition, add to the build list. |

---

## Step D: Identify cannibalization explicitly

Cannibalization is the most common compounding loss. Symptoms:

- Two URLs ping-pong in GSC across days for the same query.
- Both pages rank in positions 8-15 for the same query but neither breaks top 5.
- Click-through rates are split unevenly (one page gets 80% of the clicks, the other 20% but ranks similarly).

For each cannibalization pair:
1. Pick the canonical page (better backlink profile, better engagement, fresher content, or stronger fit-to-intent).
2. Plan: 301 the loser to the winner OR re-target the loser to a sibling intent.

---

## Step E: Cluster vs SERP volume gap

For each cluster, sum the impressions across its pages. Compare to the SERP-implied volume (sum of impressions that the top 3 in each cluster query receive, a rough proxy from `analyzing-serp-competition`).

A cluster where user-impressions < 10% of SERP-implied volume is **under-built relative to opportunity**. Either the user has too few cluster pages, or the existing pages are not deep enough to compete.

---

## Step F: Output the topic map

```yaml
topic_map:
  - cluster_name: "freelance invoicing fundamentals"
    pillar:
      url: /guides/freelance-invoicing/
      word_count: 3200
      ranking_queries: ["freelance invoicing", "how to invoice as freelancer"]
    clusters:
      - url: /blog/invoice-template-freelancer/
        word_count: 1400
        ranking_queries: ["freelance invoice template"]
      - url: /blog/invoice-multi-currency/
        word_count: 900
        ranking_queries: ["invoice multiple currencies", "invoice EUR USD"]
    diagnoses:
      - cannibalization_pair: [/blog/freelance-invoice-tool/, /blog/invoicing-software-freelancer/]
        canonical: /blog/freelance-invoice-tool/
        action: "301 the second to the first"
      - under_built: false
    next_actions:
      - "Add cluster page for 'tax-aware freelance invoicing' (greenfield, SERP reachable)"
      - "Beef up pillar word count from 3200 to 4500 with 3 expert quotes"

  - cluster_name: "freelance contract & legal"
    pillar:
      url: null
      diagnosis: pillar_gap
      next_action: "Create pillar 'Complete guide to freelance contracts' targeting 'freelance contract' (high-volume head term)."
    clusters: [...]
```

---

## Step G: Plan the next 90 days

From the topic map, produce a 90-day roadmap:

| Sprint | Focus | Why |
|--------|-------|-----|
| Sprint 1 (weeks 1-4) | Fix cannibalization in top-revenue cluster | Highest-ROI, lowest-effort. 301s + canonical fixes. |
| Sprint 2 (weeks 5-8) | Build the missing pillar in highest-impression cluster | Compounds cluster signal, lifts every existing cluster page. |
| Sprint 3 (weeks 9-12) | Add 3-5 cluster pages where SERP is reachable | Greenfield opportunity, builds topical depth. |

---

## Anti-patterns to refuse

- **Treating every page as independent.** Pages do not rank in isolation; clusters compete for topical authority. The audit must surface the topology.
- **Building 50 cluster pages before a pillar.** Inverted topology fails to consolidate signal. Pillar first.
- **Refusing to consolidate cannibalizing pages.** Founders are emotionally attached to their content. The audit's job is to flag the consolidation, not avoid the conversation.
- **Skipping the SERP-volume gap check.** Building 5 more clusters in a cluster already saturated relative to volume is wasted effort. Build where SERP volume exceeds your coverage.
- **Cluster naming that mirrors competitor categories.** Name clusters from the corpus' Pull-force language (the user's vocabulary), not from the founder's product taxonomy.

---

## Source

Adapted from the seo-audit-research methodology in agent-seo-content-pipeline. Pillar-and-cluster framework popularized by HubSpot circa 2017 and refined for 2026 with explicit AI-Overview consideration: clusters are now also designed to be cited in AI Overviews, not just to rank.
