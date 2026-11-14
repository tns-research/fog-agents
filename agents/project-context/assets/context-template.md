<!--
context.md skeleton. The build-context skill fills this from the scrape + Q&A, the
user reviews and corrects it at the context checkpoint. It mirrors context.json field
for field (dual-output convention): same facts, readable prose. Keep them in sync.
Replace every <bracket>. Delete any line you genuinely have no answer for rather than
inventing one (see Voice > claims policy).
-->

# Project context: <Project name>

- **URL**: <https://acme.example or "none">
- **Slug**: <acme>
- **Last updated**: <YYYY-MM-DD>

## One-liner

<One sentence: what it is and who it's for.>

## What it is

<2-3 sentences a stranger would understand. No jargon.>

**Category**: <the words a buyer would actually search, e.g. "freelance invoicing tools">

**Geography**: <primary market country as an ISO code, e.g. "fr", or "global"> (<optional free-text scope>)

## Who it's for (ICP)

- **Who**: <concrete buyer + qualifier, e.g. "solo designers and small studios billing 2k-15k per project">
- **Pains**:
  - <real frustration, ideally in their words>
  - <...>
- **Jobs to be done**:
  - <what they hire the product to accomplish>
  - <...>

## Offer

- **Core**: <the core thing you sell>
- **Price model**: <freemium / per-seat / usage / ...>
- **Differentiators**:
  - <why you over the alternative>
  - <...>

## Positioning

- **Against**: <the status-quo alternative you displace>
- **Promise**: <the single outcome you promise>
- **Proof** (the allowed claims: the only product proof other agents may put in copy without a new source URL):
  - <claim as written> (<kind>, <source URL or docs/deck.pdf#pN>, <date of the fact>; consent <status, scope> for a testimonial or a customer)
  - <...>

## Voice

- **Tone**: <founder | expert | casual>
- **Language**: <en | fr | ...>
- **Banned words**: <comma-separated, or "none">
- **Voice pack**: <voice/voice.json and the measured form of address, written by scripts/build_voice.py; delete this line when no pack was built>
- **Claims policy**: no invented stats, every metric must trace to a URL or be omitted.

---

<!--
Consumed by: every agent in the stack (market-signal, first-users-hunter, seo-audit,
landing-page-analyzer, cold-outreach-builder, carousel-builder, static-ads-builder).
Edit this file by hand anytime; re-run project-context only when the brand or business changes.
-->
