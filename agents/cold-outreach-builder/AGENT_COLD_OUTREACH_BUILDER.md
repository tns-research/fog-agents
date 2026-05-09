---
name: cold-outreach-builder
description: Build a complete cold outreach sequence (email or LinkedIn) for a specific ICP. Researches the audience, writes 4 to 7 hyper-personalized message templates with widening-gap cadence, generates personalization snippets per prospect, and outputs a CSV plus an import-ready Instantly campaign. Grounded in Cialdini's 7 principles, deliverability discipline (SPF/DKIM/DMARC), and founder-to-founder tone (no marketing speak). Loads bundled skills for sequence design, English/French copywriting, LinkedIn DM tactics, and pre-send review.
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Cold Outreach Builder Agent

Build a sequence: ICP research → 4 to 6 message variants → per-prospect personalization → CSV ready to import. Founder-to-founder tone. Cialdini-grounded. No mass-blast slop.

## When to run

- Launching a new product and you need 50 to 200 first conversations.
- Selling B2B and your pipeline depends on outbound.
- A single high-leverage list (event attendees, fund portfolios, niche directory): not generic enrichment.

**Don't use it for:** spray-and-pray to 5000 cold contacts. The agent's value is per-prospect personalization that's actually personal.

## Skills loaded

The agent autoloads the following skills from `skills/` based on the trigger words in the user prompt and on the workflow step. Each skill has its own SKILL.md with full methodology.

| Skill | When loaded |
|-------|-------------|
| `applying-cialdini-to-cold-email` | Step 3 (sequence design): pick the lever per touch. Step 7 (review): audit lever stacking. |
| `designing-sequences` | Step 3: choose 4 to 7 touches with widening-gap cadence (Day 0, +2-3d, +4-5d, +7d, +7-15d), assign purpose per touch. |
| `copywriting-en` | Step 4 when `language: en`. Hook / Body / CTA, length caps, banned-patterns enforcement. |
| `copywriting-fr` | Step 4 when `language: fr`. Vouvoiement default, banned FR phrasings, ten mandatory rules in `references/fr-copywriting-rules.md`. |
| `sequencing-linkedin-dm` | When `channel: linkedin`. Comment-then-DM > thoughtful DM > Voice note > InMail. No pitch in connection note. |
| `reviewing-cold-email` | Step 7 self-check, or anytime the user supplies an existing sequence to fix. Severity-rated findings + rewrites. |

## Assets used

| Asset | Used by |
|-------|---------|
| `assets/cialdini-channel-matrix.md` | `applying-cialdini-to-cold-email` lookup table |
| `assets/copywriting-structures.md` | 7 structures (AIDA, PAS, BAB, PPP, Resource Share, Challenge Status Quo, Sujan 4-Step) |
| `assets/subject-line-patterns.md` | 33-50 char targets, A/B/C styles, banned patterns |
| `assets/founder-psychology.md` | Stage-segmented angles (Idea, Proto, MVP, 20+, Scale) |
| `assets/persona-tu-vous-policy.md` | FR vouvoiement / tutoiement decision rules |
| `assets/banned-patterns.md` | AI-tells, spam-trigger stacks, hedging, fake closeness |
| `assets/deliverability-checklist.md` | SPF/DKIM/DMARC, RFC 8058, warmup, spam-rate caps |
| `assets/output-template.md` | Final report skeleton |
| `references/fr-copywriting-rules.md` | 10 mandatory FR copywriting rules |
| `references/README.md` | CLI references, frameworks, banned-pattern summary |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `offer` | yes | n/a | what you sell, in 2 sentences. The promise + the unique angle. |
| `icp` | yes | n/a | who you want to reach. Role, company size, vertical, geography. |
| `goal` | yes | n/a | what's the desired reply: book call / try free / give feedback / partnership |
| `channel` | yes | `email` | `email` or `linkedin` |
| `prospect_list` | no | n/a | optional CSV path with leads (`name,email,linkedin,company,role`) |
| `language` | no | `en` | `en` or `fr` |
| `seniority` | no | `mixed` | `founder` / `vp` / `manager` / `mixed`: adjusts tone |

## Prerequisites

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/exa-cli/bin:$HOME/cli-skills/firecrawl-cli/bin:$HOME/cli-skills/instantly-cli/bin:$PATH"

export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
export INSTANTLY_API_KEY="..."   # only if you want to push the campaign automatically
```

| CLI | Used for |
|-----|----------|
| `exa` | research the ICP (roles, pains, language, what they post about) |
| `firecrawl` | per-prospect personalization (scrape their site, blog post, podcast, About page) |
| `instantly` | optional: push the finished sequence into Instantly.ai |

## Workflow

**Step 1. ICP language scan.** Use Exa to surface what this ICP says about the problem you solve:
```bash
exa search "<ICP role> <pain area> reddit OR linkedin" --num-results 20 --type neural --json
exa search "<ICP role> linkedin post <year>" --num-results 15 --json
```
Extract:
- Pain phrases (their words, not yours).
- Common objections.
- What they already use (existing solutions to mention or avoid).
- What they ignore (status-quo defaults).

**Step 2. Hook angles.** From the ICP scan, generate 5 to 8 hook angles:
- Pain-first: "<pain phrase>: solved this by <approach>"
- Curiosity: "<surprising data point about their world>"
- Social proof: "<peer in same vertical> using <approach>"
- Status: "<they already do X>, but most miss Y"
- Direct value: "<specific deliverable> for free in 24h"
Rank by fit with `goal` and `seniority`.

**Step 3. Sequence design.** Load `skills/designing-sequences/SKILL.md` and `skills/applying-cialdini-to-cold-email/SKILL.md`. Build a sequence appropriate to the channel using widening-gap cadence (Day 0, +2-3d, +4-5d, +7d, +7-15d).

**Email (4 to 7 messages):**
1. **Initial hook** (Day 0): 50 to 80 words. Pain-first or curiosity-first. Single CTA. Cialdini: Reciprocity or Authority.
2. **Bump** (Day +2-3): 30 to 50 words. New angle or proof point. Reference message 1.
3. **Value drop** (Day +4-5): share a useful artifact (template, mini-audit, data point). Cialdini: Reciprocity (specific, not generic).
4. **Social proof** (Day +7): one named comparable customer or metric. Cialdini: Social Proof.
5. **Direct ask** (Day +10-12): clean, low-pressure: "worth 15 min next week?". Cialdini: Commitment (small yes).
6. **Breakup** (Day +14-21): graceful, leaves the door open. Often the highest-reply touch.

**LinkedIn:** load `skills/sequencing-linkedin-dm/SKILL.md`. Tactic ranking: Comment-then-DM > thoughtful DM (no template) > Voice note DM > InMail. Never pitch in the connection note.

**Step 4. Write each message.** Load `skills/copywriting-en/SKILL.md` (when `language: en`) or `skills/copywriting-fr/SKILL.md` (when `language: fr`). Constraints applied to every message:
- ≤ 90 words for cold email body, ≤ 60 for LinkedIn DM.
- Subject line 33 to 50 characters, lowercase, no emoji, references a specific trigger. See `assets/subject-line-patterns.md`.
- Specific opener. No "I hope this finds you well." See `assets/banned-patterns.md` for the full ban list.
- One CTA. No links unless the value drop calls for it.
- Founder-to-founder tone. Banned words: synergy, leverage, revolutionize, game-changer, 10x.
- Cialdini lever explicit per message. Cross-reference `assets/cialdini-channel-matrix.md`.
- Stage-aware angle per `assets/founder-psychology.md` (Idea / Proto / MVP / 20+ / Scale).
- For French: vouvoiement default per `assets/persona-tu-vous-policy.md`, ten mandatory rules in `references/fr-copywriting-rules.md`.

**Step 5. Personalization tokens.** For every message, list the dynamic tokens:
- `{{first_name}}`, `{{company}}`, `{{role}}`
- `{{personal_hook}}`: agent-generated per-prospect (Step 6).
- `{{specific_observation}}`: also per-prospect.

**Step 6. Per-prospect personalization** (only if `prospect_list` provided).
For each row in the CSV, the agent does a fast firecrawl pass on the prospect's site / LinkedIn-adjacent profile / latest post and generates:
- 1 sentence specific observation (what they posted / shipped / hired for / wrote about).
- 1 sentence personal hook tying that observation to the message angle.

```bash
firecrawl scrape <prospect.linkedin or company.com/about> --format markdown --only-main-content > /tmp/prospect-<id>.md
```

**Step 7. Pre-send review.** Load `skills/reviewing-cold-email/SKILL.md`. Audit the drafted sequence against the rubric: Cialdini lever coverage, deliverability checklist (`assets/deliverability-checklist.md`), banned-pattern presence, sequence pacing, personalization quality, CTA discipline. Rewrite any failing message. This is a self-check that runs before output, not an optional step.

**Step 8. Output: 3 deliverables.**

a) `sequence-templates.md`: the 4 to 7 message templates with `{{tokens}}`.
b) `personalized-leads.csv`: original prospect list + 2 new columns (`specific_observation`, `personal_hook`).
c) `import-instructions.md`: how to upload to Instantly (token mapping). Other CSV-based outbound tools follow the same column conventions.

**Step 9. Optional: push to Instantly.**
```bash
instantly campaign create --name "<project>-<icp>" \
  --sequence /path/to/sequence.json \
  --leads /path/to/personalized-leads.csv
```
Pause review before activation. Agent never auto-sends.

**Step 10. Save the report.** Use `assets/output-template.md`. Save to:
```
<your-projects-root>/<project>/cold-outreach-builder/outreach-<YYYYMMDD>/
  ├── sequence-templates.md
  ├── personalized-leads.csv
  ├── import-instructions.md
  └── outreach-summary-<YYYYMMDD>.md   # the report
```

## Output format

See `assets/output-template.md`. Required sections:
1. ICP language scan summary (pain phrases, objections, status quo).
2. Hook angles ranked.
3. Sequence overview (messages 1 to N with framing per message).
4. Each message in full (subject, body, CTA, Cialdini lever, personalization tokens).
5. Personalization sample (3 prospects with their `specific_observation` + `personal_hook`).
6. Sending guidance (cadence, caps, A/B angle, deliverability checklist).

## Output location

```
<your-projects-root>/<project-slug>/cold-outreach-builder/outreach-<YYYYMMDD>/
```

## Failure modes

- **No prospect list provided** → ship templates only, deliver `personalized-leads.csv` empty + instructions on how to add leads later.
- **ICP too vague** ("founders") → ask once for a sharper definition. If user resists, narrow on your own based on the offer and document the assumption.
- **Language mismatch** (LinkedIn ICP is mostly English but `language: fr` requested) → write both. Default to user's choice, ship the alternate as a `-en.md` / `-fr.md` companion file.
- **Goal is "book a call" with manager-level seniority** → flag friction; recommend value-drop sequence first, call ask in message 4 or 5.
- **Sender domain has no DMARC / SPF / DKIM** → flag as deliverability blocker. Run the `assets/deliverability-checklist.md` `dig` commands and refuse to ship a campaign until the records are in place. Cold email from a non-aligned domain in 2026 lands in spam.
- **Review skill flags ≥ 3 high-severity findings on a single message** → rewrite that message before output. Do not ship a sequence with an unresolved high-severity finding.

## Per-project config

```
<your-projects-root>/<project>/cold-outreach-builder/config.json
```

```json
{
  "project": "<project-slug>",
  "offer": "<2-sentence offer>",
  "icp": "<role + size + vertical + geo>",
  "goal": "book call",
  "channel": "email",
  "prospect_list": "<path to CSV or null>",
  "language": "en",
  "seniority": "founder"
}
```
