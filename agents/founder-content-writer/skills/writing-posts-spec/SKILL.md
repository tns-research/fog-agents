---
name: writing-posts-spec
description: Writes posts-spec.json for a batch of founder posts - per post the angle, the hook type, the structure, one body per network (a LinkedIn post, one tweet of 280 weighted characters), the source passages copied word for word, and every claim the post makes with its source. Varies hook types and angles across the batch, stays in the founder's words and voice, keeps links out of bodies, and lists under dropped whatever the notes hold that the proof list does not. Use at Step 2 of founder-content-writer. Triggers on "write my posts", "LinkedIn post from my notes", "tweet this", "founder content".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# writing-posts-spec

The model writes a spec, never a finished post on its own authority: `check_spec.py` reads every claim back against the raw material. Contract: [`../../assets/posts-spec.schema.json`](../../assets/posts-spec.schema.json). Vocabulary: [`../../assets/hook-types.md`](../../assets/hook-types.md). Claims: [`../../assets/claims-model.md`](../../assets/claims-model.md).

## Order of work

1. **Pick the angles from the inventory.** One post, one idea the founder really holds. Write `angle` as one sentence a stranger understands. Two posts on the same idea are one post.
2. **Copy the passages first.** Before writing a body, copy the passage it comes from into `source_passages`, exact, five words at least, one speaker turn at a time. A market-signal passage names its `quote_id`. If you cannot find the passage, the post has no ground: drop it.
3. **Pick the hook type the material offers.** A batch uses each hook type and each angle type at most once per three posts, rounded up. Three posts means three hook types.
4. **Write the LinkedIn body, then the tweet.** See below.
5. **Declare every claim** with its source, as the post writes it. A claim the post does not hold word for word fails (`claim-not-in-post`).
6. **List what you left out** under `dropped`, with the reason and what would make it usable. Then write `summary` for the founder, in their language.

## In the founder's words

- Reuse their nouns and verbs. "Greasy hands" stays "greasy hands"; it never becomes "manual workflows". A body that shares too few words with its passages fails (`post-not-tied-to-passage`) because it has stopped being theirs.
- Keep what they said at the strength they said it. "It calmed down" never becomes "it disappeared".
- Their opinion may go further than their anecdote, plainly as opinion, in their register. A new event, a new detail, a new result may not.
- With a voice pack, its rules bind: sentence length, person, address form, emoji, exclamation marks, banned words. Its examples show the register and are never copied (`voice-example-copied`). Without a pack, the raw material is the only voice reference: stay close to it.
- Write the way they would say it to a peer: full sentences, one thought per line of attention. The writing gate refuses the machine tics ([`../../../../shared/skills/writing-gate/SKILL.md`](../../../../shared/skills/writing-gate/SKILL.md)); fixing one means writing the fact it stood in for.

## Language and address

- Every post is in the founder's language: the config, then the voice pack, then `voice.language` of `context.json`, then the language of the raw material. A mismatch fails.
- A post in French addresses its audience with vous. Tu appears only when the project's config or an active decision says so. A voice pack that measured tu raises a warning, and the founder chooses. Words inside quotation marks stay as they were said.

## LinkedIn

- The first line carries the idea and stands alone: about 210 characters show before "see more" (`agents/content-publisher/assets/platform-limits.json`; the lint warns past it).
- Short paragraphs, one idea, developed. End on something the reader can look at or do, or on the thought itself. No question added for engagement, no promise of a resource that does not exist.
- No hashtag wall, no signature, no template slot. A post carries no sender name.
- Limit: read from content-publisher, never restated here.

## X

- One tweet that stands alone: the sharpest thought of the post plus what makes it believable. It is written for X, never a cut of the LinkedIn post.
- 280 weighted characters. Check while writing: `python3 ../content-publisher/scripts/variants.py count --network x "<text>"`.
- A thread only when `config.x_allow_thread` is true, with `---` between posts. Otherwise a thought that does not fit is cut, or stays on LinkedIn: `networks` may hold one network.

## The link

A body never holds a URL, a `www.` or a bare domain. A post with a link sets `link` (https only, from the founder's site or the raw material) and `link_note`, and the body points in words: "in the first comment" on LinkedIn, "in the first reply" on X. Most posts need no link.

## What never enters a body

Everything in [`../../assets/hard-rules.md`](../../assets/hard-rules.md). When a template or a habit asks for proof that does not exist, the post goes without it: explain the mechanism, state the stance as a stance, tell what happened without a figure.

## Done when

`<run>/posts-spec.json` validates: `python3 ../../shared/scripts/validate_json.py assets/posts-spec.schema.json <run>/posts-spec.json` exits 0. The real check is the next step.
