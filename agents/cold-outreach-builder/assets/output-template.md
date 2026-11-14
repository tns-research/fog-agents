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
**Prospects:** <n in the list> → <n excluded by the state> → A <n> / B <n> / C <n> → <n exported>
**Sender check:** <PASS | WARN | FAIL | not run> (`sender-check.json`)
**Lint:** <0 BLOCK, n WARN> after <n> passes (`lint.json`)

---

## Summary

3 to 4 sentences. Lead with how many prospects carry a verified fact (tiers A and B) and what kind of facts they are, the sequence shape (N messages over D days), the dominant Cialdini lever pattern, and anything the founder must do before importing (sender fixes, prospects to read). Do not predict a reply rate: only the founder's own sends measure it.

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
| 4 | 12 | proof or perspective | social proof (allowed claim) or authority / unity / commitment | 40 to 60 | B (allowed claim) or C |
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
> Hi {{first_name}},            (French: Bonjour {{first_name}},)
>
> {{hook}}
>
> <one or two sentences on the offer, tied to the hook>. <single low-pressure CTA>?
>
> {{sender_first_name}}

**CTA:** <text>
**Cialdini primary lever:** reciprocity
**Cialdini secondary lever:** liking
**Personalization tokens:** `{{first_name}}`, `{{hook}}`, `{{sender_first_name}}` (tier A: written in full per prospect in `messages.json`)
**Why this works for this ICP:** <one line>
**Word count:** <n>

### Message 2: Bump (Day 3)

*(repeat the block; Subject = `Re:` previous subject)*

### Message 3: Value drop (Day 7)

*(repeat the block, attach or offer-to-send the artifact reference)*

### Message 4: Proof or perspective (Day 12)

*(repeat, and state the branch used: `allowed claim: positioning.proof[i]` or `sourced URL`, or proof-free `mechanism` / `founder observation` / `question`)*

### Message 5: Direct ask (Day 18)

*(repeat)*

### Message 6: Breakup (Day 26)

*(repeat)*

## Claims ledger

Every proof, customer name, metric or testimonial used in the copy above, with its source (claims gate: `shared/skills/enforcing-claims-policy/SKILL.md` at the repo root). Write "No claims used." when the copy holds none.

| Claim (as written) | Used in | Source (`positioning.proof[i]`, URL, or user-provided observation) |
|--------------------|---------|---------------------------------------------------------------------|
| <claim> | <where> | <source> |

**Dropped:** <claims removed for lack of a source, or "none">

## Prospects and tiers

From `tiers.json` (`scripts/score_prospects.py`, grid `criteria.json`) and `dossiers/verify.json`. Every hook cites a verified fact: date, URL, the excerpt is in the dossier.

| Prospect | Company | Tier | Score | Hook fact (type, date) | Source URL | Hook as written |
|----------|---------|------|------:|------------------------|------------|-----------------|
| <id name> | <company> | A | <n> | <f2, launch, YYYY-MM-DD> | <url> | <hook sentence> |
| <id name> | <company> | B | <n> | <f1, talk, YYYY-MM-DD> | <url> | <hook sentence> |

### Tier C (not exported)

| Prospect | Reason (from `tiers.json`) |
|----------|----------------------------|
| <id name> | <no verified fact inside the freshness window / relationship known / disqualified / score> |

### Excluded by the state

| Prospect | Reason (`excluded-already-contacted.csv`) |
|----------|--------------------------------------------|
| <email> | <in open sequence outreach-YYYYMMDD / suppressed (unsubscribed) / touched on YYYY-MM-DD> |

### Research

Dossiers worked by <sub-agents in waves of 3 | a model CLI via run_dossiers.py | this session, sequentially>. Verification: <n> facts verified, <n> stale, <n> removed after a failed check (list the codes seen: excerpt-not-found, not-cached, post-date, owner-mismatch).

## Sending guidance

### Cadence
- Daily cap: 30 to 50 emails / inbox / day for cold; 15 LinkedIn DMs / day for 1st-degree.
- Warm new inboxes for 14 to 30 days before sending volume.
- Stop the sequence on any reply (positive, negative). OOO does not stop: restart later.

### Subject variants
- Message 1 ships with 2 or 3 subject variants; the export rotates them across rows (`subject_variant`).
- Compare classified replies per variant (`outreach_state.py summary --by angle`), never opens, and write the number of prospects next to every rate. Name no winner on a handful of replies: a difference of a few replies between groups of a few dozen is noise. The founder sets the sample size that decides.

### Deliverability checklist (email channel only)

`scripts/check_sender.py --domain <sending domain> --dkim-selector <s> --inbox-age-days <n> --list-size <n> --out sender-check.json` (DNS only, never an SMTP probe). Copy what it saw:

| Check | Status | Seen |
|-------|--------|------|
| SPF | <pass/warn/fail> | <record> |
| DKIM (<selector>) | <pass/fail/not checked> | <record> |
| DMARC | <pass/warn/fail> | <record, policy> |
| MX | <pass/fail> | <records> |
| Plan | | <cap per day for step 1, days to send step 1 to the list> |

- [ ] SPF, DKIM, DMARC published and aligned on the sending domain (any FAIL above blocks the campaign).
- [ ] Dedicated subdomain (e.g. `outreach.acme.example`), not the main domain.
- [ ] Inbox warmed before send (stack default: 14 to 30 days).
- [ ] Plain-text or minimal HTML, single link maximum.
- [ ] No tracking pixels (or disabled).
- [ ] List-Unsubscribe header (RFC 8058 one-click) present.
- [ ] Volume within the stack default caps of `assets/deliverability-checklist.md` (section D).
- [ ] Spam-complaint rate in Postmaster Tools below 0.10%, never 0.30% or higher (Google sender guidelines); every hard bounce removed.
- [ ] List validated within 7 days of send by a third-party service, or not at all; never by SMTP probes from the agent's machine.
- [ ] No purchased lists.

(See `assets/deliverability-checklist.md` for the full audit.)

### LinkedIn pacing
- LinkedIn publishes no exact caps: small daily batches, stop at the first limit or "unusual activity" warning.
- Comment-then-DM is preferred over a cold DM: the first touch shows the sender read the prospect's work.
- Voice notes ≤60 seconds.
- No automation tools that violate ToS.

(See `skills/sequencing-linkedin-dm/SKILL.md` for the full playbook.)

## Gates

| Gate | Result |
|------|--------|
| `verify_dossiers.py` | <n dossiers ok, n facts verified / stale / removed> |
| `lint_outreach.py` (writing gate + outreach packs + structural checks) | <0 BLOCK, n WARN kept (reasons)>, <n> passes; rows still blocking after 3 passes moved to tier C: <list or none> |
| Claims check | ledger above |
| `reviewing-cold-email` rubric | <n Critical (0 to ship), n Major kept with reasons> |
| Fresh-eyes review | <reviewer, verdict> |

## Files generated

- `leads.csv`, `excluded-already-contacted.csv`: the list as researched, and who the state kept out
- `dossiers/<id>/prospect.json`, `dossiers/verify.json`, `cache/`: the research and its proof
- `tiers.json`, `tiers.csv`: scores and tiers
- `cold-outreach-output.json`: the sidecar, templates for tier B
- `messages.json`: hooks per prospect, steps written for tier A
- `sequence-export.csv` (+ `.skipped.csv`): one row per prospect, `step_N_subject` / `step_N_body` / `step_N_delay_days`, built by `scripts/build_sequence_export.py`
- `lint.json`, `sender-check.json`: gate results
- `import-instructions.md`: column mapping for any sequencer with per-prospect custom fields, or a spreadsheet mail merge; stop conditions; the `register` command to run at import

### Skipped prospects

| Prospect | Reason (tier C / state / no contact for the channel / unresolved token) |
|----------|-------------------------------------------------------------------------|
| <email or profile> | <reason from sequence-export.csv.skipped.csv> |

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
  "_note_sequence": "Input of scripts/build_sequence_export.py. day = offset from the first send. subjects may be empty for a threaded follow-up. body = full message incl. CTA, with {{tokens}}.",
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
      "tokens": ["first_name", "hook", "sender_first_name"],
      "word_count": 87
    }
  ],
  "tiers": {"A": 0, "B": 0, "C": 0, "excluded_by_state": 0},
  "deliverability": "<the JSON written by scripts/check_sender.py --out sender-check.json, copied as is: domain, checked_at, resolver, checks with what was seen; or {\"status\": \"not run\", \"reason\": \"...\"}. Never booleans typed by hand.>"
}
```

## Methodology

- ICP language scan via `community_search` on community sources (Reddit, IndieHackers, niche forums, Twitter/X) for verbatim pain phrases and objections. Sources cited in the output.
- Tools used: community_search = <provider>, scrape = <provider>, email_finder = <provider or none>.
- Hook angles ranked against verbatim ICP language. Cialdini lever assigned per message; coverage matrix verified ≥4 distinct primary levers.
- Sequence pacing: widening-gap cadence (Day 0, +3, +7, +12, +18, +26), 6 messages for cold email; 4 to 5 for LinkedIn DM.
- Research: one dossier per prospect (<sub-agents in waves of 3 | model CLI | sequential>), every page cached, every fact checked by `verify_dossiers.py` (excerpt in the cached page, date, post id, owner). Tiers by `score_prospects.py` from `criteria.json`, never by the model.
- Gates: `lint_outreach.py` until 0 BLOCK (writing gate packs, outreach packs, duplicates, hooks, tokens, length, links, subject, sourced fact, numbers, signature), then the claims check, the review rubric, the fresh-eyes review.
- State: `<n>` leads excluded by `state/state.json`; the export registered with `outreach_state.py register` once imported.
- Anti-pattern audit: AI-tells, banned jargon, hedging, multi-CTA, manufactured urgency. (See `assets/banned-patterns.md`.)
- Deliverability audit: SPF / DKIM / DMARC / warmup / volume / format / unsubscribe. (See `assets/deliverability-checklist.md`.)

## Limitations

- Personalization depends on what is public. Prospects with no verified, dated fact are tier C: listed, never sent a generic message. Search engines index only part of LinkedIn posts: no post found is not proof of inactivity.
- Skipped capabilities: <capability: what it left unverified, e.g. N prospects without email listed in the skipped file>, or none.
- No reply rate is predicted. Only the user's actual sends measure it; compare variants on replies, with the sample size stated.
- LinkedIn ToS limits send velocity. Sequences exceeding daily caps are flagged but not auto-throttled.
- Cialdini coverage is auditable only against the visible body. A lever that is implicit (e.g. Authority via the sender's verifiable LinkedIn profile) is not always counted in the matrix.

## Sources

- ICP language scan: <provider> queries (Reddit, IndieHackers, niche forums, Twitter/X). List of queries in the methodology section.
- Prospect research: <scrape provider> on company sites, public posts, registries and press (never LinkedIn profile pages), cached in `cache/`; emails from <email_finder provider or the input list>.
- Per-prospect facts with URL, date and excerpt in `dossiers/<id>/prospect.json`; the hook's source in the `hook_source_url` column of the export.
- All verbatim quotes preserved in original wording per cross-cutting convention C5; translations are tagged `[translated]`.

---

*Generated by `cold-outreach-builder` on YYYY-MM-DD. Founders Growth Agent Stack.*
