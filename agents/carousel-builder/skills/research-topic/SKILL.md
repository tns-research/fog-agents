---
name: research-topic
description: Researches a carousel topic before any angle or copy is written, and writes research.md, a sourced dossier the rest of the run draws from. Collects facts with URL and access date, numbers usable in a chart, objects of the subject usable as visuals, real material (photos, screenshots, logos) and caveats, from project-context, the market-signal handoff, URLs and files the founder gave, and the web when the tool plan allows. Use at Step 1 of carousel-builder. Triggers on "research this topic", "find sources", "what do we know about".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*) Bash(curl:*)
---

# research-topic

A carousel written from memory reads like every other carousel on the same topic. The research is what makes slide 3 say something the reader did not know, with a number they can check. Nothing in the deck may be more precise than this file.

## Inputs

- The topic, outline or notes from chat.
- `project-context/context.json` (product, audience, `positioning.proof`) and `brand.json` assets (`assets.screenshot_path`, `assets.images[]`), loaded at Step 0.
- The `market-signal` sidecar when present: pains, hooks, verbatim quotes with permalinks.
- URLs and files the founder supplied. URLs are welcome sources.
- `web_search` and `scrape` from the tool plan, when available.

## Procedure

1. **Restate the question** the carousel answers in one sentence, for the audience of `context.json`.
2. **Read the founder's material first** (files, URLs, project-context, handoff). Then search: primary sources over aggregators (the study, the official statistic, the company's own page), the most recent version of a figure (a study updated in 2026 beats the 2022 copy quoted everywhere). Read 8 to 20 pages for an explainer, more for a contrarian claim.
3. **Fill the tables below as you read.** A fact goes in only with its URL and the date you read it. Copy numbers exactly, with their unit and their scope (who was measured, when, how).
4. **Check what the numbers mean.** Averages over different bases, survey sizes, sums that do not add up, a figure that changed between versions: write each caveat. A caveat often becomes a chart note or kills a weak angle.
5. **List objects of the subject** that can be drawn or shown: the ranking itself, a form, a timeline, a document, a page of the product, a screenshot of the source. One object of the subject per carousel is worth more than any generic diagram.
6. **List the real material**: the founder's photos (check people are not identifiable without consent), product screenshots, partner logos with the right to use them. Note the path of each file.
7. **Sketch 3 to 5 angles** in two lines each, with what the research supports and what it does not. propose-angles takes it from there.

## Output: `research.md`

```markdown
# Research: <question>

## Sources read
| id | Source (title, author or org, date) and URL | What it gives | Accessed |

## Facts usable on slides
| Fact | Value (exact, with unit and scope) | Source id |

## Caveats
- ...

## Objects from the subject usable as visuals
- ...

## Real material
- path, what it shows, rights or consent

## Angles considered
1. ... (supported by ..., weak on ...)
```

The `id` column becomes the `sources[].id` of `deck.json`, so a slide's footer source traces back to this file.

## Rules

- Never invent, round up or "illustrate" a number. A carousel with no number at all is fine; a carousel with one invented number is not.
- A quote is verbatim from its source. A translation is marked as such and keeps the original in `research.md`.
- Founder observations (qualitative, first-hand, typed in chat) are allowed as observations, recorded as `user-provided`, never turned into a statistic ([`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)).
- Do not describe the brand's own practice ("at <brand> we always...") unless the founder said it or a page of the brand states it.

## Failure modes

- **No web capability** → research the founder's material and project-context only; say so at the top of `research.md` and in the report's Limitations.
- **Source behind a paywall or a login** → do not cite what you could not read. Ask the founder to paste the passage, or drop the fact.
- **Two sources disagree** → keep the more recent primary source, write the disagreement in Caveats.
- **The material is too thin for 6 slides** → propose a shorter carousel (3 to 5 slides) or ask the founder for one more source; never pad.
