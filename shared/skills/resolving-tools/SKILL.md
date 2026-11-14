---
name: resolving-tools
description: Picks, at the start of a run, which provider fills each capability an agent needs (web search, scrape, SERP, Search Console, screenshot, page speed, image generation, email finder, transcription, publishing, analytics, vision, critic and the rest of the catalog in shared/tools.md), from the founder's declared tools, the keys present in the environment, local programs, the host agent's built-in tools, or manual input. Never blocks a run on a missing API key. Use at Step 0 of every agent, right after loading the project context.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
---

# resolving-tools

Every agent runs with or without paid APIs. This skill decides, once per run, which provider serves each capability the agent lists in its `## Tools` table. The capability catalog and the providers are in [`../../tools.md`](../../tools.md).

## Procedure

1. **List the capabilities** the agent needs, from its `## Tools` table.
2. **Read the founder's choices**, highest priority first:
   1. a choice stated in chat for this run,
   2. the `tools` object in the agent's `config.json`,
   3. `<your-projects-root>/<project>/project-context/tools.json`,
   4. `"auto"` for anything unset.
3. **Resolve each capability.**
   - A named provider: check it is usable (its key is set, or its program answers `--version`). If it is not, say so in one line and fall back to `auto`.
   - `"builtin"`: use the host agent's own web search, web fetch or browser tool.
   - `"manual"`: ask the founder for the input once, grouped with the other manual asks.
   - `"none"`: skip the capability.
   - `"auto"`: walk the tiers of [`../../tools.md`](../../tools.md) in order (API, Local, Built-in) and take the first usable one. Check keys by testing whether the variable is set, never by printing it. If nothing is usable, use Manual when the capability is core to the agent, otherwise skip.
4. **Announce the plan in one short block** before any work, then continue without waiting unless something needs manual input:

   ```
   Tools for this run: web_search = exa, scrape = builtin fetch, screenshot = playwright,
   page_speed = none (rows U023 to U028 will be Unverified).
   ```

5. **Honor the plan through the run.** A provider that fails mid-run (quota, network, 4xx) drops to the next tier for the remaining calls; note the switch.
6. **Report it.** Methodology lists the provider used per capability. Limitations lists every skipped capability and what it left unverified.

## Rules

- Never stop a run because a key is missing. Degrade, and say what degraded.
- Never print, log or write a key value.
- Never install a paid service or sign the founder up for anything.
- Results must not depend on the provider: the same capability produces the same output format whatever fills it. When a lower tier returns less (for example built-in search has no "People also ask"), mark the affected items Unverified rather than guessing them.
