# Community activity signals

Lookup table for the six activity gates and three dead-giveaways used by `gating-active-communities/SKILL.md`. Use this when scoring a candidate community before it enters the channel shortlist.

---

## The six gates (must pass all)

| Gate | Threshold | What it tells you | How to check |
|------|-----------|-------------------|--------------|
| 1. Unique posters per week | ≥10 | Real participation, not lurker-only | Count distinct authors of original posts in the last 7 days |
| 2. Most recent thread age | <48h | Community is awake | Sort by recent, read the timestamp |
| 3. Replies-per-post ratio | ≥2.0 | Conversational, not broadcast | Sum replies across last 20 threads / 20 |
| 4. Mod activity in last 7 days | yes | Active moderation = signal-to-noise stays high | Check mod handles for recent activity |
| 5. Q&A thread density | ≥30% of last 20 threads | Reply culture exists | Read titles, classify question vs announcement |
| 6. Topic diversity | ≥5 distinct topics in last 20 threads | Not a monoculture | Read titles, classify topic |

A community that fails any **one** of these is rejected from the shortlist.

---

## The three dead-giveaways (instant rejection)

| Dead-giveaway | Threshold | What it tells you |
|---------------|-----------|-------------------|
| A. Pinned welcome older than 12 months | last edit timestamp >365 days | Mods are autopilot, community is drifting |
| B. Job listings dominate | >40% of last 20 threads | Discussion culture eroded, became a job board |
| C. Self-promo dominates | >40% of last 20 threads are link drops | Became a billboard, organic reply rate collapsed |

These are independent of the six gates. A community can pass all six gates and still be rejected on a dead-giveaway.

---

## Quick scrape commands

```bash
# Reddit subreddit recent activity
firecrawl scrape "https://www.reddit.com/r/<sub>/new/" --format markdown --only-main-content

# IndieHackers group
firecrawl scrape "https://www.indiehackers.com/group/<slug>" --format markdown --only-main-content

# Hacker News submission stream
firecrawl scrape "https://news.ycombinator.com/newest" --format markdown --only-main-content

# Discord public channel preview (where available)
firecrawl scrape "https://discord.com/channels/<id>/<channel>" --format markdown --only-main-content
```

For private platforms (private Slack, members-only Discord, paid mastermind), there is no scrape path. Mark the community as `unverified` and surface to the founder.

---

## Worked examples

### Example 1: passes all gates

```
Community: r/SaaS
- Unique posters per week: 124    [pass]
- Most recent thread: 12 minutes ago    [pass]
- Replies-per-post: 4.1    [pass]
- Mod active 7d: yes (3 mod actions in last 48h)    [pass]
- Q&A density: 52%    [pass]
- Topic diversity: 9 topics    [pass]
- Dead-giveaways: none
DECISION: forward to scoring-channels
```

### Example 2: passes gates, fails dead-giveaway

```
Community: "B2B Founders Slack"
- Unique posters per week: 18    [pass]
- Most recent thread: 6h ago    [pass]
- Replies-per-post: 2.4    [pass]
- Mod active 7d: yes    [pass]
- Q&A density: 41%    [pass]
- Topic diversity: 6 topics    [pass]
- Dead-giveaway B: 58% of recent threads are hiring posts    [FAIL]
DECISION: reject (job-board drift)
```

### Example 3: gate 1 fail

```
Community: "Niche Vertical Discord"
- Unique posters per week: 4    [FAIL]
- Most recent thread: 2 days ago
- Member count: 8200
DECISION: reject (members exist, participation does not)
```

The 8200-member ghost-town pattern is the single most common false positive in channel research. Member count is vanity. Gate 1 is the truth.

---

## Calibration notes

- Thresholds are calibrated for founder-relevant communities (B2B SaaS, indie maker, niche professional, FR/EN startup). For consumer-facing communities (gaming, fandom), thresholds may need to scale up; for very niche professional pools (regulated industries with 200 members total), gate 1 may need to drop to ≥5.
- The agent should not auto-adjust thresholds. If the founder believes a marginal community is worth running anyway, log it as `marginal_pick_by_founder_override` with the reason, and run the experiment with extra-tight stop-rules.

---

## Anti-patterns to refuse

- **Treating "private" as "active"**. Gated communities can be vibrant or dead; you cannot infer from invisibility.
- **Inflating activity by counting bot posts**. If half the threads are RSS bots, subtract them before scoring gate 5.
- **Counting replies that are bumps or thanks**. Reply count means substantive replies. "Thanks!" is not a substantive reply.
- **Ignoring topic diversity for vertical communities**. Even a vertical community should have multiple sub-topics. A "SaaS founders" Slack where 90% of threads are "what's your stack" is a monoculture and rejects on gate 6.
