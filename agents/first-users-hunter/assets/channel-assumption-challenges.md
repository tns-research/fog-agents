# Channel assumption challenges

A short interrogation script run before scoring or experimenting on a channel. Surfaces the assumptions baked into "obvious" channel choices so they can be falsified before time is spent on them.

Used by both `scoring-channels` (to evaluate Confidence honestly) and `designing-channel-experiments` (to make hypotheses falsifiable).

---

## When to invoke

- Before scoring a channel that the founder considers obviously right ("of course we'll do Reddit", "everyone is on LinkedIn").
- Before designing an experiment, to make the hypothesis falsifiable.
- Whenever a channel has high ICE on first pass without explicit reasoning attached.

The cost is 10 minutes per channel. The savings are 14-day experiment slots not wasted on assumed-right channels.

---

## Five challenges to apply

### Challenge 1: Audience-fit assumption

> "Reddit is where my users are."

**Probe:**
- Which subreddit specifically? Name it.
- What % of recent posters in that subreddit match the target user persona? (Read 20 recent threads.)
- If overlap is <30%, this is not "Reddit"; this is "the wrong subreddit". The intuition was about the platform, not the community.

**Failure mode this catches**: confusing platform-level intuition with community-level reality. Reddit is 100% the right platform if your sub is /r/cscareerquestions and your persona is junior devs. It's the wrong platform if your sub is /r/Entrepreneur for B2B SaaS founders (too generic).

### Challenge 2: Density-vs-overlap assumption

> "There's a 200k subreddit for this, that's a huge audience."

**Probe:**
- What's the **active** poster count, not member count? (See `community-activity-signals.md` Gate 1.)
- What's the % of active posters that match the target user?
- Compute: active posters × overlap = your real audience. Often <100 humans even in a 200k sub.

**Failure mode this catches**: vanity-metric trap. Member count is meaningless without activity rate and persona overlap.

### Challenge 3: Founder-credibility assumption

> "I'll just post and they'll engage."

**Probe:**
- What is the founder's history in this community? Search their handle.
- If zero history: what's the path from stranger to credible voice in this community? Is it 2 weeks of helpful comments? An intro thread? A mod permission?
- Will the founder pay that cost, or is the plan "post and hope"?

**Failure mode this catches**: assumed credibility. Many channels have zero tolerance for stranger-pitches. The founder's first post will be ignored or removed unless they spend prior weeks earning context. This belongs in the Confidence dimension of ICE.

### Challenge 4: Vertical-assumption challenge

> "FinTech founders are on [X channel] because everyone says so."

**Probe:**
- Read 10 recent threads in [X channel]. Are FinTech founders actually posting? Or are they being talked about by recruiters and media?
- If no FinTech founders are posting, the "obvious" channel is consensus wisdom that has gone stale.
- Where are FinTech founders posting instead? (Often: vertical-specific communities, or no-channel-at-all because they network privately.)

**Failure mode this catches**: industry-folklore assumption. The community everyone says you should be in may be the community everyone is talking about, not the community where the persona actually shows up.

### Challenge 5: Conversion-mechanism assumption

> "If I post a great thread, people will DM me and ask about my product."

**Probe:**
- In recent threads where a founder shared their product, did the community DM them? Or did they comment, ignore, or downvote?
- What's the actual mechanism by which a thread converts to a conversation in this community?
- Is the mechanism "comment thread", "DM after thread", "external sign-up", or "no path at all"?

**Failure mode this catches**: imagined funnel. The founder mentally runs a funnel from "great post" to "first user" without checking the empirical conversion path in this specific community.

---

## How to apply during scoring

For each channel under consideration:

1. Run all five challenges. Write the answer next to each, even if "skipped, founder is established".
2. The answers feed into ICE: Impact (Challenge 1, 2, 4), Confidence (Challenge 3), and the experiment's hypothesis mechanism (Challenge 5).
3. A channel that survives all five challenges with strong answers earns its slot. A channel that needs hand-waving on 2+ challenges is parked.

---

## Example: applied to a candidate channel

```
Channel: r/SaaS

Challenge 1 (audience-fit): r/SaaS specifically. Read 20 recent threads:
  - 14 are founder-posted (70% target user overlap)
  - Persona match: ✓
Challenge 2 (density-vs-overlap): 480k members, ~120 unique posters/week, 70% overlap = ~84 real
  audience per week. Significant.
Challenge 3 (founder-credibility): founder has 6 prior comments on r/SaaS, all helpful, no removed
  posts. Confidence floor.
Challenge 4 (vertical-assumption): r/SaaS is consensus, but the consensus is correct here. Active
  founders post.
Challenge 5 (conversion-mechanism): recent founder threads attracted comments but few DMs. The
  mechanism is comment-thread, not DM. Hypothesis: post quality drives comment count, not DM count.
  Adjust experiment metric accordingly.

VERDICT: pass to scoring with Confidence ≥6.
```

---

## Anti-patterns to refuse

- **Skipping the challenges on "obvious" channels**. Obviousness is exactly when the assumption is most likely wrong.
- **Treating the challenges as a checkbox**. Each challenge needs a written answer with evidence (a link, a thread count, a percent), not "yes".
- **Using the challenges to justify a pre-decided channel**. The challenges are designed to falsify, not to confirm.

---

## Source

Adapted from first-principles reasoning patterns: question every assumption that feels obvious, especially the ones inherited from industry folklore. Specific challenge sequence calibrated for early-stage founder channel selection.
