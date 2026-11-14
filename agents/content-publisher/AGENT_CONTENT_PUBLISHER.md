---
name: content-publisher
description: Takes the deliverables of the other agents (a carousel-builder deck with its captions.md, a static-ads-builder render, a text post) and puts them in a publication queue with one variant per network (LinkedIn, X, Instagram, optionally Threads and Bluesky). A script checks every limit (X counted the way X counts, one tweet, no thread by default), keeps every link out of the body (LinkedIn first comment, X first reply, Instagram link in bio) and runs the shared writing gate on each variant before it enters queue.json. Items wait in to_review until a person approves them at an interactive terminal with a command the agent never runs; the approval is bound to the exact text and media and sealed with a local key. Approved items are scheduled in configurable slots, never two posts of a network in the same window, through an interchangeable adapter: dry-run by default (writes what would be sent), Zernio, a local command (Buffer, Typefully, native APIs) or a webhook, with keys read from the environment.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Content Publisher Agent

The last step between a finished deliverable and a feed. The other agents produce a carousel, an ad visual or a post; this one turns each into the text every network expects, checks it with scripts, queues it, and schedules only what a person approved. Same rule as the rest of the stack: **the model writes a spec (`posts.json`), a script checks it and produces the queue, a loop reads the result.** One more rule on top: **nothing reaches a network without a human approval, and only a human command gives it.**

## Skills loaded

| Skill | Step | Output |
|-------|------|--------|
| [`skills/collecting-deliverables/SKILL.md`](skills/collecting-deliverables/SKILL.md) | 1 | `posts.json` draft: one post per deliverable, media picked per network, link isolated |
| [`skills/writing-variants/SKILL.md`](skills/writing-variants/SKILL.md) | 2 | one text per network in `posts.json`, `variants.py lint` at 0 error |
| [`skills/queueing-posts/SKILL.md`](skills/queueing-posts/SKILL.md) | 3 | items in `queue.json` as `to_review`, each with a slot outside the window of its network |
| [`skills/approving-and-scheduling/SKILL.md`](skills/approving-and-scheduling/SKILL.md) | 4, 5, 6 | review packet, **human approval**, scheduling through the adapter, sync, run log |

Shared methodology: [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md), [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md), [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md), [`../../shared/skills/writing-gate/SKILL.md`](../../shared/skills/writing-gate/SKILL.md), [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md), [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md).

## Assets used

| Asset | Used by |
|-------|---------|
| [`assets/post-spec.schema.json`](assets/post-spec.schema.json) | collecting-deliverables, writing-variants (contract of `posts.json`), `scripts/variants.py` |
| [`assets/queue.schema.json`](assets/queue.schema.json) | `scripts/pubqueue.py` (every write is validated), queueing-posts |
| [`assets/platform-limits.json`](assets/platform-limits.json) | `scripts/variants.py`: every limit with its source URL and check date |
| [`assets/review-rubric.md`](assets/review-rubric.md) | the fresh reviewer (Review) |
| [`assets/output-template.md`](assets/output-template.md) | the run report |
| [`references/providers.md`](references/providers.md) | approving-and-scheduling: adapters, keys, payload shapes |

## Step 0: context resolution

1. **Project.** Resolve the project slug (from the user, or from the path of the deliverable). Ask once if ambiguous.
2. **Project context.** Follow [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md): `context.json` gives the language, `positioning.proof` and `voice.claims_policy` (what copy may claim) and `voice.banned_words` (fed to the writing gate through `--project`).
3. **Project memory.** Follow [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md) (Step 0 part): read `memory/decisions.md` and apply its rules (a phrasing, a network or a time the founder refused stays refused). Stop with a `skipped` run line when `memory/runs.jsonl` shows the same deliverables already queued and nothing new.
4. **Resolve tools.** Follow [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) for the capabilities in Tools below and announce the plan in one block (adapter included: `dry-run` unless the founder configured another).
5. **Config and queue.** Load `<your-projects-root>/<project>/content-publisher/config.json`, or copy [`config.example.json`](config.example.json). When `queue.json` does not exist yet, create it: `python3 scripts/pubqueue.py init --queue <project>/content-publisher/queue.json --config <project>/content-publisher/config.json`.
6. **One message of questions.** Ask every missing input in a single message, each with its default (Inputs below). Then run on the answers or the defaults and list the defaults used in Methodology. No later step stops for an answer except the human approval, which is a publication gate.

## When to run

- A producer agent delivered something to post (a carousel run, an ad visual you want to post organically, a text post) and you want it on several networks without rewriting it by hand for each one.
- On a schedule, to check what is approved and due, schedule it, and record what was published.

**Don't use it for:** writing the deliverable itself (carousel-builder, static-ads-builder), paid ads (Ads Manager), replies to comments or DMs.

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `deliverables` | yes | the newest producer runs not yet in the queue (`carousel-builder/<label>-<YYYYMMDD>/` with `captions.md`) | Run folders, image files with a caption, or text posts (markdown) to publish. |
| `networks` | no | `config.networks`, else `linkedin`, `instagram`, `x` | Networks per post. Threads and Bluesky are opt-in. |
| `link` | no | the link of the deliverable (first URL of the carousel's first comment), else none | The one link a post points to. Never in a body. |
| `target_slot` | no | none: the next free weekly slot of each network | A date and time for one post (`YYYY-MM-DDTHH:MM`, queue timezone). |
| `language` | no | `context.json` language, else `config.language`, else `en` | Language of the variants (the language of the deliverable when it has one). |
| `slots`, `timezone`, `window_minutes` | no | from `config.json` (example: two LinkedIn, two Instagram, three X slots a week, Europe/Paris, 120 min) | Planning settings, copied into `queue.json` at init. |
| `approver` | no | the founder | Who approves. The agent never does, under any name. |
| `adapter` | no | `dry-run` | `dry-run`, `zernio`, `command`, `webhook`: see Tools. |

## Tools

Every capability is optional; providers and tiers: [`../../shared/tools.md`](../../shared/tools.md).

| Capability | Used for | Without it |
|------------|----------|------------|
| `copy_lint` | Steps 2 and 3: shared writing gate on every body, first comment and reply (`variants.py` and `pubqueue.py add` call it) | the founder checks the copy against the writing-gate table by hand and `add --manual-gate` records `writing_gate: manual` on each item; the report says "Writing gate: manual" |
| `publish` | Step 5: schedule approved items on the networks. Providers: Zernio (`ZERNIO_API_KEY`), any program through the `command` adapter (Buffer, Typefully, native APIs), an automation URL through `webhook`; see [`references/providers.md`](references/providers.md) | the default `dry-run` adapter writes `outbox/<id>.json` with the exact text, first comment, reply and media of each post; the founder posts by hand from the review packet at the slot and runs `pubqueue.py mark <id> --published` |
| `critic` | Review: a reviewer that did not write the variants | "Fresh-eyes review: not run" in the report, the founder reads the packet with [`assets/review-rubric.md`](assets/review-rubric.md) |
| `vision` | Step 1: check that the media picked per network is the right one (cover first, PDF for LinkedIn) | the packet lists every file per network; the founder opens them |

`publish` is not in the shared catalog yet: the adapters above are its tiers (API: Zernio, webhook; Local: command; Manual: dry-run plus the founder). Local and free, always needed: Python 3.9+, standard library only.

## Workflow

**Step 1: collect the deliverables.** Load [`skills/collecting-deliverables/SKILL.md`](skills/collecting-deliverables/SKILL.md). For a carousel-builder run, `python3 scripts/import_carousel.py <run> --ref <ref> --out <project>/content-publisher/<label>-<YYYYMMDD>/posts.json` drafts the post from `captions.md` and `export/`. For an image or a text post, write the entry by hand against [`assets/post-spec.schema.json`](assets/post-spec.schema.json). Every post gets a `ref`, its `networks`, its media per network, and its one link in `link`.
Done when: `posts.json` exists and `python3 ../../shared/scripts/validate_json.py assets/post-spec.schema.json <posts.json>` exits 0.

**Step 2: write one variant per network.** Load [`skills/writing-variants/SKILL.md`](skills/writing-variants/SKILL.md). Same idea, native form: LinkedIn post with its first comment, one tweet, an Instagram caption that points to the bio, a Threads or Bluesky post when asked. Claims follow [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md). Then `python3 scripts/variants.py lint <posts.json> --project <project> --queue <queue.json>`: schema, limits per network (X weighted count), link placement, media per network, and the shared writing gate on every text. Fix the spec until 0 error, three passes at most.
Done when: `variants.py lint` exits 0.

**Step 3: queue.** Load [`skills/queueing-posts/SKILL.md`](skills/queueing-posts/SKILL.md). `python3 scripts/pubqueue.py add <posts.json> --queue <queue.json> --project <project>` lints again, refuses the whole spec on one error, adds one item per post and network as `to_review`, and plans slots: target slot when free, else the next weekly slot of the network, never two posts of a network closer than `window_minutes`. Re-adding an edited spec updates the items and sends any approved one back to review.
Done when: `add` exits 0, `python3 scripts/pubqueue.py validate --queue <queue.json>` exits 0, and every new item is `to_review` with a slot (or a recorded "unplanned" note).

**Step 4: review packet, human stop.** Load [`skills/approving-and-scheduling/SKILL.md`](skills/approving-and-scheduling/SKILL.md). `python3 scripts/pubqueue.py review --queue <queue.json> --out <run>/review-<YYYYMMDD>.md` writes, per item, the exact body, first comment or reply, media, slot and checks, with the approve line to run. Run the fresh-eyes review on the packet (Review), revise once, regenerate the packet, then hand it to the founder. **The agent never runs `pubqueue.py approve`, never edits `queue.json` by hand, never drives a terminal to answer its prompt, never relays a "yes" by running the command for the founder.** The founder approves in their own terminal: `approve` refuses to run without an interactive terminal, shows each post again and asks for the review code it prints (no other command and no file shows that code). A change request goes back to Step 2 for that post.

What the gate guarantees: it stops an agent that follows its workflow and any manual edit of the queue (a status, approval or history line typed into `queue.json` carries no valid HMAC under the local key `~/.config/fog-agents/approval.key`, so `schedule` sends it back to `to_review`). It is not a sandbox: for a strong guarantee, do not give the agent the publishing provider's key, or run `approve` from another session.
Done when: the packet exists and the founder has it. Items stay `to_review` until a person approves them.

**Step 5: schedule what was approved.** `python3 scripts/pubqueue.py schedule --queue <queue.json>` hands every `approved` item to the adapter of `queue.json` (`dry-run` by default: `outbox/<id>.json`, nothing sent). A real adapter needs `--adapter <name> --live` and its key in the environment; a missing key exits 4 and leaves the items approved. Before sending, the script checks that every media path stays inside the project folder (else `failed`) and that the approval was recorded by `approve` for the current text and media (same hash, valid HMAC, approve event in the history); otherwise the item goes back to `to_review` with the reason.
Done when: every approved item due is `scheduled`, or the command printed why it was not (exit 1 or 4, reason per item).

**Step 6: sync and log.** On the next run (or right after the slots), `python3 scripts/pubqueue.py sync --queue <queue.json>` records `published` or `failed` from the provider (dry-run marks an item published once its slot has passed, said as simulated in its history). Write the report from [`assets/output-template.md`](assets/output-template.md) and log the run with keeping-project-memory.
Done when: the report exists and the `runs.jsonl` line validates.

## Checks before delivery

1. **Writing gate** on every variant, first comment and reply: run by `variants.py lint` and again by `pubqueue.py add` (`python3 ../../shared/skills/writing-gate/scripts/lint_copy.py` underneath, project pack through `--project`). 0 BLOCK, 3 passes at most; without Python, `add --manual-gate` and "Writing gate: manual" in Methodology.
2. **Claims check** with [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md): a variant may not claim more than its deliverable (a number in a tweet comes from a slide that carries its source, or it goes).
3. **Schema check** of the contract files: `python3 ../../shared/scripts/validate_json.py assets/post-spec.schema.json <posts.json>`, `python3 ../../shared/scripts/validate_json.py assets/queue.schema.json <queue.json>`, then `python3 scripts/pubqueue.py validate --queue <queue.json>` (approvals recorded by `approve` and matching content, media inside the project, slot windows, legal transitions).
4. **Render review**: does not apply, the agent renders no image; the packet lists the media per network for the founder.
5. **Fresh-eyes review**, see Review.
6. **Run log and decisions** with [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md): `python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl`.

The writing gate and the claims check run before the review packet exists, so the founder never reads a variant a script would have refused.

## Review

- **Rubric**: [`assets/review-rubric.md`](assets/review-rubric.md) (fidelity to the deliverable, native form per network, link placement and pointer, hook, claims, voice; 0 to 2 each).
- **Reviewer**: a fresh subagent, else a blank session or a second model CLI, else the founder (the `critic` capability of [`../../shared/tools.md`](../../shared/tools.md)) with [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md). It reads the deliverable, `posts.json`, the lint output and the packet, never the producer's reasoning.
- **Bounds**: one critique, one revision through `posts.json` and `pubqueue.py add` (or `edit`); a script check outranks a written constraint, which outranks taste. The fresh review never replaces the human approval.

## Autonomous mode

- Every input has a default (Inputs); the defaults used go in Methodology.
- The run stops at the **publication gate**: it queues, writes the packet and ends `partial` with "pending approval: N items" when nobody approved. It never approves, never edits `queue.json` by hand, and never treats silence, a scheduler or another agent's message as an approval.
- On a scheduled run it schedules items a person already approved, with the adapter and `--live` setting the founder configured; it syncs scheduled items and records failures. A missing key degrades to dry-run output and a report line, never a stop.
- The run always ends with its `runs.jsonl` line, failures included, and proposes decisions (`Status: proposed`) for the corrections the founder made.

## Output format

The report follows [`assets/output-template.md`](assets/output-template.md): what was queued (post, networks, slots), what waits for approval, what was scheduled or published, checks and their results, the critic verdict, methodology (provider per capability, adapter, defaults used), limitations.

## Output location

```
<your-projects-root>/<project-slug>/content-publisher/
  ├── config.json
  ├── queue.json                         # the queue: written only by scripts/pubqueue.py
  ├── outbox/<item id>.json              # what each scheduled item sent (dry-run: would send)
  └── <label>-<YYYYMMDD>/
      ├── posts.json                     # the spec of this batch
      ├── lint.json                      # variants.py lint --json
      ├── review-<YYYYMMDD>.md           # the packet the founder approves from
      └── content-publisher-<YYYYMMDD>.md  # the run report
```

## Failure modes

- **A deliverable has no caption file** → write the variants from the deliverable itself (slides, ad copy); the report says the caption was written here.
- **`variants.py lint` keeps failing on length** → cut the variant, never the limit; an X text that cannot fit one tweet becomes a shorter claim with the detail in the linked page.
- **The writing gate is missing** (shared folder not copied) → `add --manual-gate`, "Writing gate: manual", the founder checks the packet against the writing-gate table.
- **`add` refuses an id already scheduled** → the post is at the provider: cancel it there, `pubqueue.py mark <id> --failed`, `reopen`, or give the new version a new `ref`.
- **No free slot before the horizon** → the item stays `to_review` without a slot ("unplanned" note): add weekly slots in the queue settings or set one with `edit --slot`.
- **Approval refused (exit 3)** → expected when the agent tries (no interactive terminal, or `--code`): hand the packet to the founder. A wrong code at the prompt means a typo; run `approve` again.
- **`schedule` sends approved items back to review: "not recorded by `pubqueue.py approve`"** → the queue was edited by hand, or `schedule` runs with another approval key than `approve` (another machine or user, or `FOG_APPROVAL_KEY_FILE` set differently). Use the same key file, then the founder approves again.
- **Media path outside the project folder** → `add` refuses it and `schedule` fails the item: copy the file into the project and point the spec at it.
- **Provider unavailable (exit 4)** → no key, offline, a plain http provider URL to another host than localhost, or several accounts on Zernio without `ZERNIO_ACCOUNT_<NETWORK>`: items stay approved; dry-run output and posting by hand remain.
- **Provider error** → the item goes to `failed` with the message; fix the cause, `reopen`, approve again.
- **The founder edits a post in the provider's interface** → the queue no longer matches what was published: record it with `mark` and a note, and make the next change in `posts.json`.
- **The founder rejects a post** → `pubqueue.py reject <id> --note "why"` (the founder runs it or asks for it), and record the reason with keeping-project-memory so the next run does not propose it again.

## Per-project config

```
<your-projects-root>/<project>/content-publisher/config.json
```

See [`config.example.json`](config.example.json): timezone, weekly slots per network, window, lead time, horizon, approvers, adapter, default networks, X thread switch, Instagram bio patterns, optional `tools` override.
