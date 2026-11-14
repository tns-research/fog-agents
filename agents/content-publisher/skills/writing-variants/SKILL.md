---
name: writing-variants
description: Writes one native text per network for each post of posts.json - a LinkedIn post with its first comment, a single tweet within X's weighted 280, an Instagram caption that points to the link in bio, Threads and Bluesky posts when asked - from the deliverable's own copy, without adding claims, then runs scripts/variants.py lint (limits, link placement, media per network, shared writing gate) until it exits 0. Use at Step 2 of content-publisher. Triggers on "adapt for X", "write the tweet", "LinkedIn version", "caption per network".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# writing-variants

Same idea, written the way each feed reads it. A variant is not a cut of the LinkedIn post: it has its own first line, its own length and its own way of pointing to the link. What it says stays inside what the deliverable says.

## Rules for every network

- **The body never holds a URL.** Not `https://`, not `www.`, not `domain.com/path`. Write where the link is in words; the script places it. A bare brand domain (`swanbase.co`) is a warning, because networks may turn it into a link.
- **Point to the right place.** LinkedIn: "in the first comment". X, Threads, Bluesky: "in the first reply". Instagram: "in bio" (`Link in bio.`, "linked in bio"). Pointing to the wrong place is an error (`wrong-link-pointer`); pointing with no `link` set too (`pointer-without-link`).
- **Claims come from the deliverable.** A number, a name or a result in a variant appears in the deliverable with its source, or in `positioning.proof` ([`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)). Shortening a sentence never sharpens a claim ("can help" stays "can help").
- **The language of the deliverable**, one language per variant.
- **The first line carries the idea**: feeds cut long posts after the first lines (LinkedIn about 210 characters, Instagram about 125; sources in [`../../assets/platform-limits.json`](../../assets/platform-limits.json)). The lint warns past these.
- **A different text per network.** The lint warns when two networks get the same text.

## Per network

| Network | Length (scripted) | Shape | Link |
|---------|-------------------|-------|------|
| LinkedIn | 3000 characters, first comment 1250 | the deliverable's post: idea first, short paragraphs, one question or next step at most | first comment: `link_note` + link, or `first_comment` you write (must hold the link) |
| X | 280, weighted: a URL counts 23, an emoji or a CJK character 2 | **one tweet**: the sharpest sentence of the deliverable plus one supporting line. No thread: a `---` separator or numbered parts are an error unless the queue sets `x_allow_thread` | first reply: `link_note` + link, also within 280 |
| Instagram | 2200 characters, 5 hashtags at most | caption for people who swipe: the idea, what to look at in the slides, the bio pointer, then hashtags | bio: the founder keeps the bio link current |
| Threads | 500 characters (Threads may count UTF-8 bytes: the lint warns past 500 bytes) | conversational, a question works | first reply |
| Bluesky | 300 graphemes, the URL counts in full | one short paragraph | first reply |

Check a length while writing: `python3 scripts/variants.py count --network x "<text>"`.

## Lint loop

```bash
python3 scripts/variants.py lint <posts.json> --project <your-projects-root>/<project> --queue <queue.json>
```

- Errors carry the post and network (`pitch-deck-order.x`) and a code. Fix the text in `posts.json`, never a limit in `assets/platform-limits.json` (a limit changes only when the platform's page changes, with its URL).
- `writing-gate:<code>` errors come from the shared gate ([`../../../../shared/skills/writing-gate/SKILL.md`](../../../../shared/skills/writing-gate/SKILL.md)): rewrite the sentence with the fact it was standing in for. The founder's project pack applies through `--project`.
- Read every warning: fix it or keep it with a reason (a hook past the fold that cannot be shorter).
- Three passes at most. A post still failing after the third goes to the founder with its findings, not into the queue.
- `python3 scripts/variants.py compose <posts.json>` prints what each network will receive (body, first comment, reply): read it once as the reader will.

## Done when

`variants.py lint` exits 0 and `lint.json` (`--json`) is saved in the batch folder.
