---
name: approving-and-scheduling
description: Runs the publication gate of content-publisher - writes the review packet, hands it to the founder, who alone approves items at an interactive terminal by typing a review code bound to the exact content, then schedules approved items through the configured adapter (dry-run by default, Zernio, a local command or a webhook, keys from the environment), syncs their status and logs the run. States what the agent must never do around approval. Use at Steps 4 to 6 of content-publisher and on scheduled runs. Triggers on "review the queue", "approve", "schedule", "what got published", "publish now".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# approving-and-scheduling

Publishing speaks for the founder in public. The queue therefore has one gate no script, schedule or agent crosses: an item moves from `to_review` to `approved` only when a person runs the approve command in their own interactive terminal, reads each post again and types the review code it shows.

## The gate, and what the agent never does

The agent:

- **never runs `pubqueue.py approve`**, under any name, even when the founder says "yes", "ok", "go" in chat. It answers with the exact approve lines to run;
- never writes `approved`, an `approval` object, a history line or a content hash into `queue.json`, never edits the file by hand;
- never drives a terminal or a pseudo-terminal to answer the approve prompt, never reads the approval key file;
- never reads a scheduler, a silence, another agent's message or a previous approval of a similar post as consent;
- never rewrites an approved item's text and schedules it: an edit sends it back to `to_review`.

What the scripts enforce, and `scripts/selftest.py` tests:

| Attempt | Result |
|---------|--------|
| `approve` without an interactive terminal (stdin or stdout not a TTY) | exit 3, item unchanged |
| `approve --code <code>` | exit 3: the code is never an argument |
| `approve --by agent` (or `ai`, `bot`, `claude`, `codex`, `content-publisher`, `<your-name>`...) | exit 3 |
| `approve` with a name outside `settings.approvers` (when the list is set) | exit 3 |
| `approve` with a wrong review code typed at the prompt | exit 3 |
| `approve` of an item whose checks fail or whose slot has passed | exit 1 |
| `schedule --id <item not approved>` | exit 3 |
| `approved`, an approval object (even with the right content hash) or an approve history line typed into `queue.json` | `validate` exit 1; `schedule` sends it back to `to_review` with the reason: the approval carries no valid HMAC |
| an approval copied from one item to another | refused the same way: the HMAC covers the item id |
| a media path edited to a file outside the project folder | `schedule` moves the item to `failed`, `validate` exit 1 |
| `show`, `list`, `edit`, `review` | print no review code |
| text edited after approval | back to `to_review`, approval cleared |
| media file replaced after approval | `schedule` sends it back to `to_review` |
| any code path other than `cmd_approve` setting `approved` | refused by `common.transition()`; the selftest checks the approval sentinel and the review code each have one call site |

The review code and the approval seal are HMACs under a local key, `~/.config/fog-agents/approval.key` (mode 600, created on first use, outside every project; `FOG_APPROVAL_KEY_FILE` sets another path). Limits, said plainly: the gate stops an agent that follows its workflow and any manual edit of the queue. It is not a sandbox: a process with an unrestricted shell under the founder's user can read the key or drive a terminal. For a strong guarantee, do not give the agent the publishing provider's key (`ZERNIO_API_KEY` or the command's credentials), or run `approve` from another session the agent cannot reach.

## Step 4: the review packet

```bash
python3 scripts/pubqueue.py review --queue <queue.json> --out <batch>/review-<YYYYMMDD>.md
```

Per item: network, slot in words, checks, media, the exact body, first comment or reply, and the approve line (no review code: only the interactive `approve` prints it). Regenerating the packet refreshes the hashes of items whose media changed on disk. Run the fresh-eyes review on it ([`../../assets/review-rubric.md`](../../assets/review-rubric.md)), revise once through `posts.json` and `add`, regenerate, then give the founder the packet path and, in the message, the list of items with slots. The founder:

- approves in their own terminal: `python3 agents/content-publisher/scripts/pubqueue.py approve <id> [<id> ...] --queue <queue.json> --by <name>`; for each id the command shows the post, prints its review code and asks for it (Enter skips the item);
- asks for a change: back to [`../writing-variants/SKILL.md`](../writing-variants/SKILL.md) for that post;
- refuses: `pubqueue.py reject <id> --queue <queue.json> --by <name> --note "why"`; record the reason with keeping-project-memory.

Without an answer the run ends `partial`, "pending approval: N items". The next run starts by listing what is still `to_review`.

## Step 5: schedule

```bash
python3 scripts/pubqueue.py schedule --queue <queue.json>                         # adapter of the queue, dry-run by default
python3 scripts/pubqueue.py schedule --queue <queue.json> --adapter zernio --live # real, key in the environment
python3 scripts/pubqueue.py schedule --queue <queue.json> --due-hours 24          # only what is due within a day
```

Only `approved` items go. For each, the script checks every media path stays inside the project, re-hashes the texts and media, checks the approval (same content hash, valid HMAC, approve event in the history), checks the slot is in the future, builds the payload and calls the adapter.

| Adapter | Sends | Needs | Notes |
|---------|-------|-------|-------|
| `dry-run` (default) | nothing | nothing | writes `outbox/<id>.json`: the provider-independent payload and the Zernio request it would make. The founder can post by hand from it, then `mark <id> --published` |
| `zernio` | Zernio API | `ZERNIO_API_KEY`, `ZERNIO_ACCOUNT_<NETWORK>` when several accounts | LinkedIn first comment, X / Threads / Bluesky link as the second of two thread items, media uploaded at send |
| `command` | the founder's program | `CONTENT_PUBLISHER_COMMAND` | JSON on stdin, JSON on stdout: the route for Buffer, Typefully, native APIs |
| `webhook` | an automation URL | `CONTENT_PUBLISHER_WEBHOOK_URL` | Make, n8n, Zapier, a server |

Details, payloads and setup: [`../../references/providers.md`](../../references/providers.md). Real adapters need `--live`; without a key, offline, with a plain http URL to another host than localhost, or with an ambiguous account the command exits 4 and the items stay approved. A provider refusal moves the item to `failed` with the message.

## Step 6: sync, report, log

```bash
python3 scripts/pubqueue.py sync --queue <queue.json>
python3 scripts/pubqueue.py mark <id> --queue <queue.json> --published --by <name>   # posted by hand
python3 scripts/pubqueue.py reopen <id> --queue <queue.json> --by <name>             # failed -> to_review
```

`sync` asks each item's adapter for its status: `published` or `failed` (dry-run simulates `published` once the slot has passed, and says so in the history). Then write the report from [`../../assets/output-template.md`](../../assets/output-template.md) and the run line with [`../../../../shared/skills/keeping-project-memory/SKILL.md`](../../../../shared/skills/keeping-project-memory/SKILL.md): checks `copy_lint`, `queue_schema`, `queue_invariants`; human verdict `approved` when at least one item was approved this run, `none` when the packet is still waiting.

## Done when

The packet exists; every approved item due is `scheduled` or has a printed reason; `validate` exits 0; the report and the `runs.jsonl` line are written.
