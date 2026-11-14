# Sprint summary template

The orchestrator writes this block into `<sprint dir>/summary.md`; `scripts/sprint.py report --summary` puts it on top of the generated report (steps, needs_human, defaults, breaker, next sprint input). Language: the founder's. Every number comes from a step output or a growth-pulse report, with the file named.

```markdown
**Toward the goal.** <goal metric>: <measured value and source file, or "not measured yet: growth-pulse runs on <date>">. <What shipped that serves the goal, counted from the outputs: 18 people listed, 1 carousel queued on 2 networks, 4 ads packaged PAUSED.>

**This week, in order:**
1. <action> (`<file or command>`)
2. <action> (`<file or command>`)
3. <action> (`<file or command>`)
4. <action> (`<file or command>`)
5. <action> (`<file or command>`)

**Waiting for you:** <H-id: one line each, or "nothing">.

**Decided without you:** <the defaults that change what you will see, or "nothing that changes a deliverable">.

**Not done and why:** <skipped or failed steps, one line each, or "nothing">.
```

Rules:

- Five actions at most, the first one the one that unblocks the most.
- No effect forecast ("should double", "will bring"): the next growth-pulse run measures it.
- No placeholder left: a section with nothing to say says "nothing".
