# Review rubric: sprint plan

For the fresh reviewer of Step 3 ([`../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)). The reviewer receives the goal in the founder's words, the ground-truth block, `sprint.json`, the output of `sprint.py validate` and [`agents.json`](agents.json). Hard checks first: `validate` must exit 0, or the verdict is FAIL without scoring.

Score each criterion 0, 1 or 2. Threshold: 11 of 14, and no criterion at 0.

| # | Criterion | 0 | 1 | 2 |
|---|-----------|---|---|---|
| 1 | Measurable goal | no metric | metric without target or date, and the founder gave one | metric, target and deadline as the founder stated them, or `null` where they gave none |
| 2 | Every step serves the goal | a step nobody can tie to the goal | a tie that needs explaining | each `brief` says in one sentence what the step changes for the goal |
| 3 | Handoffs used | a consumer runs before its producer, or a fresh file is redone | order right, reuse windows missing | producers before consumers, recent outputs reused through `reuse_if_fresh_days` |
| 4 | Budget and basis | a figure without basis | basis vague ("about") | every estimate names its source (agent quote, provider price, founder ceiling); cap explained |
| 5 | Spend and publication visible | an agent that can spend or publish hidden | flags right, gates not obvious from the briefs | flags right, and each brief says where the agent will stop for the founder |
| 6 | Parallelism | independent steps chained for no reason | partly | every step depends only on the files it reads |
| 7 | Size | over 12 steps or under 4 | 10 to 12 | 4 to 9 steps that fit before the deadline |

Output: PASS or FAIL on the hard check, the score per criterion with one located problem and one proposed fix each, no rewrite of the plan. One revision, then the packet.
