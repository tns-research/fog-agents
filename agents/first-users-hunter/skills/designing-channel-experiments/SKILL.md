---
name: designing-channel-experiments
description: Turns each shortlisted channel into a falsifiable 14-day experiment with a stated assumption, a single primary metric, a pre-registered success threshold, a stop-rule, and a learning to capture regardless of outcome. Uses the AARRR funnel as the metric framework, every channel is mapped to its dominant funnel stage so the metric is measured at the right step. Replaces "post and hope" channel runs with a structured test that produces a decision at the end. Triggers on words like "experiment", "test", "hypothesis", "14-day", "AARRR", "what to measure".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# designing-channel-experiments

The execution-design layer. Each top-3-to-5 channel from `scoring-channels` becomes a 14-day experiment with a falsifiable hypothesis and a clear decision rule.

The reference that pairs with this skill is `references/aarrr-funnel.md` (which funnel stage the channel maps to) and `assets/channel-assumption-challenges.md` (kills assumptions baked into the hypothesis).

---

## When to invoke

- Step 7 of the agent workflow: top channels are scored, now convert each into a runnable test.
- After every 14-day cycle: review experiment outcome, update Confidence in `scoring-channels`, design the next round.
- Whenever the founder is "running channels" without an explicit success threshold. That's posting, not testing.

---

## The 4-step process

```
1. Locate the channel on AARRR
2. State the hypothesis (falsifiable)
3. Pre-register metric, threshold, sample size, stop-rule
4. Define the learning (so failure is also useful)
```

Skip any step and the experiment becomes a vibe check.

---

## Step 1: Locate the channel on AARRR

Each channel has a dominant funnel stage. Measuring the wrong stage is the most common failure mode. See `references/aarrr-funnel.md` for the full framework.

| Channel type | Dominant AARRR stage | Primary metric to measure |
|--------------|---------------------|---------------------------|
| Reddit / HN / IndieHackers post | Acquisition | Click-through to landing OR DM/reply count |
| Slack / Discord introduction thread | Activation | Reply count + 1:1 conversation conversions |
| LinkedIn DM (cold) | Acquisition → Activation | Reply rate, then call-booking rate |
| LinkedIn DM (warm via comment) | Activation | 1:1 conversation rate |
| IRL meetup attendance | Activation | Conversations had + follow-ups scheduled |
| Newsletter sponsorship / mention | Acquisition | UTM clicks + sign-ups |
| Podcast guest appearance | Acquisition + Referral | Episode-attributed sign-ups + content reuse |
| Public build-in-public thread | Acquisition + Activation | Followers earned + DMs received |

**Anti-pattern**: measuring Revenue or Retention on a first-user channel. Too early. The first-users-hunter agent is upstream of paid conversion. The right metric for an early-stage channel is conversations had, not deals closed.

---

## Step 2: State the hypothesis (falsifiable)

The hypothesis template:

```
If I [action] on [channel] for [duration], then [primary metric] will reach [threshold]
because [behavioral mechanism specific to target user on this channel].
```

Examples:

✅ "If I post a build-in-public weekly update on Indie Hackers for 14 days (3 posts), then I will receive ≥5 substantive replies from B2B SaaS founders because IH culture rewards specific, numerical, vulnerable updates from operators they recognize as one-of-them."

❌ "I'll try posting on Indie Hackers and see what happens." (Not falsifiable. No threshold. No mechanism.)

❌ "If I post on Indie Hackers, I will get users." (Vague metric. No timeframe. No mechanism.)

The behavioral mechanism is the part most experiments skip. Without it, a failed experiment teaches nothing, you don't know if the channel is wrong, the action is wrong, or the mechanism didn't fire. With it, failure narrows the search.

---

## Step 3: Pre-register metric, threshold, sample size, stop-rule

**Primary metric**: one number, mapped to the AARRR stage from Step 1. Not "engagement", too vague. Not three metrics, too easy to cherry-pick post-hoc.

**Success threshold**: stated as a number, not "good". What value of the metric counts as success? What value counts as failure? What's the boring middle?

```yaml
primary_metric: substantive replies in 14 days
success_threshold: 5+ replies      # decision: scale this channel
failure_threshold: 1- replies       # decision: drop this channel
inconclusive_band: 2-4 replies      # decision: extend 14 days, smaller commitment
```

**Sample size**: how many touches does the experiment include? "3 posts" is a sample size. "Some posts" is not. Without a sample size, success and failure are unfalsifiable because you can always say "I didn't try enough."

**Stop-rule**: the condition that aborts the experiment early.

| Trigger | Stop reason |
|---------|-------------|
| Banned or post removed | Channel disqualified, do not retry without rule change |
| 0 replies after 50% of touches | Failure trajectory clear, save remaining bandwidth |
| Inappropriate signal (bots, spam) | Quality issue, not a signal worth scaling |

---

## Step 4: Define the learning

The bar is: **regardless of whether the metric hits, the experiment must produce a transferable learning**.

| Outcome | Learning shape |
|---------|----------------|
| Hit threshold | What specifically about the action / mechanism / channel made it work? Which sub-action drove the most signal? Can you isolate the cause? |
| Failed threshold | Was the channel wrong, the action wrong, or the mechanism wrong? Test alternative mechanism on the same channel before dropping. |
| Inconclusive | Why is the signal noisy? Sample too small, audience mismatch, action too generic? Refine and extend. |

A common failure: "the experiment didn't work, moving on" with no diagnosis. That's wasted budget. Force a 1-paragraph diagnosis at the end of every 14 days.

---

## Output format

For each top-3-to-5 channel, produce one experiment block:

```yaml
experiment:
  channel: "Indie Hackers Slack #products-and-features"
  aarrr_stage: activation
  hypothesis: |
    If I post 3 build-in-public weekly updates on IH for 14 days (one per week with concrete metrics + 1 ask),
    then I will receive 5+ substantive replies from B2B SaaS founders
    because IH rewards specific, numerical, vulnerable updates from peer operators.
  primary_metric: substantive_replies_count
  success_threshold: 5
  failure_threshold: 1
  inconclusive_band: [2, 4]
  sample_size: 3 posts over 14 days
  stop_rule: "Banned or 0 replies after post 2 → drop"
  learning_to_capture: "If success: which post variant got the most signal? If failure: was the mechanism (vulnerability) wrong, or the channel wrong? Re-test on a peer Slack."
  re_score_after: 14 days
```

Append to the report under "Experiment plan". The next 14 days have a structure.

---

## Anti-patterns to refuse

- **Running multiple channels without per-channel hypothesis**. Causes attribution mush. One hypothesis per channel.
- **Measuring three metrics**. Reduces to cherry-picking the one that came out positive. One primary metric.
- **No stop-rule**. Founder runs the channel for 30 days "to be sure" when the signal was clear by Day 5. Stop-rule preserves bandwidth.
- **No mechanism in the hypothesis**. Failure teaches nothing. Mechanism is the part that fails informatively.
- **Re-using a generic experiment template across channels**. Each channel has its own dominant AARRR stage and its own mechanism. Templates are starts, not deliverables.

---

## Source

Adapted from growth-experiment-generator's 4-step process (analysis → research → AARRR audit → action plan), restructured around channel-as-unit-of-test and AARRR-stage-as-metric-locator. Hypothesis template adapted from Lean Analytics and Experimentation Works (Stefan Thomke).
