---
name: first-users-hunter
description: Maps where your first 10 to 50 users actually hang out (Reddit, Slack/Discord, niche forums, IndieHackers, LinkedIn niches, IRL events). Pre-filters communities through six activity gates plus three dead-giveaway anti-signals so ghost-towns never reach the shortlist. Scores survivors with ICE multiplicatively (Impact × Confidence × Ease, 1-10 each), where Confidence absorbs founder reason-to-engage. Turns the top 3 to 5 channels into 14-day falsifiable experiments, each mapped to its dominant AARRR funnel stage with a single primary metric, a pre-registered success threshold, a stop-rule, and a learning to capture regardless of outcome. Returns a ranked channel list, 10 to 20 LinkedIn-adjacent target profiles via boolean patterns, channel-specific outreach templates, and a 14-day experiment plan. Run after idea validation, before broad acquisition.
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# First Users Hunter Agent

Find the first 10 to 50 real users for a new product. Map their watering holes online and IRL, gate them on activity signals, score with ICE, design falsifiable 14-day experiments per channel, write outreach templates per channel.

## When to run

After initial validation, when the question becomes: *"OK, the idea is real. Where do I find 10 humans who'll actually talk to me about it?"*

## Skills loaded

| Skill | When loaded |
|-------|-------------|
| `gating-active-communities` | Step 2: pre-filter ghost towns out of the channel pool before scoring. |
| `scoring-channels` | Step 6: ICE multiplicative scoring on the survivors. |
| `designing-channel-experiments` | Step 7: convert each top-3-to-5 channel into a 14-day falsifiable test. |

## Assets used

| Asset | Used by |
|-------|---------|
| `assets/community-activity-signals.md` | `gating-active-communities` six gates + three dead-giveaways |
| `assets/linkedin-search-patterns.md` | Step 5 boolean patterns for LinkedIn + Exa parallel queries |
| `assets/fr-startup-channels.md` | Step 2 candidate pool when `language: fr` or `geography: FR` |
| `assets/channel-assumption-challenges.md` | `scoring-channels` Confidence + `designing-channel-experiments` mechanism |
| `assets/output-template.md` | Step 8 report skeleton |
| `references/aarrr-funnel.md` | `designing-channel-experiments` stage-to-metric mapping |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `idea` | yes | n/a | one paragraph: what the product does, what problem it solves |
| `target_user` | yes | n/a | who is the early adopter, e.g. `"B2B SaaS founders 10-50 employees"`, `"freelance UX designers in France"` |
| `geography` | no | `global` | optional geo focus |
| `language` | no | `en` | `en` or `fr` |

## Prerequisites

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/exa-cli/bin:$HOME/cli-skills/firecrawl-cli/bin:$PATH"

export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
```

| CLI | Used for |
|-----|----------|
| `exa` | find communities, forums, events, LinkedIn-adjacent profiles |
| `firecrawl` | scrape community pages to verify activity gates and member counts |

## Workflow

**Step 1. Target user profile.** From `idea` + `target_user`, derive a 3-line profile:
- Job title or role pattern.
- Industry vertical + company size (if B2B).
- Daily pain context: what bothers them every Monday morning.

**Step 2. Online community scan + activity gating.** Search for active communities:
```bash
exa search "<role> community 2026" --num-results 15 \
  --include-domains reddit.com,indiehackers.com,producthunt.com,news.ycombinator.com,slack.com,discord.com --json
exa search "<problem> slack discord group" --num-results 15 --json
exa search "<industry> linkedin group" --num-results 10 --json
```

When `language: fr` or `geography: FR`, also seed candidates from `assets/fr-startup-channels.md`.

For each candidate community, load `skills/gating-active-communities/SKILL.md`. Apply the six gates (unique posters/week, recent thread <48h, replies-per-post ≥2, mod active 7d, Q&A density ≥30%, topic diversity ≥5 topics) and the three dead-giveaways (stale pinned welcome, job-listing dominance, self-promo dominance) using `assets/community-activity-signals.md`.

**Forward to scoring only communities that pass all six gates with no dead-giveaway.** Communities with private/gated access are marked `unverified` and surfaced to the founder for manual verification.

**Step 3. Niche / vertical platforms.** Search for vertical-specific watering holes (Substack publications, Notion directories, Lu.ma collections, niche forums):
```bash
exa search "best newsletter for <role>" --num-results 10 --json
exa search "<vertical> forum directory" --num-results 10 --json
```
List 5 to 8 with size and posting frequency. Same gating rules apply: a newsletter that hasn't shipped in 90 days is rejected.

**Step 4. IRL event scan.** Find recurring events where the target attends:
```bash
exa search "<role> meetup <geography> 2026" --include-domains lu.ma,meetup.com,eventbrite.com --num-results 15 --json
exa search "<industry> conference 2026" --num-results 10 --json
```
List 3 to 6 events with date, location, expected attendance pattern. For FR runs, cross-reference `assets/fr-startup-channels.md` IRL-events table.

**Step 5. LinkedIn-adjacent profile mapping.** Load patterns from `assets/linkedin-search-patterns.md`. Produce both:
- 3 to 5 LinkedIn boolean queries the founder can paste into Sales Navigator (UPPERCASE operators, max ~15 operators, parenthesized).
- Parallel Exa queries that mirror the same boolean intent on the public web (personal sites, IndieHackers, Read.cv, podcast guest pages):
```bash
exa search '"<role>" "<vertical>" -recruiter' \
  --include-domains indiehackers.com,about.me,read.cv \
  --num-results 20 --type neural --json
```
For each profile: name, role, company, why they fit, public link.

**Step 6. Channel scoring (ICE multiplicative).** Load `skills/scoring-channels/SKILL.md`. For each channel surviving Step 2-5, apply the five challenges in `assets/channel-assumption-challenges.md`, then score Impact × Confidence × Ease (1-10 each, multiplicative). Confidence absorbs founder reason-to-engage. **Reject any channel with a 1 in any dimension regardless of product.** Pick top 3 to 5.

**Step 7. Channel experiments (14-day, falsifiable).** Load `skills/designing-channel-experiments/SKILL.md`. For each top channel, locate it on the AARRR funnel using `references/aarrr-funnel.md`, then produce one experiment block: hypothesis (with mechanism), primary metric mapped to AARRR stage, success threshold, failure threshold, sample size, stop-rule, and the learning to capture regardless of outcome.

**Step 8. Outreach template per top channel.** For each top-3-to-5 channel, write **one** template:
- 2 to 3 sentences max.
- Founder-to-user tone (no marketing speak).
- Frame as **problem-validation conversation** or **value offer**, never as a pitch.
- Channel-appropriate (Reddit DM ≠ LinkedIn message ≠ Lu.ma event intro).

**Step 9. Write the report.** Use `assets/output-template.md`. Save to:
```
<your-projects-root>/<project>/first-users-hunter/first-users-<YYYYMMDD>.md
```

A JSON sidecar `first-users-output.json` is produced alongside the Markdown report (cross-cutting convention C1) so re-scoring sweeps can run without re-querying APIs.

## Output format

See `assets/output-template.md`. Required sections:
1. Target user profile (3 lines).
2. Channel inventory (8-12 communities, 5-8 niche platforms, 3-6 events) with gate-report per community.
3. LinkedIn-adjacent profile list (10-20 humans with rationale) + 3-5 boolean queries.
4. Channel scoring table (ICE multiplicative, with one-line evidence per dimension).
5. Top 3 to 5 channels with 14-day experiment blocks (hypothesis, metric, threshold, stop-rule, learning).
6. Outreach template per top channel.
7. Suggested 14-day execution plan + re-score date (D+14).

## Output location

```
<your-projects-root>/<project-slug>/first-users-hunter/first-users-<YYYYMMDD>.md
```

## Failure modes

- **No active communities found** → broaden role definition, drop geography filter, retry. If still empty, document and pivot to IRL + LinkedIn-only strategy.
- **All candidate communities fail activity gates** → before pivoting, expand the candidate pool (more exa queries, adjacent verticals). If still all failing, the persona may be too niche for community-based acquisition; recommend warm-intro + LinkedIn-DM-only strategy.
- **Activity level unverifiable** (private Slack, gated Discord) → mark `unverified` in the inventory, do not auto-include in scoring, flag for the founder to verify manually.
- **LinkedIn search blocked or rate-limited** → fall back to IndieHackers, Read.cv, About.me, and podcast guest pages: they are publicly indexed.
- **Geography too tight** → if `geography` returns < 5 channels, expand to nearest equivalent (FR → DACH or Benelux for some verticals; or escalate to global English) and note the expansion in the report.
- **Top channels all score below 100 ICE** → the persona has no clear watering hole. Recommend the founder run 5 manual customer interviews via cold-email or warm intros to refine the persona before re-running this agent.
- **Channel scores 10×10×1 (or any dimension at 1)** → veto, regardless of product. Document in the rejection appendix with reason.

## Per-project config

```
<your-projects-root>/<project>/first-users-hunter/config.json
```

```json
{
  "project": "<project-slug>",
  "idea": "<one-paragraph product description>",
  "target_user": "<who is the early adopter>",
  "geography": "global",
  "language": "en"
}
```

If missing, the agent copies `config.example.json` and asks for missing values in chat.
