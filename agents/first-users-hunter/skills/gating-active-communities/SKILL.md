---
name: gating-active-communities
description: Distinguishes alive communities from ghost towns before a channel is scored or an experiment is planned in it. Applies six activity gates (unique posters per week, age of the last thread, replies per thread, moderation, question-and-answer share, topic diversity) plus three dead-giveaways (stale pinned welcome, job-listing dominance, self-promo dominance), each with one threshold. Reads public archives with free tools and closed groups (Slack, Discord, WhatsApp, Telegram) from founder screenshots. Use at Step 8 of first-users-hunter on the communities where signal people spoke. Triggers on "active community", "ghost town", "is this Slack alive", "dead community", "activity check".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# gating-active-communities

A channel enters the map because people with signals spoke there (`<run>/channels.json`). This skill then checks that the place is alive before the founder invests an experiment in it. Member count is never a proof. The thresholds below are this stack's defaults, not figures from a study; report the measured value next to each gate so the founder can judge a borderline case. Lookup table: [`assets/community-activity-signals.md`](../../assets/community-activity-signals.md).

## When to invoke

- Step 8, for each community of `channels.json` that holds two shortlisted people or more, and for a community the founder proposes.
- Whenever a community looks promising on member count alone.

## The six gates (one threshold each)

Measured on the last 20 threads (or the last 7 days for gate 1).

| Gate | Pass when | Measure |
|------|-----------|---------|
| 1. Unique posters, last 7 days | 10 or more | distinct authors of original posts |
| 2. Last original thread | 7 days old or less | timestamp of the newest thread, not a bump |
| 3. Replies per thread | 1.0 or more on average | replies summed over the threads, divided by their count |
| 4. Moderation | a moderator or admin acted in the last 30 days, or no visible spam in the sample | role badges, pinned posts, removed-post notices |
| 5. Question-and-answer share | 10 % or more of threads are questions with a substantive answer | read titles and first replies |
| 6. Topic diversity | 5 or more distinct topics | classify titles |

Gate 4 is often invisible without a session: when it cannot be measured, write `unmeasured` and decide on the five others; an unmeasured gate never rejects alone.

## The three dead-giveaways

| Dead-giveaway | Rejects when |
|---------------|--------------|
| A. Pinned welcome or rules | last edited more than 12 months ago |
| B. Job listings | more than 40 % of the last 20 threads |
| C. Self-promotion and link drops | more than 40 % of the last 20 threads |

## Decision

| State | Decision |
|-------|----------|
| Every measured gate passes, no dead-giveaway | `active`: forward to scoring-channels |
| One gate or more fails | `reject`, with the gate and the measured value |
| A dead-giveaway is present | `reject`, with the giveaway |
| No data a non-member can read, no founder screenshots | `unverified`: listed for the founder, out of scoring |

One rule, no exception: any failed gate rejects. A borderline value is written down, not argued around.

## Reading activity without paid tools

| Platform | Free path |
|----------|-----------|
| Hacker News | Algolia `search_by_date` on the topic or `tags=ask_hn`: authors and `created_at_i` per thread, `num_comments` |
| GitHub repo or org | search API `repo:<owner>/<repo> created:>=<date>`, issue and discussion comment counts |
| Reddit | official OAuth `/r/<sub>/new` with the founder's free app keys (`scripts/collectors/reddit.py`); anonymous JSON answers 403 from servers |
| Indie Hackers, Discourse forums, public newsletters | `scrape` the "latest" page; Discourse also serves `/latest.json` |
| Luma calendar | the calendar page: events of the last and next 30 days, guest counts |
| Slack, Discord, WhatsApp, Telegram, paid groups | founder screenshots (below); nothing else: a Discord channel URL fetched from outside returns the login page |

## Closed groups: founder screenshots

Most FR and EU founder communities live in closed groups. The founder joins, then drops 3 to 5 screenshots of the recent feed (scrolling one week back) in `<project>/first-users-hunter/inbox/`. With `vision`, read: authors, timestamps, replies per thread, question share, topics, pinned message date. Compute the gates from what is visible and mark the report line `verified_by: founder_screenshot` with the screenshot file names. Without `vision`, the founder pastes the exported text of the same week. Messages in those screenshots that are signals go to `manual-signals.csv` (`network: community`, `date_source: founder`).

## Output format

```yaml
community:
  name: "Ask HN"
  url: https://news.ycombinator.com/ask
  people_with_signals: 2          # from channels.json
  verified_by: public_archive     # or founder_screenshot, or unverified
  gates:
    unique_posters_7d: 41         # pass (10 or more)
    last_thread_age_days: 0       # pass (7 or less)
    replies_per_thread: 6.2       # pass (1.0 or more)
    moderation: unmeasured
    qa_share_pct: 85              # pass (10 or more)
    topics: 11                    # pass (5 or more)
  dead_giveaways: {stale_pinned_welcome: false, job_dominant: false, self_promo_dominant: false}
  decision: active
```

## Anti-patterns

- Member count as a proxy for activity.
- Passing a community because the founder is in it.
- Marking a closed group active from its landing page.
- Keeping a community in scoring when no signal person spoke there and the founder did not ask for it.
