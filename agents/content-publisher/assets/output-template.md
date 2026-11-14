# Publication run: <project-slug>, <YYYY-MM-DD>

**Queue:** `content-publisher/queue.json` · **Timezone:** <tz> · **Adapter:** <dry-run | zernio | command | webhook> (<live | not live>)
**Status:** <ok | partial: pending approval N items | failed>

<If anything is open, list it first: items waiting for approval, items refused by the scripts after three passes, provider errors.>

---

## 1. Queued this run

| Item | From | Slot | Length | Checks |
|------|------|------|--------|--------|
| `<ref>.linkedin` | carousel-builder `<run>` | Tue 20 Oct, 09:00 | 428/3000 | lint pass, gate pass (0 BLOCK, 0 WARN) |

Review packet: `<batch>/review-<YYYYMMDD>.md`.

## 2. Decisions

| Item | Decision | By | When |
|------|----------|----|------|
| `<id>` | approved / changes asked / rejected (reason) / waiting | <person> | <date> |

## 3. Scheduled and published

| Item | Status | Provider | Post id | Slot |
|------|--------|----------|---------|------|

## 4. Quality

- **Writing gate:** <0 BLOCK on N texts, WARN kept and why> · **Claims:** <every number in a variant traced to its deliverable>
- **Lint:** <errors fixed in N passes, warnings kept and why>
- **Fresh reviewer:** <PASS/FAIL, score/12, what was revised> (or "not run")
- **Queue:** schema <pass>, `pubqueue.py validate` <pass>

## Methodology

- Tools: copy_lint <local | manual>, publish <adapter>, critic <subagent | session | founder | not run>, vision <builtin | founder>.
- Inputs: deliverables <paths>, networks <list>, defaults used <list>.

## Limitations

- <what was not checked: provider status not confirmed, media not opened, dry-run only>
