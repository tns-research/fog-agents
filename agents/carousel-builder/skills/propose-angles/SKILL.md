---
name: propose-angles
description: Turns research.md into 3 to 5 distinct carousel angles, each with two cover hooks, an audience, a slide arc and the facts that support it, ranked. Use at Step 2 of carousel-builder, after research-topic. Triggers on "carousel about", "angle", "framing", "hooks for".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write
---

# propose-angles

A topic is not an angle. An angle is a position, a lens or a surprise that gives the carousel a reason to exist in the feed, and it has to stand on the research, not on what sounds good.

## Inputs

- `research.md` (facts with sources, caveats, objects, material, angle sketches).
- Audience and voice from `context.json`; the `market-signal` sidecar when present (build at least one angle from an escalated pain or a curiosity hook, in the words people used).
- Project decisions from keeping-project-memory (angles or phrasings already rejected).

## Procedure

1. **Kernel.** One sentence: what the reader should know after the last slide.
2. **Diverge.** 3 to 5 angles that differ on at least one axis: position (contrarian, consensus, re-frame, how-to, story), lens (numerical, tactical, strategic, personal), audience, emotional pull (curiosity, status, fear, belonging, hope). No angle is a sub-topic of another.
3. **Ground.** For each angle, list the facts of `research.md` it uses. An angle the research cannot carry for 6 slides is dropped or flagged "needs one more source".
4. **Hooks.** Two cover hooks per angle, 6 to 12 words. The cover gives the start of the answer (a number, a reversal, a name) and leaves the how open; the sub-line gives half the mechanism. Banned: teasers without content ("The truth about..."), "What X taught me", announcements of length, rhetorical questions as hooks.
5. **Arc.** Cover, stakes, 3 to 7 beats (one idea each), CTA. Mark which slides are calm (one number, one quote, one photo) and which are dense (chart, list, screenshot), alternating.
6. **Rank** by support in the research x interest for the audience x distinctness. The first one is the recommendation.

## Output

```markdown
## Angles for: <kernel>

### 1. <title> (recommended)
Hooks: "<hook A>" / "<hook B>"
Audience: ...
Arc: cover > stakes > ... > CTA (calm/dense marked)
Supported by: <fact ids from research.md>
Why: one line
```

Keep the list in the run folder (`angles.md`). The two hooks of the recommended angle go into `deck.json` `meta.covers.hooks`; the founder sees them rendered on the cover board at stop 1, which is where they choose. A founder can ask there for another angle of the list.

## Failure modes

- **All angles converge** → rebuild on the axes; five phrasings of one idea is one angle.
- **The strongest hook needs a number the research lacks** → drop the hook, never the sourcing.
- **Self-promotion topic** ("how we got to N customers") → at least one angle turns the win into something the reader can reuse; proof comes from `positioning.proof` only.
