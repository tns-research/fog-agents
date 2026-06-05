---
name: build-context
description: Turn a URL scrape plus a short structured Q&A into the shared business context (context.json + context.md) for a founder's project. Covers one-liner, ICP, offer, positioning, proof, and voice. Optionally pre-fills answers from product/about/pricing pages via firecrawl or exa, then runs a human validation checkpoint. Use when setting up project-context or refreshing a project's business context. Triggers: "set up my context", "configure my project", "what we sell / who for".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(firecrawl:*) Bash(exa:*)
---

# Skill: build-context

Produce the business half of the shared context: `context.json` (machine) + `context.md` (human). Brand colors/fonts/logo are handled separately by `extract-brand`; this skill owns the business meaning.

The contract lives in `assets/context-schema.json`. The prose skeleton lives in `assets/context-template.md`. This skill fills both from the same facts.

---

## When to load

- The agent's Workflow Step 3 runs (always, on both fresh and update runs).
- The user wants to (re)configure what the project is, who it's for, the offer, or the voice.

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `url` | config / chat | no (recommended) |
| `web_enrichment` | config (`off`/`exa`/`firecrawl`/`auto`) | no, default `auto` |
| `language` | config / chat | no, default `en` |
| `output_dir` | `<project-root>/<project-slug>/project-context/` | yes |

Environment: `FIRECRAWL_API_KEY` and/or `EXA_API_KEY` enable pre-fill. Without either, the Q&A carries the full load.

---

## Procedure

### Step 1, optional pre-fill from the web

If `web_enrichment` is not `off` and a key is available, run:

```bash
python agents/project-context/scripts/enrich_context.py \
  --url "$URL" \
  --out "$OUTPUT_DIR" \
  --provider auto        # auto picks firecrawl, else exa, else degrades
```

It pulls the homepage plus likely `/about`, `/pricing`, `/product` pages and writes `brand-debug/enrichment.json` (raw) plus a short `enrichment-notes.md` (extracted candidate answers: what it is, category, offer hints, proof candidates). Treat these as **draft answers to confirm**, never as final truth. If the script exits non-zero (no key, robots block), skip silently and go to Step 2.

### Step 2, structured Q&A

Ask the founder the questions below. Pre-fill each from Step 1 when you have a candidate, and frame it as "here's what I read, correct me". Ask only what's still unknown. Keep it tight: this is a setup ritual, not an interview.

**Identity**
1. One-liner: what is it, and who is it for? (one sentence)
2. In 2-3 plain sentences, what is it? (no jargon)
3. What category would a buyer search for it under?

**ICP**
4. Who exactly buys/uses it? Add a qualifier (size, spend, role).
5. What are their top 2-3 pains? (prefer their own words)
6. What job are they hiring it to do?

**Offer**
7. What's the core thing you sell?
8. How is it priced?
9. Why you over the obvious alternative? (1-3 differentiators)

**Positioning**
10. What status-quo alternative do you displace?
11. The single outcome you promise?
12. What proof backs that promise? (numbers, named features, press) -- see claims policy.

**Voice**
13. Default tone: founder, expert, or casual?
14. Output language?
15. Any banned words/phrases?

### Step 3, claims policy (hard rule)

Every item under `positioning.proof` must trace to something real: a number with a source URL, a named feature, or a named mention. **Do not invent stats, round numbers, or first-person anecdotes.** If the founder gives a metric with no source, either tag it for them to confirm a source or omit it. Write this rule verbatim into `voice.claims_policy`:

> no invented stats, every metric must trace to a URL or be omitted

Consumers (static-ads-builder, carousel-builder) read this field and enforce it when writing copy. This is the single point where the stack's anti-fabrication rule is set.

### Step 4, draft + context checkpoint

1. Fill `assets/context-template.md` -> `context.md` with the confirmed answers, in `language`.
2. Present `context.md` to the founder. Ask them to approve, correct in chat, or edit the file directly.
3. **No iteration cap.** Loop until they approve.

### Step 5, write artifacts

Once approved, write both, keeping them in sync:

- `context.json` validated against `assets/context-schema.json` (required fields present; missing-but-optional fields omitted, never `null`-stuffed with fake values).
- `context.md` (the approved prose).

Both into `<output_dir>/` (the project's `project-context/` folder).

---

## Hard rules (do not violate)

- **No invented facts.** If you don't know it and the founder didn't say it, ask or omit. Never fabricate proof, ICP details, or metrics.
- **Dual output stays in sync.** `context.json` and `context.md` carry the same facts. Don't let them drift.
- **Schema is the contract.** Validate against `assets/context-schema.json`. Required fields must be present and non-empty.
- **Pre-fill is a draft, not truth.** Web-scraped answers are always confirmed by the founder before they're written.
- **claims_policy is always written**, even if the founder skips proof.

---

## Failure modes + fallbacks

| Failure | Fallback |
|---------|----------|
| No URL and no enrichment | Run the Q&A from scratch; still produce a valid folder. |
| `enrich_context.py` exits non-zero (no key, robots block, fetch error) | Skip pre-fill, run the Q&A manually. Never block on it. |
| Founder gives a metric with no source | Tag it `(source?)` in the draft and ask; if unresolved, omit from `proof`. |
| Founder wants to skip a whole section | Omit the optional fields; keep required ones (`one_liner`, `what_it_is`, `icp`, `offer`, `positioning.promise`, `voice`). |
| Update run, fields already on file | Show current values, only re-ask what they want to change. |

---

## Why this design

- **Context is set once, read many times.** A few minutes here saves every downstream agent from re-interrogating the founder.
- **Schema + checkpoint beats free-form.** A typed contract lets consumers read defensively; the human checkpoint keeps it honest.
- **Pre-fill accelerates, never decides.** Scraping drafts the answers; the founder owns them.
