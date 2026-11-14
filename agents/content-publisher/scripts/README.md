# scripts/

The publication engine of content-publisher. The model writes `posts.json`; these scripts check it, queue it, plan it and hand approved items to a provider. Standard library only (Python 3.9+), deterministic with `--now`, every script answers `--help`.

| Script | Does | Writes |
|--------|------|--------|
| `variants.py` | Per-network rules on a post spec: schema, limits ([`../assets/platform-limits.json`](../assets/platform-limits.json), X weighted count, Bluesky graphemes), link never in a body, pointer to the right place (first comment, first reply, bio), media per network (no PDF outside LinkedIn, four images on X, Instagram needs a visual), hashtags, then the shared writing gate on every body, first comment and reply. `count` measures one text; `compose` prints what each network receives. | stdout (`--json` for a file) |
| `pubqueue.py` | The queue CLI: `init`, `add`, `edit`, `plan`, `list`, `show`, `review`, `approve` (human only, interactive terminal), `reopen`, `reject`, `schedule`, `sync`, `mark`, `validate`. Validates every write against [`../assets/queue.schema.json`](../assets/queue.schema.json). | `queue.json`, `outbox/<id>.json`, review packet |
| `import_carousel.py` | A carousel-builder run (`captions.md`, `export/carousel.pdf`, `export/slide-NN.jpg`, or `.png` when no JPEG exists) to a post spec draft: LinkedIn post and first comment, Instagram caption, X, Threads and Bluesky texts when `captions.md` has them, alt text, link. `--append` adds the post to an existing spec (a post with the same ref is replaced). | `posts.json` |
| `common.py` | Status machine, content hash, approval key and HMACs (review code, approval seal), media path containment, clock, atomic writes, lock, schema validation through `shared/scripts/validate_json.py`. | n/a |
| `adapters/` | One interface (`base.py`: `build_payload`, `schedule`, `status`) and four providers: `dry_run.py` (default, sends nothing), `zernio.py`, `command.py`, `webhook.py`. | outbox (dry-run) |
| `selftest.py` | Offline regression test (below). | temporary folder |

## Quick run on the example

From the repo root, on a copy of the example so the repo stays clean:

```bash
cp -r agents/content-publisher/examples/swanbase-week-20261019 /tmp/cp-demo
S=agents/content-publisher/scripts
python3 $S/variants.py lint /tmp/cp-demo/posts.json
python3 $S/pubqueue.py init --queue /tmp/cp-demo/queue.json --config agents/content-publisher/config.example.json --project-name swanbase
python3 $S/pubqueue.py add /tmp/cp-demo/posts.json --queue /tmp/cp-demo/queue.json --now 2026-10-19T08:00
python3 $S/pubqueue.py review --queue /tmp/cp-demo/queue.json --out /tmp/cp-demo/review.md --now 2026-10-19T08:00
```

Then approve as a person would, in an interactive terminal (the command shows the post, prints its review code and asks you to type it; it refuses to run without a TTY), and schedule with the dry-run adapter:

```bash
python3 $S/pubqueue.py approve pitch-deck-order.x --queue /tmp/cp-demo/queue.json --by <your-name> --now 2026-10-19T08:00
python3 $S/pubqueue.py schedule --queue /tmp/cp-demo/queue.json --now 2026-10-19T08:00
cat /tmp/cp-demo/outbox/pitch-deck-order.x.json
```

## Adapters

`schedule` uses the queue's `settings.adapter` (`dry-run` unless changed) or `--adapter`. Real adapters need `--live` and read their configuration from the environment only.

| Adapter | Environment | Behaviour |
|---------|-------------|-----------|
| `dry-run` | none | Writes `outbox/<id>.json` with `would_send` (provider-independent payload) and `zernio_view`. `sync` marks an item published once its slot has passed (simulated, said in the history). |
| `zernio` | `ZERNIO_API_KEY`; `ZERNIO_ACCOUNT_LINKEDIN`, `_X`, `_INSTAGRAM`, `_THREADS`, `_BLUESKY` when several accounts exist; `ZERNIO_BASE_URL` optional | One Zernio post per item: LinkedIn `firstComment` (and `documentTitle` for a PDF), X / Threads / Bluesky `threadItems` = [post with media, link reply], Instagram caption only. Idempotency key per item, content and slot. |
| `command` | `CONTENT_PUBLISHER_COMMAND` | Runs the program with the payload as JSON on stdin; expects `{"post_id": "...", "status": "scheduled"}` on stdout. Status checks send `{"action": "status", ...}`. |
| `webhook` | `CONTENT_PUBLISHER_WEBHOOK_URL`, optional `CONTENT_PUBLISHER_WEBHOOK_TOKEN` | POSTs the payload with an `Idempotency-Key` header. |

`CONTENT_PUBLISHER_OFFLINE=1` makes every HTTP adapter refuse to open a connection (exit 4): the tests run with it. Adding a provider: a new file in `adapters/` with a class that subclasses `Adapter`, registered in `adapters/__init__.py`, plus a payload test in `selftest.py`. Provider notes: [`../references/providers.md`](../references/providers.md).

## Tests

```bash
python3 agents/content-publisher/scripts/selftest.py
```

Offline, about 10 seconds, no key, no network. It checks the counting (X URL 23, emoji, flags, CJK; graphemes), the stress spec ([`../examples/stress/posts.json`](../examples/stress/posts.json): every failure with its expected code), the reference spec and the carousel importer, the queue lifecycle (all new items `to_review`, idempotent re-add, windows, review packet without URL in a body), the approval gate (no terminal, `--code` as an argument, reserved names, wrong code typed at a pseudo-terminal, unapproved schedule, a status and a complete approval forged in `queue.json`, an approval copied between items, edit and media swap after approval, no review code in `show`, `list`, `edit` or the packet, one call site of the approval sentinel and of the review code), the adapters (refusals without `--live`, key or network, plain http refused, `Authorization` dropped on a cross-host redirect; a local fake for `command`; dry-run outbox with the link in the LinkedIn first comment and the X reply), sync, mark, reopen, validate and `--help`, then media paths outside the project refused by `add`, `schedule` and `validate`. The approval key is a throwaway file (`FOG_APPROVAL_KEY_FILE`) in the work folder; POSIX only (pty). `--keep DIR` keeps the work folder.

## Exit codes

All CLIs: 0 ok, 1 a check failed or a command was refused on the content or the state, 2 usage error or invalid file. `pubqueue.py` adds 3 (approval gate: not approved, no interactive terminal, code passed as an argument, reserved or unlisted name, wrong code, approval not recorded by `approve`) and 4 (provider unavailable: no key, offline, ambiguous account; nothing changed for the item).
