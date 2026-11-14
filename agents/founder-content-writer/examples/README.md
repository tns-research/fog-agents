# examples/

Inputs of a `founder-content-writer` run, light enough to commit. `posts.json`, the checks and the packet rebuild in one command; only the report is kept as a preview.

| Example | What it shows | Command |
|---------|---------------|---------|
| [`brindlefen-workshop-notes-20261026/`](brindlefen-workshop-notes-20261026/) | A fictional founder of a fictional bike workshop tool (domain `.example`): a voice note transcript and call notes in `raw/`, a small market-signal sidecar in `raw/`, `context.json`, the batch spec `posts-spec.json` with five posts, and [`batch-preview.md`](brindlefen-workshop-notes-20261026/batch-preview.md), the report the founder reads | see [`../scripts/README.md`](../scripts/README.md#quick-run-on-the-example) |

The founder, the brand, the workshops, the forum and every number are made up. No real person, no real company, no e-mail address.

The refusals live in [`../scripts/fixtures/stress/posts-spec.json`](../scripts/fixtures/stress/posts-spec.json), a spec built to fail on every rule, and the French address form in [`../scripts/fixtures/fr/`](../scripts/fixtures/fr/): French by necessity, the only non-English text of this agent, because that rule can only be tested on French copy.

## Rebuild the preview

Run the quick run of `scripts/README.md`, then copy `$R/founder-content-20261026.md` over `batch-preview.md`.
