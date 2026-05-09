---
name: propose-angles
description: Turns a topic or rough outline into 3 to 5 distinct carousel angles, each with a hook, a target audience, a slide arc, and a one-line rationale. Use when the agent's workflow needs angle exploration before slide writing. Triggers on words like "carousel about", "post idea", "angle", "framing", "hooks for".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# propose-angles

Most "carousels about X" fail because the topic was never narrowed into a defensible angle. This skill forces the divergence step: 3 to 5 distinct angles before any copywriting happens.

A good angle is **not** a sub-topic. It's a specific position, opinion, audience, or surprise that gives the carousel its reason to exist on the feed.

---

## Inputs

- `topic` (required): free-form text. Either one sentence ("why first 50 users matter more than PMF") or a 3-7 bullet outline.
- `audience` (optional): if known from the project context (`config.json`), pre-narrow on it. Otherwise the angles propose audiences.
- `tone` (optional): `founder` (default), `expert`, `casual`. Drives hook style.
- `language` (required): `en` or `fr`. Hooks must be written in this language.

---

## Procedure

1. **Extract the kernel.** Restate the topic in one sentence: what is the user actually trying to communicate? This is the seed, not an angle.
2. **Generate divergent angles.** Produce 3 to 5 angles. Each angle MUST be different on at least one of these axes (no two angles identical on all four):
   - **Position**: contrarian / consensus / re-frame / how-to / story
   - **Audience**: founders / operators / investors / first-time / experienced
   - **Lens**: tactical / strategic / philosophical / numerical / personal
   - **Emotional pull**: status / fear / curiosity / belonging / hope
3. **For each angle, fill four fields** (see Output below).
4. **Rank by fit.** Sort angles by fit score: relevance to topic kernel × differentiation from the others × posting feed-readiness. Top angle first.
5. **Self-check** before emitting:
   - No two angles share the same Position + Audience.
   - No angle is a sub-topic of another (e.g., "first 50 users" and "your first 10 users" — collapse).
   - Every hook is ≤ 12 words and reads as a scroll-stopping line, not a chapter title.
   - No banned filler in hooks: "Let's dive into", "Here's why", "The truth about", "What nobody tells you".

---

## Output

A markdown block with one section per angle, ranked. Followed by a sidecar JSON for downstream consumption (cross-cutting C1).

```markdown
## Angle options for: <topic kernel>

### 1. <angle title> ★ recommended
**Hook:** <≤12-word scroll-stop>
**Audience:** <who this lands for>
**Slide arc:** <cover → hook → 4-6 body beats → CTA, in 1-2 lines>
**Why this works:** <1 line on the position / lens / emotional pull>

### 2. <angle title>
...
```

```json
[
  {
    "rank": 1,
    "title": "<angle title>",
    "hook": "<hook>",
    "audience": "<who>",
    "position": "contrarian|consensus|re-frame|how-to|story",
    "lens": "tactical|strategic|philosophical|numerical|personal",
    "emotional_pull": "status|fear|curiosity|belonging|hope",
    "slide_arc": "<one-line summary of the 6-10 slide flow>",
    "rationale": "<why this works>",
    "recommended": true
  }
]
```

---

## Failure modes

- **Topic is one word** ("growth", "AI") → ask once for narrowing. If user resists, propose 5 angles each on a different sub-topic, flag in the rationale that the topic was unspecified.
- **Outline already includes a clear angle** (e.g., "5 reasons X" with strong opinion) → still produce ≥ 3 angles. The user-implied one becomes angle 1, the others diverge to give choice.
- **All angles converge on the same position/audience** → rebuild with stricter divergence on the four axes. Never ship 5 angles that are 5 phrasings of the same idea.
- **Topic is a brag / case study about the user** ("how I got 10k MRR") → propose at least one angle that re-frames the win as a learning artifact for the audience, not a self-promotion. Self-promo angles still allowed but flagged.

---

## Examples

**Topic:** "why your first 50 users matter more than product-market fit"

| # | Title | Position | Audience | Hook |
|---|-------|----------|----------|------|
| 1 | First 50 are the product | contrarian | early-stage founders | "PMF is a lagging indicator. Your first 50 users are the leading one." |
| 2 | The 50-user playbook | how-to | first-time founders | "Get to 50 users before you write a roadmap." |
| 3 | Why I stopped chasing PMF | story | post-idea founders | "I chased PMF for 18 months. 50 users would've shipped me there in 6." |
| 4 | What 50 users tell you that 5,000 can't | re-frame | growth-curious | "Your first 50 say things your dashboard never will." |

Four distinct angles, four distinct positions, same topic kernel.

---

## Notes

The skill stops at angle proposals. Slide-by-slide copy is `plan-carousel`'s job. Do not start writing slides here.

Angles are presented in a single chat message; the user replies with the chosen index ("1") or with edits ("1, but for series-A founders"). The agent does not retry without explicit user input.
