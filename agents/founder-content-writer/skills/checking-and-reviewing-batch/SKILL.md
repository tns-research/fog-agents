---
name: checking-and-reviewing-batch
description: Runs the mechanical checks of a founder-content-writer batch with scripts/check_spec.py (word-for-word passages, claims against positioning.proof, content-publisher's limits and link rules, writing gate, duplicate openings, voice pack, address form), fixes the spec until it passes within three passes, builds posts.json and the report with scripts/build_batch.py, then runs one bounded fresh-eyes review against assets/review-rubric.md and one revision. Use at Steps 3, 4 and 5 of founder-content-writer. Triggers on "check the posts", "review this batch", "why is this post refused".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# checking-and-reviewing-batch

Scripts first, then a reader who did not write the posts. A founder should never read a post a script would have refused.

## The check loop

```bash
python3 scripts/check_spec.py <run>/posts-spec.json --project <project> --out <run>/check.json
```

Fix the spec, never the source, the limits, a pack or a threshold. Three passes at most. A post still failing after the third leaves the batch and goes under `limitations` with its findings. It does not reach the founder as if it had passed.

| Finding | What it means | The fix |
|---------|---------------|---------|
| `passage-not-found`, `passage-case-changed` | the passage is not in the file as written | copy it from the file, do not rephrase |
| `passage-elided` | two parts joined by an ellipsis | cite each part as its own passage |
| `source-changed` | the file changed after ingestion | restore it, or `ingest.py add --replace` when the founder changed it |
| `quote-mismatch`, `quote-unverified` | not inside a verified market-signal quote | copy from `text_verbatim`, or drop the quote |
| `unsourced-number` | a number with no claim | trace it to `positioning.proof` or a URL, or take it out and list it under `dropped` |
| `number-needs-proof` | a number from the notes only | same: it stays out until the founder adds it to the proof list |
| `number-differs-from-proof` | rounded or changed | write the number of the proof item |
| `proof-not-usable` | the proof item is refused for posts by `shared/scripts/proof.py` (stale metric, testimonial without consent; the `proof-refused` warning gives the reason) | take the claim out or list it under `dropped`; the founder updates the item in `project-context` |
| `claim-needs-proof` | a customer, a result or a ranking resting on notes | rewrite without it, or `dropped` |
| `quote-as-testimonial` | a stranger's quote used as proof | use it as language about the problem |
| `untraced-event`, `name-not-in-sources`, `client-not-in-source`, `time-marker-not-in-source`, `quote-not-in-source` | a detail no passage holds | this is the invention the agent exists to stop: take it out, or cite the passage that holds it |
| `post-not-tied-to-passage`, `claim-not-in-passage` | the text drifted from what the founder said | write closer to the passage |
| `link-in-body`, `bare-domain-in-body`, `link-unsourced` | an address in a body, or a link from nowhere | use `link`, from the founder's site or the material |
| `over-limit`, `x-thread` | content-publisher's limits | cut the text, never the limit |
| `writing-gate:*` | a machine tic | rewrite the sentence with the fact it stood in for |
| `duplicate-opening`, `duplicate-past-opening`, `rejected-opening`, `rejected-angle` | already said, or already refused | a new first line that says something else; a rejected angle stays rejected |
| `hook-type-overused`, `angle-type-overused`, `hook-type-mismatch` | the batch does not vary, or the label lies | change the post, or the label if it was wrong |
| `address-tu` | tu in a French post | vous, unless the config or a decision says otherwise |
| `voice-banned`, `voice-example-copied` | the voice pack | rewrite |

Read every warning. Keep one only when the sentence is right and you can say why: `build_batch.py` prints the kept warnings in the report. `third-party-name` needs a look: a tool is fine, a client needs the proof list. `untraced-sentence` too: an opinion the founder would sign is fine, a fact they never stated goes.

When a sentence the founder really said fails a rule of the shared packs, the calibration rule of the writing gate applies: it is the founder's call, recorded in `memory/decisions.md`. Never ignore a rule on your own.

## Build

```bash
python3 scripts/build_batch.py <run>/posts-spec.json --project <project>
```

It runs the check again, writes `posts.json`, runs content-publisher's own `variants.py lint` on it, and writes the report and the critique packet. A refused spec leaves no `posts.json` behind. `posts.json` is built, never typed.

## Fresh-eyes review

Follow [`../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md). `build_batch.py` already wrote `review/critique-prompt.md` and `review/critique-packet.md`: the brief verbatim, the hard rules, the claims policy, `positioning.proof`, the project's decisions and voice rules, the rubric, the mechanical results, and each post with its passages. Nothing of the producer's reasoning is in it.

| Order | Reviewer | How |
|-------|----------|-----|
| 1 | Fresh subagent of the harness | started with the prompt and the packet only |
| 2 | Blank session or second model CLI | reads the prompt and the packet on stdin, read-only |
| 3 | The founder or a teammate | answers the rubric as a short form, one post at a time |
| 4 | None available | "Fresh-eyes review: not run", the batch ends `partial` and is listed as unreviewed |

A second pass by the producing session does not count.

**Bounds: one critique, one revision.** Save the critique as `review/critique.md`. Settle each point on the highest rung: a script check, then a written rule, then reasoned taste, which may be declined with the reason. Revise `posts-spec.json` once, re-run the check (up to its three passes) and build again with the role log:

```bash
python3 scripts/build_batch.py <run>/posts-spec.json --project <project> \
  --critic-reviewer subagent --critic-verdict PASS --critic-score 11/12 \
  --critic-settled "written constraint on one point, taste declined on one" --critic-changed "one LinkedIn opening"
```

No second critique. A reviewer who rewrites posts: keep the verdicts, discard the rewrite. When the revision leaves a FAIL open, the report says so and the batch ends `partial`.

## Done when

`build_batch.py` exits 0, `posts.json` exists, and the report's role log names the reviewer or says "not run".
