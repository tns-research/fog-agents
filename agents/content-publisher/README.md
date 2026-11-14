# content-publisher

The last step between a finished deliverable and a feed. It takes what the other agents made (a founder-content-writer batch of posts, a carousel-builder deck with its captions, a static ad visual, a text post), writes one variant per network, checks every limit with a script, queues it, and schedules only what a person approved. Nothing is ever approved by the agent.

## How it works

1. **Collect** (`posts.json`): one entry per deliverable, the media each network receives, the one link of the post isolated. `scripts/import_carousel.py` drafts carousel posts from `captions.md` and the exports.
2. **Write the variants**: a LinkedIn post and its first comment, one tweet, an Instagram caption that points to the bio, Threads and Bluesky when asked. `scripts/variants.py lint` checks limits (X counted the way X counts: a URL 23, an emoji 2), keeps links out of every body, checks the pointer (first comment, first reply, bio), the media per network, and runs the shared writing gate on every text.
3. **Queue** (`queue.json`): one item per post and network, always `to_review`, planned in weekly slots, never two posts of a network in the same window.
4. **Review packet, human stop**: the exact text per network, the slot, the checks and the approve command. The founder runs it in their own terminal, reads each post again and types the review code it shows; an edit afterwards sends the item back to review.
5. **Schedule**: approved items go through the adapter. Default `dry-run` sends nothing and writes what would be sent; Zernio, a local command (Buffer, Typefully, native APIs) or a webhook when the founder sets one up.
6. **Sync and log**: published or failed, recorded in the queue and the project memory.

```
to_review --approve (a person)--> approved --schedule--> scheduled --sync--> published
    |                                 |                       \--> failed --reopen--> to_review
    +--reject--> rejected             +--edit--> to_review
```

## Network rules

| Network | Body | Link | Checked by script |
|---------|------|------|-------------------|
| LinkedIn | 3000 characters | first comment (1250) | length, no URL in body, comment holds the link, PDF document allowed |
| X | one tweet, 280 weighted | first reply (280) | weighted length, no thread unless allowed, four images at most, no PDF |
| Instagram | 2200 characters, 5 hashtags | "link in bio" | length, hashtags, bio pointer present, needs an image or a video, no PDF |
| Threads (optional) | 500 characters | first reply | length, UTF-8 bytes warning, no PDF |
| Bluesky (optional) | 300 graphemes | first reply | grapheme length, no PDF |

Every limit has its source URL in [`assets/platform-limits.json`](assets/platform-limits.json).

## Quick start

```bash
# Offline test of the whole engine (about 10 s, no key, no network)
python3 agents/content-publisher/scripts/selftest.py

# Lint the reference batch
python3 agents/content-publisher/scripts/variants.py lint agents/content-publisher/examples/swanbase-week-20261019/posts.json
```

Then, from your AI coding harness:

```
Run content-publisher for project acme on the carousel from last week
```

The agent follows [`AGENT_CONTENT_PUBLISHER.md`](AGENT_CONTENT_PUBLISHER.md). Full CLI reference and the adapters: [`scripts/README.md`](scripts/README.md).

## The approval gate

- `pubqueue.py add` only ever creates `to_review` items; the spec format has no status field.
- `pubqueue.py approve <id> --by <name>` is the only way to `approved`. It needs a person's name (agent names are refused, `approvers` can restrict the list) and an interactive terminal: when stdin or stdout is not a TTY it exits 3. It shows each post, prints its review code and asks the person to type it. The code is never an argument (`--code` exits 3) and no other command prints it: not `show`, `list`, `edit` nor the review packet.
- The review code and the approval record are HMACs under a local key, `~/.config/fog-agents/approval.key` (created on first use with mode 600, outside every project folder; `FOG_APPROVAL_KEY_FILE` sets another path). `approve`, `schedule` and `mark` must see the same key file: approving on one machine and scheduling on another means copying the key.
- The approval is bound to a hash of the texts and media files. An edit, a re-added spec or a replaced image sends the item back to `to_review`. `schedule` (and `mark --published`) also require the approve event in the item's history and a valid HMAC on the approval: a status, an approval object or a history line typed into `queue.json` is sent back to `to_review` with the reason, and `validate` reports it.
- Media paths must resolve inside the project folder (the parent of `content-publisher/`): an absolute path, a `../` or a symlink that leaves it is refused by `add`, `schedule` and `validate`, so no other file of the machine can be uploaded. Provider URLs must be https (plain http only to localhost), and a redirect to another host drops the `Authorization` header.
- `scripts/selftest.py` tests each of these refusals (approvals are typed through a pseudo-terminal) and that a single function in the code holds the approval sentinel and prints the review code.

What the gate guarantees: it stops an agent that follows its workflow and any manual edit of the queue. It is not a sandbox: an agent with an unrestricted shell under your user can read the key or drive a terminal. For a strong guarantee, do not give the agent the publishing provider's key, or run `approve` from another session the agent cannot reach.

## Outputs

```
<your-projects-root>/<project>/content-publisher/
  config.json  queue.json  outbox/<id>.json
  <label>-<YYYYMMDD>/posts.json  lint.json  review-<YYYYMMDD>.md  content-publisher-<YYYYMMDD>.md
```

## Tools

All external capabilities are optional: see the Tools table of [`AGENT_CONTENT_PUBLISHER.md`](AGENT_CONTENT_PUBLISHER.md#tools). Without any publishing provider, the dry-run outbox and the review packet are what you post from by hand.

## Examples

- [`examples/swanbase-week-20261019/`](examples/swanbase-week-20261019/): a fictional week for the stack's example brand: a carousel, a text post on four networks, an image post, and the review packet they produce.
- [`examples/stress/`](examples/stress/): a spec built to fail on every rule.

## Limits

- One link per post. Several URLs go in the LinkedIn first comment; other networks get the main one.
- No cancellation at the provider from the queue: cancel there, then `mark --failed`.
- Real adapters are tested offline on their payload only; check the provider's documentation before the first live run.

## License

Apache-2.0.
