---
name: winning-recipe
description: Mode winning_recipe of static-ads-builder. Takes the winning ad named by scripts/perf.py (or by the founder), decomposes it into a recipe.json (angle, hook type, text length, layout zones and hierarchy, style, palette, CTA, funnel stage, and the ad itself as control), then writes new hooks under the claims policy and turns both into five ads.json variants that keep the winner's structure and change one variable each (hook, subhead, visual, CTA or surface), named _t-<variable> so next month's export says which variable won. scripts/recipe_variants.py measures the recipe against the ad and refuses a variant that changes more than one variable. Use at Step 2 when the performance read has a winner to extend. Triggers on "do more like the winner", "iterate on the best ad", "test new hooks", "A/B test the headline".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# winning-recipe

A winner says one thing for sure: this combination worked once. Five new concepts around it say nothing about why. Five copies that each change one thing say which part carries the result. This mode extends a winner as a test: same angle, same style, same layout, same stage, one variable moved per ad.

## When to propose it

- `ads-performance-YYYYMMDD.json` lists at least one winner whose name follows the convention (built by this agent), or the founder names the ad that works.
- It fills the extend share of the batch (`next_batch.extend_share`). On a `post_click` account it is the only creative work worth doing, after the post-click actions are said.
- Under 15 conversions in the period perf.py flags the rankings as noisy: show the winner, its CPA and conversions, and let the founder confirm it before building on it (human stop).

## 1. Seed the recipe from the ad as it ran

```bash
python3 scripts/recipe_variants.py seed --spec <run of the winner>/ads.json \
  --perf <project>/static-ads-builder/ads-performance-YYYYMMDD.json --out <run>/recipe.json
```

The first winner of the perf file that follows the naming convention and is an ad of `--spec` is picked; `--ad-name <name> --why "<reason>"` picks it by hand. The script fills what it can measure: angle, style, stage, formats, surface, the CTA on the ad and in Meta, headline and subhead word counts and their band, the zones present in reading order, and the control (the ad object itself). A winner the agent did not build has no spec: write the control by hand as an `ads.json` ad that reproduces it.

## 2. Decompose (the model's part)

Open the winning render at full size and fill the judgement fields of [`../../assets/recipe.schema.json`](../../assets/recipe.schema.json):

- `hook_type`: the headline structure of [`../../assets/ad-library.md`](../../assets/ad-library.md) section 2 (`problem-agitate-solve`, `before-after`, `question`, `number-list`, `contrarian`, `story-open`, `direct-promise`, `urgency`).
- `layout.zones[].area`: where each element sits (`top`, `upper-third`, `center`, `lower-third`, `bottom`, `left`, `right`, `full`), with a note when the size or the line count matters; `layout.hierarchy` in reading order.
- `palette.accent_role`: where the accent colour sits; `palette.colors` when worth naming.

```bash
python3 scripts/recipe_variants.py check-recipe <run>/recipe.json
```

It refuses a recipe that contradicts the ad: another angle, style, stage, formats, surface or CTA, word counts that do not match, a zone the ad does not have.

## 3. New hooks, sourced

Write `<run>/hooks.json` against [`../../assets/hooks.schema.json`](../../assets/hooks.schema.json): N new headlines in the same hook type and about the same length band, each with a `why` (what it tests) and the `claims` behind any number or fact, sourced to `positioning.proof[N]` or to a `sources[]` entry with its URL ([`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)). Optional `alternates`: a CTA text (and Meta CTA type), a visual (an `ads.json` media object, for instance an edited photo of [`../edit-real-photo/SKILL.md`](../edit-real-photo/SKILL.md)), a surface, a subhead.

## 4. Build the variants and check them

```bash
python3 scripts/recipe_variants.py build <run>/recipe.json --hooks <run>/hooks.json --out <run>/ads.json [--count 5]
```

Alternates first, one variant each, then the hooks, until five. Each variant is the control with one variable changed, `extends` the winner, carries `test.variable`, and is named `<project>_<NN>_<stage>_<angle>_<style>_<ratio>_t-<variable>`. Meta, sources and brand come from the winner's run; NN continues after it. The build runs the check:

```bash
python3 scripts/recipe_variants.py check <run>/ads.json --recipe <run>/recipe.json
```

| Error | Meaning |
|-------|---------|
| `variant-multi` | two variables changed (a hook and a CTA): split it into two variants |
| `variant-structure` | the style, stage, angle, formats, bullets, columns, proof, Meta text or the media of an ad without media changed |
| `variant-mismatch` | the variable changed is not the one declared |
| `variant-none` | nothing changed |
| `unsourced-number` and the other `ads.json` lint codes | the claims policy, as in `build.py` |

Then the normal path from Step 3 on: `build.py` to 0 error, render, review, proofread, package. The report lists, per variant, the variable tested and the control it is read against.

## Next month

`perf.py` splits `_t-<variable>` back and aggregates by tested variable (`aggregates.test`). Read the variants against the control on the same period: a variant that beats it on CPA with enough conversions becomes the next control; the variable that moved the result is the next one to test further.
