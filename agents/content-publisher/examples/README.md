# examples/

Inputs of `content-publisher` runs, light enough to commit. Queues, outboxes and review packets rebuild in one command, so only one packet is kept as a preview.

| Example | What it shows | Command (repo root) |
|---------|---------------|---------------------|
| [`swanbase-week-20261019/`](swanbase-week-20261019/) | A fictional week for the example brand: `posts.json` with three posts (a carousel on LinkedIn, Instagram and X; a text post on LinkedIn, X, Threads and Bluesky; an image post on LinkedIn and Instagram), a carousel-builder run in the format the importer reads (`captions.md`, placeholder exports), and [`review-preview.md`](swanbase-week-20261019/review-preview.md), the packet the founder approves from | `python3 agents/content-publisher/scripts/variants.py lint agents/content-publisher/examples/swanbase-week-20261019/posts.json` |
| [`stress/`](stress/) | A spec built to fail: a tweet over 280 split into a thread, a URL in a LinkedIn body, an Instagram caption pointing to a first comment with seven hashtags and no bio pointer, a PDF sent to Instagram, five images on X, a missing file, a missing Threads variant, writing-gate tics. Every failure must show with its code | `python3 agents/content-publisher/scripts/selftest.py` |

The texts are written for the tests: fictional, without numbers, names or offers. The images and the PDF are flat placeholders generated for the fixture (each under 7 KB), not real material.

## Rebuild the preview

```bash
rm -rf /tmp/cp-preview && cp -r agents/content-publisher/examples/swanbase-week-20261019 /tmp/cp-preview
python3 agents/content-publisher/scripts/pubqueue.py init --queue /tmp/cp-preview/queue.json --config agents/content-publisher/config.example.json --project-name swanbase
python3 agents/content-publisher/scripts/pubqueue.py add /tmp/cp-preview/posts.json --queue /tmp/cp-preview/queue.json --now 2026-10-19T08:00
python3 agents/content-publisher/scripts/pubqueue.py review --queue /tmp/cp-preview/queue.json --out agents/content-publisher/examples/swanbase-week-20261019/review-preview.md --now 2026-10-19T08:00
```

The committed preview then has `/tmp/cp-preview/queue.json` replaced by `<your-projects-root>/swanbase/content-publisher/queue.json` in its command lines.

## Adding an example

A folder `<brand>-<topic>-<YYYYMMDD>/` with `posts.json`, its media (each file under 150 KB) and, when a producer run is the input, that run's `captions.md` and exports in a subfolder. English, fictional or sourced copy, no real person's data. Add its expected outcome to `scripts/selftest.py`.
