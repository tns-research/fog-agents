---
name: collecting-deliverables
description: Gathers what the other agents produced (a carousel-builder run with captions.md and its exports, a static-ads-builder render, a text post the founder wrote) and turns each into one entry of posts.json, the post spec of content-publisher - a stable ref, the networks, the media each network receives, the one link isolated from the body, the source recorded. Drafts carousel posts with scripts/import_carousel.py. Use at Step 1 of content-publisher. Triggers on "publish this carousel", "queue these posts", "post the ad on Instagram", "schedule this".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# collecting-deliverables

The queue publishes what other agents made. This step finds those files, decides what each network receives, and writes it down as data the scripts can check. No copy is invented here: the texts come from the deliverable, the variants are adapted at Step 2.

Contract: [`../../assets/post-spec.schema.json`](../../assets/post-spec.schema.json). One file per batch: `<project>/content-publisher/<label>-<YYYYMMDD>/posts.json`. Media paths are relative to that file.

## Where deliverables live

Producers write in their own folder of the project ([`../../../../shared/handoffs.md`](../../../../shared/handoffs.md)). When several dated runs exist, take the newest one not already in `queue.json` (an id `<ref>.<network>` there means it was queued) and say which one you took.

| Producer | Files to read | What becomes the post |
|----------|---------------|-----------------------|
| `carousel-builder/<label>-<YYYYMMDD>/` | `captions.md` (LinkedIn post, first comment, Instagram caption, alt text per slide), `export/carousel.pdf`, `export/slide-NN.jpg` (or `.png` when no JPEG exists) | kind `carousel`: the PDF as a LinkedIn document, the slide images as the Instagram carousel, the cover as the X, Threads and Bluesky image |
| `static-ads-builder/<label>-<YYYYMMDD>/` | `renders/*.jpg` (pick the 4:5 or 1:1 render), `meta/ad-copy.md` | kind `image`: one render per post. Ad copy is written for paid placement: the organic variant is rewritten at Step 2, and an offer or a price in it needs the founder's yes |
| The founder | a markdown note, a pasted text, an image | kind `text` or `image`, `source.agent` = `founder` |

## Carousel runs: use the importer

```bash
python3 scripts/import_carousel.py <project>/carousel-builder/<label>-<YYYYMMDD> \
  --ref <short-ref> --out <project>/content-publisher/<label>-<YYYYMMDD>/posts.json \
  --networks linkedin,instagram,x --language en --source-path carousel-builder/<label>-<YYYYMMDD>
```

It reads the sections of `captions.md`, the alt text table and the exports, takes the link from the first URL of the first comment, and leaves out any network whose text `captions.md` does not have (X, Threads, Bluesky): the lint reports `missing-variant` and Step 2 writes it. `--append` adds a post to an existing batch (a post with the same ref is replaced). `--language` sets the post's language (default `en`).

## Deciding the media per network

`variants.media` lists the indexes of `post.media` a network receives. Without it, every item the network accepts goes (documents only on LinkedIn).

- **LinkedIn**: a carousel goes as the PDF document (`media: [0]`), with `title` set; an image post takes the image.
- **Instagram**: images or a video, never a PDF; the carousel's slide images in slide order, each with its alt text.
- **X**: four images at most; one image (the cover) reads best next to one tweet.
- **Threads, Bluesky**: the cover image, or nothing for a text post.

Every image carries `alt`: the carousel's alt text table, or one factual sentence about what the image shows.

## The link

One link per post, in `link` (https only). The body never holds it: Step 2 points to it in words, the scripts place it (LinkedIn first comment, first reply on X, Threads and Bluesky, Instagram bio). `link_note` is the short line before the link in the comment or reply ("The full guide:"). A deliverable with several URLs (a guide and a source) keeps the main one in `link` and the others in the LinkedIn `first_comment`.

## Refs and slots

- `ref`: lowercase and hyphens, stable for the life of the post (`pitch-deck-order`). Re-adding a spec with the same ref updates the queued items; a new version after publication needs a new ref.
- `target_slot`: only when the post is tied to a date (an event, a launch). Otherwise leave it out and the planner takes the next weekly slot of each network.

## Done when

`posts.json` validates: `python3 ../../shared/scripts/validate_json.py assets/post-spec.schema.json <posts.json>` exits 0, every post names its source, every image has alt text.
