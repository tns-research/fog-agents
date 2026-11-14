---
name: edit-real-photo
description: Mode photo_edit of static-ads-builder. Turns a phone photo the founder took (founder, product in hand, team) into ad material by rebuilding 30 to 80 % of the frame (background, light, surface, crop, clutter) with an image editing model, while the face, the expression, the pose, the hands with five fingers and the object held stay untouched. The model writes 3 to 5 edit concepts per photo in photo-edits.json; scripts/photo_edit.py validates them, checks every person against people.json for the ads scope, renders through the backend picked with the founder (manual by default: the harness's own image tool or the founder's app, 0 USD from the script, nothing sent; higgsfield, openai or fal behind the spend gates), checks the size of every result and runs a visual identity review. The ad copy is then set by the local HTML renderer, never by the model. Use at Step 3 when a concept needs a real photo that is too weak as shot. Triggers on "use my photo", "clean up this picture", "better background", "photo of me holding the product".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# edit-real-photo

A phone photo of a founder holding the product sells better than any generated scene, and it reads as a snapshot: flat ceiling light, a kettle and cables behind, a crop that cuts nothing out. This mode keeps the person and the object as they are and rebuilds the rest. Under 30 % of change the photo stays a snapshot; past 80 % it becomes a different picture. Text is never part of the edit: the headline, the button and the logo are HTML, set afterwards by `scripts/build.py`, so they come out exact.

## When to propose it

- The founder supplied a real photo with a person or a product in hand, and a concept of the plan uses a media style (`ugc-text-overlay`, `ingredient-origin-strip`, `hybrid-2d-3d-fusion`, `feature-callout-arrows`).
- The photo is weak as shot (clutter, flat light, busy background, no calm zone for the text), and the founder agrees to an edit. A photo that already works goes in as it is, at 0 USD.
- Never for a screenshot, a transparent packshot, a logo, or a photo of someone without a consent for ads (below).

## 1. Read the photo, write the spec

Open the photo at full size. Write `<run>/photo-edits.json` against [`../../assets/photo-edits.schema.json`](../../assets/photo-edits.schema.json), with the photo copied into `<run>/media/`:

- `people_present` (`none`, `hands-only`, `partial-body`, `face-visible`, `group`) and `people`: what each person does, wears and where they stand, skin and hair details. The prompt repeats it word for word; without it the model redraws the person into a stock pose.
- `held_object` and `visible_text`: the object in hand and every word printed on it, copied from the real object.
- 3 to 5 `concepts`, spread over at least two edit levels:

| `edit_level` | What changes | What stays |
|--------------|--------------|------------|
| 30 | regrade, clutter removed (cables, chargers, mugs, extra screens) | setting, crop |
| 50 | background simplified or replaced (wall becomes plaster, paper or wood), tighter crop or a 5 to 15 degree tilt | the subject and its light direction |
| 80 | subject set on a new surface or backdrop, new studio or window light with a real shadow, props reduced to the object | the subject only |

Each concept holds `changes` (concrete, in order: surface, clutter, light and grade, crop), `never_changes` (with people: face, expression, pose, hands with five fingers each; with an object: the object and its label), `text_zone` (where the copy will sit: the edit keeps that area calm and empty), `person_slug` (every person shown) and the full `prompt`, written as labelled fields, one per line:

```
edit level: 50% of the frame changes, background replaced, tighter crop.
keep: her face and expression, her pose, both hands with five fingers each, the jar she holds and its label.
transform: the kitchen becomes a plain warm plaster wall; the crop tightens to waist up; soft window light from the left.
people: the same woman, green apron, short dark hair, freckles, smiling; skin texture and hair strands stay as they are.
text zone: the upper third stays plain and empty for the headline added later.
grade: warm, soft contrast, true skin tones.
Avoid: no text, no letters, no logo, no extra people, no extra fingers, no skin smoothing, no change to the face.
```

A prompt never contains the ad copy. Check it:

```bash
python3 scripts/photo_edit.py check <run>/photo-edits.json
```

Errors carry a JSON path: `invariant-missing` (a never-changing element not named), `prompt-field`, `prompt-level`, `prompt-invariant`, `prompt-text` (the prompt does not say no text), `edit-levels`, `missing-photo`, `consent`.

## 2. Consent (BLOCK)

A photo that shows a person needs `person_slug` on every concept, and each slug must be cleared for `ads` in `<project>/project-context/people.json`: `consent.status` granted, with a date and a source, and `ads` in `consent.scope`. Refused, unknown, another scope only, or absent from the registry is a BLOCK, except the entry marked `is_operator` (the founder running the agent). The script reads the registry through `../../../../shared/scripts/registry.py` (`load_people`, `allowed`) and falls back to the same contract read from `people.json` directly. A BLOCK is never worked around: ask the person, record the answer with `project-context`, or drop the photo.

## 3. Render behind the two gates

**Gate 1 (blocking):** show the concepts (title, edit level, changes, never_changes) and let the founder pick which to render.

**Pick the backend** with the founder, once, keep it in the run log, and pass it as `--backend`:

| Backend | Cost and privacy |
|---------|------------------|
| `manual` (default) | free, nothing sent by the script; the harness's image tool or the founder's app runs the pack |
| `higgsfield` | Higgsfield credits on the founder's account (Higgsfield MCP connected), read with `get_cost`; the photo goes to their Higgsfield library |
| `openai` | `OPENAI_API_KEY`, about 0.17 USD per image (estimate, below); the photo goes to OpenAI's API, no public link |
| `fal` | `FAL_KEY` and the fal CLI, priced from the `render_ads.py` table; the photo gets a public URL on fal storage |

`--backend stub` is a local placeholder for the selftest, never for a founder's run. Keys are read from the environment and sent only to their own provider as the `Authorization` header: never ask for one in the chat, never write one in a file. Every backend makes one attempt per image, no retry.

```bash
python3 scripts/photo_edit.py render <run>/photo-edits.json --select <ids> --config <project>/static-ads-builder/config.json
```

**Manual (default).** The command writes `<out>/_manual/PHOTO-EDIT-PACK.md` and one prompt file per concept, and exits 5. When the harness has an image edit tool (an MCP server, a built-in tool), the agent runs it: the source photo attached, the prompt file as the prompt, the size asked, the result saved as `<out>/<photo>--<concept>.png` (jpg, jpeg or webp accepted). A paid tool is a spend: say the tool, the count and its price first and wait for the founder's yes. Otherwise the founder runs the pack in their own app and drops the files. The same command run again collects the files, fits them to the size and records them; exit 0 once every concept is in.

**Higgsfield.** `--backend higgsfield` writes the same pack plus `_manual/higgsfield-plan.json`, one entry per concept with the exact MCP calls, in this order: `media_upload` of each source photo (one per photo, not per concept), `curl` PUT of the bytes to `upload_url`, `media_confirm` with type `image`; then for every concept `generate_image` with the plan's `cost.params` (`get_cost: true`, nothing is submitted), credits added up. Show the founder the model, the count and the total in credits; after an explicit yes, `generate_image` with `render.params` and the photo's `media_id` in `medias` (role `image_references`), `jobs_wait` until the job is done, download the result URL to `save_as` in the output folder. Never pass `use_unlim` unless the founder asks to spend free generations. A transport timeout means the job may exist: wait on the job id instead of submitting again. Then run the same render command to collect the files, as for manual.

**OpenAI and fal (Gate 2, blocking).**

```bash
python3 scripts/photo_edit.py estimate <run>/photo-edits.json --select <ids> --backend openai --config <config>
```

prints the model, the sizes, the quality, the count, the price per image and the total. For openai the price is `photo_edit.price_per_image_usd` (default 0.17 USD, an estimate for one 1536x1024 high quality output of `gpt-image-2`, input image tokens not included): check it on OpenAI's pricing page before quoting it. For fal it comes from the `render_ads.py` table for `photo_edit.fal_model` (default `fal-ai/nano-banana-2`) and `fal_resolution`. Say where the photo goes (table above). The founder confirms model, size, count and total in one explicit answer; then:

```bash
python3 scripts/photo_edit.py render <run>/photo-edits.json --select <ids> --backend openai --config <config> --confirm-spend
```

Without `--confirm-spend` (or `FOG_ALLOW_SPEND=1`) the script sends nothing, prints the estimate and exits 4. On fal, a photo with people also needs `--accept-public-url`, passed after the founder and every person shown agree; without it the script exits 4 and sends nothing.

Output: `<run>/media/edited/<photo>--<concept>.png` and `photo-edit-run.json`, which holds for each image a ready `media` entry for `ads.json` (role `photo`, fit `contain`, the photo's `visible_text`, an `edit` block naming the spec, the concept and the people).

## 4. Check the result

```bash
python3 scripts/photo_edit.py verify <run>/photo-edits.json
```

checks that every file exists at the size asked and writes `<run>/review/photo-edit-packet.md` with `photo-edit-review.template.json`. Then the visual identity review, same reviewer order as the proofread ([`../proofread-ads/SKILL.md`](../proofread-ads/SKILL.md)): a fresh sub-agent that gets the packet and the image pairs only, a blank session or a second model CLI, the same model in a separate pass, or the founder. For each edited file it compares with the original and answers `face`, `expression`, `pose`, `hands`, `object` (`same`, `changed`, `not_in_photo`), `fingers` (`five`, `wrong`, `not_in_photo`) and `text_added`. Saved as `<run>/review/photo-edit-review.json`:

```bash
python3 scripts/photo_edit.py verify <run>/photo-edits.json --review <run>/review/photo-edit-review.json
```

| Verdict | Meaning | Fix |
|---------|---------|-----|
| `IDENTITY_OK` | person and object unchanged, no painted text | none |
| `IDENTITY_CHANGED` | a face, an expression, a pose, a hand, a finger count or the object changed or was lost | drop the image, or lower the edit level and re-render through the gates |
| `TEXT_ADDED` | the edit painted letters or a logo | re-render with the Avoid line stressed, or drop |
| `NOT_REVIEWED` | no answer for the file | review it |

Only `IDENTITY_OK` images go into `ads.json`, through the `media_entry` of the run file. The rest of the workflow is unchanged: the copy is set by `build.py`, QA measures the render, and the blind proofread reads the label words of the edited photo against `visible_text` (a label the edit distorted is an `ASSET_TEXT_MISMATCH`).

## Report

Section "Photo edits": photos, concepts proposed and picked, backend, spend (estimate and count), consent decision per person, verify and review verdicts.
