---
name: art-direct
description: Chooses the art direction of a carousel on a rendered image, not a description. Picks the directions that fit the content among the six shipped ones, renders the same cover in each with two hooks at feed size, reviews the board, then shows it to the founder as the first human stop - one direction and one hook to pick. Use at Step 4 of carousel-builder, after write-deck. Triggers on "which style", "art direction", "show me options", "cover options".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# art-direct

People choose a look in a second when they see it and argue for an hour over adjectives. This step renders the choice.

## Inputs

- `deck.json` with `meta.covers.hooks` (two or three hooks from propose-angles) and a cover slide (title, plus the photo or object of the subject when there is one).
- The directions: [`../../directions/README.md`](../../directions/README.md) (table of the six, with what each is best and worst for) and each `direction.json` (`best_for`, `avoid_for`, `rules`).
- Project decisions (keeping-project-memory): a direction the founder rejected before is not proposed again; a direction already locked for a series is used without asking.

## Procedure

1. **Shortlist three directions** from the content, not from taste: data-heavy decks lean on `swiss-grid` or `data-notebook`; a real photo carries `photo-poster`; an opinion or explainer suits `editorial-paper`; culture, events and playful teaching suit `riso-print`; developer topics suit `terminal`. Cross out what `avoid_for` excludes. With sub-agents or time, render all six and shortlist from the board.
2. **Render the board**:

   ```bash
   python3 scripts/pipeline.py <run>/deck.json --covers --directions a,b,c --first-layout
   ```

   Output `covers/cover-board.jpg`: rows = hooks, columns = directions, each tile at 360 px wide (what a phone feed shows). Without `--first-layout` every cover layout of each direction is rendered (use it to compare layouts inside the chosen direction). Tiles with QA errors are outlined in red; their details are in `covers/<direction>/qa.json`.
3. **Review it yourself first** (vision): at 360 px, does the hook read in one second, is the number or the photo the first thing seen, is the logo present and small, would it stop the scroll next to a text post? Remove a direction that fails, fix a hook that breaks badly (a hook that only fits in 5 lines at minimum size is too long), re-render.
4. **Stop 1, the founder.** Show the board with one line per column (what the direction is good at) and ask for one direction and one hook, optionally a second cover layout. Nothing else is asked here.
5. **Apply**: set `meta.direction`, move the chosen hook into the cover title block (and the cover `layout` if one was picked), keep the other hook as a caption idea. Record a rejection as a decision.

## Brand on top

The brand never changes a direction's structure. `build.py` maps the brand accent to accent roles that keep contrast on each surface (`--accent-mark`, `--accent-text`, `--accent-fill`, `--accent-solid`), takes the logo variant matching the surface (`logos.on_light` or `logos.on_dark`), and uses the brand fonts only when the direction allows it (`brand.fonts` in `direction.json`) or the deck asks (`meta.use_brand_fonts`). If the brand accent makes a direction look wrong, choose another direction rather than overriding colours.

## Failure modes

- **No vision** → skip step 3's self-review; the founder sees the board directly, and the report says so.
- **The founder wants a look no direction gives** → note it, pick the closest direction for this run; a new direction is a contribution (copy the closest folder, see the directions README).
- **Every tile has QA errors** → the hook is too long for any cover: shorten it before showing the board.
