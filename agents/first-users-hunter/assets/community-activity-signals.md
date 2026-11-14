# Community activity signals

Lookup table for the six activity gates and three dead-giveaways used by `skills/gating-active-communities/SKILL.md` at Step 8, on the communities where signal people spoke.

---

## The six gates (one threshold each)

| Gate | Pass when | What it tells you | How to check |
|------|-----------|-------------------|--------------|
| 1. Unique posters, last 7 days | 10 or more | real participation, not lurkers | distinct authors of original posts |
| 2. Last original thread | 7 days old or less | the community is awake | sort by newest, read the timestamp |
| 3. Replies per thread | 1.0 or more | conversation, not broadcast | replies over the last 20 threads / 20 |
| 4. Moderation | an action in the last 30 days, or no visible spam | signal-to-noise stays high | role badges, pinned posts; `unmeasured` when invisible (never rejects alone) |
| 5. Question-and-answer share | 10 % or more of the last 20 threads | a reply culture exists | questions with a substantive answer |
| 6. Topic diversity | 5 or more topics in the last 20 threads | not a monoculture | classify titles |

Any failed gate rejects the community, with the measured value in the report. These are the stack's defaults, not figures from a study.

---

## The three dead-giveaways (instant rejection)

| Dead-giveaway | Threshold | What it tells you |
|---------------|-----------|-------------------|
| A. Pinned welcome older than 12 months | last edit more than 365 days ago | mods are on autopilot |
| B. Job listings dominate | more than 40 % of the last 20 threads | became a job board |
| C. Self-promo dominates | more than 40 % of the last 20 threads are link drops | became a billboard |

These are independent of the six gates.

---

## Free ways to read activity

| Platform | Path | Note |
|----------|------|------|
| Hacker News | `curl "https://hn.algolia.com/api/v1/search_by_date?tags=ask_hn&hitsPerPage=50"` | authors, `created_at_i`, `num_comments`, no key |
| GitHub | `curl "https://api.github.com/search/issues?q=repo:<owner>/<repo>+created:>=<date>"` | no key, 10 searches a minute |
| Reddit | official OAuth, `scripts/collectors/reddit.py` with `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` (free script app) | anonymous `.json` URLs answer 403 from servers (tested 2026-10-10) |
| Discourse forums | `<forum>/latest.json` | public forums only |
| Indie Hackers, newsletters, forums | any `scrape` provider of [`shared/tools.md`](../../../shared/tools.md) on the "latest" page | |
| Slack, Discord, WhatsApp, Telegram, paid groups | founder screenshots of the last week, read with `vision`, `verified_by: founder_screenshot` | a Discord channel URL fetched from outside shows the login page |

---

## Worked examples

### Example 1: passes all gates

```
Community: r/SaaS
- Unique posters per week: 124    [pass]
- Most recent thread: 12 minutes ago    [pass]
- Replies per thread: 4.1    [pass]
- Moderation: 3 mod actions in the last 48h    [pass]
- Q&A share: 52%    [pass]
- Topic diversity: 9 topics    [pass]
- Dead-giveaways: none
DECISION: forward to scoring-channels
```

### Example 2: passes gates, fails dead-giveaway

```
Community: "B2B Founders Slack"
- Unique posters per week: 18    [pass]
- Most recent thread: 6h ago    [pass]
- Replies per thread: 2.4    [pass]
- Moderation: unmeasured (closed group, founder screenshots)
- Q&A share: 41%    [pass]
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

- Thresholds are calibrated for founder-relevant communities (B2B SaaS, indie maker, niche professional, FR/EN startup). For consumer-facing communities (gaming, fandom), thresholds may need to scale up; for very niche professional pools (regulated industries with 200 members total), gate 1 may need to drop to 5.
- The agent should not auto-adjust thresholds. If the founder believes a marginal community is worth running anyway, log it as `marginal_pick_by_founder_override` with the reason, and run the experiment with extra-tight stop-rules.

---

## Anti-patterns to refuse

- **Treating "private" as "active"**. Gated communities can be vibrant or dead; you cannot infer from invisibility.
- **Inflating activity by counting bot posts**. If half the threads are RSS bots, subtract them before scoring gate 5.
- **Counting replies that are bumps or thanks**. Reply count means substantive replies. "Thanks!" is not a substantive reply.
- **Ignoring topic diversity for vertical communities**. Even a vertical community should have multiple sub-topics. A "SaaS founders" Slack where 90% of threads are "what's your stack" is a monoculture and rejects on gate 6.
