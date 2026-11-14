---
name: queueing-posts
description: Adds a linted post spec to the publication queue with scripts/pubqueue.py - one item per post and network, always in to_review, never approved - and plans slots from the weekly slots of each network so that two posts of the same network never sit in the same window. Covers queue creation, re-adding an edited spec, edits, slot changes, and the validate command. Use at Step 3 of content-publisher. Triggers on "add to the queue", "plan the week", "when does it go out", "move this post".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Bash(python3:*)
---

# queueing-posts

`queue.json` is written by one script only, `scripts/pubqueue.py`. It validates every write against [`../../assets/queue.schema.json`](../../assets/queue.schema.json); never edit the file by hand (a hand edit is caught by `validate` and by `schedule`, and an `approved` status or approval typed by hand carries no valid HMAC under the local approval key, so it is sent back to review).

## Create the queue (first run)

```bash
python3 scripts/pubqueue.py init --queue <project>/content-publisher/queue.json \
  --config <project>/content-publisher/config.json
```

The settings travel with the queue: `timezone` (every slot is local time there), `slots` (weekly times per network), `window_minutes`, `lead_minutes`, `horizon_days`, `approvers`, `adapter`, `x_allow_thread`, `link_in_bio_patterns`.

## Add a batch

```bash
python3 scripts/pubqueue.py add <batch>/posts.json --queue <queue.json> --project <your-projects-root>/<project>
```

- The spec is linted again with the writing gate. One error anywhere and nothing is added.
- Each post becomes one item per network, id `<ref>.<network>`, status `to_review`, with its checks (lint, writing gate, BLOCK and WARN counts, length) and a content hash over its texts and media files.
- Re-adding the same spec changes nothing. Re-adding an edited post updates its items; an approved item whose content changed goes back to `to_review` with its approval cleared. An item already `scheduled` or `published` is never replaced: the command refuses and names it.
- Without the shared writing gate (agent copied alone), `--manual-gate` records `writing_gate: manual`: say who checked the copy in the report.

## How slots are planned

`plan` runs after every `add`, `edit`, `reopen` and `reject` (and alone: `pubqueue.py plan`):

1. Scheduled and published items are fixed.
2. Items whose slot is still valid keep it (approved items first): in the future by at least `lead_minutes`, before the horizon, and at least `window_minutes` from every kept post of the same network.
3. The others take their `target_slot` when it is valid, else the next weekly slot of their network that is.

A new post never pushes a planned one. Different networks may share a time. An item with no free slot stays without one and the command prints an "unplanned" note: add weekly slots to the queue settings or give it a slot.

## Edits

```bash
python3 scripts/pubqueue.py edit <id> --queue <queue.json> --text-file new.txt   # or --text "..."
python3 scripts/pubqueue.py edit <id> --queue <queue.json> --first-comment "..."  # LinkedIn only
python3 scripts/pubqueue.py edit <id> --queue <queue.json> --slot 2026-10-27T09:00
```

A text edit re-runs the lint and the writing gate on that item and refuses on an error. Any content change clears the approval. A slot change keeps it: the approval covers what is said, the planner covers when. For several networks of one post, edit `posts.json` and run `add` again rather than item by item.

## Read the queue

- `pubqueue.py list --queue <queue.json> [--status to_review] [--network x]`: id, status, slot, length, checks (no review code: only the interactive `approve` prints it).
- `pubqueue.py show <id> --queue <queue.json>`: the exact texts, media, approval and history of one item.
- `pubqueue.py validate --queue <queue.json>`: schema, every approved, scheduled or published item has an approval matching its content, no two live posts of a network in one window, every recorded status move is legal. Exit 0 or 1.

## Done when

`add` exits 0, `validate` exits 0, every new item is `to_review` with a slot or an "unplanned" note in the report.
