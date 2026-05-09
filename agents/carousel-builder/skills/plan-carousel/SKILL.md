---
name: plan-carousel
description: Turns a chosen angle into a slide-by-slide markdown plan for a LinkedIn or Instagram carousel. Produces 5 to 15 slides with type, title, body copy, optional visual note, and slide arc that respects retention curves (cover, hook, body, CTA). Use when the agent has a locked angle and needs a writeable copy plan before HTML rendering. Triggers on words like "plan slides", "slide-by-slide", "write carousel copy", "outline".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# plan-carousel

Take a locked angle, output a slide-by-slide plan that:
- Hooks in slide 1-2 (scroll-stop or close).
- Holds attention through slides 3 to N-1 (retention curve respected).
- Closes with a clear, low-friction CTA in the last slide.

A plan is **markdown text + slide-type metadata**, not HTML. Rendering is `render-carousel`'s job.

---

## Inputs

- `angle` (required): the angle JSON object emitted by `propose-angles` (rank, title, hook, audience, position, lens, slide_arc, rationale).
- `slide_count` (optional, default 8): integer in [5, 15]. Cap at 15.
- `tone` (required): `founder`, `expert`, or `casual`.
- `language` (required): `en` or `fr`.
- `cta` (optional): if user has a specific CTA ("comment X", "DM keyword", "follow", "read full article at <url>"), use it. Otherwise default to "Follow for more on <topic kernel>".

---

## Slide types

Six types are supported. Pick per-slide based on what each beat needs.

| Type | Use when | Body shape |
|------|----------|-----------|
| `cover` | Slide 1, always | Hook line + subline + visual cue |
| `text` | Body slides 2 to N-1 | Title + 2-4 short paragraphs OR 3-5 bullets |
| `quote` | A verbatim from a source / customer / yourself | Quote (≤25 words) + attribution + tiny context |
| `chart` | A data point that benefits from a visual | Title + chart description + 1-line takeaway |
| `image` | Showing a screenshot, photo, or AI-generated illustration | Caption + image source (`user`, `svg`, `fal`) |
| `cta` | Last slide, always | Action verb + 1 sentence + handle / link |

Forbidden: a body slide that is just a wall of text with no breathable structure.

---

## Procedure

1. **Compute slide budget.** From `slide_count`:
   - 1 cover (always)
   - 1 cta (always)
   - Remaining = body slides
2. **Build the slide arc.** Use the angle's `slide_arc` as the spine. Distribute beats across body slides:
   - Slide 2 = "second hook" (re-anchor the reader who survived the cover).
   - Slides 3 to N-2 = body beats (one beat per slide, no doubling up).
   - Slide N-1 = "the takeaway" (synthesize, often the most-screenshotted slide).
   - Slide N = `cta`.
3. **Choose slide type per beat.** Default to `text`. Use `quote` / `chart` / `image` only when the beat genuinely benefits. Two consecutive `text` slides are fine; three in a row signals weak structure (replace one with a `quote` or visual).
4. **Write each slide.** Constraints:
   - **Title**: ≤ 8 words. Active voice. Specific.
   - **Body**: ≤ 50 words on cover/cta, ≤ 80 words on body slides.
   - **No filler openers**: "In this post...", "Today we'll...", "Have you ever wondered...".
   - **One idea per slide.** If a slide has two ideas, split it.
   - **Tone**: per `tone` parameter (see Tone matrix below).
   - **Language**: write in `language`. No mixed-language hooks.
5. **Add visual notes** (optional but recommended). For each slide, suggest:
   - `visual: none` (clean text-only slide).
   - `visual: svg-chart` (if `chart` type).
   - `visual: bg-pattern` (subtle background visual).
   - `visual: user-image:<filename>` (if user provided an image and indicated which slide it goes on).
   - `visual: fal:<short prompt>` (only if `fal_images=true` in config).
6. **Self-check** before emitting:
   - Slide 1 has a hook ≤ 12 words.
   - Slide N has a CTA with a verb and a destination.
   - No two consecutive slides are exactly the same type.
   - Total slide count = the budget computed in step 1.
   - Each slide stands alone (a reader who lands on slide 5 should still get value).
   - No banned filler (see `propose-angles` ban list, plus: "Did you know", "I bet you didn't know", "Let me explain").

---

## Tone matrix

| Tone | Voice | Sentence length | Example opener |
|------|-------|-----------------|----------------|
| `founder` | First-person plural ("we"), specific war-stories, no buzzwords | mixed (short + medium) | "We shipped before we had a database." |
| `expert` | Third person, claims-with-evidence, named frameworks | medium | "Most retention curves bend at day 7." |
| `casual` | First-person singular, conversational, occasional self-effacement | short | "I used to think PMF was binary. It's not." |

Banned in all tones: synergy, leverage, revolutionize, game-changer, 10x, "let's dive in", "buckle up".

---

## Output

A markdown plan + sidecar JSON (C1). The JSON drives `render-carousel`.

```markdown
## Carousel plan: <angle title>

**Audience:** <who> · **Slides:** <N> · **Ratio:** <1:1 | 4:5> · **Tone:** <tone> · **Language:** <lang>

### Slide 1 — cover
**Title:** <hook ≤ 12 words>
**Body:** <subline, 1 sentence>
**Visual:** <visual note>

### Slide 2 — text
**Title:** <≤ 8 words>
**Body:** <≤ 80 words>
**Visual:** <visual note>

...

### Slide N — cta
**Title:** <action verb + benefit>
**Body:** <1 sentence + handle/link>
**Visual:** <visual note>
```

```json
{
  "angle_title": "<angle title>",
  "audience": "<who>",
  "slide_count": 8,
  "ratio": "4:5",
  "tone": "founder",
  "language": "en",
  "slides": [
    {
      "n": 1,
      "type": "cover",
      "title": "<hook>",
      "body": "<subline>",
      "visual": "bg-pattern"
    },
    {
      "n": 2,
      "type": "text",
      "title": "<title>",
      "body": "<body copy>",
      "visual": "none"
    }
  ]
}
```

---

## Failure modes

- **Angle is missing a slide arc** → run `propose-angles` again with a stricter prompt. Do not invent an arc.
- **`slide_count` < 5** → cap at 5, log a warning. Below 5, the carousel format collapses (cover + body + cta = minimum 3, and one body slide is too thin).
- **`slide_count` > 15** → cap at 15. LinkedIn document posts above 15 see steep drop-off.
- **User provides a CTA that's vague** ("learn more") → ask once for the actual destination (URL, handle, keyword). If user resists, default to "Follow <handle> for more" and flag in the report.
- **Body copy exceeds 80 words on a single slide** → split into two slides (cap at `slide_count + 1` if needed and log).
- **Three consecutive `text` slides** → replace the middle one with a `quote` or `chart`. If neither fits, leave as-is and log a "rhythm warning".

---

## Notes

This skill writes the markdown plan only. Layout (font sizes, color, logo placement) is the responsibility of `render-carousel`. Visual generation (charts, AI images) happens during render.

The plan is presented to the user for approval before render. The user can edit any field directly in the markdown, or ask for a rewrite. The JSON is regenerated from the edited markdown automatically before render.
