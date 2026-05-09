---
name: gating-active-communities
description: Distinguishes alive communities from ghost towns before they enter the channel-scoring shortlist. Applies six activity gates (unique posters per week, recent thread recency, replies-per-post, mod activity, answer-thread density, post diversity) plus three dead-giveaway anti-signals (stale pinned welcome, job-listing dominance, self-promo dominance). A community that fails any single gate is rejected outright, regardless of vanity-metric member count. Triggers on words like "active community", "ghost town", "is this Slack alive", "dead community", "activity check".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# gating-active-communities

The pre-filter layer. Run before a community enters the channel-scoring shortlist. Communities that fail this filter never reach `scoring-channels` and never burn founder bandwidth.

The asset that pairs with this skill is `assets/community-activity-signals.md` (the lookup table for the six gates).

---

## When to invoke

- Step 2 of the agent workflow: after exa returns candidate communities, before they go to scoring.
- Whenever a candidate community looks promising on member count alone. Member count is a vanity metric. Activity gates filter for real life.
- Whenever the founder says "I'm thinking of trying [community]" without prior evidence it's active.

---

## Why pre-filter at all

The default failure mode of channel research is the **180k-member dead Slack**, a community that looks great on its landing page (member count, professional vibe, founder testimonials) but where the last real thread was three months ago and the active poster pool is 40 humans, half of whom are recruiters.

Scoring a dead community produces a shortlist where the founder spends 14 days posting into a void and learns nothing. The pre-filter prevents that.

---

## The six activity gates

A community must pass **all six** to enter the shortlist. A single failure rejects it.

### Gate 1: Unique posters per week ≥10

Members with at least one post in the last 7 days. Not member count. Not view count. Original posters.

**How to check**: scrape the last 7 days of threads from the public archive, count distinct authors.

**Reject if**: <10 distinct posters per week. Indicates a community with a long-tail of lurkers and a tiny core that probably knows each other already (low chance of new-founder traction).

### Gate 2: Most recent thread <48 hours old

The most recent original post (not a bump or reply) is within 48 hours.

**How to check**: open the channel landing page or last-post timestamp. Sort by recent.

**Reject if**: most recent thread is older than 7 days. The community is sleeping. Posting into it gets buried by the next person who shows up after a month.

### Gate 3: Replies-per-post ratio ≥2.0

Across the last 20 threads, the average reply count divided by post count.

**How to check**: scrape thread list, sum replies / count of threads.

**Reject if**: <1.0 (broadcast-only behavior, people post but no one engages). 1.0 to 2.0 is the marginal band; only pass if other gates are strong.

### Gate 4: Moderator or admin active in last 7 days

A mod has posted, replied, or pinned something in the last 7 days.

**How to check**: identify mods (member roles), search recent activity by their handles.

**Reject if**: mods inactive >30 days. A community without active moderation tends to drift into spam, which lowers signal-to-noise and gets your post buried.

### Gate 5: Question-and-answer threads exist (not just announcements)

At least 30% of recent threads are questions getting substantive answers, not announcements / launches / hires.

**How to check**: read the titles of the last 20 threads. Count question-format threads.

**Reject if**: <10% of recent threads are Q&A. Indicates a broadcast medium where members shout into the void rather than help each other. Founder posts will not get replies because no one is in reply mode.

### Gate 6: Post diversity (no single-topic dominance)

The last 20 threads cover at least 5 distinct topics (product launches, hiring, tooling questions, market chatter, intros, etc.).

**How to check**: classify recent thread topics.

**Reject if**: 90% of recent threads are one topic (e.g. all hiring posts, all "what's your stack?", all newsletter shares). A monoculture community has narrow signal even if it's active.

---

## The three dead-giveaways (instant rejection)

Even if the gates pass, these signal a dying community:

### Dead-giveaway A: Pinned welcome message older than 12 months

A community that hasn't refreshed its onboarding in over a year is on autopilot. Active mods refresh. Inactive mods don't.

### Dead-giveaway B: Job listings dominate (>40% of recent threads)

A "founder" community where every other thread is "we're hiring" has lost its discussion culture. It's a job board with a Slack skin.

### Dead-giveaway C: Self-promo dominates (>40% of recent threads are link drops)

A community that has become a billboard. Reply rate to non-promotional posts collapses. Founder's substantive question gets buried under three Product Hunt launches.

---

## Decision matrix

| State | Decision |
|-------|----------|
| All 6 gates pass, no dead-giveaway | Forward to `scoring-channels` |
| 1 gate fails, no dead-giveaway | Reject. Note in inventory as "marginal, fails gate N". |
| Any dead-giveaway present | Reject. Note in inventory with the giveaway. |
| Gates uncheckable (gated Slack, members-only) | Mark as `unverified`, do not auto-include. Flag for manual founder verification. |

---

## How to scrape activity signals

For platforms with public archives:

```bash
# Reddit
firecrawl scrape "https://www.reddit.com/r/<sub>/new/" --format markdown
# Discord servers with public web preview
firecrawl scrape "https://discord.com/channels/<id>" --format markdown
# IndieHackers groups
firecrawl scrape "https://www.indiehackers.com/group/<slug>" --format markdown
```

For private/gated platforms (private Slack, members-only Discord, paid groups), the agent cannot verify directly. Mark as `unverified` and surface to the founder. **Never mark a private community as "active" without first-hand evidence.**

---

## Output format

Append a per-community gate report to the channel inventory:

```yaml
community:
  name: "Indie Hackers Slack #products-and-features"
  url: https://...
  member_count: 4200
  gates:
    unique_posters_7d: 47           # gate 1: pass (≥10)
    most_recent_thread: 14h ago     # gate 2: pass (<48h)
    replies_per_post: 3.4           # gate 3: pass (≥2)
    mod_active_7d: true             # gate 4: pass
    qa_thread_pct: 38               # gate 5: pass (≥30%)
    topic_diversity: 7 topics       # gate 6: pass (≥5)
  dead_giveaways:
    stale_pinned_welcome: false
    job_dominant: false
    self_promo_dominant: false
  decision: forward_to_scoring
  notes: "Strong founder-discussion culture, several recent first-user threads."
```

For rejected communities:

```yaml
community:
  name: "B2B SaaS Founders Discord"
  decision: reject
  reason: "Gate 5 fail (8% Q&A), dead-giveaway B (52% hiring posts)."
```

---

## Anti-patterns to refuse

- **Member count as proxy for activity**. The most cited mistake. Pre-filter exists specifically to override this.
- **Auto-passing communities the founder is in**. Founder bias. Run the gates anyway.
- **Single-gate rejection on ambiguous evidence**. If Gate 3 is exactly 1.0 (the marginal band), look at Gates 5 and 6 before rejecting. Marginal alone is not a veto.
- **Marking unverified communities as active**. Do not invent activity signals from a community's about page. Mark `unverified` and surface to founder.
- **Skipping the dead-giveaways**. They are independent of gate scores. A 6/6-passing community with a self-promo monoculture is still rejected.

---

## Source

Adapted from active-community heuristics published by First Round, Stripe Atlas, and the Slack-and-Discord activity-research community. Gate thresholds calibrated to founder-relevant communities (B2B SaaS, indie maker, niche professional) where reply rate matters more than reach.
