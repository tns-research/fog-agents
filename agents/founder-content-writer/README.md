# founder-content-writer

Turns what a founder said or wrote (a voice note, notes, a call, a past talk, a market-signal report) into LinkedIn and X posts in their own voice, checked by scripts, then hands them to `content-publisher`. It never publishes.

Nothing else in the stack writes a founder's organic posts: `carousel-builder` makes carousels, `static-ads-builder` makes ads, `content-publisher` adapts a finished deliverable per network and queues it.

## How it works

1. **Ingest** (`scripts/ingest.py`): the raw material is copied verbatim into the batch, with its hash.
2. **Spec** (`posts-spec.json`): the model writes, per post, the angle, the hook type, one body per network, the passages it comes from, and every claim with its source.
3. **Check** (`scripts/check_spec.py`): each passage is searched word for word in the source. Every number, name, quoted sentence, ranking and time marker traces to `positioning.proof`, a sourced passage or the cited passages. Limits and link rules are content-publisher's own code, the writing gate is the shared one. Openings are compared inside the batch and against past posts; hook types and angles have to vary; the voice pack applies when the project has one.
4. **Build** (`scripts/build_batch.py`): `posts.json`, accepted by content-publisher's own lint before it counts, the founder's report with its claims ledger, and a critique packet.
5. **Fresh eyes**: a reviewer that did not write the posts scores them against a rubric. One critique, one revision.
6. **Memory** (`scripts/project_memory.py`): past openings are recorded, and a post the founder rejects becomes a rule.

## What it refuses

| Refused | Code |
|---------|------|
| A passage that is not in the source word for word | `passage-not-found` |
| A number that is not in `positioning.proof` or a sourced passage, even if the founder's notes hold it | `unsourced-number`, `number-needs-proof` |
| A rounded number | `number-differs-from-proof` |
| A claim resting on a proof item that `shared/scripts/proof.py` finds unusable for posts (a stale metric, a testimonial without consent) | `proof-not-usable` |
| An event, a client, a date, a name or a quoted sentence no passage holds | `untraced-event`, `client-not-in-source`, `time-marker-not-in-source`, `name-not-in-sources`, `quote-not-in-source` |
| A market-signal quote used as a testimonial | `quote-as-testimonial` |
| A link or a domain in a body, a tweet over 280 weighted characters, a thread when threads are off | `link-in-body`, `over-limit`, `x-thread` |
| A machine tic | `writing-gate:*` |
| An opening already used, or one the founder rejected | `duplicate-past-opening`, `rejected-opening` |
| Tu in a French post, unless the project chose it | `address-tu` |

What the notes hold and the policy refuses goes in the report's dropped list, so the founder can add a real number to the proof list.

## Quick start

```bash
# Offline test of the whole agent, no key, no network
python3 agents/founder-content-writer/scripts/selftest.py
```

Then, from your AI coding harness:

```
Run founder-content-writer for project acme on this voice note: <transcript or file>
```

The agent follows [`AGENT_FOUNDER_CONTENT_WRITER.md`](AGENT_FOUNDER_CONTENT_WRITER.md). The commands and a run on the example: [`scripts/README.md`](scripts/README.md).

## Outputs

```
<your-projects-root>/<project>/founder-content-writer/<label>-<YYYYMMDD>/
  brief.md  sources/  posts-spec.json  check.json
  posts.json  lint.json  founder-content-<YYYYMMDD>.md  review/
<your-projects-root>/<project>/project-context/memory/posts.jsonl   # past openings and rejections
```

Hand `posts.json` to content-publisher: `pubqueue.py add`, then a person approves each item in their own terminal.

## Tools

All external capabilities are optional: see the Tools table of [`AGENT_FOUNDER_CONTENT_WRITER.md`](AGENT_FOUNDER_CONTENT_WRITER.md#tools). The checks are local and free.

## Examples

[`examples/brindlefen-workshop-notes-20261026/`](examples/brindlefen-workshop-notes-20261026/): a fictional founder's voice note and call notes, the batch spec, and the report they produce.

## Limits

- A script proves that a passage exists and that numbers and names trace to a source. Whether a sentence stays faithful to its passage is the reviewer's and the founder's call.
- A sentence that reuses the words of its passage to say something else passes the scripts: the reviewer reads every post next to its passages. A capitalized name at the start of a sentence is only a warning (`possible-name`).
- LinkedIn and X only. Other networks are content-publisher's variants.
- No performance claim: this agent does not say which hook gets more reach. Read your own numbers with growth-pulse.

## License

Apache-2.0.
