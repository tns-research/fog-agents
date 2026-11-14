# AARRR funnel

The Pirate Metrics framework (Dave McClure, 500 Startups, 2007) for breaking customer flow into five stages. Used by `designing-channel-experiments` to locate where a candidate channel acts in the funnel, and therefore which metric the experiment should measure.

---

## The five stages

### A - Acquisition

How a stranger first becomes aware of the product or founder. Visit, follow, sign-up to a list. The metric is **first touch**: clicks, visits, follows, signups.

**Channels that act here**: SEO, paid ads, public posts (HN, Reddit, IH, X), newsletter sponsorships, podcast appearances, conference talks.

### A - Activation

The first meaningful experience. Not just signed up, **understood and used something**. Reads a post, replies to a thread, books a call, sends a DM, completes onboarding.

**Channels that act here**: introduction threads in Slack/Discord, IRL meetup conversations, LinkedIn DMs (cold or warm), founder build-in-public threads that draw replies, 1:1 outreach with a meeting hook.

### R - Retention

The user comes back. Returns to a thread, replies again, opens the next email, logs into the product on day 2.

**Channels that act here**: rare for first-users-hunter. Retention lives downstream of first conversations. Out of scope for a first-50-users channel hunt unless explicitly testing community-driven retention.

### R - Referral

The user brings someone else. Shares the post, mentions the founder, makes an intro.

**Channels that act here**: invitation-driven communities, content that gets reshared (HN front page, viral X thread), referral programs (rare at this stage).

### R - Revenue

The user pays. Conversion to a trial-to-paid, signed contract, paid subscription.

**Channels that act here**: typically downstream of all the above. **Out of scope for first-users-hunter**, measuring revenue on a first-user channel is a category error. The agent runs upstream of paid conversion.

---

## Channel-to-stage mapping

The single most useful table for `designing-channel-experiments`:

| Channel | Dominant stage | Secondary stage | Primary metric |
|---------|----------------|-----------------|----------------|
| Reddit / HN / IH posts | Acquisition | Activation (DM after thread) | Click-through OR DM count |
| Slack/Discord intro thread | Activation | Acquisition | Substantive replies |
| LinkedIn cold DM | Acquisition | Activation | Reply rate, then call rate |
| LinkedIn warm DM (after comment) | Activation | - | 1:1 conversation rate |
| IRL meetup attendance | Activation | Referral | Conversations + follow-ups scheduled |
| Newsletter sponsorship | Acquisition | - | UTM clicks, sign-ups |
| Podcast guest spot | Acquisition | Referral | Episode-attributed sign-ups + share count |
| Public build-in-public thread | Acquisition | Activation | Followers earned + DMs received |
| Personal outreach (warm intro) | Activation | Referral | Conversations had + intros generated |

The dominant stage is what the experiment metric measures. The secondary stage is the bonus signal that's nice-to-have but not falsifiable.

---

## Common stage-mismatch errors

### Error 1: measuring revenue on an acquisition channel

> "I posted on HN for 2 weeks and only got 3 paid users, so HN is dead."

The error: revenue is too far downstream of HN. The acquisition stage might have produced 200 visitors, of which 30 read the landing, of which 8 signed up, of which 3 paid. The channel may be working perfectly at the acquisition stage; the conversion problem is downstream and unrelated.

### Error 2: measuring activation on an awareness channel

> "My podcast guest spot didn't get me 10 DMs."

The error: most podcast listeners do not DM. The right metric is awareness lift (mentions, follows, sign-ups attributed via tracked link), not 1:1 conversation count.

### Error 3: measuring retention on a first-touch channel

> "I posted in Slack and got 5 great replies, but no one engaged with my next post."

The error: a single great-reply thread is an activation event. Whether they engage with the next post is retention, which depends on the founder's ongoing presence in the community, not the original channel decision.

---

## How to apply per experiment

1. Locate channel on AARRR (use the table above).
2. State the metric in the language of that stage.
3. **Do not measure across stages within one experiment.** A channel that "delivers acquisition" cannot be marked failed for poor activation; that's a different experiment.
4. Multi-stage channels (e.g. Reddit producing both clicks and DMs) get a primary metric and a secondary metric, with thresholds for each stated separately.

---

## Why first-users-hunter rarely measures Retention or Revenue

The agent runs in the **first 50 users** zone. By definition, this is upstream of paid conversion and upstream of long-term retention. Most channels at this stage are tested for:

- Will a target user notice me here? (Acquisition)
- Will they engage in a 1:1 conversation? (Activation)

That's the entire scope. Retention and revenue are downstream agents' problems (`growth-experiment-generator`-type agents that operate post-PMF). The first-users-hunter that scopes itself to AAR (acquisition + activation + the start of referral) keeps experiments tight and fast.

---

## Source

Dave McClure, 500 Startups (2007), original AARRR framing. Stage-to-channel mapping calibrated for 2026 founder-stage acquisition where AI Overviews + community gating shifted the channel mix vs the original 2007 SaaS examples.
