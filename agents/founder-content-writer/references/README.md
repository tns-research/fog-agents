# references/

| File | Read by | What it holds |
|------|---------|---------------|
| [`../assets/hook-types.md`](../assets/hook-types.md) | writing-posts-spec | Hook types, angle types and structures of a batch, with what the script ties to each |
| [`../assets/claims-model.md`](../assets/claims-model.md) | writing-posts-spec, checking-and-reviewing-batch | How claims map to the shared policy, and what the script looks for in a body |
| [`../assets/hard-rules.md`](../assets/hard-rules.md) | every skill, the fresh reviewer (inlined in the packet) | The rules a post never breaks |

## Sources behind the rules

- Network limits, the X weighted count, link placement: [`../../content-publisher/assets/platform-limits.json`](../../content-publisher/assets/platform-limits.json), each number with its source URL and check date. This agent reads that file through `agents/content-publisher/scripts/variants.py` and copies no number.
- X, one tweet of 280 weighted characters: https://docs.x.com/fundamentals/counting-characters
- The writing rules: [`../../../shared/skills/writing-gate/SKILL.md`](../../../shared/skills/writing-gate/SKILL.md). The claims rules: [`../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../shared/skills/enforcing-claims-policy/SKILL.md).
- The founder's voice: [`../../project-context/assets/voice-schema.json`](../../project-context/assets/voice-schema.json), measured by project-context on the founder's own texts.

## What this agent does not claim

No benchmark on hook performance, ideal post length or best posting time appears in this folder, because none was verified for it. A founder who has their own numbers can read them with growth-pulse. Hook types here describe what a first line does; they carry no promise of reach.
