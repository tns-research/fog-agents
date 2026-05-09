# Cold Outreach: <project>: <icp-shortname>

**Project:** <project-slug>
**Date:** YYYY-MM-DD
**ICP:** <role + size + vertical + geo>
**Offer:** <2-sentence offer>
**Goal:** <book call | try free | feedback | partnership>
**Channel:** <email | linkedin>
**Language:** <en | fr>
**Register (FR only):** <tu | vous>
**Seniority:** <founder | vp | manager | mixed>
**Stage focus:** <idea | proto | mvp | 20+ | scale>

---

## Summary

3 to 4 sentences. Lead with the chosen hook angle for Message 1, the sequence shape (N messages over D days), the dominant Cialdini lever pattern across the sequence, and the key personalization tokens. State expected reply-rate band given the ICP.

## ICP language scan

### Pain phrases (their words, verbatim)

- "<pain phrase 1>" (source: <url or community>)
- "<pain phrase 2>" (source: <url or community>)
- "<pain phrase 3>" (source: <url or community>)

### Common objections

- <objection 1>
- <objection 2>

### Status-quo defaults (what they currently do or use)

- <default 1>
- <default 2>

### What they ignore

- <ignored option 1>

## Hook angles (ranked by fit)

| # | Angle | Type | Cialdini lever | Why it fits | Best for |
|---|-------|------|----------------|-------------|----------|
| 1 | <angle> | pain-first | reciprocity | <reason> | message 1 |
| 2 | <angle> | curiosity | authority | <reason> | message 1 alt or message 3 |
| 3 | <angle> | direct value | reciprocity | <reason> | message 3 |

## Sequence overview

| # | Day | Type | Cialdini lever | Word count | Subject style |
|---|----:|------|----------------|-----------:|---------------|
| 1 | 0 | initial hook | reciprocity | 60 to 100 | A or C |
| 2 | 3 | bump | commitment | 30 to 50 | Re: |
| 3 | 7 | value drop | reciprocity | 70 to 100 | C |
| 4 | 12 | social proof | social proof | 50 to 80 | B |
| 5 | 18 | direct ask | commitment | 40 to 60 | C short |
| 6 | 26 | breakup | unity | 35 to 50 | C short |

### Cialdini coverage matrix

| Message | Reciprocity | Commitment | Social Proof | Authority | Liking | Scarcity | Unity |
|---------|:-----------:|:----------:|:------------:|:---------:|:------:|:--------:|:-----:|
| 1 | ● | | | ○ | ○ | | |
| 2 | | ● | | | | | |
| 3 | ● | | | ○ | | | |
| 4 | | | ● | | | | ○ |
| 5 | | ● | | | | | |
| 6 | | | | | ● | | ○ |

`●` = primary lever, `○` = secondary lever. Target: ≥ 4 distinct primary levers across the sequence.

## Messages (full)

### Message 1: Initial hook (Day 0)

**Subject A (style: question):** `<≤50 chars>`
**Subject B (style: stat):** `<≤50 chars>`
**Subject C (style: direct):** `<≤50 chars>`

**Body:**
> Hey {{first_name}},
>
> <hook tied to {{specific_observation}}>. <one-line value prop>.
>
> {{personal_hook}}.
>
> <single low-pressure CTA>?

**CTA:** <text>
**Cialdini primary lever:** reciprocity
**Cialdini secondary lever:** liking
**Personalization tokens:** `{{first_name}}`, `{{specific_observation}}`, `{{personal_hook}}`
**Why this works for this ICP:** <one line>
**Word count:** <n>

### Message 2: Bump (Day 3)

*(repeat the block; Subject = `Re:` previous subject)*

### Message 3: Value drop (Day 7)

*(repeat the block, attach or offer-to-send the artifact reference)*

### Message 4: Social proof (Day 12)

*(repeat)*

### Message 5: Direct ask (Day 18)

*(repeat)*

### Message 6: Breakup (Day 26)

*(repeat)*

## Personalization sample (3 prospects)

| # | Name | Company | `specific_observation` | `personal_hook` | source URL |
|---|------|---------|------------------------|-----------------|------------|
| 1 | <name> | <company> | <one sentence about a recent post / launch / hire> | <one sentence tying it to the offer> | <url> |
| 2 | <name> | <company> | <...> | <...> | <url> |
| 3 | <name> | <company> | <...> | <...> | <url> |

## Sending guidance

### Cadence
- Daily cap: 30 to 50 emails / inbox / day for cold; 15 LinkedIn DMs / day for 1st-degree.
- Warm new inboxes for 14 to 30 days before sending volume.
- Stop the sequence on any reply (positive, negative). OOO does not stop: restart later.

### A/B/C subject test
- Email 1 ships with Subjects A / B / C.
- Tool splits 33/33/33 on first batch (≥30 prospects per variant).
- Winner is shipped to the rest. Loser variants logged for future reference.

### Deliverability checklist (email channel only)
- [ ] SPF, DKIM, DMARC published and aligned on the sending domain.
- [ ] Dedicated subdomain (e.g. `outreach.acme.com`), not the main domain.
- [ ] Inbox warmed 14 to 30 days minimum before send.
- [ ] Plain-text or minimal HTML, single link maximum.
- [ ] No tracking pixels (or disabled).
- [ ] List-Unsubscribe header (RFC 8058 one-click) present.
- [ ] Volume ≤ 50 cold emails / inbox / day.
- [ ] Spam-complaint rate target ≤ 0.1%; hard-bounce rate ≤ 2%.
- [ ] List validated within 7 days of send (NeverBounce / ZeroBounce).
- [ ] No purchased lists.

(See `assets/deliverability-checklist.md` for the full audit.)

### LinkedIn caps
- Max 100 connection requests per week.
- Max 50 DMs per day to 1st-degree connections.
- Comment-then-DM tactic is preferred over cold DM (3 to 4x better reply rate).
- Voice notes ≤60 seconds.
- No automation tools that violate ToS.

(See `skills/sequencing-linkedin-dm/SKILL.md` for the full playbook.)

## Files generated

- `sequence-templates.md`: message templates with tokens
- `personalized-leads.csv`: leads + `specific_observation` + `personal_hook` + `source_url` columns
- `import-instructions.md`: Instantly token mapping (other tools follow the same column conventions)
- `cold-outreach-output.json`: structured sidecar (see C1)

## Sidecar JSON schema (cold-outreach-output.json)

```json
{
  "project": "<slug>",
  "date": "YYYY-MM-DD",
  "icp": {
    "role": "<role>",
    "company_size": "<size>",
    "vertical": "<vertical>",
    "geo": "<geo>",
    "language": "en|fr",
    "register": "tu|vous|null",
    "stage_focus": "idea|proto|mvp|20+|scale"
  },
  "channel": "email|linkedin",
  "sequence": [
    {
      "n": 1,
      "day": 0,
      "type": "initial_hook",
      "cialdini_primary": "reciprocity",
      "cialdini_secondary": "liking",
      "subjects": [
        {"variant": "A", "style": "question", "text": "..."},
        {"variant": "B", "style": "stat", "text": "..."},
        {"variant": "C", "style": "direct", "text": "..."}
      ],
      "body": "...",
      "cta": "...",
      "tokens": ["first_name", "specific_observation", "personal_hook"],
      "word_count": 87
    }
  ],
  "personalization_sample": [
    {"name": "...", "company": "...", "tokens": {...}, "source_url": "..."}
  ],
  "deliverability": {
    "spf": true,
    "dkim": true,
    "dmarc": true,
    "subdomain_dedicated": true,
    "warmup_days": 21
  }
}
```

## Methodology

- ICP language scan via `exa search` on community sources (Reddit, IndieHackers, niche forums, Twitter/X) for verbatim pain phrases and objections. Sources cited in the output.
- Hook angles ranked against verbatim ICP language. Cialdini lever assigned per message; coverage matrix verified ≥4 distinct primary levers.
- Sequence pacing: widening-gap cadence (Day 0, +3, +7, +12, +18, +26), 6 messages for cold email; 4 to 5 for LinkedIn DM.
- Personalization tokens: `{{specific_observation}}`, `{{personal_hook}}` resolved per prospect from public signals (LinkedIn posts, recent hires, fundraises, talks). Drop prospect if a critical token cannot be filled.
- Anti-pattern audit: AI-tells, banned jargon, hedging, multi-CTA, manufactured urgency. (See `assets/banned-patterns.md`.)
- Deliverability audit: SPF / DKIM / DMARC / warmup / volume / format / unsubscribe. (See `assets/deliverability-checklist.md`.)

## Limitations

- Personalization quality depends on prospect-list richness. Prospects without a fresh public artifact (post, hire, raise, talk) get the generic angle and a lower expected reply rate.
- Reply-rate bands are estimates calibrated on ICP fit. Only the user's actual sends measure ground truth.
- LinkedIn ToS limits send velocity. Sequences exceeding daily caps are flagged but not auto-throttled.
- Cialdini coverage is auditable only against the visible body. A lever that is implicit (e.g. Authority via the sender's verifiable LinkedIn profile) is not always counted in the matrix.

## Sources

- ICP language scan: `exa search` queries (Reddit, IndieHackers, niche forums, Twitter/X). List of queries in the methodology section.
- Prospect enrichment: `firecrawl scrape` on public profile pages and company URLs.
- Per-prospect source URL in `personalized-leads.csv` `source_url` column.
- All verbatim quotes preserved in original wording per cross-cutting convention C5; translations are tagged `[translated]`.

---

*Generated by `cold-outreach-builder` on YYYY-MM-DD. Founders Growth Agent Stack.*
