---
name: scoring-channels
description: Scores candidate user-acquisition channels using ICE (Impact × Confidence × Ease) on a 1-10 scale, multiplicatively. Multiplication amplifies real differences between channels, a channel scoring 10/2/8 (=160) is correctly recognized as worse than 6/7/6 (=252) even though their additive sums look similar. Encodes reason-to-engage (founder identity, contribution history) inside the Confidence dimension so that "easy but no credibility" channels are demoted automatically. Re-score every two weeks because Confidence rises with data. Triggers on words like "score", "rank", "prioritize channels", "ICE", "which channel first".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# scoring-channels

The prioritization layer. Once Steps 2 to 5 of the agent workflow have produced a long list of candidate channels (online communities, niche platforms, IRL events, LinkedIn-adjacent profile pools), this skill picks the 3 to 5 worth running first.

The asset that pairs with this skill is `assets/community-activity-signals.md` (gates Confidence) and `assets/channel-assumption-challenges.md` (kills lazy assumptions baked into Impact).

---

## When to invoke

- Step 6 of the agent workflow: the long list exists, the founder needs the short list.
- Re-scoring sweeps every 2 weeks while channels are running. Confidence climbs with data; channels that were guesses become evidenced (or get demoted).
- Whenever a channel "feels right" but has no scoring artifact attached. Feelings are not a prioritization method.

---

## Inputs

- `channel_list`: candidate channels from Steps 2 to 5 (community / platform / event / profile pool).
- `target_user`: from agent input. Used to evaluate Impact relevance.
- `founder_context`: founder's existing footprint per channel. Have they posted there? Do they know members? Are they invisible? Used to evaluate Confidence.

---

## The ICE model

Three dimensions, each rated 1 to 10. **Final score is the product, not the sum.**

```
ICE_score = Impact × Confidence × Ease
```

Range: 1 to 1000. A score above ~250 is an active candidate. Below ~100 is parked.

### Why multiplicative

Additive scoring (1-5 + 1-5 + 1-5 = max 15) compresses real differences. A channel rated 5+1+5 = 11 looks comparable to 4+4+4 = 12, but the first one is **broken on Confidence** and almost guaranteed to fail. Multiplication: 5×1×5 = 25 vs 4×4×4 = 64. The broken-Confidence channel is correctly demoted by 2.5×.

A 1 in any dimension caps the total severely. That is the point. A channel where the founder has zero credibility, zero access, or zero reach is not a good channel even if the other two dimensions are perfect.

---

## Dimension 1: Impact (1 to 10)

How big is the upside if this channel works?

| Score | Criterion |
|-------|-----------|
| 10 | Audience is exactly the target user, concentrated, not yet served by a competitor presence. Conversion to first conversations would be high. |
| 8 | Audience is the target user but mixed with adjacent personas. Or an aligned competitor is already there reaping signal. |
| 6 | Audience overlaps with the target user 30-60%, broader category, narrower fit. |
| 4 | Audience is one persona-step away (e.g. target = "freelance designer", channel = "small agency owner"). Useful spillover. |
| 2 | Audience is two personas away or a different vertical entirely. |
| 1 | Audience does not include the target user. Stop. Do not run this channel. |

**Concrete proxies for Impact**: estimated overlap of channel members with target user (%); average post engagement (replies, not vanity); presence of identifying language ("I'm a [target role]") in member bios; thread topics matching target's pain.

**Anti-pattern**: rating Impact by raw audience size. A 100k subreddit with 5% target-user overlap is worse than a 2k Slack with 80% overlap. Score the **concentrated target user count**, not member count.

---

## Dimension 2: Confidence (1 to 10)

How sure are you that running this channel will produce conversations? This dimension absorbs **reason-to-engage**.

| Score | Criterion |
|-------|-----------|
| 10 | Founder is already a known contributor (months of helpful posts, recognizable handle). Direct evidence the channel converts (case studies of similar founders, prior wins). |
| 8 | Founder has a credible reason to be there (alumni, relevant role, prior member). No active history but not a stranger. |
| 6 | Founder is a stranger but the community welcomes outsiders with relevant questions. Public access, low gatekeeping. |
| 4 | Founder is a stranger and gatekeeping is real (introduction required, members-only thread, mod approval). |
| 2 | Founder has no reason to be there and the channel actively penalizes self-promo or strangers. |
| 1 | The community is gated AND the founder has zero credibility AND prior outsider attempts have been removed. |

**The reason-to-engage rule**: a channel where the founder has no reason to engage, no prior contribution, no shared context, no relevant identity, caps Confidence at ~3. This is what kills "high Ease" channels: they are easy to post in, but the founder will be ignored or banned.

**Concrete proxies for Confidence**: founder's post history in this channel (search their handle); shared cohort or alumni status; explicit invitation; community moderator-tolerance for new founders (look for "founders, introduce yourselves" threads).

---

## Dimension 3: Ease (1 to 10)

How cheap is it (time + effort) to run a single touch on this channel?

| Score | Criterion |
|-------|-----------|
| 10 | Public, free to post, no application, no quota. Reddit, IndieHackers, X, public Discord. Single message = 10 min. |
| 8 | Public but requires a quality bar (HN, niche subreddits with rules). Single message = 20-30 min including read-up. |
| 6 | Free Slack/Discord with introduction etiquette. Single message = 30-45 min including warming up and replying to others first. |
| 4 | Application or invitation required. One-time cost is high; per-message cost is then medium. |
| 2 | Paid membership, gated mastermind, exclusive list. Per-touch cost includes the subscription amortized. |
| 1 | IRL events requiring travel + days of attendance. Or 1:1 introductions only via warm referrer. |

**Anti-pattern**: rating Ease by Step 1 cost only. A subreddit ban on Day 2 makes Ease = 1 retroactively. Discount Ease by likelihood of getting blocked, banned, or buried.

---

## Scoring procedure

1. List every channel from Steps 2 to 5 in a table with columns: name, type, target-user fit estimate, founder reason-to-engage, posting cost.
2. For each, score Impact × Confidence × Ease. Cite **one specific reason** per dimension. No bare numbers.
3. Compute the product. Sort descending.
4. Pick the top 3 to 5 (depending on founder bandwidth) where each dimension is at least 5. **Reject any channel with a 1 in any dimension regardless of the product.**
5. For the picks, draft the assumption being tested (per `assets/channel-assumption-challenges.md`) and pass to `designing-channel-experiments`.

**Output table format**:

```yaml
channels:
  - name: "Indie Hackers Slack #products-and-features"
    type: community
    impact: 8           # 65% target-user overlap, identifying bios, active threads
    confidence: 6       # founder is a stranger but channel welcomes intros
    ease: 8             # public, quality bar but no gatekeeping
    score: 384
    pick: true
    assumption: "Posting a build-in-public update will yield 3+ replies from target users in 48h."
  - name: "B2B SaaS Founders LinkedIn Group"
    type: community
    impact: 6
    confidence: 3       # founder has no presence, gatekept by mod
    ease: 4             # mod approval required for posts
    score: 72
    pick: false
    assumption: null
```

---

## Re-scoring cadence

Re-score every 2 weeks while channels are running. The dimension that changes most is **Confidence**:

- Channels that produce replies → Confidence climbs (was a guess, now evidenced).
- Channels that produce silence → Confidence drops (was a guess, now disproven).
- Impact rarely changes (target audience does not shift in 2 weeks).
- Ease can drop fast if the channel rate-limits, bans, or buries the founder's posts.

After 2 to 3 re-scorings, the agent has a real-data ranking. The first ranking is a hypothesis; the third ranking is a finding.

---

## Anti-patterns to refuse

- **Listing every channel mentioned in the corpus**. The agent's value is the cut, not the breadth. Aim for top 3 to 5 actionable, not 20 listed.
- **Scoring channels in isolation from founder identity**. A founder who is invisible on LinkedIn will fail on LinkedIn DM regardless of audience size. Confidence absorbs founder fit.
- **Treating multiplication as a tiebreaker only**. The product is the score. Two channels with similar products are tied; large products always win.
- **Skipping the "1 cap" rule**. A 10×10×1 = 100 is not a viable channel. The 1 is a veto, not a discount.
- **Re-scoring on vibes**. Re-score from data: reply count, conversation count, time-to-response, conversion rate.

---

## Source

Adapted from the ICE prioritization framework (Sean Ellis, Hiten Shah, BJ Fogg variants) with two specific deltas vs the generic version: (1) multiplicative aggregation rather than additive, (2) Confidence dimension absorbs reason-to-engage rather than treating it as a separate axis.
